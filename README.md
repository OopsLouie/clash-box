# clash-box

个人 Mihomo 部署配置仓库。使用官方镜像，为本机和局域网设备提供 HTTP/SOCKS5 代理。

## 一键启动

准备好 Docker、Docker Compose v2，以及服务商下载的完整 Clash/Mihomo YAML。在 clone 后的仓库目录执行：

```bash
./start.sh ~/Downloads/config.yaml
```

将路径换成你下载的文件。脚本会自动导入配置、适配容器监听、校验并后台启动，你无需编辑 YAML 或 Compose 文件。

启动成功后：

- 本机代理填写 `127.0.0.1:7890`，支持 HTTP 和 SOCKS5。
- 局域网设备填写 Docker 主机的局域网 IP，端口 `7890`。
- 原来的 SOCKS5 客户端也可继续使用 `7891`。

第一次会下载官方 Mihomo 和一次性 yq 工具镜像。后续复用已下载的镜像，不需要在本机安装 Python 或 yq。代理在后台运行，关闭终端后仍然工作；Docker 重启时会按 Compose 策略恢复。

## 后续启动或更新配置

成功导入过一次后，直接运行：

```bash
./start.sh
```

下载新的服务商配置后，再把新文件路径传给脚本：

```bash
./start.sh ~/Downloads/new-config.yaml
```

也可以把服务商配置放在仓库的 `config/config.yaml` 再运行 `./start.sh`。无参数时优先读取该文件，其次读取仓库根目录 `config.yaml`。带参数的相对路径按照执行命令时所在的目录解析，脚本自身可从其他目录调用。

查看状态、查看日志、停止服务：

```bash
docker compose ps
docker compose logs -f --tail=100 mihomo
docker compose down
```

停止会保留数据卷。再次启动仍使用 `./start.sh`。

## 自动处理哪些设置

脚本读取 YAML 并生成独立的运行配置，保留节点、密码、策略组、规则、DNS 和代理认证。部署入口统一为：

- 混合代理 `7890`、兼容 SOCKS5 `7891`，关闭冲突的原 HTTP 入口。
- 容器内允许局域网请求、监听所有地址，允许本机和私有 IPv4 地址段。
- 关闭管理 API、TUN、iptables 自动规则及 redir/tproxy 透明代理入口。

YAML 锚点先展开再修改。原始下载文件不改写；成功启动后保存一份未经修改的副本，供下次运行使用。

配置解析或 Mihomo 校验失败时，脚本退出，保留已有运行配置和服务。后台启动失败时恢复上一份运行配置，并在之前已有服务运行时尝试重新启动原服务。镜像版本和宿主机端口等部署参数不自动回退；失败详情保存在本机 `runtime/start.log`。

就绪检查确认两个代理监听端口已打开。节点是否可用以及访问是否按预期分流仍需用实际目标验证。

## 修改端口或镜像版本（可选）

通常无需创建 `.env`。需要修改部署参数时，复制 `.env.example` 为 `.env` 再调整。

例如，主机已经运行旧 Clash，可在 `.env` 中设置：

```dotenv
MIXED_PORT=17890
SOCKS_PORT=17891
```

然后执行相同的启动命令。此时本机和局域网客户端使用 `17890/17891`；脚本始终把容器内部端口固定为 `7890/7891`。本机现有 `~/clash` 的迁移方式见 [迁移说明](docs/migration.md)。

`PROXY_BIND_IP` 默认 `0.0.0.0`，支持本机和局域网访问。若只绑定主机的局域网 IPv4 地址，本机客户端也填写该地址。局域网客户端需设置系统或应用代理，主机防火墙需允许对应端口。

升级时，在 `.env` 修改 `MIHOMO_VERSION` 后执行 `./start.sh`。需要回退时恢复原镜像版本及对应的服务商配置，再执行脚本。数据卷中的地理数据库独立保存，不随镜像版本自动回退。

## 文件与数据

| 文件或位置 | 用途 | 提交 Git |
| --- | --- | --- |
| `start.sh` | 一键导入、适配、校验和后台启动 | 是 |
| `scripts/prepare-config.yq` | 自动调整 YAML 的规则 | 是 |
| `compose.yaml` | 官方镜像、端口、数据卷、重启、日志与就绪检查 | 是 |
| `.env.example` | 可选部署参数示例 | 是 |
| `examples/config.example.yaml` | 无节点凭据的配置示例 | 是 |
| `config/config.yaml` | 成功导入的服务商配置副本 | 否 |
| `runtime/config.yaml` | 自动生成并挂载的运行配置 | 否 |
| `runtime/start.log` | 校验及启动失败详情，可能包含配置内容 | 否 |
| `.env` | 本机部署参数 | 否 |
| Docker 命名卷 `mihomo-data` | 地理数据库、缓存和节点选择状态 | 否 |

代理配置和日志以仅当前用户可读写的权限创建。备份时保存私有配置和需要保留的数据卷；GitLab 只存部署文件和脱敏示例。

第一版接收单个 YAML 文档，不接收网页、订阅 URL 或 Base64 节点列表。若配置额外引用本地文件，需另外挂载所需文件。示例采用直连占位，没有可用的 VPN 节点。

详细决策见 [设计文档](docs/design.md)。集成测试使用临时目录、独立 Compose 项目和临时端口，运行方式：

```bash
python3 -m unittest discover -s tests -v
```

当前仓库使用 `main` 分支，尚未绑定 GitLab 远端。
