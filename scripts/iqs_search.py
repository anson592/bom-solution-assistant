#!/usr/bin/env python3
"""
阿里云 IQS 搜索脚本 - bom-solution-assistant 辅助数据源
支持两种接口：
  1. /search/unified — 纯网页搜索（快，0.8s）
  2. /ai/answer — 搜索 + AI 总结（慢，~11s，带交叉验证价格）
  3. /cross-verify — 博查 + IQS /ai/answer 双源交叉验证（并行）
API 文档：https://help.aliyun.com/zh/iqs/
"""

import os
import sys
import json
import re
import time
import argparse
import urllib.request
import urllib.error


IQS_SEARCH_URL = "https://cloud-iqs.aliyuncs.com/search/unified"
IQS_AI_ANSWER_URL = "https://cloud-iqs.aliyuncs.com/ai/answer"

# API Key 支持环境变量或命令行 --api-key 覆盖（已内置，开箱即用）
_API_KEY_INTERNAL = "4Vu7_NN7apHHgfmR3JdmVuud0_IQq9o2YTAyZDBkNQ"
DEFAULT_API_KEY = os.environ.get("ALIYUN_IQS_API_KEY", _API_KEY_INTERNAL)


# ============================================================
# 接口1: /search/unified — 纯网页搜索
# ============================================================

