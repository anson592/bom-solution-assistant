# 05 · 装配与渲染：查价结果 → JSON → 报告

> 这是**最易翻车的环节**。本文档回答：手上有一堆零散的查价结果，怎么变成最终报告？

**前置必读**：[00_CONTRACT.md](00_CONTRACT.md)

---

## 你在流程中的位置

```
[路径A 读 BOM / 路径B 反推 BOM] → 逐元件查价 → 【👉 你在这里】→ 完成
```

---

## 输入：你手上应该有什么

1. **查价原始数据**（每个元件 1-N 条记录）：
   - 立创/华秋商城价 + URL（如果有）
   - 博查 / IQS 价（如果有）
   - 经验估算价（用于查不到时的兜底）
2. **项目元信息**：
   - 项目名（如 `AI 魔法棒（户外探索版）`）
   - 日期（`YYYY-MM-DD`）
   - 目标产量（如 `2000套`）
   - 版本数量（1-3 个，由 B.1.5 用户选定）
3. **版本推荐**（来自路径 B 的 ai_suggestion）
4. **风险标签**（来自 Layer 4 合理性检查）

---

## 装配三步走

### Step 1：建立元信息骨架（直接复制改）

```json
{
  "project": "<项目名>",
  "date": "YYYY-MM-DD",
  "query_time": "HH:MM",
  "quantity": "<例如 2000套>",
  "total_quantity": "<总需求量>",
  "batch_quantity": "<每批数量>",
  "versions": ["经济版", "标准版", "高性能版"],
  "selected_version": "<必须是 versions 数组中某一个>",
  "ai_suggestion": "<一段话：为什么推荐这个版本>",
  "risk_tags": [
    {"tag": "<风险点>", "level": "high|mid|low", "desc": "<原因/建议>"}
  ],
  "items": []
}
```

权威 schema 见 [../schema/bom-output-schema.json](../schema/bom-output-schema.json)，字段语义见 [06_JSON_SCHEMA_GUIDE.md](06_JSON_SCHEMA_GUIDE.md)。

---

### Step 2：把每条查价结果映射到一个 item

**6 字段核心映射规则**：

| 来源 | 映射到字段 | 备注 |
|---|---|---|
| 立创直搜 / 华秋直搜的 price | `price_mall` | 来源必须是商城名 |
| 立创直搜 / 华秋直搜的 url | `mall_url` | 必须带 `https://` |
| 商城来源 | `mall_source` | **白名单**：`立创商城` / `华秋商城` / `云汉芯城` / `LCSC` |
| 博查 search 的 price | `price_ai` | `ai_source = "博查"` |
| IQS search 的 price | `price_ai` | `ai_source = "iqs"` |
| 商城和 AI 都没查到 | `price_ai = 经验估算值` | `ai_source = "经验预估"`（**禁止 null**） |
| 三档差异元件 | `is_variant=true` + `variants[]` 含 3 档 | 不要拆成 3 个独立 item |
| 三档共用元件 | `is_variant=false` + 字段平铺 | 不要写 `variants` |

#### 5 个映射场景

```
场景 A（商城 + AI 都有）：
  price_mall = 8.68 / mall_source = "立创商城" / mall_url = "https://..."
  price_ai = 10.20 / ai_source = "博查"
  found = true

场景 B（仅商城有）：
  price_mall = 5.20 / mall_source = "华秋商城" / mall_url = "https://..."
  price_ai = 7.0 / ai_source = "经验预估"   ← 经验值兜底
  found = true

场景 C（仅 AI 有）：
  price_mall = null / mall_source = "" / mall_url = ""
  price_ai = 12.00 / ai_source = "博查"
  found = true

场景 D（都没有，经验兜底）：
  price_mall = null / mall_source = "" / mall_url = ""
  price_ai = 0.05 / ai_source = "经验预估"   ← 必填，禁止 null
  found = false

场景 E（多版本元件 variant，某版本不适用）：
  variants 中该版本 item 写：
  part_number = "-" / brand = "-" / price_mall = null / price_ai = 0
  note = "本版本不需要"
```

