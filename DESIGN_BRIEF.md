# BOM Solution Assistant · 报告页面设计简报

> 给设计师的需求说明。本文只描述**用户是谁、要解决什么问题、可用数据**。不规定页面布局、视觉风格、组件形式——交给设计师做主。

---

## 1. 工具是什么

`bom-solution-assistant` 是一个 BOM（电子元器件清单）询价工具：

1. 用户用一句话描述产品需求（比如"做一个拍立得"），AI 反推出完整的元器件清单——可以是单一方案，也可以是 1~3 个版本对比（比如 经济版 / 标准版 / 高性能版，每个版本选不同档次的 MCU、存储、通信模组）
2. 工具跨平台查询每个元器件的真实价格（立创/华秋商城 + 博查/IQS AI 搜索）
3. 把所有数据写入一个 JSON 文件，渲染成**一份单页 HTML 报告**，用户可以在浏览器里看，也可以导出 Excel、打印 PDF 给上下游

**报告就是这次设计的对象。**

---

## 2. 用户是谁，他在什么情境下看这份报告

**典型用户**：硬件创业者、产品经理、采购、供应链工程师。

**典型场景**：
- 项目早期评估"这个产品做出来要花多少钱"——快速看总成本
- 几个方案之间选一个——对比各版本的总价 + 关键元件差异
- 把方案带去和老板/合伙人/投资人讨论——需要打印或截图
- 拿着比价单去和供应商谈——需要看清每个元件的市场价、AI 价、来源链接

**用户不是**：
- 不是工程师（不需要看完整数据手册）
- 不是会计（不需要追踪每分钱的会计科目）
- 不是开发者（不需要看代码或调试信息）

**视口环境**：
- 主要在桌面浏览器看（视口典型 1280~1440 px，少数 1920 px 大屏）
- 偶尔在平板上看
- 经常打印 PDF（A4 纵向 / A3 横向）和导出 Excel

---

## 3. 用户要解决的问题（用户故事）

**P0（核心）**：

- 我打开报告 5 秒内要知道"这个 BOM 总成本是多少"
- 如果有多版本，我要一眼能比较出"哪个版本贵多少 / 贵在哪些元件上"
- 我要知道哪些元件的价格是真实查到的、哪些是 AI 估的、哪些是经验值——可信度不一样
- 我要能点击元件的商城链接，跳到立创/华秋商城页面验证价格
- 我要看到 AI 给我的整体建议（能不能砍成本、有没有缺货风险等）

**P1（重要）**：

- 我要知道每个元件占整套成本多少百分比——挑出大头集中谈判
- 我要看到风险提示（缺货、停产、批量供应风险等）
- 我要能切换不同版本，对应的占比和饼图要跟着变
- 多版本对比时，我要在同一行看到不同版本各自的型号 / 品牌 / 价格

**P2（加分）**：

- 我要能导出 Excel 给采购同事
- 我要能打印 PDF 带去开会
- 我要能看到每个元件的"功能影响"和"体验影响"——理解砍掉它会有什么后果

---

## 4. 可用数据

报告渲染所有内容都来自一个 JSON 文件。结构如下（完整 schema 在 [schema/bom-output-schema.json](schema/bom-output-schema.json)）。

### 4.1 整体信息

| 字段 | 类型 | 含义 | 是否必填 |
|---|---|---|---|
| `project` | string | 项目名（如"拍立得"） | 是 |
| `date` | string | 查询日期 YYYY-MM-DD | 是 |
| `query_time` | string | 查询时间 HH:MM | 否 |
| `quantity` | string | 目标产量描述（如"2000 套"） | 否 |
| `total_quantity` | string | 总需求量数字 | 否 |
| `batch_quantity` | string | 每批次数量 | 否 |
| `versions` | string[] | 版本列表（如 `["经济版", "标准版", "高性能版"]`，1~3 个） | 是 |
| `selected_version` | string | 默认选中版本 | 否 |
| `ai_suggestion` | string | AI 整体建议（一段长文本，可能多句） | 否 |
| `risk_tags` | array | 风险提示列表，见下 | 否 |

### 4.2 风险提示（risk_tags）

每个风险一个对象，0~10 个。

| 字段 | 类型 | 含义 |
|---|---|---|
| `tag` | string | 风险标题（如"热敏打印模块缺货风险"） |
| `level` | "high" / "mid" / "low" | 严重等级 |
| `desc` | string | 风险描述（一两句话） |

### 4.3 BOM 元件清单（items[]）—— 两种类型

每条元件要么是**共享元件**（所有版本都用同一个），要么是**变体元件**（不同版本选不同型号）。

