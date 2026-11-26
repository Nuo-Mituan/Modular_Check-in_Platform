# v1.1.1 变更说明

- 版本：`1.1.1`
- 状态：开发/验证中

## 安全与异步修复

- 管理员强密码不再因重启被强制改密。
- 兜底发送失败不再触发非法状态跃迁或重复发送。
- 账号返回的 message/error 在敏感上下文中预脱敏。
- PBKDF2 校验与哈希移出事件循环。
- 自定义推送驱动同步 send 在线程中执行。
- Docker 默认仅信任 127.0.0.1，新增 TRUSTED_PROXY_IPS。
- SQLite 路径、WAL、权限和 ring_log 使用实际 DATABASE_URL。
- 强制改密白名单使用 settings.api_prefix。
- 模块 sys.path 仅在导入期间生效。

## 统一推送

- 关闭 noop 批次后重算为立即可触发。
- 已移出统一推送集合的模块明细置为 skipped。
- outbox 连续失败达到上限后进入 dead 终态，不再阻塞队列。

## 验证

- 后端：327 passed / 0 failed
- 前端：44 passed
- mypy：0 errors
- OpenAPI：paths=43 / breaking=0

## 审查修复

- 统一推送改为锁内准备、锁外 HTTP 发送、锁内条件回写；发送期间不再持有 cycle 锁。
- migrate_schema 拆分为模块列、推送列、用户列、幂等键和旧周期回填五个步骤。
- 修复用户名修改接口当前密码校验漏 await。

## 结构收尾

- 核心长函数拆分完成，TD-37 清零。

## 第二轮审查修复

- 统一推送发送占用增加租约与 claim token；进程崩溃后过期占用可由下次 sweep 接管，旧 worker 失去回写资格。
- outbox dead 行超过 7 天或 1000 条后归档到 ring 日志并删除。
- 主触发计算仅在存在 timeout=0 模块时加载统一兜底设置。

## 第三轮审查修复

- 锁外发送期间到达的执行结果保留为 late row，并作为补发消息发送，避免被终态清池丢弃。
- 版本检查缓存刷新不再在持有全局锁时执行网络请求；并发请求等待同一刷新事件。

## 第五轮审查修复

- late row 补发失败时 PushRecord 保持 pending，由 recover_pending_supplements 重试；成功后清理对应 PushPool。
- outbox dead 行达到 800 条时触发容量清理；新增 scripts/cleanup_outbox.py 手动清理入口。

## 第六轮审查修复

- push_after_flush_mode=none 时不再把迟到结果标记为已处理；保留池明细并记录 warning，避免静默丢弃。
- cleanup_outbox 脚本增加数据库初始化、sys.path 判重，并输出剩余 dead 行数量。

## 第七轮审查修复

- 终态批次后的迟到结果若未被补发，写入 supplement_unhandled outbox 审计并记录 warning，不再静默丢弃。
