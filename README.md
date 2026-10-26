# clash-box

把 Mihomo（Clash Meta）封装成可供本机和局域网设备使用的 Docker 代理服务。目标是用户提供一份 Clash/Mihomo YAML 配置，然后通过 Docker Compose 启动。

当前阶段：本地 Git 仓库和设计文档已经建立，尚未实现、构建或启动容器。详细方案见 [设计文档](docs/design.md)。

## 已确定的方向

- 使用 Mihomo，先验证现有 `~/clash/config.yaml` 的兼容性。
- 本机和局域网设备共用代理入口，设备或应用自行设置 HTTP/SOCKS5 代理。
- 真实配置在运行时只读挂载，镜像包含内核、证书和所需基础地理数据库。
- 启动时生成适合容器网络的运行配置，保留用户的节点、策略组、规则和 DNS 设置。
- 现有宿主机 Clash 在验证阶段继续运行，新容器使用临时端口进行对比。

## 预期使用方式

以下是实施完成后的目标流程，目前还不能执行：

```bash
mkdir -p config
cp ~/clash/config.yaml config/config.yaml
docker compose up -d
```

镜像构建和发布完成后，部署端只需要 Docker、Compose 和配置文件；第一次启动仍需能取得镜像。

计划默认使用 `7890` 作为 HTTP/SOCKS5 混合代理端口，并保留 `7891` 的 SOCKS5 入口以便兼容现有客户端。本机填写 `127.0.0.1`，局域网设备填写运行 Docker 的主机局域网 IP。

## 仓库约定

真实配置、订阅凭据、运行数据和本地二进制不提交到 Git。后续实现 Docker 构建时，还需用 `.dockerignore` 将真实配置排除在构建上下文外。

当前仓库使用 `main` 分支，尚未绑定 GitLab 远端。本地 Git 仓库可在确定 GitLab 项目地址后关联并推送。