#### A. 共享元件 shared item

例：电阻、电容、PCB、外壳——所有版本都一样。

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | int | 自增编号 |
| `category` | string | 分类（"MCU" / "电源" / "晶振" / "存储-Flash" / "存储-内存" / "传感器" / "WiFi_BLE" 等，22+ 类） |
| `is_variant` | false | 共享元件标志 |
| `brand` | string | 品牌 |
| `package` | string | 封装（如"QFP-64"） |
| `part_number` | string | 具体型号 |
| `description` | string | 关键参数（如"168MHz, Cortex-M4, 1MB Flash"） |
| `price_mall` | number / null | 商城价（立创/华秋查到的最低价；查不到留 null） |
| `mall_source` | string / null | 商城来源（"立创商城" / "华秋商城" / null） |
| `mall_url` | string / null | 商城链接（仅商城价存在时有，可点击） |
| `price_ai` | number | AI 价（博查/IQS 查到的；都查不到时填经验估算值——此字段不允许 null） |
| `ai_source` | string | AI 来源（"博查" / "iqs" / "经验预估"） |
| `price_unit` | number | 小计（脚本算的，规则：mall 优先，没有则用 ai） |
| `cost_ratio` | number | 占整套成本百分比（脚本算） |
| `found` | boolean | 是否有任一真实价格（商城或 AI 查到的，非经验估算） |
| `func_impact` | string | 这个元件的"功能影响"——一句简短描述（≤ 25 字） |
| `exp_impact` | string | "体验影响"——一句简短描述（≤ 25 字） |
| `user_value` | "低" / "中" / "高" | 这个元件对最终用户的价值等级 |
| `note` | string | 备注（任意长度，可能很长） |

#### B. 变体元件 variant item

例：MCU、存储、通信模组——不同版本选不同型号。

整体结构：

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | int | 自增编号 |
| `category` | string | 分类（同上） |
| `is_variant` | true | 变体元件标志 |
| `func_impact` | string | 功能影响（**整组共享**，所有版本一份） |
| `exp_impact` | string | 体验影响（整组共享） |
| `user_value` | "低" / "中" / "高" | 用户价值（整组共享） |
| `note` | string | 备注（整组共享） |
| `variants` | array | 各版本的具体型号，下表 |

每个 variant（数组里 1~3 个）：

| 字段 | 类型 | 含义 |
|---|---|---|
| `version` | string | 版本名（"经济版" / "标准版" / "高性能版"，与外层 `versions` 对应） |
| `brand` | string | 该版本选的品牌 |
| `package` | string | 该版本封装 |
| `part_number` | string | 该版本具体型号 |
| `description` | string | 该版本关键参数 |
| `price_mall`, `mall_source`, `mall_url`, `price_ai`, `ai_source`, `price_unit`, `cost_ratio`, `found` | 同共享元件的字段 | 每个版本各自一份 |

### 4.4 数据示例

