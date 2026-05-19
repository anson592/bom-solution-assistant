#!/usr/bin/env python3
"""
BOM Solution Assistant —— 输出契约硬阫校验脚本

用法:
  python3 validate_output.py [--project <项目名>]

不带参数：扫描 data/ 目录全部最近输出，全部通过才 ✅。
带 --project：只校验指定项目（按 project 字段匹配）。

校验项（任一失败退码 2）：
  1. data/ 下存在至少 1 个 JSON（LLM 已产出）
  2. data/ 下存在至少 1 个 *_report.html（generate_report.py 跑过）
  3. *_report.html 含模板指纹 `<script type="__bundler/manifest">` 或 `// __BOM_DATA_INJECTION_POINT__`
     —— 防止 LLM 手写 HTML 冒充
  4. 项目根目录无"野生" *.html（除 report-template.html）
  5. 最新 JSON 通过 schema/bom-output-schema.json 校验
  6. 最新 JSON 与 *_report.html 同源（project + date 匹配）

通过：stdout 打印 ✅ CONTRACT PASSED，退码 0
失败：stderr 打印每条失败原因 + 修复指引，退码 2
"""

import json
import sys
import argparse
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
SCHEMA_PATH = SCRIPT_DIR / "schema" / "bom-output-schema.json"
TEMPLATE_PATH = SCRIPT_DIR / "report-template.html"

# 模板指纹：新模板（bundler）和旧模板（legacy marker）两种都接受
TEMPLATE_FINGERPRINTS = (
    '<script type="__bundler/manifest">',
    "// __BOM_DATA_INJECTION_POINT__",
)


def err(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)


def hint(msg: str) -> None:
    print(f"   → {msg}", file=sys.stderr)


