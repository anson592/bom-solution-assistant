# Examples · 参考样本

> 完整跑通的案例，供 LLM 装配 JSON 时对照。

## AI 魔法棒（户外探索版）

- 输入 JSON：[AI魔法棒_input.json](AI魔法棒_input.json)
  - 18 个 items（10 个 variant + 多个 shared）
  - 三版本对比（经济版 / 标准版 / 高性能版）
  - 6 个 risk_tags
  - 来源混合：立创直搜（7 项）+ 博查（4 项）+ 经验估算（剩余）
- 生成 HTML：[AI魔法棒_report.html](AI魔法棒_report.html)（7.8MB，含完整模板 + 注入数据）

## 复现方法

```bash
# 1. 把 input.json 复制到 data/
cp examples/AI魔法棒_input.json data/test_input.json

# 2. 跑生成
python3 generate_report.py data/test_input.json

# 3. 校验
python3 validate_output.py --project test_input
```

预期：`✅ CONTRACT PASSED`，退码 0。

---

## 学习要点

阅读 [AI魔法棒_input.json](AI魔法棒_input.json) 时重点看：

1. **顶层结构**：`project` / `date` / `versions` / `selected_version` / `ai_suggestion` / `risk_tags` / `items`
2. **variants 数组写法**（item id=1 主控 SoC）：3 个 version 平铺
3. **shared item 写法**（id=15/16/17）：字段平铺，无 variants
4. **mall_source 白名单**：每个有商城价的 item 都标 `"立创商城"` / `"华秋商城"`
5. **price_ai 全部非 null**：包括 ai_source="经验预估" 兜底
6. **没有 price_unit / cost_ratio 字段**：由 generate_report.py 自动算

字段含义详见 [../docs/06_JSON_SCHEMA_GUIDE.md](../docs/06_JSON_SCHEMA_GUIDE.md)。
