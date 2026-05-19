# BOM 询价 → 报告 工作流

> **本文件为指针。** 完整规范请参考下列权威来源，避免出现多份互相矛盾的字段说明。

## JSON 格式权威来源

- **Schema 定义**：[schema/bom-output-schema.json](schema/bom-output-schema.json)
- **填写示例**：[schema/bom-input-example.json](schema/bom-input-example.json)
- **工作流详解**：[SKILL.md](SKILL.md) 第 5 章「数据组装与报告生成」

## 快速命令

```bash
# 1. 强制校验 JSON（generate_report.py 已内置，可单独运行）
python3 -c "import json,jsonschema; jsonschema.validate(json.load(open('data/xxx.json')), json.load(open('schema/bom-output-schema.json')))"

# 2. 生成 HTML 报告
python3 generate_report.py data/<项目名>_final.json
```

输出文件：`data/<项目名>_<日期>_report.html`

## 关键约束（速查）

| 字段 | 类型 | 取值约束 |
|---|---|---|
| `items[].is_variant` | bool | **必填**，true/false |
| `items[].variants` | array | `is_variant=true` 时必填，**必须是数组 `[...]`，不能是对象 `{...}`** |
| `items[].user_value` | string | 取值 `"低"` / `"中"` / `"高"`，不接受整数 |
| `mall_source` | string | `"立创商城"` / `"华秋商城"` / `"云汉芯城"` / `"LCSC"` / 空字符串；**严禁** `"博查"` / `"IQS"` / `"经验预估"` |
| `ai_source` | string | `"博查"` / `"iqs"` / `"经验预估"` / 空字符串 |
| `price_unit` / `cost_ratio` | number | **由 generate_report.py 自动计算**，LLM 不填 |

详细字段说明以 schema 文件为准。
