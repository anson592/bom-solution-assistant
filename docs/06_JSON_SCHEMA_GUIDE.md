# 06 · JSON Schema 字段字典

> 本文档解释 `schema/bom-output-schema.json` 每个字段的含义与合法值。**权威 schema 以 [../schema/bom-output-schema.json](../schema/bom-output-schema.json) 为准**，本文档负责把 schema 翻译成人话。

参考完整正例：[../schema/bom-input-example.json](../schema/bom-input-example.json) 和 [../examples/](../examples/)。

---

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project` | string | ✅ | 项目名称（用于报告标题和文件名） |
| `date` | string | ✅ | `YYYY-MM-DD` 格式 |
| `query_time` | string | | `HH:MM` 查询时间 |
| `quantity` | string/number | | 目标产量描述（如 `"2000套"`） |
| `total_quantity` | string/number | | 总需求量 |
| `batch_quantity` | string/number | | 每批次数量 |
| `versions` | string[] | | 版本名数组（如 `["经济版", "标准版", "高性能版"]`） |
| `selected_version` | string | | 用户选定的主版本，**必须是 `versions` 数组中某一个** |
| `ai_suggestion` | string | | AI 推荐建议（一段话） |
| `risk_tags` | object[] | | 风险标签数组，元素含 `tag` / `level` / `desc` |
| `items` | object[] | ✅ | 元器件数组（至少 1 个） |

---

## items 数组元素：两种形态

每个 item **必须显式声明 `is_variant`**，根据值进入不同分支。

### 形态 A：`is_variant = true`（三版本差异化元件）

**必填字段**：`id` / `category` / `is_variant` / `variants`

```json
{
  "id": 1,
  "category": "主控 SoC",
  "is_variant": true,
  "cost_tier": "high",
  "user_value": "高",
  "func_impact": "决定整机算力上限",
  "exp_impact": "影响 AI 响应速度",
  "func_impact_label": "关键",
  "exp_impact_label": "关键",
  "note": "三版本性能跨度大",
  "variants": [
    {
      "version": "经济版",
      "brand": "ESPRESSIF",
      "package": "Module",
      "part_number": "ESP32-S3-WROOM-1",
      "description": "双核 240MHz + WiFi/BT",
      "price_mall": 22.5,
      "mall_source": "立创商城",
      "mall_url": "https://item.szlcsc.com/3198300.html",
      "price_ai": 24.0,
      "ai_source": "博查",
      "found": true,
      "func_impact_score": 55,
      "exp_impact_score": 55
    },
    {"version": "标准版", "part_number": "ESP32-P4", ...},
    {"version": "高性能版", "part_number": "RK3566", ...}
  ]
}
```

⚠️ **`variants` 必须是数组**，绝不可写成对象 `{"经济版": {...}}`。

### 形态 B：`is_variant = false`（三版本共用元件）

**必填字段**：`id` / `category` / `is_variant` / `part_number`

```json
{
  "id": 16,
  "category": "按键",
  "is_variant": false,
  "brand": "通用",
  "package": "SMD",
  "part_number": "侧键×2 + 触发键×1",
  "description": "...",
  "price_mall": null,
  "mall_source": "",
  "mall_url": "",
  "price_ai": 0.6,
  "ai_source": "经验预估",
  "found": true,
  "cost_tier": "low",
  "user_value": "低",
  "func_impact": "物理交互入口",
  "exp_impact": "手感影响第一印象",
  "func_impact_label": "一般",
  "exp_impact_label": "一般",
  "note": "三版本通用"
}
```

---

## 价格相关字段（重灾区）

| 字段 | 类型 | 谁填 | 合法值 |
|---|---|---|---|
| `price_mall` | number / null | LLM | 商城实际查到的最低价；**没查到 → `null`**（不要把 AI 价复制过来） |
| `mall_source` | string / null | LLM | 白名单：`"立创商城"` / `"华秋商城"` / `"云汉芯城"` / `"LCSC"` / `"立创商城+华秋商城"` / `""` |
| `mall_url` | string / null | LLM | 仅商城来源时填 URL；其他 → `""` |
| `price_ai` | number | LLM | 博查/IQS 最低价；**禁止 null**（查不到时填经验估算） |
| `ai_source` | string | LLM | `"博查"` / `"iqs"` / `"经验预估"` / `""` |
| `price_unit` | number | **脚本** | **LLM 不填**；脚本算：`price_mall ?? price_ai` |
| `cost_ratio` | number | **脚本** | **LLM 不填**；脚本算：`price_unit / 单套总成本 × 100` |
| `found` | boolean | LLM | `price_mall` 或 `price_ai` 任一非 null → `true` |

### mall_source ↔ ai_source 严禁混填

| 来源 | 应填 |
|---|---|
| 立创商城 / 华秋商城 / 云汉芯城 / LCSC | `mall_source` |
| 博查 / IQS / 1688（搜索来的） | `ai_source` |
| 经验估算 | `ai_source = "经验预估"`，`mall_source = ""` |

❌ 错误：`mall_source: "博查"` → 脚本会清空并 stderr 警告

---

## 枚举字段合法值

| 字段 | 合法值 |
|---|---|
| `cost_tier` | `"high"` / `"mid"` / `"low"` |
| `user_value` | `"低"` / `"中"` / `"高"`（**字符串！不是数字**） |
| `risk_tags[].level` | `"high"` / `"mid"` / `"low"` |
| `is_variant` | `true` / `false`（**必填，不能省略**） |

---

## variants 数组元素字段

每个 variant 必填：`version` / `part_number`

| 字段 | 类型 | 说明 |
|---|---|---|
| `version` | string | **必须出现在顶层 `versions` 数组**中 |
| `part_number` | string | 元器件型号 |
| `brand` | string | 品牌（核心元件必填，散装件允许 `"混用"`） |
| `package` | string | 封装 |
| `description` | string | 关键参数 |
| `price_mall` / `mall_source` / `mall_url` | 同上 | |
| `price_ai` / `ai_source` | 同上 | |
| `found` | boolean | |
| `func_impact_score` | integer | 功能影响分（0-100，可选） |
| `exp_impact_score` | integer | 体验影响分（0-100，可选） |
| `price_unit` / `cost_ratio` | **脚本算** | LLM 不填 |

---

## 字段别名（兼容旧数据）

`generate_report.py` 会自动把以下旧字段名迁移到新字段名（仅一次性，老 JSON 仍能跑）：

| 旧字段名 | 新字段名 |
|---|---|
| `price_market` | `price_mall` |
| `market_source` | `mall_source` |
| `market_url` | `mall_url` |
| `price_ecommerce` | `price_ai` |
| `ecommerce_source` | `ai_source` |
| `price_estimated` | `price_unit` |
| `price_estimated_experience` | `price_unit` |
| `source` | `mall_source` |
| `source_url` | `mall_url` |

**新 JSON 必须用新字段名**。

---

## 一次性费用（严禁进 items）

以下 category **不允许**出现在 `items[]`：

- `认证费` / `NRE` / `开模费` / `工装费` / `模具费` / `认证` / `合规认证`

理由：一次性费用不是单套物料成本，写进 items 会被算进 BOM 成本导致严重虚高。脚本会自动 stderr 警告并清空它们的 `cost_ratio`。

如需说明，写在 `ai_suggestion` 字段或对话里。

---

## 极简正例（最小可校验 JSON）

```json
{
  "project": "示例",
  "date": "2026-05-19",
  "versions": ["经济版"],
  "selected_version": "经济版",
  "items": [
    {
      "id": 1,
      "category": "MCU",
      "is_variant": false,
      "part_number": "STM32F103C8T6",
      "brand": "ST",
      "price_mall": 8.68,
      "mall_source": "立创商城",
      "mall_url": "https://...",
      "price_ai": 9.5,
      "ai_source": "博查",
      "found": true
    }
  ]
}
```

跑通：
```bash
python3 generate_report.py data/示例_2026-05-19.json
# → 输出 data/示例_2026-05-19_report.html
python3 validate_output.py
# → ✅ CONTRACT PASSED
```
