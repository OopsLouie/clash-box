# clash-box

我的 Mihomo 部署配置仓库。直接使用 [Mihomo 官方镜像](https://hub.docker.com/r/metacubex/mihomo)，通过 Docker Compose 给本机和局域网设备提供 HTTP/SOCKS5 代理。

当前已整理部署配置、示例和设计，尚未拉取镜像或启动容器，现有 `~/clash` 服务继续运行。详细决策见 [设计文档](docs/design.md)。

## 仓库内容

| 文件 | 用途 |
| --- | --- |
| `compose.yaml` | 官方镜像、端口、配置挂载、数据卷、重启策略与日志 |
| `.env.example` | 镜像版本、宿主机端口和绑定地址的本地设置示例 |
| `examples/config.example.yaml` | 无节点凭据的 Mihomo 配置示例 |
| `docs/design.md` | 部署结构、维护方式与扩展边界 |
| `docs/migration.md` | 从当前 `~/clash` 并行验证和迁移的步骤 |

部署时自行创建 `config/config.yaml`；该文件和 `.env` 均已被 Git 忽略。`.env` 是可选的部署参数，采用默认端口时可省略；当前主机的并行验证用它保存临时端口。

## 准备配置

要求安装 Docker 和 Docker Compose v2。在仓库目录执行：

```bash
mkdir -p config
cp ~/clash/config.yaml config/config.yaml
cp .env.example .env
```

编辑复制后的 `config/config.yaml`，把下面这些顶层配置项调整成以下值；已有同名项应替换，避免重复的 YAML 键。保留原来的节点、策略组、规则和 DNS 设置。

```yaml
port: 0
mixed-port: 7890
socks-port: 7891
allow-lan: true
bind-address: "*"
external-controller: ""
```

`mixed-port` 同时接受 HTTP 和 SOCKS5；`7891` 保留给使用旧 SOCKS5 端口的客户端。第一版使用显式代理，配置中的 TUN 应关闭。

按 [配置示例](examples/config.example.yaml) 设置 `lan-allowed-ips`，允许本机及私有局域网地址。示例末尾采用直连占位，不包含可用的 VPN 节点。多网卡主机可在 `.env` 中把 `PROXY_BIND_IP` 设为目标局域网接口的 IPv4 地址。

## 启动与访问

当前机器的 `7890/7891` 已被旧 Clash 使用，首次验证请按 [迁移说明](docs/migration.md) 把 `.env` 中的宿主机端口改为 `17890/17891`。容器内的 `7890/7891` 保持固定。

```bash
docker compose config --quiet
docker compose pull
docker compose run --rm --no-deps mihomo -t -d /root/.config/mihomo -f /etc/mihomo/config.yaml
docker compose up -d
docker compose logs --tail=50 mihomo
```

逐条执行，每一步成功后再继续。`-t` 通过说明内核能解析配置，节点是否可用需要另测。缺失输入文件时，挂载会报错，不会自动创建一个名为 `config.yaml` 的目录。

使用正式默认端口时：

| 客户端 | 地址 | 端口 |
| --- | --- | --- |
| 本机应用 | `127.0.0.1` | `7890`，支持 HTTP/SOCKS5 |
| 局域网设备 | Docker 主机的局域网 IP | `7890`，支持 HTTP/SOCKS5 |
| 原有 SOCKS5 客户端 | 上述对应地址 | `7891` |

如果 `.env` 修改了端口，客户端填写修改后的宿主机端口。若仅绑定主机的局域网 IP，本机客户端也填写该 IP。局域网设备需设置系统或应用代理，主机防火墙需允许目标局域网连接。此部署提供 TCP 代理入口。

## 日常维护

查看状态和日志：

```bash
docker compose ps
docker compose logs -f --tail=100 mihomo
```

更新配置时，先备份当前文件，再替换 `config/config.yaml` 并执行：

```bash
docker compose run --rm --no-deps mihomo -t -d /root/.config/mihomo -f /etc/mihomo/config.yaml
docker compose up -d --force-recreate
```

只有检查通过后才重建服务。重建会重新挂载替换后的配置文件；校验失败时先恢复备份。

升级时，记录 `.env` 中的原版本，改为准备升级的固定版本，再重复拉取、配置校验和重建步骤。需要回退时恢复原版本和对应配置备份。Docker 数据卷中的数据库和状态独立保存，不会因为换镜像自动恢复成旧版本。

停止服务并保留数据：

```bash
docker compose down
```

真实配置、订阅链接、账号和密码留在本机；GitLab 远端用于保存部署文件和脱敏示例。当前仓库使用 `main` 分支，尚未绑定远端。
