# 07 · 常见错误排查

> 列出已发生过的失败模式和修复方法。如果你的报错不在这里，参考 [00_CONTRACT.md](00_CONTRACT.md) 和 [06_JSON_SCHEMA_GUIDE.md](06_JSON_SCHEMA_GUIDE.md)。

---

## 灾难级错误：手写 HTML 当报告

**症状**：
- 项目根目录或 `data/` 下出现自定义 `*.html` 文件
- 跑 `python3 validate_output.py` 退码 2，提示"野生 HTML"或"不含模板指纹"

**根因**：跳过了 `JSON → generate_report.py → report-template.html` 的标准产物链路，直接 `Write` 了一个 HTML。

**修复**：
1. 删除手写的 HTML 文件
2. 按 [05_ASSEMBLE_AND_RENDER.md](05_ASSEMBLE_AND_RENDER.md) 重做 JSON
3. 跑 `python3 generate_report.py data/<项目>_<日期>.json`
4. 跑 `python3 validate_output.py` 确认 ✅

**预防**：开工前先读 [00_CONTRACT.md](00_CONTRACT.md)。最终交付物**只能**是 `data/*_report.html` 且必须经 `generate_report.py` 生成。

---

## Schema 校验错误

### `variants 不是数组`

**症状**：`generate_report.py` 退码 2，错误位置 `items/N/variants`。

**错误写法**：
```json
"variants": {"经济版": {...}, "标准版": {...}}
```

**正确**：
```json
"variants": [
  {"version": "经济版", "part_number": "...", ...},
  {"version": "标准版", "part_number": "...", ...}
]
```

### `is_variant 缺失`

每个 item 必须显式声明 `"is_variant": true` 或 `false`，不能省略。

### `user_value 类型错误`

必须是字符串 `"低"` / `"中"` / `"高"`，不能是数字 `0` / `1` / `2`。

### `selected_version 不在 versions 中`

`selected_version` 必须是 `versions` 数组中某一个**字符串**。

**反例**：`"selected_version": "经济版+标准版"` ❌（拼接）

**正例**：`"selected_version": "经济版"` ✅

---

## 价格字段填错

### `mall_source = "博查"` 被脚本清空

**症状**：`generate_report.py` stderr 警告：
```
⚠️  mall_source='博查' 是 AI 来源，清空 price_mall/mall_source/mall_url
```

**根因**：把 AI 来源填到了商城字段。

**修复**：博查/IQS 是 AI 来源，价格应填到 `price_ai` + `ai_source="博查"`，`price_mall` 留 `null`。

### `price_ai = null`

**症状**：报告中"电商价"列空白。

**根因**：商城和 AI 都没查到，但没填经验估算值。

**修复**：`price_ai` **不允许 null**，查不到时填经验估算值，标 `ai_source = "经验预估"`。

### `price_unit / cost_ratio` 被脚本覆盖

**症状**：stderr 警告 LLM 手填的值被覆盖。

**根因**：这两个字段必须由脚本算，LLM 不要手填。

**修复**：从 JSON 中删掉 `price_unit` 和 `cost_ratio`，让脚本自动算。

---

## 一次性费用进了 items

**症状**：stderr 警告：
```
⚠️  category='认证费' 是一次性费用，不计入单套成本
```

**根因**：把认证费 / NRE / 开模费等一次性费用写进了 items 数组。

**修复**：从 items 中删除这些 entry，需要说明时写在 `ai_suggestion` 字段或对话中。

---

## 环境问题

### `import requests` 失败

```bash
pip3 install requests
```

### Playwright 启动失败

```bash
pip3 install playwright && python3 -m playwright install chromium
```

### IQS Key 额度耗尽

脚本会提示。用户提供新 Key 后，按 [01_ENV_SETUP.md](01_ENV_SETUP.md) Step 3 的方法更新。

---

## 查价异常

### 立创单价高于 1688 报价 3 倍以上

**症状**：立创直搜返回 ¥50 但 1688 模块价 ¥3-5。

**根因**：立创对该型号小批量散料定价偏高，或库存稀缺。

**修复**：立创价仅供参考，2000 套量应以 1688 一手代理价为准。在 JSON 的 `note` 字段说明。

### OV5640 等冷门 Sensor 立创未上架

**症状**：立创直搜返回 `found: false`。

**修复**：走博查/IQS（`ai_source="博查"`），或换国产替代（SC500AI / GC5025）。

### 型号混淆（STM32F103C8T6 vs VCT6）

**症状**：博查返回的价格里混入了不同型号。

**修复**：在搜索关键词里加封装信息（如 `"STM32F103C8T6 LQFP48"`），人工核对 part_number。

---

## validate_output.py 失败

| stderr 关键字 | 含义 | 修复 |
|---|---|---|
| `data/ 目录下没有 *.json` | LLM 没产出 JSON | 按 [05_ASSEMBLE_AND_RENDER.md](05_ASSEMBLE_AND_RENDER.md) 写 JSON |
| `data/ 目录下没有 *_report.html` | 没跑 generate_report.py | `python3 generate_report.py data/<json>` |
| `HTML 不含模板指纹` | 疑似手写 HTML | 删除野生 HTML，重新走标准链路 |
| `HTML 与 JSON 不同源` | 项目名/日期对不上 | 删旧 HTML，用最新 JSON 重新生成 |
| `JSON Schema 校验失败` | 字段问题 | 看错误位置，对照 [06_JSON_SCHEMA_GUIDE.md](06_JSON_SCHEMA_GUIDE.md) |
| `项目根目录发现野生 HTML` | LLM 在根目录写了 HTML | 删除非 `report-template.html` 的根目录 HTML |

---

## 仍然解决不了？

1. 用 `examples/` 下的样本作参照（最小可校验 JSON + 生成的 HTML）
2. 直接 Read `schema/bom-input-example.json` 看完整正例
3. 用 `python3 generate_report.py` 不带参数会列出可用数据文件
