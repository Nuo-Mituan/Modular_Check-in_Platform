# v1.0.9 变更说明

- 版本：`1.0.9`
- 状态：**已交付**（2026-11-14）

## 手动执行不推送

- 模块详情页「立即执行」无论成功或失败都不触发推送，也不进入统一推送池。
- 只有定时执行会产生独立推送或统一批次结果；测试推送按钮行为不变。

## 发布归类说明

- 本行为属于 v1.0.9 新功能；

## 最终验证

- 后端：311 passed / 0 failed
- pytest harness：303 passed / 0 failed
- 前端：37 Node + 7 component = 44 passed
- mypy：0 errors
- OpenAPI：paths=43 / breaking=0
- TECH_DEBT：36 = 33 + 0 + 3
- Snapshot：238 files / shasum OK=239 / FAIL=0
- checklist：23/23 pass

## 验证

- 后端：pytest 通过（手动执行推送相关用例已按新行为调整）
- 前端：构建通过
- TD-35 已完成：Chrome 同步写入复用统一模块参数校验。


## 运行时告警修复

- SQLite 默认使用 NullPool；不再尝试注册不存在的 `disconnect`/`error` 连接池事件，避免每次指标刷新输出 traceback。

## TD-35

- Chrome 同步参数写入前执行 `validate_and_normalize_params`，非法参数返回 409。

- Chrome 同步参数校验失败返回 422；解密/状态写入失败返回 409。

## Chrome 同步健壮性修复

- 模块 Chrome 参数解密失败或 chrome_version 非法时返回 409，不再返回 enabled=true/null 的半有效状态。
- Chrome 同步校验优先读取实时 config.json，读取失败才回退数据库 param_schema。
- 全局 Chrome 版本存储损坏时记录 warning，并在设置读取响应中返回 degraded=true。
- 前端对 sync-error 做 3 秒去重，并提示全局配置损坏状态。

## 已知技术债

- TD-36 已完成：Chrome 同步读取实时 config.json，并在差异时刷新 DB param_schema。
- 前端 sync-error 去重暂无专门自动化测试。

## TD-36 集成修复

- Chrome 支持性判断先读取实时 config.json，DB schema 陈旧时不再直接返回“不支持”。
- config.json 读取/解析移入 asyncio.to_thread，避免阻塞事件循环。
- config.json 存在但解析失败返回 409；仅文件缺失时回退 DB schema。

## TD-36 第二轮修复

- GET Chrome 同步状态不再修改 ORM param_schema，避免只读接口触发 autoflush。
- PUT/全局同步仍可在事务内刷新 schema。
- 单次 Chrome 同步请求复用同一份 ModuleConfig，避免重复文件读取和解析。

## TD-36 第三轮修复

- 关闭 Chrome 同步不再读取/解析 config.json，损坏配置不会阻止关闭。
- 保存全局 Chrome 版本后同步清除前端 degraded 状态。

## TD-36 第四轮修复

- config.json 的存在性检查与解析合并到 asyncio.to_thread，异步请求路径不再执行同步 stat。
- 关闭同步复用最近一次实时 supported 结果；无缓存时回退 DB schema，不改变 API 类型。

## TD-36 第五轮修复

- supported 缓存改为 (module.key, updated_at) 复合键，并限制为 256 条 LRU，避免 ID 复用脏读和无限增长。
- 关闭路径的 owner_user_id 查询纳入异常保护，失败时版本回退 null，不阻塞关闭。

## TD-36 第六轮修复

- 关闭同步首次请求在缓存未命中时尝试读取实时 supported，损坏配置再回退 DB。
- chromeStore.load 支持 force 刷新，设置页进入时强制同步后端版本与 degraded 状态。
