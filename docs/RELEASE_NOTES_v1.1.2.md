# v1.1.2 变更说明

- 版本：`1.1.2`
- 状态：开发/验证中

## Python 3.13 迁移

- 运行时、Dockerfile、CI、ruff/mypy 目标统一升级到 Python 3.13；Docker 使用 `python:3.13-slim`，跟随 3.13 最新补丁版。
- 开发依赖升级为 pytest 9.2.0 + pytest-asyncio 1.5.0，修复 pytest 9 与 pytest-asyncio 0.25 的安装冲突。
- Pillow/redis/hypothesis 下限提升到具备 cp313 wheel 的版本。
- 清理 ruff F/E9 问题，后端在 Python 3.13 下 329 项测试通过。

- 修复 import-linter CI 的无效 `pip install -e .` 步骤；import-linter 在 Python 3.13 下 3 项契约全部通过。

## 前端依赖升级

- Vue 3.5.46、Element Plus 2.14.9、Pinia 4.1.0、Vue Router 5.5.3。
- Vite 8.4.0、@vitejs/plugin-vue 6.0.11、Vitest 5.1.2、jsdom 31.0.1。
- 适配 Vite 8/Rolldown 的 manualChunks 函数式配置；Node 引擎要求提升到 >=22.22.2。
- Element Plus 改为按需组件解析并移除全量图标注册；Element Plus vendor JS 从约 1.14 MB（gzip 358 KB）降至约 547 KB（gzip 186 KB）。
- npm audit 0，前端单测 37 + 组件 7 全部通过。

## 后端依赖升级

- FastAPI 0.165.0、Uvicorn 0.55.0、SQLAlchemy 2.1.9、aiosqlite 0.22.1。
- APScheduler 3.11.3、cryptography 50.0.2、pydantic-settings 2.16.3。
- python-multipart 0.0.34、httpx 0.29.0、tzdata 2026.6。
- Pillow 13.0.0、redis 8.2.0、hypothesis 6.170.23。
- 开发工具升级到 ruff 0.17.6、mypy 2.4.1。
- SQLAlchemy 2.1 默认异步 SQLite 连接池会变为 QueuePool；显式保持 SQLite NullPool，并对 pool 指标做非负钳制。
