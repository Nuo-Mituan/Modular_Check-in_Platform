# v1.1.2 变更说明

- 版本：`1.1.2`
- 状态：开发/验证中

## Python 3.13 迁移

- 运行时、Dockerfile、CI、ruff/mypy 目标统一升级到 Python 3.13；Docker 使用 `python:3.13-slim`，跟随 3.13 最新补丁版。
- 开发依赖升级为 pytest 9.2.0 + pytest-asyncio 1.5.0，修复 pytest 9 与 pytest-asyncio 0.25 的安装冲突。
- Pillow/redis/hypothesis 下限提升到具备 cp313 wheel 的版本。
- 清理 ruff F/E9 问题，后端在 Python 3.13 下 329 项测试通过。

- 修复 import-linter CI 的无效 `pip install -e .` 步骤；import-linter 在 Python 3.13 下 3 项契约全部通过。