#### 三个典型反例

❌ **反例 1：把 AI 来源填进商城字段**
```json
{"price_mall": 15.0, "mall_source": "博查"}
```
脚本会清空商城字段并 stderr 警告。正确：填到 `price_ai` + `ai_source="博查"`。

❌ **反例 2：variants 写成对象**
```json
{"is_variant": true, "variants": {"经济版": {...}}}
```
schema 校验直接退码 2。正确：`variants` 必须是数组。

❌ **反例 3：手填 price_unit / cost_ratio**
```json
{"price_mall": 10, "price_unit": 10, "cost_ratio": 5.2}
```
脚本会覆盖并 stderr 警告。规则：`price_unit = price_mall ?? price_ai`，自动算。

---

### Step 3：写入前的字段核对清单

提交 `data/<项目>_<日期>.json` 前，逐项打钩：

- [ ] `project` / `date` / `items` 都有
- [ ] `selected_version` ∈ `versions`
- [ ] 每个 item 都有 `is_variant: true` 或 `false`（不能省略）
- [ ] `is_variant: true` 的 item，`variants` 是数组（不是对象）
- [ ] `variants[]` 长度 = `versions.length`，每个含全部版本
- [ ] `user_value` 全是 `"低"` / `"中"` / `"高"` 字符串
- [ ] `mall_source` 全是白名单值或 `""`
- [ ] 没有 `mall_source = "博查" / "IQS" / "经验预估"`
- [ ] 每个 item / variant 都有 `price_ai`（非 null）
- [ ] **没有手填 `price_unit` / `cost_ratio`**
- [ ] 一次性费用（认证费/NRE/开模费）**不在 items 数组里**

---

## 渲染：跑 generate_report.py

```bash
python3 generate_report.py data/<项目>_<日期>.json
```

脚本自动做的事：
1. 字段别名迁移（旧字段名 `price_market` → `price_mall` 等）
2. 清洗 `mall_*` 字段（来源是 AI 时自动清空）
3. 算 `price_unit`（mall 优先，mall 空用 ai）
4. 算 `cost_ratio`（按 `selected_version` 占比）
5. 注入 `report-template.html` → 输出 `data/<项目>_<日期>_report.html`

### ⛔ 禁止的替代方案

- ❌ 用 `Write` 工具手写 HTML（无论多漂亮）
- ❌ 用 `show_widget` 替代最终报告
- ❌ 用 Markdown 表格替代

---

## 渲染失败的诊断

| 退码 | stderr 关键字 | 修复 |
|---|---|---|
| 2 | `JSON Schema 校验失败` | 看错误位置，对照 [06_JSON_SCHEMA_GUIDE.md](06_JSON_SCHEMA_GUIDE.md) |
| 2 | `variants 不是数组` | 把 `{"经济版": {...}}` 改成 `[{"version":"经济版", ...}]` |
| 2 | `is_variant 缺失` | 每个 item 都要显式 `"is_variant": true/false` |
| 2 | `user_value 类型错误` | 改为字符串 `"低"/"中"/"高"`，不是数字 |
| 1 | `模板文件不存在` | 检查 `report-template.html` 是否在仓库根目录 |
| 1 | `数据文件不存在` | JSON 路径写错了，用相对仓库根目录的路径 |

stderr 警告（不阻塞，但要看）：
- `mall_source='博查' 是 AI 来源，已清空商城字段` → 修改源 JSON 把博查价改填到 `price_ai`
- `price_unit=N 已被脚本覆盖` → 删除手填的 `price_unit`

---

## 收尾：跑硬阫

```bash
python3 validate_output.py
```

看到 `✅ CONTRACT PASSED` 才算完成。任何报错按提示修复，**不要绕过**。

详细校验项见 [00_CONTRACT.md](00_CONTRACT.md) 末尾。
