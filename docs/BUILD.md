## 包管理器约定（TD-29）

本项目唯一受支持的包管理器是 **npm**，lockfile 为 `frontend/package-lock.json`。

```bash
cd frontend
npm ci --include=optional     # CI / 发布环境，严格按 lock 安装
npm install                   # 本地开发，会更新 lock（需随 commit 提交）
npm run build                 # 产出 frontend/dist
```

### 版本升级

`npm version <newver>` 只修改 `package.json` 与 `package-lock.json`（npm 侧内部同步）。
后端版本需另行同步 `backend/app/__init__.py` 与 `pyproject.toml`；
发布脚本会做跨侧等值断言，不等即拒绝打包。

### 不支持

pnpm / yarn：未验证，不提供排障支持。`pnpm-lock.yaml` / `yarn.lock` 若出现在工作区，
发布门禁将直接拒绝（TD-29）。
