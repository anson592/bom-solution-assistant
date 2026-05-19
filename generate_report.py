#!/usr/bin/env python3
"""
BOM 报告生成器 —— 将 JSON 数据注入模板，生成独立可分享的 HTML 报告。

用法:
  python3 generate_report.py <data.json> [output.html]
  python3 generate_report.py data/智能台灯_20260512.json

默认输出到同目录下: <项目名>_<日期>_report.html

normalize_data 阶段做四件事：
  1. 字段兼容层：旧字段名 (price_market/price_ecommerce/...) 自动迁移到新字段名
  2. 自动计算 price_unit（小计 = price_mall 优先；mall 空则取 price_ai）
  3. 自动计算 cost_ratio（每颗占单套总成本百分比，按 selected_version）
  4. 轻量校验，违规打 stderr 警告但不阻塞
"""

import json
import sys
import os
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
TEMPLATE_PATH = SCRIPT_DIR / "report-template.html"
INJECTION_MARKER = "// __BOM_DATA_INJECTION_POINT__"

FIELD_ALIASES = {
    "price_market": "price_mall",
    "market_source": "mall_source",
    "market_url": "mall_url",
    "price_ecommerce": "price_ai",
    "ecommerce_source": "ai_source",
    "price_estimated": "price_unit",
    "price_estimated_experience": "price_unit",
    "source": "mall_source",
    "source_url": "mall_url",
}

# mall_source 填了 AI 来源时，视为商城未查到，清空商城字段
_AI_SOURCES = {"博查", "博查搜索", "博查+IQS", "iqs", "IQS搜索", "经验预估"}

# 一次性费用类别，不参与单套成本计算
_ONE_TIME_CATEGORIES = {"认证费", "NRE", "开模费", "工装费", "模具费", "认证", "合规认证"}


def _apply_aliases(node: dict) -> None:
    for old, new in FIELD_ALIASES.items():
        if old in node:
            if new not in node or node.get(new) in (None, ""):
                node[new] = node.pop(old)
            else:
                del node[old]


def _sanitize_mall_fields(node: dict) -> None:
    """清洗商城字段：
    1. mall_source 是 AI 来源时，清空商城三字段
    2. price_mall=0 且 mall_url='' 时，视为占位行，清零为 null（避免渲染空链接）
    """
    src = node.get("mall_source") or ""
    if src in _AI_SOURCES:
        print(
            f"⚠️  mall_source='{src}' 是 AI 来源，清空 price_mall/mall_source/mall_url "
            f"(part_number={node.get('part_number','?')})",
            file=sys.stderr,
        )
        node["price_mall"] = None
        node["mall_source"] = ""
        node["mall_url"] = ""
    elif node.get("price_mall") == 0 and not node.get("mall_url"):
        # price_mall=0 + 无链接 = AI 把占位行误填为 0，应为 null
        node["price_mall"] = None


def _compute_price_unit(node: dict) -> None:
    """计算 price_unit（小计）：mall 优先，mall 空则取 ai；PCB 特殊处理"""
    mall = node.get("price_mall")
    ai = node.get("price_ai")
    existing = node.get("price_unit")
    category = node.get("category", "")

    # PCB 特殊处理：如果 mall 和 ai 都为 null，用公式计算
    if category == "PCB" and mall is None and ai is None:
        computed = _compute_pcb_price(node)
        if computed is not None:
            node["price_unit"] = computed
            node["ai_source"] = f"脚本公式（{node.get('description', 'PCB')}）"
            return

    if mall is not None:
        computed = mall
    elif ai is not None:
        computed = ai
    else:
        computed = existing

    if (
        existing is not None
        and computed is not None
        and isinstance(existing, (int, float))
        and isinstance(computed, (int, float))
        and abs(existing - computed) > 0.001
    ):
        print(
            f"⚠️  price_unit 覆盖：原 {existing} → 重算 {computed} "
            f"(part_number={node.get('part_number','?')})",
            file=sys.stderr,
        )
    # 确保 price_unit 始终是数字，null 会导致前端 .toFixed() 崩溃
    if computed is None:
        print(
            f"⚠️  price_unit 无法计算（mall/ai/existing 均为 null），设为 0 "
            f"(part_number={node.get('part_number','?')})",
            file=sys.stderr,
        )
        computed = 0
    node["price_unit"] = computed


