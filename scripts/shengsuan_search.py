#!/usr/bin/env python3
"""
胜算云联网搜索 - 元器件价格查询脚本
支持博查AI搜索（中文优化）和 Tavily 搜索（全球搜索）
通过大模型 + 联网搜索自动提取元器件价格信息

用法:
  python3 shengsuan_search.py "STM32F103C8T6 价格"               # 博查搜索
  python3 shengsuan_search.py "ESP32-S3 price" --engine tavily    # Tavily 全球搜索
  python3 shengsuan_search.py "STM32F103C8T6 价格" --engine auto  # 自动降级
  python3 shengsuan_search.py "STM32F103C8T6 价格" --json         # JSON 输出
"""

import argparse
import json
import os
import sys
import requests
import re

# ========== 配置 ==========
API_URL = "https://router.shengsuanyun.com/api/v1"
# API Key（已内置，开箱即用）
# 如需更换，可设置环境变量 SHENGSUAN_API_KEY 覆盖
_API_KEY_INTERNAL = "4lfkEMbNr8v-Z2bFd-5tpKu6OcDKy0PeGOrwxtKKV3wV9jslh0Jfvr75VLHAf9YQyY1EWYWz7lqQn0132Mawlhxc53GRtOEziJQ0yqQ6DdMCw5UXmv5WUnjf"
API_KEY = os.environ.get("SHENGSUAN_API_KEY", _API_KEY_INTERNAL)
MODEL = "ali/qwen3.5-flash"


SYSTEM_PROMPT = """你是一个专业的电子元器件价格查询助手。你的任务是通过联网搜索，找到指定型号元器件在各个平台上的价格。

输出规则（非常重要）：
1. 你只能输出一个 JSON 数组，不要输出任何其他内容
2. 不要输出思考过程、不要输出解释说明、不要输出 markdown 代码块标记
3. 每个 JSON 元素必须包含以下字段：
   - "source": 来源平台名称（中文，如"立创商城"、"华秋商城"、"LCSC"、"Mouser"、"淘宝/1688"等）
   - "price": 单价（纯数字，不要包含货币符号）
   - "quantity": 对应的数量档位（如 "1+", "100+", "1000+", "2000+"）
   - "currency": 货币代码（"CNY" 或 "USD"）
   - "link": 来源链接 URL（如果能找到）
   - "note": 备注（如"含税"、"不含运费"、"原装正品"等）
4. 如果找到多个档位价格，每个档位单独一条记录
5. 优先找批量价（100+或2000+）
6. 只返回芯片/元器件本身的价格，不要返回开发板价格（除非型号本身是模块）
7. 如果某个搜索结果看起来是开发板而不是芯片，在 note 中标注"疑似开发板价"
8. 价格为0或明显异常（如0.01元）的数据不要返回"""


def extract_content(message: dict) -> str:
    """提取消息内容，处理 reasoning_content 和 thinking 标签"""
    # 优先使用 reasoning_content（DeepSeek 等模型）
    content = message.get("content", "")

    # qwen3 系列会用 <think>...</think> 或 </think> 包裹思考内容
    # 实际输出可能在 think 标签之后
    # 有些模型 content 里包含 [] 空数组，真正的数据在 reasoning_content 里

    # 尝试从 reasoning_content 获取
    reasoning = message.get("reasoning_content", "")
    if reasoning and len(reasoning) > 100:
        # reasoning 中可能包含 JSON
        return reasoning + "\n" + content

    # 去除 qwen 的 <think> 标签
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
    if cleaned:
        return cleaned

    return content


