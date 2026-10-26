# clash-box

用官方 Mihomo 镜像，为本机和局域网设备提供 HTTP/SOCKS5 代理。

## 一键启动

先安装 Docker 和 Docker Compose v2，下载服务商提供的完整 Clash/Mihomo YAML 配置，然后在仓库目录执行：

```bash
./start.sh ~/Downloads/config.yaml
```

把路径换成你下载的配置文件。脚本会自动调整配置、校验并后台启动 Mihomo 和 MetaCubeXD 网页面板，无需手动编辑 YAML。首次会下载所需镜像，关闭终端后代理仍然运行。

原始下载文件保持不变，成功导入的副本保存在 `config/config.yaml`，生成的运行配置保存在 `runtime/config.yaml`。这些文件不会提交到 Git。

## 怎么连接

| 使用位置 | 代理地址 |
| --- | --- |
| 本机 | `127.0.0.1:7890` |
| 局域网设备 | `运行 Docker 的主机局域网 IP:7890` |

`7890` 同时支持 HTTP 和 SOCKS5，也保留 `7891` 供原有 SOCKS5 客户端使用。局域网设备需设置系统或应用代理，主机防火墙需放行对应端口。

## 网页管理

启动后打开 `http://127.0.0.1:8080/`，局域网设备把 `127.0.0.1` 换成主机的局域网 IP。可以切换节点、测速、切换规则/全局模式、查看连接和日志。

首次连接面板时，后端地址填写 `http://127.0.0.1:19090`（局域网访问填写主机 IP），密钥使用脚本启动完成时显示的管理密钥，也可执行 `cat runtime/secret` 查看。密钥自动生成并保存，后续启动继续复用，不提交 Git。

节点选择保存在数据卷中。模式等临时设置不改写服务商文件，下次执行 `start.sh` 时按配置重新加载。长期修改节点、规则或 DNS 可编辑 `config/config.yaml` 再启动；`runtime/config.yaml` 会由脚本重新生成。

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

新配置校验失败时，已有服务继续运行。失败详情见 `runtime/start.log`。启动就绪表示代理和管理面板已准备好，上游节点是否可用仍取决于服务商配置。

## 修改端口或镜像版本（可选）

首次需要自定义设置时，把 `.env.example` 复制为 `.env`，按需修改其中的代理端口、面板端口 `DASHBOARD_PORT`、管理 API 端口 `CONTROLLER_PORT`、绑定地址或镜像版本，然后执行 `./start.sh`。

例如，已有旧 Clash 占用默认端口时，将 `.env` 中两项改为：

```dotenv
MIXED_PORT=17890
SOCKS_PORT=17891
```

客户端随后使用 `17890/17891`。若只绑定了特定局域网 IP，本机客户端也使用该 IP。

此部署提供显式 TCP 代理和带管理密钥的网页面板，自动关闭 TUN。配置需为完整 YAML；订阅链接、网页及 Base64 节点列表不能直接使用。
