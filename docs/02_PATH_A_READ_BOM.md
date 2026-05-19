# 02 · 路径 A：读取现有 BOM 表

> 用户已有 BOM 表（Excel / CSV），跳过反推直接进入比价。

**前置**：[01_ENV_SETUP.md](01_ENV_SETUP.md) 环境检查通过。

---

## 1. 接受用户上传的文件

支持：
- Excel 文件（`.xlsx`）
- CSV 文件（`.csv`）

## 2. 必须包含的列

- `型号`（必须）
- 其他可选列：`封装`、`数量`、`品牌`、`分类`

## 3. 使用 Python + openpyxl 读取文件

```python
import openpyxl

wb = openpyxl.load_workbook('BOM.xlsx')
ws = wb.active

for row in ws.iter_rows(min_row=2, values_only=True):
    model = row[0]      # 型号
    package = row[1]    # 封装（可选）
    quantity = row[2]   # 数量（可选）
    brand = row[3]      # 品牌（可选）
```

如果只有 CSV：

```python
import csv

with open('BOM.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        model = row['型号']
```

## 4. 文件格式示例

```csv
型号,封装,数量,品牌
STM32F103C8T6,LQFP-48,2000,ST
WS2812B,LED-5050,2000,Worldsemi
SIM7600CE-CNSE-PCIE,PCIE,100,SimCom
```

---

## 5. 下一步

路径 A 完成后，直接进入：
- **逐元件查价** → [04_SCRIPTS_API.md](04_SCRIPTS_API.md)
- **装配 JSON + 渲染报告** → [05_ASSEMBLE_AND_RENDER.md](05_ASSEMBLE_AND_RENDER.md)

> ⛔ 输出契约见 [00_CONTRACT.md](00_CONTRACT.md)：最终交付物必须经 `generate_report.py` 生成，不允许手写 HTML。
