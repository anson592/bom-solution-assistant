# BOM Solution Assistant

> WorkBuddy Skill · 智能 BOM 解决方案助手

从产品需求反推 BOM 清单（支持经济版/标准版/高性能版多版本对比），或直接读取 BOM 表，跨多个平台查询最低价，生成带来源链接的比价单。

**版本**: 1.0 | **更新**: 2026-05-18

## 功能特性

- **需求反推 BOM**：描述产品需求 → 五层推理（Layer 0 约束矩阵 → Layer 1 子系统 → Layer 2 模块槽位 → Layer 3 选型 → Layer 4 辅料补全）→ 完整元器件清单
- **版本数量用户自选**：B.1 需求确认后立刻问 1-3 个版本，按选定数量推理（不浪费 token）
- **4 大价格来源**：立创/华秋商城直搜、博查 AI 搜索、IQS 交叉验证、Playwright 实时点验
- **AI 价强制查询**：所有元器件强制走博查 + IQS 并行（不论商城价是否查到），获取电商对比维度
- **双源交叉验证**：立创 + 华秋商城并行查询
- **可视化输出**：show_widget 表格预览 + HTML 报告（generate_report.py 自动算 price_unit / cost_ratio）
- **环境自检**：Phase 0 自动检测依赖，一键安装配置

## 关键约束

- **基础参数必问**：B.1 交互时产品核心功能、供电方式、通信需求、屏幕大小、产量、成本偏好、版本数量必须确认，不允许"自行推断跳过"
- **可选外设多选**：B.1.4 提供 10 类外设多选询问（显示屏/摄像头/4G_5G/WiFi_BLE/GPS/NFC/麦克风/IMU/马达/LED），用户决定而非模型预判
- **防凑齐幻觉**：标准分类扩展为 22+ 类词典，每类标注取舍依据；用户没说且 B.1.4 没勾的分类严禁出现在 BOM
- **核心元件强制具体品牌**：MCU、传感器、电池、电源 IC、显示模组、Camera、通信模组、Flash、内存——`brand` 不允许为空 / "混用" / "通用" / "-"
- **散装件允许 brand="混用"**：阻容感、轻触开关、喇叭、连接器、PCB、外壳——但 description 必须列 ≥ 1 个候选品牌
- **存储分两行**：eMMC（`存储-Flash`）和 LPDDR（`存储-内存`）独立分行查询，不合并
- **模组类走成品**：屏幕、Camera、GPS 等模组的 part_number 写"模组型号"+ brand 写"模组厂家"，driver IC 仅写 description（不当作 part_number）
- **查价失败汇总**：系统性失败（连续 ≥3 次/失败率 >80%/完全无结果）才反馈，偶发单次失败静默降级

## 依赖

| 依赖 | 必须 | 说明 |
|------|------|------|
| Python 3.11+ | 是 | 脚本运行环境 |
| requests | 是 | `pip3 install requests` |
| openpyxl | 是 | `pip3 install openpyxl` |
| playwright | 推荐 | 立创商城直搜 |
| 博查 API Key | 推荐 | 已内置，开箱即用 |
| IQS API Key | 推荐 | 已内置，开箱即用 |

> API Key 已内置，缺失时自动降级但不阻塞流程。

## 安装到 WorkBuddy

### 方式一：直接克隆（推荐）

```bash
# 克隆到 WorkBuddy skills 目录
git clone https://github.com/anson592/bom-solution-assistant.git ~/.workbuddy/skills/bom-solution-assistant
```

### 方式二：手动下载

1. 从 GitHub 下载 ZIP 并解压
2. 将文件夹重命名为 `bom-solution-assistant`
3. 放入 `~/.workbuddy/skills/` 目录

## 项目结构

```
bom-solution-assistant/
├── SKILL.md                    # Skill 定义文件（核心）
├── README.md                   # 说明文档
├── README_WORKFLOW.md          # 工作流文档
├── report-template.html        # HTML 报告模板
├── generate_report.py           # 报告生成脚本
├── scripts/
│   ├── shengsuan_search.py     # 博查 AI 搜索
│   ├── iqs_search.py           # 阿里云 IQS 搜索
│   ├── hqchip_search.py        # 华秋商城搜索
│   ├── lcsc_szlcsc_search.py  # 立创商城搜索
│   ├── lcsc_playwright_verify.py # Playwright 实时点验
│   └── generate_bom_comparison.py # BOM 对比表格生成
├── schema/                     # JSON Schema
└── data/                       # 数据目录
```

## 使用示例

在 WorkBuddy 对话中直接说：

