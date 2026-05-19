# 04 · 查价脚本 API 参考

> 6 个查询脚本的签名与典型用法。所有脚本支持 `--json` 参数返回结构化数据。

---

## 查询策略总览

```
所有元器件统一流程：

  Step 0: 华秋 + 立创商城并行（★商城价，无需登录）
    └─ 双源验证或单源采纳，2-3 秒

  Step 1: 博查 + IQS 并行（★AI 价，强制执行 ⚠️）
    └─ 不论 Step 0 结果如何，每个元件都必须执行

  Step 2: 可选 Playwright 实时点验（仅 Step 0 失败时触发，兜底校准）
```

**核心约束**：⚠️ Step 1 是**所有元件都必须执行**的 AI 价查询，**不是** Step 0 失败时的"降级补救"。**price_ai 不允许 null**——查不到时必须填经验估算值并标 `ai_source = "经验预估"`。

---

## 1. 立创商城直搜（`scripts/lcsc_szlcsc_search.py`）

商城价首选源。Playwright 实现，3-5 秒。

```bash
python3 scripts/lcsc_szlcsc_search.py "STM32F103C8T6" --json
```

**JSON 输出**：
```json
{
  "keyword": "STM32F103C8T6",
  "found": true,
  "source": "立创商城",
  "part_number": "STM32F103C8T6",
  "brand": "ST(意法)",
  "price": 8.68,
  "price_ladder": 1,
  "url": "https://so.szlcsc.com/global.html?k=STM32F103C8T6"
}
```

**注意**：连续 4 次会触发登录（脚本已处理）。映射到 `price_mall` / `mall_source="立创商城"` / `mall_url`。

---

## 2. 华秋商城直搜（`scripts/hqchip_search.py`）

商城价补充源，裸 requests，2-3 秒，无反爬。

```bash
python3 scripts/hqchip_search.py "STM32F103C8T6" --json
```

**JSON 输出**：
```json
{
  "keyword": "STM32F103C8T6",
  "found": true,
  "source": "华秋商城",
  "price": 8.50,
  "price_ladder": 1,
  "url": "https://www.hqchip.com/search.html?keyword=STM32F103C8T6"
}
```

映射到 `price_mall` / `mall_source="华秋商城"` / `mall_url`。

---

## 3. 博查 AI 搜索（`scripts/shengsuan_search.py`）

通过胜算云 API + 博查搜索引擎，AI 提取多平台价格，**首选 AI 价**。

```bash
# 基础搜索
python3 scripts/shengsuan_search.py "STM32F103C8T6 价格" --json

# 深度搜索（覆盖更多渠道）
python3 scripts/shengsuan_search.py "STM32F103C8T6 价格" --depth advanced --json

# 自动模式（博查无结果自动降级 Tavily 全球搜索）
python3 scripts/shengsuan_search.py "STM32F103C8T6 价格" --engine auto --json
```

**JSON 输出**：
- `content`: 价格数组（含 source / price / quantity / currency / link / note）
- `search_results`: 原始网页摘要
- `search_queries`: 实际搜索的关键词列表

**价格已内置 API Key，无需配置**。映射到 `price_ai` / `ai_source="博查"`。

**注意**：
- 偶尔出现型号混淆（如 C8T6 vs VCT6），需人工复核
- 搜索缓存价格可能与实时价有轻微差异

---

## 4. 阿里云 IQS 搜索（`scripts/iqs_search.py`）

与博查互补，双源交叉验证。

```bash
# 纯搜索（辅助信息，~0.8s）
python3 scripts/iqs_search.py "STM32F103C8T6 datasheet" --json

# AI 问答（搜索 + AI 总结，~11s）
python3 scripts/iqs_search.py "STM32F103C8T6 价格 批量" --ai-answer --json

# ★ 双源交叉验证（博查 + IQS 并行）
python3 scripts/iqs_search.py "STM32F103C8T6 价格 批量" --cross-verify --json
```

**JSON 输出**：
- `parsed_prices`: 同博查格式
- `raw_answer`: AI 大模型原始回答（`--ai-answer` 模式）
- `query_results`: 搜索结果列表

映射到 `price_ai` / `ai_source="iqs"`。

**注意**：`--cross-verify` 需要 `ALIYUN_IQS_API_KEY`（脚本已内置）；偶尔会把开发板价格混入芯片价格，需人工复核。

---

## 5. 立创实时点验（`scripts/lcsc_playwright_verify.py`）

**兜底校准**：仅 Step 0 失败 + Step 1 有 AI 价时触发。