def parse_price_json(content: str) -> list:
    """从大模型返回的内容中解析 JSON 价格数据，支持多种格式"""
    # 提取所有 JSON 数组候选
    candidates = []

    # 方法1: 在 markdown 代码块中找
    for match in re.finditer(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content):
        candidates.append(match.group(1).strip())

    # 方法2: 找所有非空的 JSON 数组 [...]
    for match in re.finditer(r'(\[[\s\S]*?\])', content):
        text = match.group(1)
        # 跳过空数组
        if re.match(r'\[\s*\]', text):
            continue
        # 跳过太短的（不太可能是有效价格数据）
        if len(text) < 20:
            continue
        candidates.append(text)

    # 方法3: 直接尝试解析整个内容
    if content.strip().startswith('['):
        candidates.append(content.strip())

    # 按长度排序，优先解析最长的（最可能包含完整数据）
    candidates.sort(key=len, reverse=True)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, list) and len(data) > 0:
                # 验证数据结构
                valid = []
                for item in data:
                    if isinstance(item, dict) and "price" in item and "source" in item:
                        # 验证价格是数字
                        price = item.get("price")
                        if isinstance(price, (int, float)) and price > 0:
                            valid.append(item)
                if valid:
                    return valid
        except (json.JSONDecodeError, TypeError):
            continue

    return []


def extract_prices_from_search_results(search_results: list) -> list:
    """直接从搜索结果的 snippet 中提取价格信息"""
    prices = []
    price_pattern = re.compile(
        r'[¥￥$]\s*([\d,]+\.?\d*)|(?:单价|价格|报价)[：:]\s*([\d,]+\.?\d*)',
        re.IGNORECASE
    )

    for result in search_results:
        snippet = result.get("snippet", "")
        title = result.get("title", "")
        url = result.get("url", "")
        site = result.get("site_name", "")

        # 从标题判断是否包含目标型号信息
        combined = title + " " + snippet

        for match in price_pattern.finditer(combined):
            price_str = match.group(1) or match.group(2)
            try:
                price_val = float(price_str.replace(",", ""))
                if 0.01 < price_val < 100000:  # 合理的价格范围
                    prices.append({
                        "source": site,
                        "price": price_val,
                        "quantity": "未知",
                        "currency": "CNY" if "¥" in match.group(0) or "￥" in match.group(0) else "USD",
                        "link": url,
                        "note": "从搜索结果摘要提取"
                    })
            except ValueError:
                continue

    return prices


def do_search(component: str, engine: str = "bocha", depth: str = "basic") -> dict:
    """执行搜索请求"""
    user_prompt = f"请查询元器件 {component} 在各平台的价格"

    if depth == "advanced":
        user_prompt += "。请尽可能全面地搜索所有渠道，包括立创、华秋、云汉、Mouser、DigiKey、淘宝、1688等。"

    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "online_search": True,
    }

    if engine == "tavily":
        data["online_search_options"] = {"global": True}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        response = requests.post(
            f"{API_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=90
        )
        response.raise_for_status()
        result = response.json()

        message = result["choices"][0]["message"]
        content = extract_content(message)
        search_result = result.get("search_result", {})
        search_results = search_result.get("search_results", [])
        search_queries = search_result.get("search_queries", [])

        # 方式1: 从大模型输出中解析 JSON
        parsed_prices = parse_price_json(content)

        # 方式2: 如果模型没返回好 JSON，从搜索结果摘要中提取
        if not parsed_prices and search_results:
            parsed_prices = extract_prices_from_search_results(search_results)

        return {
            "success": True,
            "engine": engine,
            "content": content,
            "search_queries": search_queries,
            "search_results_count": len(search_results),
            "search_results": search_results[:5],  # 只保留前5条
            "parsed_prices": parsed_prices,
            "model": result.get("model", MODEL),
        }
    except requests.exceptions.Timeout:
        return {"success": False, "engine": engine, "error": "请求超时（90秒）"}
    except Exception as e:
        return {"success": False, "engine": engine, "error": str(e)}


