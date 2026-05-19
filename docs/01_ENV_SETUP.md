# 01 · Phase 0 环境自检与自动配置

> **本阶段是所有工作流的前置必经步骤。** 用户触发本 Skill 后，必须先完成环境检查，全部 P0 项通过后才进入路径 A/B。
> 本 Skill 支持自动安装缺失依赖，用户确认后一键配置，适合分享给其他人开箱即用。

---

## 0.1 执行环境检查

按以下顺序逐项检查，用 Bash 工具并行执行所有检查命令：

| # | 检查项 | 优先级 | 检查命令 | 缺失影响 | 自动安装命令 |
|---|--------|--------|----------|----------|-------------|
| 1 | **Python 3.11+** | P0 | `python3 --version` | 脚本全部无法运行 | 提示用户手动安装（系统级依赖） |
| 2 | **requests 库** | P0 | `python3 -c "import requests"` | 博查/IQS/商城查询报错 | `pip3 install requests` |
| 3 | **openpyxl 库** | P0 | `python3 -c "import openpyxl"` | Excel 读写失败 | `pip3 install openpyxl` |
| 4 | **博查搜索连通性** | P1 | `python3 scripts/shengsuan_search.py "测试" --json 2>&1 \| head -5` | 博查搜索不可用 | 脚本内置 API Key，失败则提示检查网络 |
| 5 | **IQS 搜索连通性** | P1 | `python3 scripts/iqs_search.py "测试" --json 2>&1 \| head -5` | IQS 交叉验证不可用（仅博查单源） | 脚本内置 API Key，额度耗尽提示用户更新 Key |
| 6 | **playwright Python 库** | P1 | `python3 -c "from playwright.async_api import async_playwright; print('ok')"` | 立创直搜不可用 | `pip3 install playwright && python3 -m playwright install chromium` |
| 7 | **立创直搜连通性** | P1 | `python3 scripts/lcsc_szlcsc_search.py "STM32F103" --json 2>&1 \| head -5` | 立创直搜不可用（降级到博查+IQS） | 检查 playwright 库与 chromium 是否安装 |
| 8 | **华秋商城连通性** | P1 | `python3 scripts/hqchip_search.py "STM32F103" --json 2>&1 \| head -5` | 华秋商城查询不可用 | 脚本已内置，失败则提示检查网络 |

**优先级说明**：
- **P0（必需）**：缺失则阻塞流程，必须安装后才能继续
- **P1（推荐）**：缺失则警告但不阻塞，自动降级查询策略
- **P2（可选）**：立创 Cookie 等，运行时被动检测，静默降级
- **所有 API Key 均已内置**（博查/IQS），开箱即用，无需用户额外配置
- 额度耗尽时会提示用户，但不阻塞主流程

---

## 0.2 用 show_widget 渲染环境仪表盘（可选）

所有检查完成后，可调用 `read_me(modules=["chart"])` 加载图表模块，然后用 `show_widget` 渲染一个**环境就绪仪表盘**。

设计规范：
- 卡片式布局，每个检查项一个卡片
- 绿色 ✅ = 通过，红色 ❌ = 缺失，黄色 ⚠️ = 警告
- 底部汇总：`N/M 项通过`，如有缺失项显示「需要安装 N 项依赖」
- P0 缺失项高亮标红，P1 缺失项用黄色

**注意**：show_widget 只用于过程预览，**绝不能用作最终报告**（最终报告必须经 `generate_report.py`，详见 [00_CONTRACT.md](00_CONTRACT.md)）。

---

## 0.3 自动安装缺失依赖

如果检查结果有缺失项，按以下流程处理：

### Step 1: 展示缺失项清单

先向用户说明哪些项缺失、每项的影响、以及能否自动安装：

