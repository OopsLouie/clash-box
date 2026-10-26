# 从 ~/clash 迁移

旧 Clash 继续使用 `7890/7891`，新容器使用 `17890/17891` 并行验证。无需改动原配置或停止旧进程。

## 一键启动测试实例

先复制 `.env.example` 为 `.env`，将两项改为：

```dotenv
MIXED_PORT=17890
SOCKS_PORT=17891
```

在仓库目录执行：

```bash
./start.sh ~/clash/config.yaml
```

脚本自动读取、适配和校验配置，后台启动并等待代理入口就绪。原始文件保持不变；成功后保留副本供 `./start.sh` 再次使用。旧 `cache.db` 不复制，由新服务使用独立数据卷。

## 本机和局域网验证

查看状态和日志：

```bash
docker compose ps
docker compose logs --tail=100 mihomo
```

分别检查 HTTP 和 SOCKS5，例如：

```bash
curl --fail --show-error --connect-timeout 10 --max-time 30 --noproxy '' --proxy http://127.0.0.1:17890 https://www.example.com/ -o /dev/null
curl --fail --show-error --connect-timeout 10 --max-time 30 --noproxy '' --proxy socks5h://127.0.0.1:17891 https://www.example.com/ -o /dev/null
```

若原配置启用了代理认证，客户端需提供对应账号密码。上述请求只确认入口和访问结果；另选已知命中代理规则的目标，结合日志验证实际代理节点，再验证直连目标。

另一台局域网设备填写 Docker 主机的局域网 IP 和 `17890`，检查实际访问及主机防火墙。单机自测不能替代此项。

## 正式切换与回退

验证通过后可以继续使用新端口。需要沿用 `7890/7891` 时，先记录旧 Clash 的恢复方式，安排停止旧进程，再把 `.env` 端口改回 `7890/7891`，执行 `./start.sh`。

需要恢复旧 Clash 时，先执行 `docker compose down` 释放新服务端口，再按原方式启动旧进程。保留 `~/clash` 全部原文件，脚本不会停止旧服务或修改系统代理。

更新服务商配置时执行 `./start.sh /路径/新配置.yaml`。新配置未通过校验时，当前服务继续运行。后台启动失败会恢复旧运行配置并尝试恢复服务，但部署端口、镜像版本和数据卷需按实际情况回退。
