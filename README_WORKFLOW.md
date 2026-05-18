# BOM 询价→报告 标准工作流

## 整体流程

```
询价完成
  ↓
直接组装最终 JSON（字段对标 HTML 模板）
  ↓
python3 generate_report.py data/xxx_final.json
  ↓
生成 HTML 报告（可预览/分享）
```

**重要原则：价格直接抄，不计算，不转换。**

---

## 第一步：组装最终 JSON

询价完成后，填写以下格式的文件，字段**直接对标 HTML 模板**：

```json
{
  "project": "项目名称",
  "date": "2026-05-14",
  "quantity": "2000套",
  "total_quantity": "100000",
  "batch_quantity": "5000",
  "versions": ["经济版", "标准版", "高性能版"],
  "selected_version": "高性能版",
  "ai_suggestion": "AI推荐建议",
  "risk_tags": [
    {"tag": "风险描述", "level": "high", "desc": "详细说明"}
  ],
  "items": [
    {
      "id": 1,
      "category": "MCU",
      "is_variant": true,
      "func_impact": "...",
      "exp_impact": "...",
      "user_value": 5,
      "note": "...",
      "variants": [
        {
          "version": "经济版",
          "brand": "<MCU_品牌>",
          "package": "<封装>",
          "part_number": "<具体型号-占位>",
          "description": "<关键参数>",
          "price_mall": 8.5,              // 商城价：搜到什么填什么，两个商城取最低
          "mall_source": "立创商城",        // 来源：立创/华秋/云汉/LCSC/博查搜索/IQS搜索
          "mall_url": "https://...",        // 仅立创/华秋/云汉/LCSC有链接
          "price_ai": 12,                  // AI价：博查/IQS查到什么填什么
          "ai_source": "博查",              // 来源：博查/iqs/经验预估
          "price_unit": 8.5,               // 小计：mall优先；mall空用price_ai
          "found": true,
          "func_impact_score": 50,
          "exp_impact_score": 50
        }
      ]
    },
    {
      "id": 7,
      "category": "接口",
      "is_variant": false,
      "brand": "-",
      "package": "SMD",
      "part_number": "USB-C 插座 16P",
      "description": "...",
      "price_mall": null,                 // 商城价：查不到填 null
      "mall_source": "",                   // 来源
      "mall_url": "",                     // 链接（仅立创/华秋/云汉/LCSC有）
      "price_ai": null,                   // AI价：查不到填 null
      "ai_source": "经验预估",              // AI价查不到时填"经验预估"
      "price_unit": 1.50,                 // 小计：商城优先；商城空用AI；都没有用经验估算
      "found": true,
      "note": "经验估算"
    }
  ]
}
```

### 价格字段填写规则（直接抄，不计算）

| 字段 | 填什么 | 示例 |
|------|--------|------|
| `price_mall` | 商城搜到的最低价 | `30.00` |
| `mall_source` | 商城来源 | `"立创商城"` |
| `mall_url` | 商城链接（仅立创/华秋/云汉/LCSC有） | `"https://..."` |
| `price_ai` | 博查/IQS查到的价格 | `28.50` |
| `ai_source` | AI来源 | `"博查"` 或 `"iqs"` 或 `"经验预估"` |
| `price_unit` | 小计：mall优先；mall空用price_ai | `30.00` |
| `found` | mall或ai至少一个有值 | `True` |

---

## 第二步：生成 HTML 报告

```bash
cd ~/.workbuddy/skills/bom-solution-assistant
python3 generate_report.py data/<项目名>_final.json
```

输出文件：`data/<项目名>_<日期>_report.html`

在 WorkBuddy 中用 `preview_url` 预览。

---

## 文件清单

| 文件 | 作用 |
|------|------|
| `schema/bom-output-schema.json` | 标准输出 JSON Schema（对接模板） |
| `generate_report.py` | 标准 JSON→HTML 报告 生成脚本 |
| `report-template.html` | HTML 报告模板 |