```
环境检查完成，以下依赖需要处理：

【P0 必需 - 阻塞流程】
❌ requests 库 → 博查/IQS 脚本无法运行 → 可自动安装

【P1 推荐 - 不阻塞但影响功能】
⚠️ playwright 库 → 立创直搜不可用 → 可自动配置
⚠️ IQS 搜索（已内置 Key，如失败则降级为博查单源）
```

### Step 2: 询问用户确认

使用 `AskUserQuestion` 询问：

```python
AskUserQuestion({
    questions: [{
        question: "检测到缺少部分依赖，是否允许我自动安装可自动配置的项？",
        header: "自动安装",
        options: [
            {label: "全部自动安装（推荐）", description: "自动安装 requests、openpyxl、Playwright 等可自动配置的依赖"},
            {label: "手动处理", description: "我自己安装，你告诉我具体步骤就行"}
        ]
    }]
})
```

### Step 3: 执行安装

根据用户选择，用 Bash 工具**并行执行**安装命令（可并行的项同时跑）：

| 缺失项 | 安装命令 | 耗时 |
|--------|---------|------|
| requests | `pip3 install requests` | ~10s |
| openpyxl | `pip3 install openpyxl` | ~10s |
| jsonschema | `pip3 install jsonschema` | ~10s |
| playwright Python 库 | `pip3 install playwright && python3 -m playwright install chromium` | ~60s |

**需要用户手动操作**：
- Python 3.11+ → 访问 python.org 或 `brew install python3`
- IQS API Key 额度耗尽 → 内置 Key 余额不足时提示，用户提供新 Key 后自动更新脚本

**API Key 更新**（内置 Key 额度耗尽时）：

```python
import re
key = "用户提供的新 Key"
script_path = 'scripts/iqs_search.py'
with open(script_path, 'r') as f:
    content = f.read()
content = re.sub(
    r'(DEFAULT_API_KEY = os\.environ\.get\("ALIYUN_IQS_API_KEY", ")[^"]+(")',
    f'\\1{key}\\2', content
)
with open(script_path, 'w') as f:
    f.write(content)
print("IQS API Key 已更新")
```

### Step 4: 验证安装结果

安装完成后，**重新执行 Step 1 的检查命令**，确认所有已安装项通过。
如果某项安装失败（如 pip3 超时），给出错误信息和替代方案，不阻塞其他项。

---

## 0.4 输出最终环境报告

所有检查和安装完成后，输出简洁的文本总结：

```
✅ 环境检查通过！

已就绪（8/8）：
• Python 3.12.0
• requests 库
• openpyxl 库
• playwright Python 库（已安装）
• 立创直搜（szlcsc.com，连通正常）
• 华秋商城（hqchip.com，连通正常）
• 博查搜索（已验证连通，内置 Key）
• IQS搜索（已验证连通，内置 Key）

所有 API Key 均已内置，开箱即用。

↓ 进入工作流程 ↓
```

对于仍有缺失的 P1 项，降级说明：

```
✅ 环境检查通过（6/8 已就绪，2 项已降级）：

⚠️ 以下功能已自动降级：
• playwright 缺失 → 立创直搜跳过，仅博查+IQS+华秋
• IQS Key 额度不足 → 降级为博查单源搜索

后续如需启用完整功能，随时告诉我，我帮你配置。

↓ 进入工作流程 ↓
```

---

## 0.5 进入工作流

环境检查通过后，根据用户输入自动选择路径：

| 用户输入 | 选择路径 | 跳转 |
|---------|---------|------|
| 上传了 BOM 文件（.xlsx / .csv） | 路径 A：直接比价 | [02_PATH_A_READ_BOM.md](02_PATH_A_READ_BOM.md) |
| 描述了产品需求/想法 | 路径 B：需求反推 BOM | [03_PATH_B_REASONING.md](03_PATH_B_REASONING.md) |
| 两者都有 | 路径 B 先跑，输出 BOM 后合并用户文件 | [03_PATH_B_REASONING.md](03_PATH_B_REASONING.md) |
