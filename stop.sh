#!/usr/bin/env bash
set -euo pipefail
umask 077

usage() {
  cat <<'HELP'
用法：./stop.sh

停止本仓库的 Mihomo 和网页管理面板，保留配置、管理密钥和数据卷。
再次启动：./start.sh
HELP
}

die() { printf '错误：%s\n' "$*" >&2; exit 1; }

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  usage
  exit 0
fi
[[ $# -eq 0 ]] || { usage >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die '请先安装 Docker 和 Docker Compose v2。'
docker compose version >/dev/null 2>&1 || die '未找到 docker compose，请安装 Compose v2。'
docker info >/dev/null 2>&1 || die '无法连接 Docker，请检查 Docker 是否已启动及当前用户的权限。'

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd -- "$repo_dir"
mkdir -p runtime
# 与 start.sh 共用操作锁，避免启动和停止同时执行。
lock_dir=$repo_dir/runtime/.start.lock
mkdir "$lock_dir" 2>/dev/null || die "已有启动或停止任务，或操作锁未清理：$lock_dir"
cleanup() { rmdir -- "$lock_dir" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '[clash-box] 正在停止代理和网页管理面板……\n'
docker compose --project-directory "$repo_dir" -f "$repo_dir/compose.yaml" stop ||
  die '停止服务失败，请检查 Docker 状态及上方错误信息。'
printf '[clash-box] 已停止，配置、管理密钥和数据已保留。再次启动：./start.sh\n'