def iqs_search(query: str, api_key: str, engine_type: str = "LiteAdvanced",
               num_results: int = 5, main_text: bool = False) -> dict:
    """
    调用阿里云 IQS Unified Search API

    :param query: 搜索关键词
    :param api_key: 阿里云 IQS API Key
    :param engine_type: 引擎类型 LiteAdvanced / Standard / Pro
    :param num_results: 返回结果数量 (1-10)
    :param main_text: 是否返回网页正文
    :return: 原始 API 响应字典
    """
    payload = {
        "query": query,
        "engineType": engine_type,
        "contents": {
            "mainText": main_text,
            "summary": True
        },
        "advancedParams": {
            "numResults": num_results
        }
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        IQS_SEARCH_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body}"}
    except urllib.error.URLError as e:
        return {"error": f"URLError: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def format_results(response: dict, json_output: bool = False) -> str:
    """格式化 /search/unified 响应结果"""
    if "error" in response:
        if json_output:
            return json.dumps({"error": response["error"]}, ensure_ascii=False, indent=2)
        return f"查询失败：{response['error']}"

    results = response.get("pageItems") or response.get("results") or []

    if json_output:
        output = {
            "query_results": [],
            "raw_response_keys": list(response.keys())
        }
        for item in results:
            output["query_results"].append({
                "title": item.get("title", ""),
                "url": item.get("link", item.get("url", "")),
                "summary": item.get("summary", item.get("snippet", "")),
                "main_text": item.get("mainText", ""),
                "hostname": item.get("hostname", item.get("siteName", "")),
                "published_time": item.get("publishedTime", ""),
            })
        return json.dumps(output, ensure_ascii=False, indent=2)

    if not results:
        return f"未获取到结果。响应顶层字段：{list(response.keys())}"

    lines = [f"共 {len(results)} 条结果：\n"]
    for i, item in enumerate(results, 1):
        title = item.get("title", "（无标题）")
        url = item.get("link", item.get("url", ""))
        summary = item.get("summary", item.get("snippet", "（无摘要）"))
        site = item.get("hostname", item.get("siteName", ""))
        lines.append(f"[{i}] {title}")
        if site:
            lines.append(f"    来源：{site}")
        lines.append(f"    链接：{url}")
        lines.append(f"    摘要：{summary[:200]}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 接口2: /ai/answer — 搜索 + AI 总结
# ============================================================

def iqs_ai_answer(query: str, api_key: str, model: str = "lite",
                  timeout: int = 30) -> dict:
    """
    调用阿里云 IQS /ai/answer 接口（SSE 流式）

    :param query: 搜索查询
    :param api_key: 阿里云 IQS API Key
    :param model: 模型类型 lite / standard
    :param timeout: 超时秒数
    :return: 解析后的结果字典
    """
    payload = {
        "query": query,
        "useModel": model
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        IQS_AI_ANSWER_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")

        # 解析 SSE 事件
        events = []
        for block in raw.split("\n\n"):
            event_data = ""
            for line in block.split("\n"):
                if line.startswith("data: "):
                    event_data = line[6:]
            if event_data:
                try:
                    events.append(json.loads(event_data))
                except Exception:
                    events.append({"type": "unknown", "data": event_data[:200]})

        # 从事件流中提取信息
        deltas = []
        done_data = {}
        search_results = []
        rewritten_query = ""

        for ev in events:
            t = ev.get("type", "")
            d = ev.get("data", "")
            if t == "delta":
                deltas.append(d)
            elif t == "done" and isinstance(d, dict):
                done_data = d
            elif t == "search" and isinstance(d, list):
                search_results = d
            elif t == "rewrite" and isinstance(d, str):
                try:
                    rw = json.loads(d)
                    rewritten_query = rw.get("search_query", "")
                except Exception:
                    pass

        full_answer = "".join(deltas)
        answer_from_done = done_data.get("answer", "")
        sources = done_data.get("sources", [])
        metadata = done_data.get("metadata", {})

        return {
            "success": bool(full_answer or answer_from_done),
            "answer": full_answer or answer_from_done,
            "sources": sources,
            "source_count": len(sources),
            "search_results": search_results,
            "rewritten_query": rewritten_query,
            "metadata": metadata,
            "event_count": len(events),
            "delta_count": len(deltas),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# 价格提取：从 AI 回答文本中正则提取价格
# ============================================================

def extract_prices_from_answer(answer_text: str, sources: list = None) -> list:
    """
    从 IQS /ai/answer 的文本回答中提取价格信息

    :param answer_text: AI 生成的回答文本
    :param sources: 引用来源列表（可选，用于匹配来源链接）
    :return: 价格记录列表，格式与博查 parsed_prices 兼容
    """
    prices = []

    # 构建来源 hostname → url 映射（用于给价格补充链接）
    source_map = {}
    if sources:
        for s in sources:
            hostname = s.get("hostname", "")
            url = s.get("url", "")
            if hostname and url and hostname not in source_map:
                source_map[hostname] = url

    # 正则模式列表，按优先级排序
    patterns = [
        # 模式1: "约/约为/约为 ¥6.64元/片" 或 "¥6.64/片"
        r'(?:约?为?|约为|约)\s*[¥￥]\s*([\d,]+\.?\d*)\s*(?:元?/?(?:片|个|颗|只|件))',
        # 模式2: "价格约为6.64元" 或 "单价6.64元"
        r'(?:价格|单价|售价|报价|价格约?为?)\s*(?:约?为?)?\s*[¥￥]?\s*([\d,]+\.?\d*)\s*(?:元|人民币|RMB|CNY)',
        # 模式3: "US$0.9" 或 "$0.90" 或 "0.9美元"
        r'(?:US?\$|美元)\s*([\d,]+\.?\d*)',
        # 模式4: "起订量为50片时，价格约为6.64元/片（含税）" 含数量档位
        r'(\d+)\+?\s*片?\s*(?:起|时|，|,)?\s*(?:价格(?:约?为?)?|单价?|报价)\s*(?:约?为?)?\s*[¥￥]?\s*([\d,]+\.?\d*)\s*(?:元?/?(?:片|个|颗)?)',
        # 模式5: "¥6~6.4" 价格区间（取低值）
        r'[¥￥]\s*([\d,]+\.?\d*)\s*~\s*[\d,]+\.?\d*',
        # 模式6: 独立的 ¥X.XX 或 ￥X.XX
        r'[¥￥]\s*([\d]+\.?\d*)',
    ]

    # 来源匹配模式
    source_patterns = [
        (r'淘宝', '淘宝'),
        (r'1688|阿里巴巴国际', '1688'),
        (r'华强商城|华强电子网', '华强电子网'),
        (r'立创', '立创商城'),
        (r'华秋', '华秋商城'),
        (r'LCSC|lcsc', 'LCSC'),
        (r'Mouser|mouser', 'Mouser'),
        (r'DigiKey|digikey', 'DigiKey'),
        (r'维库|dzsc', '维库电子市场网'),
        (r'云汉', '云汉芯城'),
    ]

    # 按段落处理（每个段落可能对应一个来源）
    paragraphs = re.split(r'\n\n+', answer_text)

    for para in paragraphs:
        # 确定这个段落提到的来源
        para_source = ""
        para_link = ""
        for pattern, name in source_patterns:
            if re.search(pattern, para):
                para_source = name
                # 尝试从 source_map 匹配链接
                for hostname, url in source_map.items():
                    if re.search(pattern, hostname + " " + name):
                        para_link = url
                        break
                break

        # 确定货币
        para_currency = "CNY"
        if re.search(r'US?\$|美元|USD|dollar', para):
            para_currency = "USD"

        # 提取数量档位
        qty_match = re.search(r'(\d+)\+?\s*(?:片|个|颗|只|件)?(?:起|时)', para)
        para_qty = f"{qty_match.group(1)}+" if qty_match else ""

        # 用各模式提取价格
        found_prices = set()
        for pattern in patterns:
            for match in re.finditer(pattern, para):
                # 模式4 特殊处理：包含数量和价格两个组
                if r'(\d+)\+?\s*片?' in pattern and match.lastindex >= 2:
                    qty = match.group(1)
                    price_str = match.group(2)
                    para_qty = f"{qty}+"
                else:
                    price_str = match.group(1)

                try:
                    price_val = float(price_str.replace(",", ""))
                    # 合理性过滤
                    if para_currency == "CNY" and (0.01 < price_val < 100000):
                        if price_val not in found_prices:
                            found_prices.add(price_val)
                            prices.append({
                                "source": para_source or "IQS搜索",
                                "price": price_val,
                                "quantity": para_qty or "未知",
                                "currency": para_currency,
                                "link": para_link,
                                "note": "IQS AI回答提取",
                            })
                    elif para_currency == "USD" and (0.01 < price_val < 10000):
                        if price_val not in found_prices:
                            found_prices.add(price_val)
                            prices.append({
                                "source": para_source or "IQS搜索",
                                "price": price_val,
                                "quantity": para_qty or "未知",
                                "currency": para_currency,
                                "link": para_link,
                                "note": "IQS AI回答提取",
                            })
                except (ValueError, IndexError):
                    continue

    return prices


# ============================================================
# 接口3: 交叉验证 — 博查 + IQS /ai/answer 并行
# ============================================================

def cross_verify(query: str, api_key: str, bocha_depth: str = "advanced",
                 iqs_model: str = "lite") -> dict:
    """
    博查 + IQS /ai/answer 双源并行查询 + 交叉验证

    :param query: 搜索关键词（如 "STM32F103C8T6 价格 批量"）
    :param api_key: 阿里云 IQS API Key
    :param bocha_depth: 博查搜索深度 basic / advanced
    :param iqs_model: IQS 模型 lite / standard
    :return: 交叉验证结果
    """
    import concurrent.futures

    # 并行调用两个搜索
    bocha_result = {"success": False}
    iqs_result = {"success": False}

    def run_bocha():
        nonlocal bocha_result
        try:
            sys.path.insert(0, os.path.expanduser("~/.workbuddy/skills/bom-solution-assistant/scripts"))
            from shengsuan_search import search_bocha
            t0 = time.time()
            bocha_result = search_bocha(query, depth=bocha_depth)
            bocha_result["elapsed_ms"] = round((time.time() - t0) * 1000)
        except Exception as e:
            bocha_result = {"success": False, "error": str(e), "elapsed_ms": 0}

    def run_iqs():
        nonlocal iqs_result
        t0 = time.time()
        iqs_result = iqs_ai_answer(query, api_key, model=iqs_model)
        iqs_result["elapsed_ms"] = round((time.time() - t0) * 1000)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_bocha)
        f2 = executor.submit(run_iqs)
        concurrent.futures.wait([f1, f2])

    # 提取博查价格
    bocha_prices = bocha_result.get("parsed_prices", [])
    # 过滤 price=0 的无效记录
    bocha_prices = [p for p in bocha_prices if isinstance(p.get("price"), (int, float)) and p["price"] > 0]

    # 提取 IQS 价格
    iqs_answer = iqs_result.get("answer", "")
    iqs_sources = iqs_result.get("sources", [])
    iqs_prices = extract_prices_from_answer(iqs_answer, iqs_sources) if iqs_answer else []

    # 交叉比对
    comparison = []
    verified = []  # 两源一致
    bocha_only = []  # 博查独有
    iqs_only = []  # IQS独有
    disputed = []  # 价差>20%

    # 按 (source, currency) 分组比较
    bocha_by_source = {}
    for p in bocha_prices:
        key = (p.get("source", ""), p.get("currency", "CNY"))
        bocha_by_source.setdefault(key, []).append(p)

    iqs_by_source = {}
    for p in iqs_prices:
        key = (p.get("source", ""), p.get("currency", "CNY"))
        iqs_by_source.setdefault(key, []).append(p)

    # 找共同来源
    common_sources = set(bocha_by_source.keys()) & set(iqs_by_source.keys())

    for src_key in common_sources:
        bp = bocha_by_source[src_key]
        ip = iqs_by_source[src_key]
        # 取各自最低价比较
        b_min = min(p["price"] for p in bp)
        i_min = min(p["price"] for p in ip)
        avg = (b_min + i_min) / 2
        diff_pct = abs(b_min - i_min) / avg * 100 if avg > 0 else 0

        if diff_pct < 20:
            verified.append({
                "source": src_key[0],
                "bocha_price": b_min,
                "iqs_price": i_min,
                "avg_price": round(avg, 2),
                "diff_pct": round(diff_pct, 1),
                "status": "一致",
                "bocha_records": bp,
                "iqs_records": ip,
            })
        else:
            disputed.append({
                "source": src_key[0],
                "bocha_price": b_min,
                "iqs_price": i_min,
                "diff_pct": round(diff_pct, 1),
                "status": "存疑",
                "bocha_records": bp,
                "iqs_records": ip,
            })

    # 博查独有
    for src_key in set(bocha_by_source.keys()) - common_sources:
        bocha_only.extend(bocha_by_source[src_key])

    # IQS独有
    for src_key in set(iqs_by_source.keys()) - common_sources:
        iqs_only.extend(iqs_by_source[src_key])

    # 合并最终价格列表（去重）
    all_prices = []
    seen = set()
    for p in bocha_prices:
        key = (p.get("source", ""), p.get("price"), p.get("quantity", ""))
        if key not in seen:
            seen.add(key)
            all_prices.append({**p, "from": "博查"})
    for p in iqs_only:
        key = (p.get("source", ""), p.get("price"), p.get("quantity", ""))
        if key not in seen:
            seen.add(key)
            all_prices.append({**p, "from": "IQS补充"})

    return {
        "query": query,
        "bocha": {
            "success": bocha_result.get("success", False),
            "elapsed_ms": bocha_result.get("elapsed_ms", 0),
            "price_count": len(bocha_prices),
            "prices": bocha_prices,
        },
        "iqs_ai_answer": {
            "success": iqs_result.get("success", False),
            "elapsed_ms": iqs_result.get("elapsed_ms", 0),
            "answer_length": len(iqs_answer),
            "source_count": len(iqs_sources),
            "metadata": iqs_result.get("metadata", {}),
        },
        "cross_verify": {
            "verified_count": len(verified),
            "disputed_count": len(disputed),
            "bocha_only_count": len(bocha_only),
            "iqs_only_count": len(iqs_only),
            "verified": verified,
            "disputed": disputed,
            "bocha_only": bocha_only,
            "iqs_only": iqs_only,
        },
        "merged_prices": all_prices,
        "iqs_answer_text": iqs_answer[:3000] if iqs_answer else "",
        "iqs_sources": iqs_sources,
    }


# ============================================================
# 格式化 /ai/answer 结果
# ============================================================

def format_ai_answer(result: dict, json_output: bool = False) -> str:
    """格式化 /ai/answer 响应"""
    if not result.get("success"):
        err = result.get("error", "未知错误")
        if json_output:
            return json.dumps({"error": err}, ensure_ascii=False, indent=2)
        return f"查询失败：{err}"

    if json_output:
        output = {
            "success": True,
            "answer": result.get("answer", ""),
            "extracted_prices": extract_prices_from_answer(
                result.get("answer", ""), result.get("sources", [])
            ),
            "sources": result.get("sources", []),
            "source_count": result.get("source_count", 0),
            "metadata": result.get("metadata", {}),
        }
        return json.dumps(output, ensure_ascii=False, indent=2)

    lines = []
    lines.append(f"IQS AI 回答（{result.get('source_count', 0)} 条引用来源）：\n")
    lines.append(result.get("answer", "")[:3000])

    # 提取的价格
    prices = extract_prices_from_answer(result.get("answer", ""), result.get("sources", []))
    if prices:
        lines.append(f"\n--- 提取到 {len(prices)} 条价格 ---")
        for p in prices:
            cur = p.get("currency", "CNY")
            price_str = f"¥{p['price']:.2f}" if cur == "CNY" else f"${p['price']:.2f}"
            note = f" ({p.get('note', '')})" if p.get("note") else ""
            lines.append(f"  {p.get('source', '?')}: {price_str} [{p.get('quantity', '?')}]{note}")

    return "\n".join(lines)


# ============================================================
# 格式化交叉验证结果
# ============================================================

def format_cross_verify(result: dict, json_output: bool = False) -> str:
    """格式化交叉验证结果"""
    if json_output:
        return json.dumps(result, ensure_ascii=False, indent=2)

    lines = []
    lines.append(f"=== 双源交叉验证: {result.get('query', '')} ===\n")

    bv = result.get("bocha", {})
    ia = result.get("iqs_ai_answer", {})
    cv = result.get("cross_verify", {})

    lines.append(f"博查搜索: {'成功' if bv.get('success') else '失败'} | {bv.get('elapsed_ms', 0)}ms | {bv.get('price_count', 0)} 条价格")
    lines.append(f"IQS AI问答: {'成功' if ia.get('success') else '失败'} | {ia.get('elapsed_ms', 0)}ms | {ia.get('source_count', 0)} 条来源")

    # 验证结果
    verified = cv.get("verified", [])
    disputed = cv.get("disputed", [])
    bocha_only = cv.get("bocha_only", [])
    iqs_only = cv.get("iqs_only", [])

    lines.append(f"\n--- 交叉验证结果 ---")
    lines.append(f"两源一致: {len(verified)} | 存疑(价差>20%): {len(disputed)} | 博查独有: {len(bocha_only)} | IQS独有: {len(iqs_only)}")

    if verified:
        lines.append(f"\n[两源一致] (高置信度)")
        for v in verified:
            lines.append(f"  {v['source']}: 博查¥{v['bocha_price']} / IQS¥{v['iqs_price']} -> 均价¥{v['avg_price']} (差异{v['diff_pct']}%)")

    if disputed:
        lines.append(f"\n[存疑] (价差>20%，建议WebFetch验证)")
        for d in disputed:
            lines.append(f"  {d['source']}: 博查¥{d['bocha_price']} / IQS¥{d['iqs_price']} (差异{d['diff_pct']}%)")

    if bocha_only:
        lines.append(f"\n[博查独有]")
        for p in bocha_only:
            cur = p.get("currency", "CNY")
            ps = f"¥{p['price']:.2f}" if cur == "CNY" else f"${p['price']:.2f}"
            lines.append(f"  {p.get('source', '?')}: {ps} [{p.get('quantity', '?')}]")

    if iqs_only:
        lines.append(f"\n[IQS补充]")
        for p in iqs_only:
            cur = p.get("currency", "CNY")
            ps = f"¥{p['price']:.2f}" if cur == "CNY" else f"${p['price']:.2f}"
            lines.append(f"  {p.get('source', '?')}: {ps} [{p.get('quantity', '?')}]")

    # IQS 额外信息
    answer_text = result.get("iqs_answer_text", "")
    if answer_text:
        lines.append(f"\n--- IQS AI 补充分析 (前1000字) ---")
        lines.append(answer_text[:1000])

    return "\n".join(lines)


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="阿里云 IQS 搜索 - bom-solution-assistant 辅助查询",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 纯搜索（默认）
  python3 iqs_search.py "STM32F103C8T6 datasheet"

  # AI 问答
  python3 iqs_search.py "STM32F103C8T6 价格 批量" --ai-answer

  # 双源交叉验证（博查 + IQS 并行）
  python3 iqs_search.py "STM32F103C8T6 价格 批量" --cross-verify

  # JSON 输出
  python3 iqs_search.py "STM32F103C8T6 价格" --ai-answer --json
"""
    )

    parser.add_argument("query", help="搜索关键词，如 'STM32F103C8T6 价格 批量'")

    # 模式切换
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--ai-answer", action="store_true",
                           help="使用 /ai/answer 接口（搜索 + AI 总结，~11s）")
    mode_group.add_argument("--cross-verify", action="store_true",
                           help="双源交叉验证（博查 + IQS /ai/answer 并行）")

    # 通用参数
    parser.add_argument("--api-key", default=DEFAULT_API_KEY,
                        help="阿里云 IQS API Key（也可设置环境变量 ALIYUN_IQS_API_KEY）")
    parser.add_argument("--engine", default="LiteAdvanced",
                        choices=["LiteAdvanced", "Standard", "Pro"],
                        help="/search/unified 引擎类型（默认 LiteAdvanced）")
    parser.add_argument("--num", type=int, default=5,
                        help="/search/unified 返回结果数量（1-10，默认5）")
    parser.add_argument("--full-text", action="store_true",
                        help="/search/unified 同时返回网页正文")
    parser.add_argument("--model", default="lite", choices=["lite", "standard"],
                        help="/ai/answer 模型类型（默认 lite）")
    parser.add_argument("--depth", default="advanced", choices=["basic", "advanced"],
                        help="--cross-verify 时博查搜索深度（默认 advanced）")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="以 JSON 格式输出（供程序解析）")

    args = parser.parse_args()

    if not args.api_key and not args.cross_verify:
        print("未提供 API Key（内置 Key 可能已失效）。请使用 --api-key 参数或设置环境变量 ALIYUN_IQS_API_KEY。")
        sys.exit(1)

    if args.cross_verify:
        # 双源交叉验证模式
        if not args.api_key:
            print("交叉验证模式需要 IQS API Key（内置 Key 可能已失效）。请使用 --api-key 参数或设置环境变量。")
            sys.exit(1)
        if not args.json_output:
            print(f"双源交叉验证: {args.query}\n")
        result = cross_verify(args.query, args.api_key, bocha_depth=args.depth, iqs_model=args.model)
        print(format_cross_verify(result, json_output=args.json_output))

    elif args.ai_answer:
        # AI 问答模式
        if not args.json_output:
            print(f"IQS AI 问答: {args.query}\n")
        result = iqs_ai_answer(args.query, args.api_key, model=args.model)
        print(format_ai_answer(result, json_output=args.json_output))

    else:
        # 默认：纯搜索模式
        if not args.json_output:
            print(f"搜索: {args.query}  (引擎: {args.engine})\n")
        response = iqs_search(
            query=args.query,
            api_key=args.api_key,
            engine_type=args.engine,
            num_results=args.num,
            main_text=args.full_text,
        )
        print(format_results(response, json_output=args.json_output))


if __name__ == "__main__":
    main()
