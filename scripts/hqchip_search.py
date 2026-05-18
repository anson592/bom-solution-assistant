#!/usr/bin/env python3
"""
华秋商城（hqchip.com）元器件价格查询
通过 requests 访问搜索页，提取 HTML 中的产品数据。

用法:
  python3 hqchip_search.py "ESP32-S3-WROOM-1-N8R8"
  python3 hqchip_search.py "ESP32-S3-WROOM-1-N8R8" --json
"""

import argparse
import json
import re
import sys
import requests

SEARCH_URL_TPL = "https://www.hqchip.com/search.html?keyword={}"


def parse_hqchip_html(html: str, keyword: str) -> dict:
    """
    从华秋商城 HTML 提取产品数据
    数据在 HTML 表格中，格式：
    <td class="price">￥30.1448</td>
    """
    result = {
        "keyword": keyword,
        "found": False,
        "source": "华秋商城",
        "part_number": None,
        "brand": None,
        "price": None,
        "price_ladder": None,
        "stock": None,
        "currency": "CNY",
        "total_found": 0,
        "url": SEARCH_URL_TPL.format(keyword),
    }

    # 提取所有价格
    prices = re.findall(r'<td class="price">￥([\d.]+)</td>', html)
    if not prices:
        return result

    result["total_found"] = len(prices)
    result["found"] = True

    # 取第一个产品的最低价（第一个价格通常是1+的价格）
    result["price"] = float(prices[0])
    result["price_ladder"] = 1

    # 提取型号（data-goodsname属性）
    model_match = re.search(r'data-goodsname="([^"]+)"', html)
    if model_match:
        result["part_number"] = model_match.group(1)

    # 提取品牌
    brand_match = re.search(r'<span class="tag">品牌：</span><a[^>]*>([^<]+)</a>', html)
    if brand_match:
        result["brand"] = brand_match.group(1)

    # 提取库存
    stock_match = re.search(r'<span class="c-bc">(\d+)</span>（当天发货）', html)
    if stock_match:
        result["stock"] = stock_match.group(1)

    return result


def search(keyword: str) -> dict:
    """查询华秋商城"""
    url = SEARCH_URL_TPL.format(keyword)

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {
                "keyword": keyword,
                "found": False,
                "error": f"HTTP {resp.status_code}",
                "source": "华秋商城",
                "url": url,
            }

        return parse_hqchip_html(resp.text, keyword)

    except requests.exceptions.Timeout:
        return {
            "keyword": keyword,
            "found": False,
            "error": "请求超时",
            "source": "华秋商城",
            "url": url,
        }
    except Exception as e:
        return {
            "keyword": keyword,
            "found": False,
            "error": str(e),
            "source": "华秋商城",
            "url": url,
        }


def _format_text(r: dict) -> str:
    if not r.get("found"):
        err = r.get("error", "未找到匹配型号")
        return f"[{r['keyword']}] 华秋商城 - {err}"

    lines = [
        f"[{r['keyword']}] 华秋商城",
        f"  型号  : {r.get('part_number', '?')}",
        f"  品牌  : {r.get('brand', '?')}",
        f"  单价  : ¥{r['price']:.4f} ({r.get('price_ladder', 1)}+ 起)",
        f"  库存  : {r.get('stock', '?')}",
        f"  共找到: {r['total_found']} 条",
        f"  链接  : {r['url']}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="华秋商城元器件价格查询",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="元器件型号")
    parser.add_argument("-j", "--json", action="store_true", dest="json_output",
                        help="JSON 格式输出")
    args = parser.parse_args()

    result = search(args.keyword)

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_format_text(result))

    sys.exit(0 if result.get("found") else 1)


if __name__ == "__main__":
    main()
