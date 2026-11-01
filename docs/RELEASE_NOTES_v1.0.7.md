# v1.0.7 变更说明（草案）

- 版本：`1.0.7`
- 日期：2026-11-01
- 状态：**待发布 / 构建、快照与 MANIFEST 已通过**
- 主题：图标链路安全收敛 + 发布与质量门禁收口

> 本版本包含图标链路安全收敛、版本更新判定、发布清单闸门，以及测试/类型/分层门禁收口。
> 未改变 `Module.icon` 存储结构或 DB schema。

## 五条行为变更

### 1. 公网 `http://` 图标 URL 默认拒绝（TD-21）

- 远程图标保存时，`http://` 仅允许字面本地/内网地址：
  - `localhost`、`127.0.0.0/8`、`::1`；
  - RFC1918（`10/8`、`172.16/12`、`192.168/16`）；
  - IPv6 `fc00::/7`。
- 公网域名和公网 IP 的 `http://` 返回明确错误：
  `远程地址使用 http:// 时仅允许本地或内网地址，公网请使用 https://`
- 不做 DNS 解析、不做静默 HTTP→HTTPS 改写；`https://` 保持原值。
- 扫描/加载旧公网 http 配置：只 warning + fallback，不阻断模块加载、不改写原值。

**修复路径**：把 `config.json` 的 `icon` 改为 `https://...`，或使用本地/内网 http。
**回退**：回退 TD-21 的保存校验与前端提示；旧 URL 原值未改，无需数据迁移。

### 2. 远程图标改为服务端同源代理（TD-22）

- 新增加认证端点：`GET /api/modules/{module_id}/icon`；
- 只接受模块 ID，不接受 `?url=`；URL 从 `Module.icon` 服务端读取；
- 代理执行 DNS 解析后 IP deny 校验、逐跳重定向校验、超时、256KB 上限；
- 不传 Cookie / Authorization / Referer；错误不返回目标 URL/IP/堆栈；
- 响应 `Content-Type` 由魔数推断，带 `nosniff`、ETag、`Cache-Control`；
- 前端远程图标不再直接使用原始 URL 作为 `<img src>`。

**修复路径**：前端与后端同时升级；旧客户端直接使用远程 URL 时不再享受代理保护。
**回退**：移除代理端点与 ModuleIcon 的 remote fetch，恢复直接 URL 渲染；不改 DB。

### 3. 旧公网 http 远程图标在代理层失效（TD-22 兼容取舍）

- 代理层对公网 `http` 一律拒绝，即使 TD-21 的 allowlist 曾放行；
- 内网字面 http 仍允许，以满足内网部署；
- DNS 解析到 loopback/link-local/ULA/unspecified 的地址拒绝（https 同样适用）；
- 已知残余：DNS 校验与 httpx 连接之间存在 TOCTOU 窗口，当前接受并文档化。

**修复路径**：重新上传 `https://` 图标，或改用本地/内网图标。
**回退**：回退 TD-22 代理层 host 策略；不自动改写旧 URL。

### 4. 图标格式统一为 ICO/PNG/JPEG/GIF/WebP，SVG 全链路拒绝（TD-23）

- 单一策略 `ICON_ALLOWED = {ico, png, jpeg, gif, webp}`；
- 上传 ZIP 内图标执行扩展名 + 魔数双检；`.png` 包 JPEG/SVG 等伪造扩展名拒绝；
- `data:image/svg+xml` 在所有路径拒绝；
- GIF 正式加入允许集合；CUR（ICO type=2）明确拒绝；
- 本地 serving 仍统一输出 `image/png`。

**修复路径**：`.svg` 改 PNG/JPEG/GIF/WebP/ICO；伪造扩展名重新导出正确格式。
**回退**：回退 `icon_policy.py` 与各引用点；`Module.icon` 存储值未改。

### 5. Base64/data URI 也执行 MIME + 魔数校验（TD-23）

- 允许 `image/png`、`image/jpeg`、`image/gif`、`image/webp`、ICO MIME；
- MIME 与解码魔数不一致 → 拒绝；
- 上传/保存严格拒绝；扫描/加载旧的不合规图标只 warning，图标 fallback，模块继续加载；
- 不写回 DB、不改模块目录文件；原值保留，重启后仍按同一策略处理。

**修复路径**：重新导出合规 data URI/图标并上传。
**回退**：回退 `validate_data_uri` 与加载侧 fallback；原值未改。

## 工程与发布链路

- **TD-18**：新增 `.importlinter` 分层合同与 CI job；3 contracts kept、0 broken。
- **TD-19a**：新执行不再写 `execution_logs.output`，旧行保留只读 fallback；ring 写入失败时显式告警。
- **TD-23a**：新增公开 `GET /api/version`（ETag / Cache-Control），前端增加版本比较与升级判定纯函数及 6 条单测；OpenAPI paths 40→41。
- **TD-23b**：`release_snapshot.py` 增加 checklist 前置闸门；`MANIFEST.json` 写入 `checklist`、`payload_checksum`、`git_commit`；失败时不生成 manifest。
- **TD-24**：新增 ModuleIcon 组件级挂载测试（@vue/test-utils + jsdom + vitest），前端测试 31→36。
- **TD-26**：全量 mypy 从 9 errors / 2 files 清零。
- **TD-27 / TD-29 / TD-31**：版本单一来源与 baseline、npm lockfile 门禁、checklist 失败统一 `FAIL:` 前缀。
- **TD-25**：项目标识统一为 `modular-checkin-platform`；旧镜像名无过渡 alias，迁移见 `docs/MIGRATION_v1.0.7.md`。

## 验证摘要

- 后端：284 passed，1 failed（既有 `test_noop_batch_restores_outbox_audit`，基线白名单）
- PBT：5 passed
- 前端：42 passed（Node 37 + 组件 5）
- mypy：61 source files，0 errors
- OpenAPI：paths=41，breaking=0；TD-22 新增 `GET /api/modules/{module_id}/icon`，TD-23a 新增 `GET /api/version`
- 前端单元测试：42 passed；生产构建：exit 0，版本注入 1.0.7，产物无 `"dev"`
- `frontend/dist`：已纳入 v1.0.7 payload，`shasum -c` OK

## 已知限制

- 代理层 DNS TOCTOU 残余，未做 IP 固定；
- 旧公网 http 远程图标需重新上传 https 图标；
- ICO 在现代浏览器/预览场景的兼容性弱于 PNG/GIF/WebP，但本轮保留 ICO；
- 模块图标没有独立 URL 编辑表单，修复远程 URL 需重新上传 ZIP；
- 全量测试仍有 1 个既有失败（`test_noop_batch_restores_outbox_audit`），已列入基线白名单；
- `test_sync_modules_different_keys_concurrent` 存在偶发并发失败，单跑/重跑通过，后续固化；
- TD-32 自定义推送驱动 URL 策略仍未实施。

## 回退说明

本版本无 DB schema、无 `Module.icon` 存储格式变化。回退代码即可恢复旧行为；
已保存的 HTTPS/本地图标无需迁移。已上传的 v1.0.7 产物不可覆盖，修复走下一版本。