```bash
python3 scripts/lcsc_playwright_verify.py 'STM32F103C8T6' --ai-price 11.80 --json
```

**JSON 输出**：
```json
{
  "step2_verified": true,
  "price_realtime": 12.50,
  "price_ai": 11.80,
  "price_diff_pct": 5.9,
  "confidence": "verified",
  "laddered_prices": [{"qty": 10, "price": 12.50}, ...],
  "source": "szlcsc.com"
}
```

**三种 confidence 标记**：

| confidence | 差价 | 后续处理 |
|---|---|---|
| `verified` | < 15% | 以 AI 价为准 |
| `suspicious` | ≥ 15% | 用 Playwright 实测价覆盖 AI 价，`mall_source = "立创商城"` |
| `unverified` | Playwright 失败 | 保留 AI 价 |

---

## 6. BOM 比价模板生成（`scripts/generate_bom_comparison.py`）

辅助工具：生成 Excel 比价模板。**与最终报告无关**——最终报告必须用 `generate_report.py`，详见 [00_CONTRACT.md](00_CONTRACT.md)。

---

## 并行查询模板（推荐）

```python
import concurrent.futures, subprocess, json

def run_script(args):
    res = subprocess.run(args, capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"found": False, "error": res.stderr[:200]}

# Step 0: 商城双源并行
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    f_hq  = ex.submit(run_script, ["python3", "scripts/hqchip_search.py", keyword, "--json"])
    f_lc  = ex.submit(run_script, ["python3", "scripts/lcsc_szlcsc_search.py", keyword, "--json"])
    hq_result, lc_result = f_hq.result(), f_lc.result()

# Step 1: AI 双源并行（强制执行，不论 Step 0 结果如何）
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    f_bocha = ex.submit(run_script, ["python3", "scripts/shengsuan_search.py", f"{keyword} 价格", "--json"])
    f_iqs   = ex.submit(run_script, ["python3", "scripts/iqs_search.py", f"{keyword} 价格 批量", "--cross-verify", "--json"])
    bocha_result, iqs_result = f_bocha.result(), f_iqs.result()
```

---

## 价格结果标注规则

每个元器件的价格数据标注来源和验证状态：

| 来源场景 | 标注格式 | 示例 |
|---------|---------|------|
| 华秋商城直搜 | `华秋商城 ¥X.XX ↗` | `华秋商城 ¥30.14 ↗` |
| 立创商城直搜 | `立创商城 ¥X.XX ↗` | `立创商城 ¥8.68 ↗` |
| 博查+IQS 一致 + Playwright 验证 | `{商城名} ¥X.XX ↗` | `立创商城 ¥5.20 ↗` |
| 博查+IQS 一致（未验证商城） | `博查+IQS ¥X.XX` | `博查+IQS ¥8.50` |
| 博查独有 | `博查 ¥X.XX` | `博查 ¥1.23` |
| IQS 独有 | `IQS ¥X.XX` | `IQS ¥6.64` |
| 存疑（价差 > 20%） | `存疑 ¥X.XX（博查¥A/IQS¥B）` | - |
| 经验估算 | `经验估算 ¥X.XX` | `经验估算 ¥0.01` |

**HTML 输出**：`↗` 仅在 `mall_source` 含白名单关键词（立创/华秋/云汉/LCSC）且 `mall_url` 有值时生成可点击链接。

---

## 经验估算（所有来源均失败时的兜底）

当 Step 0 和 Step 1 全部没有查到任何价格时，使用经验估算：

| 分类 | 经验价格范围 |
|------|-------------|
| 电阻(0805/0603) | ¥0.01 ~ 0.03/颗 |
| 电容(0805/0603) | ¥0.02 ~ 0.08/颗 |
| 电感 | ¥0.05 ~ 0.20/颗 |
| 二极管/LED | ¥0.05 ~ 0.50/颗 |
| 晶振 | ¥0.30 ~ 1.50/颗 |
| 连接器 | ¥0.10 ~ 2.00/颗 |
| MCU（如 STM32F103） | ¥3 ~ 15/颗 |
| 电源 IC（如 AMS1117） | ¥0.50 ~ 3.00/颗 |
| 传感器（如 MPU-6050） | ¥2 ~ 15/颗 |
| 通信模块（WiFi/BLE） | ¥8 ~ 35/颗 |

**写入规则**：`price_ai = 经验值`，`ai_source = "经验预估"`，`found = false`（如果商城价也没查到）。

---

## 查完后：装配 JSON

详见 [05_ASSEMBLE_AND_RENDER.md](05_ASSEMBLE_AND_RENDER.md)。
