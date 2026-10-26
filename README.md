# clash-box

用官方 Mihomo 镜像，为本机和局域网设备提供 HTTP/SOCKS5 代理。

## 一键启动

先安装 Docker 和 Docker Compose v2，下载服务商提供的完整 Clash/Mihomo YAML 配置，然后在仓库目录执行：

```bash
./start.sh ~/Downloads/config.yaml
```

把路径换成你下载的配置文件。脚本会自动调整配置、校验并后台启动，无需手动编辑 YAML。首次会下载所需镜像，关闭终端后代理仍然运行。

原始下载文件保持不变，成功导入的副本保存在 `config/config.yaml`，生成的运行配置保存在 `runtime/config.yaml`。这些文件不会提交到 Git。

## 怎么连接

| 使用位置 | 代理地址 |
| --- | --- |
| 本机 | `127.0.0.1:7890` |
| 局域网设备 | `运行 Docker 的主机局域网 IP:7890` |

`7890` 同时支持 HTTP 和 SOCKS5，也保留 `7891` 供原有 SOCKS5 客户端使用。局域网设备需设置系统或应用代理，主机防火墙需放行对应端口。

## 更新、查看和停止

```bash
# 使用已导入的配置重新启动
./start.sh

# 导入新的服务商配置并重新启动
./start.sh ~/Downloads/new-config.yaml

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f --tail=100 mihomo

# 停止服务，保留数据
docker compose down
```

新配置校验失败时，已有服务继续运行。失败详情见 `runtime/start.log`。启动就绪表示代理端口已打开，上游节点是否可用仍取决于服务商配置。

## 修改端口或镜像版本（可选）

首次需要自定义设置时，把 `.env.example` 复制为 `.env`，按需修改其中的端口、绑定地址或镜像版本，然后执行 `./start.sh`。

例如，已有旧 Clash 占用默认端口时，将 `.env` 中两项改为：

```dotenv
MIXED_PORT=17890
SOCKS_PORT=17891
```

客户端随后使用 `17890/17891`。若只绑定了特定局域网 IP，本机客户端也使用该 IP。

此部署提供显式 TCP 代理，自动关闭管理接口和 TUN。配置需为完整 YAML；订阅链接、网页及 Base64 节点列表不能直接使用。