def safe_project_name(project: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", project)


def check_data_dir() -> tuple[list[Path], list[Path]]:
    """返回 (json_files, html_files)，按修改时间倒序。"""
    if not DATA_DIR.exists():
        err(f"data/ 目录不存在: {DATA_DIR}")
        hint("先按 docs/00_CONTRACT.md 写一份 JSON 到 data/ 下")
        sys.exit(2)
    jsons = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    htmls = sorted(DATA_DIR.glob("*_report.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jsons, htmls


def check_no_wild_html() -> list[Path]:
    """扫项目根目录有没有 LLM 误写的 HTML（template 除外）。"""
    wild = []
    for p in SCRIPT_DIR.glob("*.html"):
        if p.name == TEMPLATE_PATH.name:
            continue
        wild.append(p)
    return wild


def check_template_fingerprint(html_path: Path) -> bool:
    """报告 HTML 必须含模板指纹，否则疑似手写。"""
    try:
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            # 只读前 200KB，模板标记一定在头部
            head = f.read(200_000)
    except Exception as e:
        err(f"无法读取 {html_path}: {e}")
        return False
    for fp in TEMPLATE_FINGERPRINTS:
        if fp in head:
            return True
    return False


def validate_schema(data: dict) -> list[str]:
    """复用 generate_report.py 的 schema 校验逻辑（懒导入 jsonschema）。"""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema 未安装（pip3 install jsonschema 启用强校验）"]
    if not SCHEMA_PATH.exists():
        return [f"schema 文件不存在: {SCHEMA_PATH}"]
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(data))
    msgs = []
    for e in errors[:5]:
        path = "/".join(str(p) for p in e.absolute_path) or "(root)"
        msgs.append(f"位置={path} | 原因={e.message[:200]}")
    if len(errors) > 5:
        msgs.append(f"...（共 {len(errors)} 处，仅显示前 5 处）")
    return msgs


def html_matches_json(json_data: dict, html_path: Path) -> bool:
    """检查 HTML 文件名是否对应 JSON 的 project/date。"""
    project = safe_project_name(json_data.get("project", ""))
    date = json_data.get("date", "")
    if not project:
        return True  # JSON 无 project，跳过此检查
    expected = f"{project}_{date}_report.html" if date else f"{project}"
    return expected in html_path.name or project in html_path.name


def main() -> int:
    parser = argparse.ArgumentParser(description="BOM 输出契约硬阫校验")
    parser.add_argument("--project", help="只校验指定项目")
    args = parser.parse_args()

    print("🔍 BOM Solution Assistant - 输出契约校验")
    print(f"   工作目录: {SCRIPT_DIR}")
    print()

    failed = False

    # ── 检查 1：野生 HTML（项目根目录）─────────────────
    wild = check_no_wild_html()
    if wild:
        failed = True
        err(f"项目根目录发现 {len(wild)} 个 \"野生\" HTML（疑似 LLM 手写报告）:")
        for p in wild:
            hint(f"删除: {p.relative_to(SCRIPT_DIR)}")
        hint("最终报告只能在 data/ 下、且必须由 generate_report.py 生成")
        hint("详见 docs/00_CONTRACT.md")
        print(file=sys.stderr)

    # ── 检查 2：data/ 下有 JSON & HTML ─────────────────
    jsons, htmls = check_data_dir()
    if not jsons:
        failed = True
        err("data/ 目录下没有 *.json 文件")
        hint("LLM 必须先产出符合 schema 的 JSON")
        hint("schema 见 schema/bom-output-schema.json，装配步骤见 docs/05_ASSEMBLE_AND_RENDER.md")
        print(file=sys.stderr)
        return 2  # 没 JSON 没法继续后续检查

    if not htmls:
        failed = True
        err("data/ 目录下没有 *_report.html")
        hint(f"跑: python3 generate_report.py {jsons[0].relative_to(SCRIPT_DIR)}")
        print(file=sys.stderr)

    # ── 检查 3：选定校验目标 ───────────────────────────
    target_json = jsons[0]
    target_html = htmls[0] if htmls else None
    if args.project:
        matched = [j for j in jsons if args.project in j.stem]
        if not matched:
            err(f"未找到匹配项目 '{args.project}' 的 JSON")
            return 2
        target_json = matched[0]
        if htmls:
            matched_h = [h for h in htmls if args.project in h.stem]
            target_html = matched_h[0] if matched_h else htmls[0]

    print(f"📄 校验 JSON: {target_json.relative_to(SCRIPT_DIR)}")
    if target_html:
        print(f"📄 校验 HTML: {target_html.relative_to(SCRIPT_DIR)}")
    print()

    # ── 检查 4：JSON 加载 + schema 校验 ────────────────
    try:
        with open(target_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        failed = True
        err(f"JSON 解析失败: {e}")
        return 2

    schema_errors = validate_schema(data)
    if schema_errors:
        failed = True
        err(f"JSON Schema 校验失败（{len(schema_errors)} 处错误）:")
        for m in schema_errors:
            hint(m)
        hint("修复指引: docs/06_JSON_SCHEMA_GUIDE.md + schema/bom-input-example.json")
        print(file=sys.stderr)

    # ── 检查 5：HTML 模板指纹 ──────────────────────────
    if target_html:
        if not check_template_fingerprint(target_html):
            failed = True
            err(f"HTML 不含模板指纹: {target_html.name}")
            hint("可能是手写 HTML 冒充。删除后跑: python3 generate_report.py <json>")
            hint(f"指纹应包含: {TEMPLATE_FINGERPRINTS[0]!r} 或 {TEMPLATE_FINGERPRINTS[1]!r}")
            print(file=sys.stderr)

        # ── 检查 6：JSON 与 HTML 同源 ────────────────────
        if not html_matches_json(data, target_html):
            failed = True
            err(f"HTML 与 JSON 不同源: JSON.project='{data.get('project')}' 对不上 HTML='{target_html.name}'")
            hint(f"重新跑: python3 generate_report.py {target_json.relative_to(SCRIPT_DIR)}")
            print(file=sys.stderr)

    # ── 结果 ───────────────────────────────────────────
    if failed:
        print("\n❌ CONTRACT VIOLATED — 请按上方提示修复后重跑", file=sys.stderr)
        return 2
    print("✅ CONTRACT PASSED")
    print(f"   项目: {data.get('project', '?')}")
    print(f"   日期: {data.get('date', '?')}")
    print(f"   器件: {len(data.get('items', []))} 项")
    print(f"   版本: {', '.join(data.get('versions', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
