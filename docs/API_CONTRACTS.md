# API 契约清单

版本：`1.1.1`

> 由 `scripts/openapi_base.json` 生成；请求/响应字段以 OpenAPI schema 为准。

| 方法 | 路径 | 摘要 |
| --- | --- | --- |
| `POST` | `/api/auth/change-password` | 修改密码 |
| `POST` | `/api/auth/login` | 账号密码登录 |
| `POST` | `/api/auth/logout` | 退出当前会话 |
| `POST` | `/api/auth/logout-all` | 注销全部会话 |
| `GET` | `/api/auth/me` | 当前登录用户 |
| `GET` | `/api/auth/session` | 校验并续期当前会话 |
| `PUT` | `/api/auth/username` | 修改用户名 |
| `GET` | `/api/dashboard` | 仪表盘统计与最近执行 |
| `GET` | `/api/health` | 健康检查 |
| `DELETE` | `/api/logs` | 清空执行记录 |
| `GET` | `/api/logs` | 分页查询执行记录 |
| `GET` | `/api/logs/{log_id}` | 执行详情 |
| `GET` | `/api/logs/{log_id}/stream` | 实时日志流（SSE，支持 last_seq 断点续读） |
| `GET` | `/api/meta` | 系统信息 |
| `GET` | `/api/modules` | 模块列表 |
| `GET` | `/api/modules/icon` | 读取签到模块本地图标 |
| `POST` | `/api/modules/scan` | 扫描模块目录并热加载 |
| `POST` | `/api/modules/schedule/preview` | 预览周期子选项与下一次执行日期 |
| `POST` | `/api/modules/upload` | 上传 ZIP 模块并热安装 |
| `DELETE` | `/api/modules/{module_id}` | 彻底删除模块 |
| `GET` | `/api/modules/{module_id}` | 模块详情、账号与执行时间 |
| `PUT` | `/api/modules/{module_id}` | 保存账号、随机时间与推送开关 |
| `GET` | `/api/modules/{module_id}/chrome-sync` | 读取模块 Chrome 同步状态 |
| `PUT` | `/api/modules/{module_id}/chrome-sync` | 设置模块 Chrome 同步开关 |
| `PATCH` | `/api/modules/{module_id}/enabled` | 启用或禁用模块 |
| `GET` | `/api/modules/{module_id}/icon` | 代理远程模块图标 |
| `POST` | `/api/modules/{module_id}/reveal-sensitive` | 二次密码校验后显示敏感参数明文 |
| `POST` | `/api/modules/{module_id}/run` | 立即执行一次 |
| `POST` | `/api/modules/{module_id}/schedule/regenerate` | 手动重新生成本期随机时间 |
| `POST` | `/api/modules/{module_id}/test` | 开发者模式下执行一次测试 |
| `GET` | `/api/push/batches` | 统一推送批次摘要 |
| `GET` | `/api/push/config` | 读取全局推送配置 |
| `PUT` | `/api/push/config` | 保存全局推送配置 |
| `GET` | `/api/push/drivers` | 推送驱动列表 |
| `POST` | `/api/push/drivers/upload` | 上传并热加载自定义推送驱动 |
| `DELETE` | `/api/push/drivers/{key}` | 删除自定义推送驱动 |
| `POST` | `/api/push/drivers/{key}/rollback` | 回滚自定义驱动 |
| `GET` | `/api/push/records` | 推送历史记录 |
| `POST` | `/api/push/reveal` | 二次密码校验后显示推送凭据明文 |
| `POST` | `/api/push/test` | 发送推送测试消息 |
| `GET` | `/api/push/unified-settings` | 读取统一推送兜底设置 |
| `PUT` | `/api/push/unified-settings` | 保存统一推送兜底设置 |
| `GET` | `/api/settings/chrome` | 读取全局 Chrome 版本 |
| `PUT` | `/api/settings/chrome` | 保存全局 Chrome 版本 |
| `GET` | `/api/settings/developer` | 读取开发者模式 |
| `PUT` | `/api/settings/developer` | 开启或关闭开发者模式 |
| `GET` | `/api/settings/logs` | 读取日志保留设置 |
| `PUT` | `/api/settings/logs` | 修改日志保留天数并立即裁剪 |
| `GET` | `/api/system/logs` | 只读系统/应用日志 |
| `GET` | `/api/system/metrics` | 只读运行时指标 |
| `GET` | `/api/version` | 版本与更新判定信息 |
| `GET` | `/metrics` | Prometheus Metrics |

## 版本检查响应

`GET /api/version` 额外返回：

- `latest_version`
- `has_update`
- `html_url`
- `check_failed`

## 错误响应

项目统一使用 FastAPI 标准格式：

```json
{"detail": "错误信息"}
```
