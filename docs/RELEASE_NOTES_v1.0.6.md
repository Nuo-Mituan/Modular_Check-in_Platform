# v1.0.6 变更说明

- 版本：`1.0.6`
- 发布日期：2026-10-31
- 状态：已封板；本文件为 `docs` 目录下的版本变更说明。
- 发布归档：[Releases/v1.0.6/RELEASE_NOTES.md](../Releases/v1.0.6/RELEASE_NOTES.md)

v1.0.6 是自 v1.0.3 以来的累积快照，主题为模块图标契约，同时包含 observability、
模块上传、调度、auth/cookie、推送子系统、UI 等既有改动。不得描述为“仅图标改动”。

---

## 1. 破坏性变更：模块 SVG 图标移除

**仅影响模块作者。**

- 模块图标不再支持 `.svg`；
- `.svg` 请求返回 HTTP 415，detail 为：

  ```text
  SVG 图标已停止支持，请改用 PNG 格式
  ```

- Base64 Data URI 不再接受 `image/svg+xml`；
- 原因：手写 SVG 净化器作为唯一防线风险收益不匹配；栅格化需要
  cairosvg/svglib 及系统依赖，本版本暂不引入。

## 2. 图标支持集与响应

- 支持集统一为 ico/png/jpg/jpeg/webp；
- 后端后缀与文件魔数必须一致；
- 前端本地路径、Base64 与远程 URL 使用同一支持集；
- 栅格图标统一输出 `image/png`；
- 响应包含 ETag、`Cache-Control: public, max-age=86400, must-revalidate`，
  支持 `If-None-Match` / 304；
- 本地图标仍受路径沙箱、软链接阻断、64KB 文件上限与 1024×1024 像素上限保护。

## 3. 图标错误契约

图标错误保持原有 HTTP 状态码与 detail，并新增可选 `code`：

| code | 状态码 | 条件 |
|---|---|---|
| `icon_format_default` | 415 | 默认格式错误（后缀/魔数不匹配、解码失败） |
| `icon_size_default` | 413 | 文件超限、像素超限、DecompressionBomb |
| 无 code | 415 | 例如 SVG 迁移提示 |

- `code` 为 None 时不输出 `"code": null`；
- 403 detail 不再回显内部目录名，状态码仍为 403；
- 前端 413/415 图标文案仅在 `/modules/icon` 生效，按 code 回退，具体 detail 优先；
- 远程图标 URL 的不支持扩展名（含 `.svg`、GIF 等）在前端 fallback，不发起请求；
- 图标错误文案收敛到共享函数 `iconErrorMessage.js`。

## 4. 前端与其他累积改动

- 前端图标错误语义由 Axios 与 ModuleIcon fetch 共用；
- `.cursorrules` / `.cursorrules.md` 合并为单一权威，后者为废弃 stub；
- 包含 observability、模块上传、调度、auth/cookie、推送子系统与 UI 等
  自 v1.0.3 以来的既有改动。

## 5. 迁移指引

- 将 `config.json` 中指向 `.svg` 的 `icon` 改为 PNG（推荐）/JPG/JPEG/WebP/ICO；
- 远程图标如使用原先可加载但不支持的扩展名（例如 GIF），改为支持格式；
- 站点 favicon（`frontend/public/favicon.svg`）与 UI 内联 `<svg>` 品牌图形
  不是模块图标，不受影响；
- 仓库扫描未发现存量模块 SVG 图标。

## 6. 验证摘要

- 后端默认测试：238 passed；
- PBT：5 passed；
- 前端单测：27 passed；
- 改动文件 mypy：通过；
- 全量 `backend/app` mypy：9 个既有错误（`push_delivery.py`、`bootstrap.py`）；
- 前端构建：**未验证**（Rollup `@rollup/rollup-darwin-arm64` `ERR_DLOPEN_FAILED`）。

## 7. 发布产物状态

- 发布归档目录：`Releases/v1.0.6/`；
- 完整性凭据：`MANIFEST.json` / `MANIFEST.sha256`；
- 当前 payload 不含 `frontend/dist`，因此**不可上传**；
- 需在 Node 18+ 环境构建 `frontend/dist`，通过
  `release_snapshot.py --dist-source frontend/dist` 重新注入并校验后再上传；
- 上传后冻结，修正进入 v1.0.7。

## 8. 已知遗留

- TD-21 P1：远程 `http://` HTTPS-only；
- TD-22 P1：远程图标真实内容校验；
- TD-23 P1：发布清单/客户端版本更新判定缺失；
- TD-25 P2：项目标识 B 类改名（package/image/import/仓库与 CI 工件名）；
- TD-30 P3：前端 UI 品牌词“签到云台”待产品确认；
- TD-31 P3：checklist Python 断言块 `FAIL:` 前缀统一化。

历史版本说明保持原样；本文件只描述 v1.0.6。
