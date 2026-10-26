# 从 ~/clash 迁移

本说明用于后续执行迁移，当前尚未执行。旧 Clash 继续使用 `7890/7891`，并行验证的新容器使用 `17890/17891`。

## 准备私有副本

按 [README](../README.md) 复制原配置和 `.env.example`，只编辑仓库中的私有副本。配置中的节点、策略组、规则和 DNS 先保留，调整监听、局域网访问、管理接口和 TUN 设置。

把 `.env` 中的两项改为：

```dotenv
MIXED_PORT=17890
SOCKS_PORT=17891
```

首次验证不复制旧 `cache.db`，由 Mihomo 使用新数据卷。原文件和数据库继续供旧服务使用。

## 校验并启动测试实例

```bash
docker compose config --quiet
docker compose pull
docker compose run --rm --no-deps mihomo -t -d /root/.config/mihomo -f /etc/mihomo/config.yaml
docker compose up -d
docker compose logs --tail=100 mihomo
```

每一步成功后再执行下一步。`-t` 失败时先根据错误调整副本，不启动新服务；旧 Clash 的配置检查通过不能代替 Mihomo 检查。

## 本机和局域网验证

在本机选择用于验证的 HTTPS 目标，分别检查 HTTP 与 SOCKS5，例如：

```bash
curl --fail --show-error --connect-timeout 10 --max-time 30 --noproxy '' --proxy http://127.0.0.1:17890 https://www.example.com/ -o /dev/null
curl --fail --show-error --connect-timeout 10 --max-time 30 --noproxy '' --proxy socks5h://127.0.0.1:17891 https://www.example.com/ -o /dev/null
```

这两项只检查代理入口和访问结果。应另外选择已知命中代理规则的目标，结合 Mihomo 日志确认实际使用代理节点；只有直连成功不能证明节点可用。再检查原先需要直连的目标是否仍按规则工作。

另一台局域网设备填写 Docker 主机的局域网 IP 和 `17890`，检查实际访问、访问范围以及主机防火墙。单机自测不能替代此项。

配置更新后通过 README 中的检查和重建步骤验证其生效，再检查重启和正常停止。管理 API 不应发布到宿主机。

## 正式切换与回退

全部验证通过后，可继续使用新端口；如需沿用 `7890/7891`，先确认旧 Clash 的启动和恢复方式，安排停止旧进程，再把 `.env` 的端口改回 `7890/7891`，执行 `docker compose up -d` 并验证客户端。

保留 `~/clash` 全部原文件和服务启动方式。需要回退时先用 `docker compose down` 释放新服务端口，再按原来的启动方式恢复旧 Clash。当前阶段不自动停止旧服务或修改系统代理设置。

迁移成功后，本仓库只提交部署文件、文档和脱敏示例。`config/config.yaml`、`.env` 和数据卷备份留在私有备份位置。
