#!/usr/bin/env bash
set -euo pipefail
umask 077

usage() {
  cat <<'HELP'
用法：
  ./start.sh /路径/服务商配置.yaml   导入配置，自动适配并后台启动
  ./start.sh                       使用 config/config.yaml，或根目录 config.yaml

需要 Docker 和 Docker Compose v2。首次运行会下载代理、面板和 YAML 工具镜像。
可选 .env 用于修改宿主机端口；已有 Clash 时可设为 17890 / 17891。
HELP
}

die() { printf '错误：%s\n' "$*" >&2; exit 1; }
info() { printf '[clash-box] %s\n' "$*"; }

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  usage
  exit 0
fi
[[ $# -le 1 ]] || { usage >&2; exit 1; }

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source_file=${1:-"$repo_dir/config/config.yaml"}
if [[ $# -eq 0 && ! -f $source_file && -f $repo_dir/config.yaml ]]; then
  source_file=$repo_dir/config.yaml
fi
[[ -f $source_file && -r $source_file && -s $source_file ]] ||
  die "找不到可读的非空配置文件：$source_file。请运行 ./start.sh /路径/配置.yaml"
source_file=$(cd -- "$(dirname -- "$source_file")" && printf '%s/%s' "$PWD" "$(basename -- "$source_file")")

command -v docker >/dev/null 2>&1 || die '请先安装 Docker 和 Docker Compose v2。'
docker compose version >/dev/null 2>&1 || die '未找到 docker compose，请安装 Compose v2。'
docker info >/dev/null 2>&1 || die '无法连接 Docker，请检查 Docker 是否已启动及当前用户的权限。'

cd -- "$repo_dir"
mkdir -p config runtime
lock_dir=$repo_dir/runtime/.start.lock
mkdir "$lock_dir" 2>/dev/null || die "已有启动任务，或启动锁未清理：$lock_dir"
work_dir=''
runtime_file=$repo_dir/runtime/config.yaml
had_previous=false
promoted=false
committed=false
restore_config() {
  if [[ $had_previous == true ]]; then
    cp -- "$work_dir/previous.yaml" "$work_dir/restored.yaml"
    mv -- "$work_dir/restored.yaml" "$runtime_file"
  else
    rm -f -- "$runtime_file"
  fi
}
cleanup() {
  if [[ $promoted == true && $committed == false ]]; then
    restore_config
  fi
  [[ -z $work_dir ]] || rm -rf -- "$work_dir"
  rmdir -- "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
work_dir=$(mktemp -d "$repo_dir/runtime/.start.XXXXXX")
log_file=$repo_dir/runtime/start.log
: > "$log_file"
chmod 600 "$log_file"
cp -- "$source_file" "$work_dir/source.yaml"

compose=(docker compose --project-directory "$repo_dir" -f "$repo_dir/compose.yaml")
"${compose[@]}" config --quiet || die 'Compose 设置无效，请检查 .env。'
yq_image=mikefarah/yq:4.54.1
info '准备镜像（已下载的镜像会复用）……'
if ! docker image inspect "$yq_image" >/dev/null 2>&1; then
  docker pull "$yq_image" || die '下载 yq 镜像失败，请检查 Docker 的网络连接。'
fi
"${compose[@]}" pull --policy missing mihomo dashboard || die '下载代理或面板镜像失败，请检查 Docker 的网络连接。'

secret_file=$repo_dir/runtime/secret
if [[ ! -e $secret_file ]]; then
  info '生成管理密钥……'
  docker run --rm --network none --log-driver none --entrypoint /bin/sh "$yq_image" \
    -c 'od -An -N32 -tx1 /dev/urandom | tr -d " \n"' > "$work_dir/secret" ||
    die '无法生成管理密钥。'
  mv -- "$work_dir/secret" "$secret_file"
fi
[[ -f $secret_file && -r $secret_file ]] || die "无法读取管理密钥：$secret_file"
admin_secret=$(< "$secret_file")
[[ $admin_secret =~ ^[a-f0-9]{64}$ ]] || die "管理密钥文件无效：$secret_file"
chmod 600 "$secret_file"

info '生成适合本机和局域网使用的运行配置……'
filter=$(< "$repo_dir/scripts/prepare-config.yq")
if ! CLASH_BOX_SECRET=$admin_secret docker run --rm --interactive --network none --log-driver none \
  --env CLASH_BOX_SECRET "$yq_image" \
  --yaml-fix-merge-anchor-to-spec eval-all --no-colors --exit-status "$filter" - \
  < "$work_dir/source.yaml" > "$work_dir/config.yaml" 2>> "$log_file"; then
  die "配置必须是单份有效的 Clash/Mihomo YAML 映射。详情见 $log_file；当前运行配置未替换。"
fi
[[ -s $work_dir/config.yaml ]] || die '生成的配置为空，未启动服务。'

info '使用 Mihomo 校验配置……'
candidate_path=/etc/mihomo/$(basename -- "$work_dir")/config.yaml
if ! "${compose[@]}" run --rm --no-deps -T mihomo \
  -t -d /root/.config/mihomo -f "$candidate_path" >> "$log_file" 2>&1; then
  die "Mihomo 配置校验失败。详情见 $log_file；当前运行配置未替换。"
fi

if [[ -f $runtime_file ]]; then
  cp -- "$runtime_file" "$work_dir/previous.yaml"
  had_previous=true
fi
was_running=$("${compose[@]}" ps --quiet --status running mihomo)
# 收到中断或启动失败时，cleanup 会恢复上一份已验证的运行配置。
mv -- "$work_dir/config.yaml" "$runtime_file"
promoted=true

info '后台启动，等待代理和网页面板就绪……'
if ! "${compose[@]}" up -d --force-recreate --wait --wait-timeout 60; then
  "${compose[@]}" logs --tail=50 >> "$log_file" 2>&1 || true
  restore_config
  promoted=false
  if [[ $had_previous == true && -n $was_running ]]; then
    info '新配置启动失败，尝试恢复原服务……'
    if ! "${compose[@]}" up -d --force-recreate --wait --wait-timeout 60 >> "$log_file" 2>&1; then
      printf '原配置已恢复，服务恢复失败；请检查日志：%s\n' "$log_file" >&2
    fi
  else
    "${compose[@]}" stop >> "$log_file" 2>&1 || true
  fi
  die "启动失败。请检查端口及 $log_file。已有 Clash 时可在 .env 将代理端口改为 17890 / 17891。"
fi

# 只在成功启动后保存未经修改的服务商配置副本，供下次无参数启动。
mv -- "$work_dir/source.yaml" "$repo_dir/config/config.yaml"
committed=true
info '已在后台运行。后续可直接执行 ./start.sh 更新并重启。'
printf 'HTTP/SOCKS5 入口：%s\n' "$("${compose[@]}" port mihomo 7890)"
printf 'SOCKS5 兼容入口：%s\n' "$("${compose[@]}" port mihomo 7891)"
printf '本机填写 127.0.0.1；局域网设备填写这台主机的局域网 IP。\n'
printf '若 .env 限定了绑定 IP，本机也使用该 IP。\n'
dashboard_endpoint=$("${compose[@]}" port dashboard 80)
dashboard_host=${dashboard_endpoint%:*}
[[ $dashboard_host != 0.0.0.0 ]] || dashboard_host=127.0.0.1
controller_endpoint=$("${compose[@]}" port mihomo 9090)
controller_host=${controller_endpoint%:*}
[[ $controller_host != 0.0.0.0 ]] || controller_host=127.0.0.1
printf '管理面板：http://%s:%s/\n' "$dashboard_host" "${dashboard_endpoint##*:}"
printf '首次登录的后端地址：http://%s:%s\n' "$controller_host" "${controller_endpoint##*:}"
printf '管理密钥：%s\n' "$admin_secret"
printf '密钥保存在 runtime/secret；局域网访问时将面板和后端地址中的主机改为本机局域网 IP。\n'
printf '查看状态：docker compose ps\n查看日志：docker compose logs -f --tail=100 mihomo\n'