def format_output(result: dict) -> str:
    """格式化输出结果"""
    if not result["success"]:
        return f"搜索失败 [{result['engine']}]: {result.get('error', '未知错误')}"

    lines = []
    engine_name = "博查AI搜索" if result["engine"] == "bocha" else "Tavily全球搜索"
    lines.append(f"搜索引擎: {engine_name}")
    lines.append(f"模型: {result.get('model', '?')}")
    lines.append(f"搜索结果数: {result.get('search_results_count', 0)}")

    queries = result.get("search_queries", [])
    if queries:
        lines.append(f"搜索词: {', '.join(queries)}")

    lines.append("")

    prices = result.get("parsed_prices", [])
    if prices:
        lines.append(f"找到 {len(prices)} 条价格:")
        lines.append(f"{'来源':<20} {'单价':>12} {'档位':<12} {'货币':<6} 备注")
        lines.append("-" * 75)
        for p in prices:
            source = p.get("source", "?")
            price = p.get("price", "?")
            qty = p.get("quantity", "-")
            cur = p.get("currency", "CNY")
            note = p.get("note", "")
            link = p.get("link", "")

            if isinstance(price, (int, float)):
                if cur == "CNY":
                    price_str = f"¥{price:.2f}"
                else:
                    price_str = f"${price:.2f}"
            else:
                price_str = str(price)

            line = f"  {source:<18} {price_str:>12} {qty:<12} {cur:<6} {note}"
            if link:
                line += f"\n    -> {link}"
            lines.append(line)
    else:
        lines.append("未能解析出结构化价格数据")
        lines.append("")

        # 显示搜索结果作为备选
        search_results = result.get("search_results", [])
        if search_results:
            lines.append("搜索到的相关网页:")
            for sr in search_results[:8]:
                lines.append(f"  - [{sr.get('site_name', '?')}] {sr.get('title', '?')}")
                lines.append(f"    {sr.get('url', '')}")
                snippet = sr.get("snippet", "")[:200]
                if snippet:
                    lines.append(f"    {snippet}")
                lines.append("")

    # 显示原始内容（仅在无结构化数据时）
    if not prices:
        content = result.get("content", "")
        if content:
            lines.append("原始回复（前2000字）:")
            lines.append(content[:2000])

    return "\n".join(lines)


def search_auto(component: str, depth: str = "basic") -> dict:
    """自动模式：先用博查搜索，无结果时降级到 Tavily"""
    print(f"[1/2] 博查AI搜索: {component}", file=sys.stderr)
    result = search_bocha(component, depth)

    if result["success"] and result.get("parsed_prices"):
        print(f"  成功，找到 {len(result['parsed_prices'])} 条价格", file=sys.stderr)
        return result

    reason = "失败" if not result["success"] else "无结构化价格"
    print(f"  博查{reason}，切换 Tavily...", file=sys.stderr)

    print(f"[2/2] Tavily全球搜索: {component}", file=sys.stderr)
    result2 = search_tavily(component, depth)

    if result2["success"] and result2.get("parsed_prices"):
        print(f"  成功，找到 {len(result2['parsed_prices'])} 条价格", file=sys.stderr)
    else:
        print(f"  Tavily也未找到结构化价格", file=sys.stderr)

    # 合并：如果博查有搜索结果但没解析出价格，保留搜索链接
    if result["success"] and not result.get("parsed_prices") and result2["success"]:
        result2["search_results"] = result.get("search_results", []) + result2.get("search_results", [])
        result2["search_results_count"] = len(result2["search_results"])

    return result2 if result2["success"] else result


def search_bocha(component: str, depth: str = "basic") -> dict:
    return do_search(component, engine="bocha", depth=depth)


def search_tavily(component: str, depth: str = "basic") -> dict:
    return do_search(component, engine="tavily", depth=depth)


def main():
    parser = argparse.ArgumentParser(
        description="胜算云联网搜索 - 元器件价格查询",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help="搜索查询（元器件型号 + 价格）")
    parser.add_argument("-e", "--engine", choices=["bocha", "tavily", "auto"], default="bocha",
                        help="搜索引擎 (默认: bocha)")
    parser.add_argument("-d", "--depth", choices=["basic", "advanced"], default="basic",
                        help="搜索深度 (默认: basic)")
    parser.add_argument("-j", "--json", action="store_true", help="JSON 格式输出")

    args = parser.parse_args()

    search_fn = {"bocha": search_bocha, "tavily": search_tavily, "auto": search_auto}
    result = search_fn[args.engine](args.query, args.depth)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_output(result))

    # 退出码
    sys.exit(0 if result["success"] and result.get("parsed_prices") else 1)


if __name__ == "__main__":
    main()
