#!/usr/bin/env python3
"""
本地测试脚本 — 推送前运行
用法: python3 test_report.py
通过: 打印 PASS 并以 0 退出
失败: 打印具体原因并以 1 退出
"""
import gzip, base64, json, re, subprocess, sys, tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
GENERATOR  = SCRIPT_DIR / "generate_report.py"
JSON_INPUT = SCRIPT_DIR / "data" / "4G定位手表_20260517.json"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

errors = []

def check(name, cond, detail=""):
    if cond:
        print(f"  {PASS}  {name}")
    else:
        msg = f"{name}" + (f": {detail}" if detail else "")
        print(f"  {FAIL}  {msg}")
        errors.append(msg)

# ── Step 1: 运行生成器 ────────────────────────────────────────────────────────
print("\n[Step 1] 运行 generate_report.py ...")
result = subprocess.run(
    [sys.executable, str(GENERATOR), str(JSON_INPUT)],
    capture_output=True, text=True, cwd=SCRIPT_DIR
)
check("退出码为 0", result.returncode == 0,
      f"exit={result.returncode}\n{result.stderr[:400]}")
check("stderr 无致命错误",
      "错误:" not in result.stderr and "Traceback" not in result.stderr,
      result.stderr[:400] if result.stderr else "")
if result.stderr.strip():
    print(f"    (stderr 警告: {result.stderr.strip()[:200]})")

# 找到生成的 HTML 文件
stdout_match = re.search(r'报告已生成:\s*(.+\.html)', result.stdout)
if stdout_match:
    report_path = SCRIPT_DIR / stdout_match.group(1).strip()
else:
    # 按项目名推断
    data = json.loads(JSON_INPUT.read_text(encoding="utf-8"))
    project = data.get("project", "report")
    import datetime
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    report_path = SCRIPT_DIR / "data" / f"{project}_{date_str}_report.html"

# ── Step 2: 验证 HTML 结构 ────────────────────────────────────────────────────
print("\n[Step 2] 验证 HTML 结构 ...")
check("报告文件存在", report_path.exists(), str(report_path))

if report_path.exists():
    html = report_path.read_text(encoding="utf-8")
    check("文件大小 > 1MB", len(html) > 1_000_000, f"{len(html):,} chars")
    check("manifest 标记存在", '<script type="__bundler/manifest">' in html)

    # 解析 manifest
    manifest = None
    manifest_start = html.find('<script type="__bundler/manifest">')
    if manifest_start >= 0:
        cs = manifest_start + len('<script type="__bundler/manifest">')
        while html[cs] in ' \t\n\r': cs += 1
        depth = 0; in_str = False; i = cs
        while i < len(html):
            ch = html[i]
            if in_str:
                if ch == '\\': i += 2; continue
                if ch == '"': in_str = False
            else:
                if ch == '"': in_str = True
                elif ch in ('{', '['): depth += 1
                elif ch in ('}', ']'):
                    depth -= 1
                    if depth == 0: break
            i += 1
        try:
            manifest = json.loads(html[cs:i+1])
            check("manifest JSON 可解析", True)
        except Exception as e:
            check("manifest JSON 可解析", False, str(e))

    # 找数据 entry
    data_src = None
    if manifest:
        for uuid, entry in manifest.items():
            if not isinstance(entry, dict) or 'data' not in entry: continue
            try:
                raw = base64.b64decode(entry['data'])
                src = gzip.decompress(raw).decode() if entry.get('compressed') else raw.decode()
                if 'window.BOM_DATA' in src and 'BOM_HELPERS' in src:
                    data_src = src
                    break
            except Exception:
                pass
        check("数据 entry 可解压", data_src is not None)

    # ── Step 3: 验证 BOM_DATA 内容 ───────────────────────────────────────────
    print("\n[Step 3] 验证注入的 BOM_DATA ...")
    bom_data = None
    if data_src:
        m = re.search(r'window\.BOM_DATA\s*=\s*', data_src)
        if m:
            obj_start = m.end()
            depth = 0; in_str = False; sc = None; esc = False; i = obj_start
            while i < len(data_src):
                c = data_src[i]
                if esc: esc = False
                elif c == '\\': esc = True
                elif in_str:
                    if c == sc: in_str = False
                elif c in ('"', "'", '`'): in_str = True; sc = c
                elif c == '{': depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0: break
                i += 1
            try:
                bom_data = json.loads(data_src[obj_start:i+1])
                check("BOM_DATA 可解析为 JSON", True)
            except Exception as e:
                check("BOM_DATA 可解析为 JSON", False, str(e))

    if bom_data:
        versions = bom_data.get("versions", [])
        items    = bom_data.get("items", [])
        check("versions 非空", len(versions) > 0, str(versions))
        check("items 非空",    len(items) > 0,    f"{len(items)} items")

        # price_unit 全为数字
        bad_price = []
        for item in items:
            if item.get("is_variant"):
                for v in item.get("variants") or []:
                    pu = v.get("price_unit")
                    if not isinstance(pu, (int, float)):
                        bad_price.append(f"id={item['id']} {v.get('version')} price_unit={pu!r}")
            else:
                pu = item.get("price_unit")
                if not isinstance(pu, (int, float)):
                    bad_price.append(f"id={item['id']} price_unit={pu!r}")
        check("所有 price_unit 是数字", len(bad_price) == 0,
              "; ".join(bad_price[:5]))

        # cost_ratio 已计算
        bad_ratio = []
        for item in items:
            if item.get("is_variant"):
                for v in item.get("variants") or []:
                    cr = v.get("cost_ratio")
                    if not isinstance(cr, (int, float)):
                        bad_ratio.append(f"id={item['id']} {v.get('version')} cost_ratio={cr!r}")
            else:
                cr = item.get("cost_ratio")
                if not isinstance(cr, (int, float)):
                    bad_ratio.append(f"id={item['id']} cost_ratio={cr!r}")
        check("所有 cost_ratio 已计算", len(bad_ratio) == 0,
              "; ".join(bad_ratio[:5]))

    # ── Step 4: JS 语法检查（需要 node）────────────────────────────────────────
    print("\n[Step 4] JS 语法检查 ...")
    node_ok = subprocess.run(["which", "node"], capture_output=True).returncode == 0
    if not node_ok:
        print(f"  (跳过: node 不可用)")
    elif data_src:
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write(data_src)
            tmp = f.name
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        check("数据脚本 JS 语法正确", r.returncode == 0,
              r.stderr[:200] if r.stderr else "")
        Path(tmp).unlink(missing_ok=True)

# ── 结果汇总 ──────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"{'='*50}")
    print(f"结果: {FAIL}  ({len(errors)} 项失败)")
    for e in errors:
        print(f"  • {e}")
    sys.exit(1)
else:
    print(f"{'='*50}")
    print(f"结果: {PASS}  所有检查通过")
    sys.exit(0)
