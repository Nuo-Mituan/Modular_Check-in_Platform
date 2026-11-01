## v1.0.7 部署标识变更（TD-25）

项目所有标识已统一为 `modular-checkin-platform`。

### 影响

- 镜像名：`daily-checkin-platform` → `modular-checkin-platform`（旧 tag 不再维护，无过渡 alias）
- 容器名：同上
- Python 包名：`daily-sign-in-platform` → `modular-checkin-platform`（需重新 `pip install -e .`）
- 前端包名：`daily-checkin-platform-web` → `modular-checkin-platform-web`（仅元数据，不影响产物）

### 具名卷/网络自查

升级前执行：

```bash
docker volume ls --filter name=daily-checkin-platform
docker network ls --filter name=daily-checkin-platform
```

- 若输出非空：旧卷/网络保留原名字段，不会自动迁移；需手动 `docker cp` 或在 compose 中使用 `external: true` 指向旧资源。
- 若输出为空：直接 `docker compose down` → `docker compose up -d` 即可。

### 升级步骤

```bash
docker compose down
# 拉取新镜像 / 重新构建
docker compose up -d
# 可选：清理旧镜像
docker rmi daily-checkin-platform:latest
```

### Python editable 安装

包名变更后，旧 editable 安装的 dist-info 可能残留：

```bash
pip uninstall -y modular-checkin-platform daily-sign-in-platform 2>/dev/null || true
pip install -e .
```

未变更：数据库库名/表名、Alembic 迁移、Python import 路径（`app.*`）、版本号 1.0.7。

### 运维检查

请同步检查 registry 仓库名、CI secret 中的镜像前缀、监控/拉取脚本是否仍引用旧镜像名。
