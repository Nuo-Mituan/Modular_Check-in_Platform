## v1.0.7 部署标识变更（TD-25）

项目所有标识已统一为 `modular-checkin-platform`。

### 影响

- 镜像名：`daily-checkin-platform` → `modular-checkin-platform`（旧 tag 不再维护，无过渡 alias）
- 容器名：同上
- Python 包名：`daily-sign-in-platform` → `modular-checkin-platform`（需重新 `pip install -e .`）
- 前端包名：`daily-checkin-platform-web` → `modular-checkin-platform-web`（仅元数据，不影响产物）

### 升级步骤

```bash
docker compose down
# 拉取新镜像 / 重新构建
docker compose up -d
# 可选：清理旧镜像
docker rmi daily-checkin-platform:latest
```

未变更：数据库库名/表名、Alembic 迁移、Python import 路径（`app.*`）、版本号 1.0.7。

### 运维检查

请同步检查 registry 仓库名、CI secret 中的镜像前缀、监控/拉取脚本是否仍引用旧镜像名。