def _compute_pcb_price(node: dict) -> float:
    """PCB 价格经验公式"""
    desc = node.get("description", "")

    # 从 description 提取层数、尺寸
    layers_match = re.search(r'(\d+)层', desc)
    size_match = re.search(r'(\d+)[×x](\d+)\s*mm', desc)

    layers = int(layers_match.group(1)) if layers_match else 4
    if size_match:
        w, h = int(size_match.group(1)), int(size_match.group(2))
        size_mm2 = w * h
    else:
        size_mm2 = 10000  # 默认 100×100mm

    # 从全局数据获取产量（这里简化为默认 2000）
    qty = 2000

    # 公式
    base_price_map = {2: 5, 4: 12, 6: 22, 8: 35}
    base = base_price_map.get(layers, 12)
    size_factor = max(1.0, size_mm2 / 10000)

    qty_discount_map = {100: 1.5, 500: 1.2, 1000: 1.05, 2000: 1.0, 5000: 0.9, 10000: 0.85}
    qty_key = min(qty_discount_map.keys(), key=lambda k: abs(k - qty))
    qty_discount = qty_discount_map[qty_key]

    return round(base * size_factor * qty_discount, 2)


def _validate_node(node: dict, ctx: str) -> None:
    if (
        node.get("found") is True
        and node.get("price_mall") is None
        and node.get("price_ai") is None
    ):
        print(
            f"⚠️  {ctx}: found=true 但 price_mall 和 price_ai 都为 null",
            file=sys.stderr,
        )


def normalize_data(data: dict) -> dict:
    versions = data.get("versions") or []
    selected = data.get("selected_version") or (versions[0] if versions else None)

    for item in data.get("items") or []:
        _apply_aliases(item)
        if item.get("is_variant"):
            variants = item.get("variants")
            if not isinstance(variants, list):
                raise TypeError(
                    f"item id={item.get('id')} is_variant=true，"
                    f"但 variants 是 {type(variants).__name__}，应为 list。"
                    f"常见错误：把 variants 写成对象 {{\"经济版\": ...}}，应写成数组 [...]"
                )
            for v in item.get("variants") or []:
                _apply_aliases(v)
                _sanitize_mall_fields(v)
                _compute_price_unit(v)
                _validate_node(
                    v, f"{item.get('category','?')}/{v.get('version','?')}"
                )
                if versions and v.get("version") not in versions:
                    print(
                        f"⚠️  version '{v.get('version')}' 不在 versions {versions} "
                        f"(item id={item.get('id')})",
                        file=sys.stderr,
                    )
            if not (item.get("variants") or []):
                print(
                    f"⚠️  item id={item.get('id')} is_variant=true 但 variants 为空",
                    file=sys.stderr,
                )
        else:
            _sanitize_mall_fields(item)
            _compute_price_unit(item)
            _validate_node(
                item, f"{item.get('category','?')}/{item.get('part_number','?')}"
            )
        # 一次性费用警告
        if item.get("category") in _ONE_TIME_CATEGORIES:
            print(
                f"⚠️  category='{item.get('category')}' 是一次性费用，不计入单套成本 "
                f"(id={item.get('id')}, part_number={item.get('part_number','?')})",
                file=sys.stderr,
            )

    total = 0.0
    for item in data.get("items") or []:
        if item.get("category") in _ONE_TIME_CATEGORIES:
            continue
        if item.get("is_variant"):
            v = next(
                (
                    x
                    for x in (item.get("variants") or [])
                    if x.get("version") == selected
                ),
                None,
            )
            if v and isinstance(v.get("price_unit"), (int, float)):
                total += v["price_unit"]
        else:
            if isinstance(item.get("price_unit"), (int, float)):
                total += item["price_unit"]

    if total > 0:
        for item in data.get("items") or []:
            if item.get("category") in _ONE_TIME_CATEGORIES:
                # 一次性费用：清除旧 cost_ratio，不参与成本占比
                if item.get("is_variant"):
                    for v in item.get("variants") or []:
                        v.pop("cost_ratio", None)
                else:
                    item.pop("cost_ratio", None)
                continue
            if item.get("is_variant"):
                for v in item.get("variants") or []:
                    if isinstance(v.get("price_unit"), (int, float)):
                        v["cost_ratio"] = round(v["price_unit"] / total * 100, 1)
            else:
                if isinstance(item.get("price_unit"), (int, float)):
                    item["cost_ratio"] = round(item["price_unit"] / total * 100, 1)

    return data