完整 schema 见 GitHub 仓库：[schema/bom-output-schema.json](https://github.com/anson592/bom-solution-assistant/blob/main/schema/bom-output-schema.json)

下面是一个**精简但真实结构**的示例（同时包含变体元件和共享元件）：

```json
{
  "project": "拍立得",
  "date": "2026-05-16",
  "query_time": "16:21",
  "quantity": "2000 套",
  "versions": ["标准版", "高性能版"],
  "selected_version": "标准版",
  "ai_suggestion": "标准版 BOM 总成本约 ¥120~145/套，高性能版约 ¥175~205/套。热敏打印模块（¥88）是最大成本项，可考虑拆分采购降本。摄像头模组建议锁定 1688 供应商长期合作价。ESP32-C3/S3 库存均紧张，需备 2~4 周安全库存。",
  "risk_tags": [
    { "tag": "热敏打印模块缺货风险", "level": "high", "desc": "国内主供应商交期 4 周以上" },
    { "tag": "ESP32-C3/S3 库存紧张", "level": "mid",  "desc": "建议提前 2 周下单" }
  ],
  "items": [
    {
      "id": 1,
      "category": "MCU",
      "is_variant": true,
      "func_impact": "主控性能",
      "exp_impact": "操作流畅",
      "user_value": "高",
      "note": "STM32 系列，国内现货充足",
      "variants": [
        {
          "version": "标准版",
          "brand": "ST",
          "package": "QFP-64",
          "part_number": "STM32F405RGT6",
          "description": "168MHz, Cortex-M4, 1MB Flash, 192KB SRAM",
          "price_mall": 16.24,
          "mall_source": "立创商城",
          "mall_url": "https://item.szlcsc.com/16424.html",
          "price_ai": 14.50,
          "ai_source": "博查",
          "price_unit": 16.24,
          "cost_ratio": 13.5,
          "found": true
        },
        {
          "version": "高性能版",
          "brand": "ST",
          "package": "QFP-100",
          "part_number": "STM32H743VIT6",
          "description": "480MHz, Cortex-M7 双核, 2MB Flash, 1MB SRAM",
          "price_mall": 52.0,
          "mall_source": "立创商城",
          "mall_url": "https://item.szlcsc.com/45123.html",
          "price_ai": 48.0,
          "ai_source": "iqs",
          "price_unit": 52.0,
          "cost_ratio": 30.2,
          "found": true
        }
      ]
    },
    {
      "id": 2,
      "category": "晶振",
      "is_variant": false,
      "brand": "NDK",
      "package": "SMD-3225",
      "part_number": "8MHz + 32.768KHz 无源晶振",
      "description": "8MHz 系统时钟 + 32.768KHz RTC时钟",
      "price_mall": null,
      "mall_source": null,
      "mall_url": null,
      "price_ai": 1.0,
      "ai_source": "经验预估",
      "price_unit": 1.0,
      "cost_ratio": 0.9,
      "found": true,
      "func_impact": "时钟基准",
      "exp_impact": "稳定性保证",
      "user_value": "中",
      "note": "通用料，价格极低，散装件 brand 用 NDK / EPSON / KDS 都行"
    }
  ]
}
```

---

## 5. 数据特征（设计时要考虑的真实分布）

基于实际项目跑出来的统计：

- **元件数量**：典型 BOM 15~25 个元件，少数项目 30+
- **变体元件比例**：约 20%~40%（如 MCU、存储、通信模组、显示模组、电池）；其余是共享元件
- **变体版本数**：每个变体通常 2~3 个，不会更多
- **价格量级跨度大**：最低 0.01 元（电阻），最高不设限——可能是几百元的高端 SoC、模组、屏幕模组，也可能是上千元的工业级传感器
- **元件间成本占比悬殊**：常见 1~2 个元件吃掉 50%+ 成本，大量小元件占比 < 1%
- **price_mall 缺失率**：约 30~50%（商城找不到该型号或已停产）；price_ai 强制有值
- **note 字段长度差异极大**：可能空字符串，也可能 100+ 字
- **risk_tags 数量**：0~5 个常见
- **func_impact / exp_impact**：很短，≤ 10 字
- **description**：通常 20~80 字，含数字和单位

---

## 6. 必须保留的功能能力

设计可以重构信息架构和视觉，但下面这些**功能能力**必须存在：

1. **多版本切换**：用户能切换查看不同版本，对应的占比和成本分布要跟着变
2. **商城链接可点击**：mall_url 不为空时，能点击跳转到供应商页面
3. **价格三种来源的可区分性**：用户能识别哪些是真实商城价、哪些是 AI 查到的或者经验估算作为AI价
4. **导出 Excel**：当前用 SheetJS 实现，导出整张 BOM 表
5. **打印 PDF**：浏览器 `window.print()` 触发，要打印友好（A4 / A3 都能合理分页）
6. **移动端可看**：不要求单独设计，但桌面布局在移动端不能完全坏掉

---

## 7. 不在本次设计范围内

- 数据 schema 不能改（和上游 AI 流程约定好的）
- 不需要做 dark mode（用户主要在打印场景下用）

---

## 8. 交付物

设计稿，重点说明：

- 信息架构（哪些区块、各占多少视觉权重）
- 多版本对比的呈现方式
- 变体元件（同一行多个版本）的呈现方式
- 三种价格来源的视觉区分方式
- 风险提示、AI 建议的呈现位置和形式
- 表格列的取舍 / 排序 / 折叠（14 个字段全展示？分主次？折叠次要列？）
- 打印模式下的差异

代码实现交给开发，不需要设计师写代码。

---

## 9. 参考素材

GitHub 仓库：https://github.com/anson592/bom-solution-assistant

- 当前 HTML 模板（视觉旧，可作为反例）：[report-template.html](https://github.com/anson592/bom-solution-assistant/blob/main/report-template.html)
- 数据 schema 完整定义：[schema/bom-output-schema.json](https://github.com/anson592/bom-solution-assistant/blob/main/schema/bom-output-schema.json)
- 示例数据：[schema/bom-input-example.json](https://github.com/anson592/bom-solution-assistant/blob/main/schema/bom-input-example.json)