- 「帮我做一个智能台灯，查一下 BOM 成本」
- 「帮我查 BOM 价格」，然后上传 BOM 表
- 「STM32F103C8T6 2000套多少钱」

## 版本历史

- **1.0** (2026-05-18)
  - **首次发布**：项目重命名为 BOM Solution Assistant，版本归零到 1.0
  - 沿用 bom-price-checker v9.5.6 的全部能力：需求反推 BOM、4 大价格来源、AI 价强制查询、HTML 报告生成
  - 清理代码内版本标记，简化文档

<details>
<summary>Pre-1.0 历史（bom-price-checker v9.x 演进，仅作参考）</summary>

- **9.5.6** (2026-05-17)
  - **修复商城价列显示 AI 价根因**：SKILL.md 字段速查表（Step A）和 JSON 模板注释中，`mall_source` 明确只允许 `"立创商城"` / `"华秋商城"` / `"云汉芯城"` / `"LCSC"`，严禁填 `"博查"` / `"IQS搜索"` / `"经验预估"`；`price_mall` 商城没查到时必须填 `null`，不能把 AI 价复制过来。`generate_report.py` 加防御层：`mall_source` 是 AI 来源时自动清空商城三字段
  - **修复认证费算进单套成本根因**：SKILL.md Step A 价格字段说明处加硬约束：认证费 / NRE / 开模费 / 工装费 / 模具费等一次性费用严禁写进 `items` 数组，否则会虚高单套成本。`generate_report.py` 加防御层：`_ONE_TIME_CATEGORIES` 跳过 total 累加，清除其 `cost_ratio`
  - **修复多版本占位行 `price_mall=0` 问题**：SKILL.md 明确某版本不适用时 `price_mall` 必须填 `null` 不能填 `0`；`generate_report.py` 加防御层：`price_mall=0` 且无 `mall_url` 时自动转为 `null`
- **9.5.5** (2026-05-17)
  - **修复多版本报告白屏**：用户在 Step 5 选"两个都要"时，AI 错误地将 `selected_version` 填为 `"经济版+标准版"`（版本名拼接），导致前端 `totals[version]` 为 `undefined`，`.toFixed()` 崩溃白屏。在 SKILL.md 的 Step 5 和 Step A JSON 模板两处加入硬约束：`selected_version` 必须严格等于 `versions` 数组中的某一个字符串，多版本时取 `versions[0]`，严禁拼接
- **9.5.4** (2026-05-17)
  - **修复报告白屏崩溃**：`price_unit` 为 null 时（mall/ai/existing 均缺失）`generate_report.py` 现在强制设为 0 并打印警告，不再注入 null 到前端；React 组件里所有 `.toFixed()` 调用加 `?? 0` 防护，防止任何边界数据导致整页崩溃
- **9.5.3** (2026-05-17)
  - **悬停背景色修复（进行中）**：CSS2 的 `background-color: transparent` 被 CSS1 的 `background` shorthand 覆盖，改用 `background: transparent !important` 强制覆盖；鼠标悬停背景色问题尚未完全解决，待后续跟进
  - **rail 列分隔线修复**：`.w2-vrow-sub.is-vfirst > .w2-rail { border-bottom }` 被同块 `not(.is-vlast) > td { border-bottom: none !important }` 覆盖，加 `!important` 修复；分类/功能/体验/备注列组间分隔线现已正常显示
- **9.5.2** (2026-05-17)
  - **Treemap 回退**：将 v9.5.1 引入的 squarified treemap 算法回退到 v9.5.0 原始 flex 行打包版本（CSS1 `.ws-tm` 规则 + JS `W2Treemap` 函数均回退）
  - **悬停外框清理**：删除 v9.5.1 追加的粗糙 box-shadow 规则，只保留原有精细版（按组边界画线）
  - **悬停背景色**：将 `rgba(217, 119, 87, 0.012)` 改为 `transparent`（被 CSS1 覆盖，未生效，见 v9.5.3）
  - **rail 分隔线**：恢复 `is-vfirst > .w2-rail { border-bottom: 1px solid }` 规则（被 `!important` 覆盖，未生效，见 v9.5.3）
- **9.5.1** (2026-05-17)
  - **品牌列加宽**：colgroup 品牌列从 116px 加宽到 148px ✅
  - **悬停外框**：删除 `outline` 规则，改用 box-shadow 模拟组边界框（第一行顶边+左右、最后一行底边+左右、中间行仅左右）✅
  - **Treemap squarified 算法**：引入 squarify 函数 + 绝对定位布局（后在 v9.5.2 回退）
  - **悬停背景色**：0.025 → 0.012（后在 v9.5.2 改为 transparent）
  - **rail 分隔线**：尝试 is-vfirst border-bottom: none + is-vlast border-bottom（方向错误，在 v9.5.2 回退）