def load_template() -> str:
    """读取模板 HTML"""
    if not TEMPLATE_PATH.exists():
        print(f"错误: 模板文件不存在: {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def load_data(json_path: str) -> dict:
    """读取 JSON 数据"""
    path = Path(json_path)
    if not path.exists():
        # 尝试相对于脚本目录
        path = SCRIPT_DIR / json_path
    if not path.exists():
        print(f"错误: 数据文件不存在: {json_path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def validate_schema(data: dict) -> None:
    """JSON Schema 强校验：在 normalize 之前 fail-fast，避免错误结构生成损坏的 HTML。

    退出码 2 专门用于 schema 校验失败（区别于退出码 1 的文件/模板错误）。
    """
    try:
        import jsonschema
    except ImportError:
        print("⚠️  jsonschema 未安装，跳过 schema 校验（pip3 install jsonschema 可启用）", file=sys.stderr)
        return

    schema_path = SCRIPT_DIR / "schema" / "bom-output-schema.json"
    if not schema_path.exists():
        print(f"⚠️  schema 文件不存在: {schema_path}，跳过校验", file=sys.stderr)
        return

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(data))
    if not errors:
        return

    print("❌ JSON Schema 校验失败，已阻止生成报告：", file=sys.stderr)
    print(f"   共 {len(errors)} 处错误，展示前 5 处：\n", file=sys.stderr)
    for e in errors[:5]:
        path = "/".join(str(p) for p in e.absolute_path) or "(root)"
        print(f"   位置: {path}", file=sys.stderr)
        print(f"   原因: {e.message[:200]}", file=sys.stderr)
        print(f"", file=sys.stderr)
    print("修复指引：参考 schema/bom-input-example.json 的字段结构", file=sys.stderr)
    print("特别注意：variants 必须是 JSON 数组 [...]，不能写成对象 {\"经济版\": ...}", file=sys.stderr)
    sys.exit(2)


def _inject_legacy(template: str, data: dict, json_path: str) -> str:
    """旧模板：替换 // __BOM_DATA_INJECTION_POINT__ 所在 <script> 块"""
    marker_pos = template.find(INJECTION_MARKER)
    script_start = template.rfind("<script>", 0, marker_pos)
    if script_start == -1:
        script_start = template.rfind("<script ", 0, marker_pos)
    script_end = template.find("</script>", marker_pos)
    if script_end == -1:
        print("错误: 未找到脚本结束标记", file=sys.stderr)
        sys.exit(1)
    script_end += len("</script>")

    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    new_script = f"""<!-- ── Data (injected by generate_report.py) ─────────────── -->
<script>
// __BOM_DATA_INJECTION_POINT__
// 此数据由 generate_report.py 自动注入，源文件: {Path(json_path).name}
window.BOM_DATA = {data_json};
</script>"""
    result = template[:script_start] + new_script + template[script_end:]
    trigger_script = """<script>
// 在所有脚本加载完毕后触发渲染
window.dispatchEvent(new Event('bom-data-ready'));
</script>"""
    return result.replace("</body>", trigger_script + "\n</body>")


def _inject_bundler(template: str, data: dict, json_path: str) -> str:
    """新模板（Claude Design bundler）：替换 manifest 里数据脚本 entry 的 base64 内容。

    bundler 模板通过 4 个 <script src="UUID"> 加载脚本，其中一个是数据文件，
    源码形如 `window.BOM_DATA = {...}; window.BOM_HELPERS = (...)()`。
    我们解压源码，用正则替换 BOM_DATA 的对象字面量为新数据，重新 gzip+base64 写回。
    """
    import base64
    import gzip

    # 找到 manifest 行 —— 模板里只有一个 type="__bundler/manifest" script
    manifest_marker = '<script type="__bundler/manifest">'
    manifest_start = template.find(manifest_marker)
    if manifest_start == -1:
        print("错误: 未找到 __bundler/manifest 标记", file=sys.stderr)
        sys.exit(1)
    json_start = template.find("\n", manifest_start) + 1
    json_end = template.find("\n  </script>", json_start)
    if json_end == -1:
        print("错误: __bundler/manifest 未正确闭合", file=sys.stderr)
        sys.exit(1)

    manifest_json = template[json_start:json_end]
    manifest = json.loads(manifest_json)

    # 找到数据脚本 entry —— 解压后包含 `window.BOM_DATA =`
    data_uuid = None
    data_src = None
    for uuid, entry in manifest.items():
        if entry.get("mime") not in ("application/javascript", "text/javascript"):
            continue
        try:
            raw = base64.b64decode(entry["data"])
            src = (
                gzip.decompress(raw).decode("utf-8")
                if entry.get("compressed")
                else raw.decode("utf-8")
            )
        except Exception:
            continue
        if "window.BOM_DATA" in src and "BOM_HELPERS" in src:
            data_uuid = uuid
            data_src = src
            break
    if data_uuid is None:
        print("错误: bundler manifest 中未找到 BOM 数据脚本", file=sys.stderr)
        sys.exit(1)

    # 用正则把 `window.BOM_DATA = {...}` 整个替换掉
    # BOM_DATA 块结束 = 最近一个 `};\n` 后跟 `\n` 或 `// ` 注释或 `window.`/`const `
    match = re.search(r"window\.BOM_DATA\s*=\s*", data_src)
    if not match:
        print("错误: 数据脚本中未找到 window.BOM_DATA 赋值", file=sys.stderr)
        sys.exit(1)
    obj_start = match.end()
    # 平衡花括号扫描找对象结尾
    depth = 0
    i = obj_start
    in_string = False
    string_char = None
    escape_next = False
    while i < len(data_src):
        c = data_src[i]
        if escape_next:
            escape_next = False
        elif c == "\\":
            escape_next = True
        elif in_string:
            if c == string_char:
                in_string = False
        elif c in ('"', "'", "`"):
            in_string = True
            string_char = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                obj_end = i + 1
                break
        i += 1
    else:
        print("错误: 无法定位 BOM_DATA 对象字面量结尾", file=sys.stderr)
        sys.exit(1)

    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    new_src = data_src[:match.start()] + (
        f"// 此数据由 generate_report.py 注入，源文件: {Path(json_path).name}\n"
        f"window.BOM_DATA = {data_json}"
    ) + data_src[obj_end:]

    # 重新压缩 + base64
    new_bytes = new_src.encode("utf-8")
    if manifest[data_uuid].get("compressed"):
        new_bytes = gzip.compress(new_bytes, compresslevel=9)
    manifest[data_uuid]["data"] = base64.b64encode(new_bytes).decode("ascii")

    new_manifest_json = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    return template[:json_start] + new_manifest_json + template[json_end:]


def inject_data(template: str, data: dict, json_path: str = "") -> str:
    """根据模板形态自动选择注入方式。

    - 旧模板（含 // __BOM_DATA_INJECTION_POINT__ 标记）：替换标记所在 script 块
    - 新模板（Claude Design bundler）：改写 manifest 里数据脚本 entry
    """
    if '<script type="__bundler/manifest">' in template:
        return _inject_bundler(template, data, json_path)
    if INJECTION_MARKER in template:
        return _inject_legacy(template, data, json_path)
    print("错误: 模板形态无法识别（既不是旧模板也不是 bundler 模板）", file=sys.stderr)
    sys.exit(1)


def generate_output_name(data: dict, json_path: str) -> str:
    """根据项目名和日期生成输出文件名"""
    project = data.get("project", "BOM")
    date = data.get("date", "")
    # 清理文件名中的特殊字符
    safe_project = re.sub(r'[\\/:*?"<>|]', '_', project)
    if date:
        return f"{safe_project}_{date}_report.html"
    # 从 JSON 文件名提取日期
    base = Path(json_path).stem
    return f"{base}_report.html"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("可用数据文件:")
        data_dir = SCRIPT_DIR / "data"
        if data_dir.exists():
            for f in sorted(data_dir.glob("*.json")):
                print(f"  data/{f.name}")
        sys.exit(0)

    json_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    # 加载
    template = load_template()
    data = load_data(json_path)
    validate_schema(data)
    data = normalize_data(data)

    # 注入
    result = inject_data(template, data, json_path)

    # 输出
    if output_path is None:
        json_dir = Path(json_path).parent
        output_path = str(json_dir / generate_output_name(data, json_path))

    Path(output_path).write_text(result, encoding="utf-8")
    print(f"✅ 报告已生成: {output_path}")
    print(f"   项目: {data.get('project', '?')}")
    print(f"   器件: {len(data.get('items', []))} 项")
    print(f"   版本: {', '.join(data.get('versions', []))}")


if __name__ == "__main__":
    main()
