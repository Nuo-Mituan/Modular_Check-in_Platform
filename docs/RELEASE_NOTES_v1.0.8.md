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


## TD-19 Partial

- SQLite：旧 `execution_logs.output` 已在启动迁移中回填到 `ring_logs`，随后重建表删除列；已有自动化迁移测试。
- PostgreSQL：路径代码已实现（`DROP COLUMN`），但未在真实 PG 实例验证，未做回滚演练。
- TD-19 保持 Partial；读取侧已移除 legacy fallback。
- SQLite 迁移的 `PRAGMA foreign_keys` 已改为 AUTOCOMMIT 连接上、显式事务外切换。