- **9.5.0** (2026-05-17)
  - **报告模板换代**：用 Claude Design 输出的 React 单文件 bundler 模板替换原 vanilla JS 模板。新模板内嵌 React 18 + Babel 标准版 + IBM Plex Mono 字体，整体 7.8MB（多数为字体），打开即用，无需联网
  - **数据接口保持不变**：`window.BOM_DATA` 形态完全沿用，`generate_report.py` 自动识别旧/新模板，分别注入数据。新模板额外提供 `window.BOM_HELPERS`（`fmt` / `fmtBig` / `priceFor` / `totalFor` / `ratiosFor` / `sourceKind`）作为前端组件公共工具
  - **旧模板备份**：`report-template.v9.4.1.bak.html`
- **9.4.0** (2026-05-16)
  - **立创商城详情页 URL 修复**：scripts/lcsc_szlcsc_search.py 用 productId 拼 `item.szlcsc.com/{id}.html`（v9.3 用 `www.szlcsc.com/search?q=` 是 API 端点，浏览器访问报 500）
  - **AI 价强制查询根除歧义**：v9.3 流程图把 Step 1 / Step 3 都写成"博查+IQS"，决策树 5 处"跳过 Step 1、Step 2"导致模型把强制 AI 查询一起跳过——v9.4 把 Step 1/Step 3 合并为统一 Step 1（强制执行），所有商城价查到的元件**仍然必须**走博查+IQS
  - **存储行强制两行**：Flash + 内存即便 MCU 内置也要写占位行（part_number="MCU 内置"，price_unit=0，note 说明），不允许省略
  - **可选分类占位规则**：B.1.4 勾选了但实际不需要的分类，写占位行不省略；用户没勾的分类严禁出现（v9.1 防幻觉约束）
  - **HTML 字段简化**：func_impact / exp_impact 改为 ≤ 10 字短语；user_value 改为"低/中/高"枚举；废弃 `_label` `_score` 后缀字段；删除进度条渲染
  - **HTML 列宽优化**：备注列加宽到 240px+ 弹性，品牌缩窄到 84px，功能/体验影响压到 96px
  - **NaN 回归修复**：v9.3 改动 3.C 漏改的 ver-tab `t.market`（已删除字段）和 tfoot 引用，统一切到 `t.estimated`
- **9.3.0** (2026-05-16)
  - **交互流程优化**：B.1 改为基础参数必问；新增 B.1.4 可选外设多选询问（10 类）；B.1.5 改为 multiSelect 支持 1-3 版本多选
  - **查价失败反馈**：新增失败汇总规则，系统性失败（连续 ≥3 次/失败率 >80%/完全无结果）才反馈，偶发单次失败静默降级
  - **分类扩展 + 防幻觉**：标准分类从 15 类扩展为 22+ 类词典（LED/4G_5G/GPS/NFC/麦克风/扬声器/IMU/马达/按键独立），每类标注取舍依据；Layer 1 新增"按需展开"硬约束，用户没说且 B.1.4 没勾的分类严禁出现
  - **HTML 报告 UI 优化**：ver-tab 卡片改为单价"小计合计"；成本分布图改用 price_unit；表格去内嵌滚动改 sticky 表头；表头重设计（14px/primary 色/渐变背景）；备注自动换行
  - **PCB 价格公式**：generate_report.py 新增 compute_pcb_price() 经验公式，PCB 类别且 mall+ai 都为 null 时自动调用
- **9.2.0** (2026-05-15)
  - 修复屏幕选型走 driver IC 而非成品模组
  - 修复核心元件品牌丢失（电池、合并存储退化为"混用"）
  - 拆分 `存储` 分类为 `存储-Flash` + `存储-内存`，BOM 必须分两行
  - 版本数量改为用户在 B.1 后自选（1-3 个），不再固定 2-3 个
  - AI 价改为强制查询（所有元器件，不论商城价是否查到）
- **9.1.0** (2026-05-15)
  - 解决 ESP32 幻觉（候选清单 ≥ 3 + 必写排除理由）
  - 字段名统一到 `price_mall` / `price_ai` / `price_unit`，generate_report.py 加字段兼容层
  - `price_unit` 和 `cost_ratio` 由生成脚本自动计算
- **9.0.1** (2026-05-14)
  - 移除 build_bom_json.py，简化管线流程

</details>

## License

MIT
