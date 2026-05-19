# 00 · 输出契约（⛔ 任何路径前必读）

> 这是本 Skill 唯一的硬契约文件。**违反任一条，`generate_report.py` 退码 2 阻断，`validate_output.py` 退码 2 阻断。**

---

## ⛔ 三条红线（最先记住）

1. **最终交付物 = `data/<项目>_<日期>_report.html`**，由 `python3 generate_report.py <json>` 生成。
2. **LLM 唯一产出 = JSON**（符合 [../schema/bom-output-schema.json](../schema/bom-output-schema.json)）。**不允许手写 HTML 作为最终交付**（包括 Write、show_widget、Markdown 表格都不算最终报告）。
3. **完成后必须跑 `python3 validate_output.py`**，看到 `✅ CONTRACT PASSED` 才算交付。

---

## 标准产物链路（不可绕过）

```
路径A/B 推理出 BOM
       │
       ▼
   逐元件查价（立创/华秋/博查/IQS）
       │
       ▼
   组装符合 schema 的 JSON  ← LLM 的产物到此为止
       │
       ▼
   python3 generate_report.py data/<项目>_<日期>.json
       │（脚本做：schema 校验 → 字段别名迁移 → 算 price_unit/cost_ratio → 注入模板）
       ▼
   data/<项目>_<日期>_report.html
       │
       ▼
   python3 validate_output.py   ← ⭐ 收尾必跑
       │
       ▼
   ✅ CONTRACT PASSED
```

---

## 8 条铁律（违反任一退码 2）

1. **顶层必填字段**：`project`、`date`、`items`
2. **每个 item 必须显式声明 `is_variant: true` 或 `false`**，不能省略
3. **`is_variant: true` 的 item，`variants` 必须是 JSON 数组 `[...]`**
   - ❌ 严禁写成对象 `{"经济版": {...}, "标准版": {...}}` —— 这是最常见的错误
4. **`selected_version` 必须是 `versions` 数组中的某一个字符串**，禁止拼接（如 `"经济版+标准版"` 错误）
5. **`user_value` 必须是字符串** `"低"` / `"中"` / `"高"`，不能是整数
6. **`mall_source` 只能填商城名**（`立创商城` / `华秋商城` / `云汉芯城` / `LCSC`）或空字符串 `""`
   - ❌ 严禁填 `"博查"` / `"IQS"` / `"经验预估"` —— 这些是 AI 来源，只能填 `ai_source`
7. **`price_ai` 不允许 `null`**，查不到时必须填经验估算值并标 `ai_source="经验预估"`
8. **`price_unit` 和 `cost_ratio` 由 `generate_report.py` 自动计算，LLM 不填**

---

## 三个常见错误（反例）

### ❌ 反例 1：手写 HTML 当报告

```python
# 错误：LLM 自己写了一个 HTML 文件作为最终交付
Write("AI魔法棒_报告.html", "<html>...</html>")
```

正确做法：先写 JSON，再跑 `generate_report.py`。

### ❌ 反例 2：把 AI 来源填进商城字段

```json
{
  "price_mall": 15.0,
  "mall_source": "博查",        // ❌ 错误！博查是 AI 来源
  "mall_url": ""
}
```

正确：

```json
{
  "price_mall": null,            // 商城没查到 → null
  "mall_source": "",
  "mall_url": "",
  "price_ai": 15.0,
  "ai_source": "博查"            // ✅ 填到 ai_source
}
```

### ❌ 反例 3：variants 写成对象

```json
{
  "is_variant": true,
  "variants": {                  // ❌ 错误！必须是数组
    "经济版": {...},
    "标准版": {...}
  }
}
```

正确：

```json
{
  "is_variant": true,
  "variants": [                  // ✅ 数组
    {"version": "经济版", "part_number": "...", ...},
    {"version": "标准版", "part_number": "...", ...}
  ]
}
```

---

## 一次性费用红线

**严禁**把以下类别写进 `items` 数组：

- `认证费` / `NRE` / `开模费` / `工装费` / `模具费` / `合规认证`

这些是一次性投入，不是单套物料成本，写进 items 会被算进 BOM 成本导致严重虚高。需说明时写在对话或 `ai_suggestion` 字段。

---

## 字段写法快速对照

| 字段 | 谁填 | 填什么 | 空值规则 |
|---|---|---|---|
| `price_mall` | LLM | 立创/华秋/云汉/LCSC 商城查到的价格 | 没查到 → `null`（**不要复制 AI 价**） |
| `mall_source` | LLM | `"立创商城"` / `"华秋商城"` / `"云汉芯城"` / `"LCSC"` | 没查到 → `""` |
| `mall_url` | LLM | 商城实际 URL | 其他 → `""` |
| `price_ai` | LLM | 博查/IQS 最低价 或 经验估算值 | **不允许 `null`** |
| `ai_source` | LLM | `"博查"` / `"iqs"` / `"经验预估"` | - |
| `found` | LLM | `price_mall` 或 `price_ai` 任一非 null | - |
| `price_unit` | **脚本自动** | 不填 | - |
| `cost_ratio` | **脚本自动** | 不填 | - |

完整字段字典见 [06_JSON_SCHEMA_GUIDE.md](06_JSON_SCHEMA_GUIDE.md)。装配步骤见 [05_ASSEMBLE_AND_RENDER.md](05_ASSEMBLE_AND_RENDER.md)。

---

## 收尾验收

```bash
python3 validate_output.py
```

输出 `✅ CONTRACT PASSED` 才算完成。任何报错按提示修复后重跑，**不要绕过**。
