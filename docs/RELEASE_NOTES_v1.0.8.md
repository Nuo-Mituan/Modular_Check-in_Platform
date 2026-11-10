# v1.0.8 变更说明（草案）

- 版本：`1.0.8`（开发中）
- 状态：开发/验证中

## Chrome 版本同步

- 用户设置页新增全局 Chrome 主版本号（默认 156，范围 1-999）。
- 模块详情页新增「同步全局 Chrome 版本」Switch：
  - 仅 `e-hentai` / `ikuuu_vpn` 支持；
  - 其他模块显示 disabled，tooltip 说明不支持；
  - 开启时后端立即把全局值写入模块 `params.chrome_version` 并保存；
  - 全局值更新时，后端自动更新所有已开启同步的模块；
  - 关闭后保留当前模块值，不再跟随全局变化。
- 模块 UA 仍只读取自身 `params.chrome_version`，不直接读取全局设置。
- 持久化复用 `app_settings`，不使用 localStorage 或 Pinia 持久化插件。

## 文档

- `docs/V1.0.8_CHROME_SYNC.md`
- `docs/MODULE_DEVELOPMENT.md` Chrome 接入指南

## 已知边界

- `trae` / `ehtag_data` 保持固定 UA，不参与 Chrome 同步。
- 仅单账号模块支持同步；多账号模块当前不提供该能力。


## 技术债清除

- 所有含 `chrome_version` 的模块参数统一校验为 1-999 整数；0、1000、小数、非数字字符串拒绝写入。
- UA 构造函数保持显式整数参数；调用异常由执行层统一捕获并记录，不中断其他模块。
- 全局 Chrome 版本更新改为一次查询已开启同步的模块，避免逐模块查询；实测 156→159 自动同步成功。
- `glob` override `14.0.4`，保留 `minimatch 11.0.1`；`npm audit` 归零。
- 更新 e-hentai / ikuuu_vpn 的 UA 注释，移除“固定 Chrome 版本”表述，明确由模块参数或同步机制注入。


## 固定时间执行

- 模块开始时间与结束时间相同（例如 09:00–09:00）时，平台按固定时间执行，不再随机生成。
- 结束时间早于开始时间仍拒绝保存。


## TD-19 Ignored（PostgreSQL 不在当前交付范围）

- SQLite：旧 `execution_logs.output` 已在启动迁移中回填到 `ring_logs`，随后重建表删除列；已有自动化迁移测试。
- PostgreSQL：当前镜像不含 PG 驱动、Compose 服务与迁移支持，不属于当前交付范围；不再以 Partial 阻塞 v1.0.8。
- 读取侧已移除 legacy fallback。


## 审查修复

- TD-19 回填 ring_logs 时使用 started_at 的真实 epoch，避免历史日志被 retention 立即删除。
- Chrome 同步开启写入失败时回滚开关并返回 409，不再静默成功。
- ModuleChromeSync 监听 moduleId 变化，避免路由复用导致状态串模块。
- /api/version 的 git_commit 解析移到 asyncio.to_thread，并缓存结果。
- valid_chrome_version 拒绝浮点数与布尔值。


## 并发与同步反馈修复

- 全局 Chrome 版本保存返回 synced_count/expected_count/failed_module_ids；存在失败时 HTTP 207，前端提示部分模块同步失败。
- Chrome 同步读改写增加进程内 asyncio 锁，避免同一进程并发保存互相覆盖。
- ModuleChromeSync 在全局值与模块值不一致或读取失败时向父页面发出警告。
