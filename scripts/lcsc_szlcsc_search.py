#!/usr/bin/env python3
"""
立创商城（szlcsc.com）元器件直搜 — 无需登录 Cookie
通过 Playwright 匿名访问搜索页，提取 SSR 产品数据和阶梯价格。

用法:
  python3 lcsc_szlcsc_search.py "ESP32-S3-WROOM-1-N8R8"
  python3 lcsc_szlcsc_search.py "ESP32-S3-WROOM-1-N8R8" --json
  python3 lcsc_szlcsc_search.py "ESP32-S3-WROOM-1-N8R8" --qty 2000 --json
  python3 lcsc_szlcsc_search.py "USB-C 16P" --json   # 自动关键词映射
"""

import argparse
import asyncio
import json
import re
import sys

# 关键词映射：szlcsc 使用中文连接器术语，英文/简称需转换
KEYWORD_MAP = {
    "USB-C":      "TYPE-C 16PIN母座",
    "USB C":      "TYPE-C 16PIN母座",
    "TYPE-C 16P": "TYPE-C 16PIN母座",
    "USBC":       "TYPE-C 16PIN母座",
}

def _pick_price(prices: list) -> tuple[float | None, int | None]:
    """
    从阶梯价格列表中取最低价（即最大批量档位）。
    返回 (min_price, 对应的 startPurchasedNumber)，找不到时返回 (None, None)。
    """
    if not prices:
        return None, None
    best = min(prices, key=lambda p: p.get("productPrice") or float("inf"))
    return best.get("productPrice"), best.get("startPurchasedNumber")


SEARCH_URL_TPL = "https://so.szlcsc.com/global.html?k={}"
DETAIL_URL_TPL = "https://item.szlcsc.com/{}.html"
HOMEPAGE = "https://www.szlcsc.com/"
SEARCH_INPUT_ID = "#global-seach-input"  # 原页面 typo，少了一个 r


def _map_keyword(keyword: str) -> str:
    for k, v in KEYWORD_MAP.items():
        if k.lower() in keyword.lower():
            return v
    return keyword


def _parse_html(html: str) -> list:
    """从 Next.js SSR HTML 的 <script> 块提取产品列表。
    数据路径: props.pageProps.soData.searchResult.productRecordList
    """
    m = re.search(r'<script[^>]*>(\{"props":\{.*?\})</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        return (
            data.get("props", {})
                .get("pageProps", {})
                .get("soData", {})
                .get("searchResult", {})
                .get("productRecordList") or []
        )
    except Exception:
        return []


def _best_record(records: list, keyword: str) -> dict | None:
    """从产品列表中选出最匹配的一条（优先完全型号匹配，否则取第一条）。"""
    kw_lower = keyword.lower()
    for rec in records:
        vo = rec.get("productVO") or {}
        model = (vo.get("productModel") or "").lower()
        if kw_lower == model or kw_lower in model:
            return rec
    return records[0] if records else None


async def _search_async(keyword: str) -> dict:
    from playwright.async_api import async_playwright

    mapped = _map_keyword(keyword)
    result = {
        "keyword": keyword,
        "mapped_keyword": mapped if mapped != keyword else None,
        "found": False,
        "login_required": False,
        "source": "立创商城",
        "part_number": None,
        "brand": None,
        "price": None,
        "price_ladder": None,   # 最低价对应的阶梯起购量
        "currency": "CNY",
        "total_found": 0,
        "url": SEARCH_URL_TPL.format(mapped),
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            },
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        try:
            await page.goto(HOMEPAGE, wait_until="load", timeout=20000)
            await asyncio.sleep(1.5)

            await page.fill(SEARCH_INPUT_ID, mapped)
            await asyncio.sleep(0.3)
            await page.press(SEARCH_INPUT_ID, "Enter")

            await page.wait_for_load_state("load", timeout=15000)
            await asyncio.sleep(2)

            # 频率限制检测：szlcsc 在连续搜索后会跳到登录页
            if "passport.jlc.com" in page.url or "login" in page.url.lower():
                result["login_required"] = True
                return result

            html = await page.content()
            records = _parse_html(html)
            result["total_found"] = len(records)

            if records:
                best = _best_record(records, mapped)
                vo = best.get("productVO") or {}
                prices = vo.get("productPriceList") or []
                price_val, ladder = _pick_price(prices)

                result["found"] = True
                result["part_number"] = vo.get("productModel")
                result["brand"] = vo.get("productGradePlateName")
                result["price"] = float(price_val) if price_val is not None else None
                result["price_ladder"] = ladder  # 最低价对应的阶梯起购量

                # v9.4: 用 productId 拼详情页 URL（实测：item.szlcsc.com/{productId}.html 200 OK）
                # 拿不到 productId 时保留搜索页 URL 作为 fallback
                product_id = vo.get("productId")
                if product_id:
                    result["url"] = DETAIL_URL_TPL.format(product_id)

        except Exception as e:
            result["error"] = str(e)
        finally:
            await browser.close()

    return result


def search(keyword: str) -> dict:
    return asyncio.run(_search_async(keyword))


def _format_text(r: dict) -> str:
    if r.get("login_required"):
        return f"[{r['keyword']}] ⚠ 触发频率限制，请稍后重试（szlcsc 跳转登录页）"
    if not r.get("found"):
        mapped = r.get("mapped_keyword")
        note = f"（映射关键词: {mapped}）" if mapped else ""
        return f"[{r['keyword']}] 未在立创商城找到匹配型号{note}"
    ladder = r.get("price_ladder")
    ladder_note = f"（{ladder}+ 起）" if ladder is not None else ""
    lines = [
        f"[{r['keyword']}] 立创商城",
        f"  型号  : {r['part_number']}",
        f"  品牌  : {r['brand']}",
        f"  单价  : ¥{r['price']:.4f}{ladder_note}" if r.get("price") else "  单价  : 暂无",
        f"  共找到: {r['total_found']} 条",
        f"  链接  : {r['url']}",
    ]
    if r.get("mapped_keyword"):
        lines.insert(1, f"  映射词: {r['mapped_keyword']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="立创商城元器件直搜（无需 Cookie）",
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
