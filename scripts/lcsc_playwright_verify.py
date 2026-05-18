#!/usr/bin/env python3
"""
Step 2: Playwright 实时点验 — 验证 AI 搜索价格
用 Playwright headless 访问立创商城搜索页，提取实时价格与阶梯价格，
与 Step 1 AI 搜索价格做差价比对，输出三种 confidence 标记。

用法:
  python3 lcsc_playwright_verify.py "ESP32-S3-WROOM-1-N8R8" --ai-price 11.80 --json
  python3 lcsc_playwright_verify.py "STM32F103C8T6" --ai-price 5.20 --json
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone

# 复用 lcsc_szlcsc_search.py 的关键词映射和 HTML 解析
from lcsc_szlcsc_search import _map_keyword, _parse_html, _best_record

SEARCH_URL_TPL = "https://www.szlcsc.com/search?q={}"
HOMEPAGE = "https://www.szlcsc.com/"
SEARCH_INPUT_ID = "#global-seach-input"

DIFF_THRESHOLD = 0.15  # 15% 差价阈值
TIMEOUT_MS = 15000     # 15 秒超时

# 需要拦截的搜索 API 路径（szlcsc 的搜索结果接口）
API_PATTERN = re.compile(r"/api/.*search|/api/.*product|/so/.*search")


def _extract_laddered_prices(vo: dict) -> list:
    """从 productVO 中提取阶梯价格列表。"""
    prices = vo.get("productPriceList") or []
    result = []
    for p in prices:
        qty = p.get("startPurchasedNumber")
        price = p.get("productPrice")
        if qty is not None and price is not None:
            result.append({"qty": qty, "price": float(price)})
    return sorted(result, key=lambda x: x["qty"])


def _compute_diff(price_realtime: float, price_ai: float) -> float:
    """计算价格差异百分比（以 AI 价格为基准）。"""
    if price_ai <= 0:
        return 100.0
    return abs(price_realtime - price_ai) / price_ai * 100


def _judge_confidence(diff_pct: float) -> str:
    """根据差价百分比判断 confidence 等级。"""
    if diff_pct < DIFF_THRESHOLD * 100:
        return "verified"
    else:
        return "suspicious"


async def _verify_async(keyword: str, ai_price: float) -> dict:
    """用 Playwright 访问立创商城，实时验证 AI 价格。"""
    from playwright.async_api import async_playwright

    mapped = _map_keyword(keyword)
    now_iso = datetime.now(timezone.utc).isoformat()

    base_result = {
        "keyword": keyword,
        "step2_verified": False,
        "price_realtime": None,
        "price_ai": ai_price,
        "price_diff_pct": None,
        "confidence": "unverified",
        "laddered_prices": [],
        "source": "szlcsc.com",
        "verified_at": now_iso,
        "error": None,
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

        # 拦截搜索 API 响应，提取实时价格
        api_data = {}

        async def on_response(response):
            try:
                url = response.url
                if API_PATTERN.search(url) and response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        body = await response.json()
                        api_data[url] = body
            except Exception:
                pass  # 拦截失败不影响主流程

        page.on("response", on_response)

        try:
            await page.goto(HOMEPAGE, wait_until="load", timeout=TIMEOUT_MS)
            await asyncio.sleep(1.0)

            await page.fill(SEARCH_INPUT_ID, mapped)
            await asyncio.sleep(0.3)
            await page.press(SEARCH_INPUT_ID, "Enter")

            await page.wait_for_load_state("load", timeout=TIMEOUT_MS)
            await asyncio.sleep(2)

            # 频率限制检测
            if "passport.jlc.com" in page.url or "login" in page.url.lower():
                base_result["error"] = "触发频率限制（跳转登录页）"
                base_result["confidence"] = "unverified"
                return base_result

            # 策略1：从 API 响应中提取（最准确）
            price_realtime = None
            laddered = []

            for url, body in api_data.items():
                # 尝试从 API 响应中找到产品列表
                records = (
                    body.get("data", {})
                        .get("searchResult", {})
                        .get("productRecordList")
                ) or (
                    body.get("result", {})
                        .get("searchResult", {})
                        .get("productRecordList")
                )

                if records:
                    best = _best_record(records, mapped)
                    if best:
                        vo = best.get("productVO") or {}
                        prices = vo.get("productPriceList") or []
                        if prices:
                            # 取最低价（最大批量档位）
                            price_realtime = min(
                                p.get("productPrice") or float("inf")
                                for p in prices
                            )
                        laddered = _extract_laddered_prices(vo)
                    break

            # 策略2：从 SSR HTML 解析（兜底）
            if price_realtime is None:
                html = await page.content()
                records = _parse_html(html)
                if records:
                    best = _best_record(records, mapped)
                    if best:
                        vo = best.get("productVO") or {}
                        prices = vo.get("productPriceList") or []
                        if prices:
                            price_realtime = min(
                                p.get("productPrice") or float("inf")
                                for p in prices
                            )
                        laddered = _extract_laddered_prices(vo)

            # 判断验证结果
            if price_realtime is not None:
                price_realtime = float(price_realtime)
                diff_pct = _compute_diff(price_realtime, ai_price)
                confidence = _judge_confidence(diff_pct)

                base_result["step2_verified"] = True
                base_result["price_realtime"] = price_realtime
                base_result["price_diff_pct"] = round(diff_pct, 1)
                base_result["confidence"] = confidence
                base_result["laddered_prices"] = laddered
            else:
                base_result["error"] = "未提取到实时价格（页面解析失败）"
                base_result["confidence"] = "unverified"

        except Exception as e:
            base_result["error"] = str(e)
            base_result["confidence"] = "unverified"
        finally:
            await browser.close()

    return base_result


def verify(keyword: str, ai_price: float) -> dict:
    """同步接口"""
    return asyncio.run(_verify_async(keyword, ai_price))


def _format_text(r: dict) -> str:
    """格式化文本输出"""
    status_map = {
        "verified": "已验证 ✅",
        "suspicious": "存疑 ⚠️",
        "unverified": "未验证 ❓",
    }
    status = status_map.get(r["confidence"], r["confidence"])
    lines = [
        f"[{r['keyword']}] Step 2 实时验证 - {status}",
        f"  来源  : {r['source']}",
        f"  时间  : {r['verified_at']}",
    ]

    if r["step2_verified"]:
        lines.append(f"  AI价格: ¥{r['price_ai']:.4f}")
        lines.append(f"  实测价: ¥{r['price_realtime']:.4f}")
        lines.append(f"  差价  : {r['price_diff_pct']}%")
        if r["confidence"] == "verified":
            lines.append(f"  结论  : 差价 < 15%，以 AI 价格 ¥{r['price_ai']:.4f} 为准")
        elif r["confidence"] == "suspicious":
            lines.append(f"  结论  : 差价 ≥ 15%，以 Playwright 实测价 ¥{r['price_realtime']:.4f} 覆盖")
        if r["laddered_prices"]:
            lines.append("  阶梯价:")
            for lp in r["laddered_prices"]:
                lines.append(f"    {lp['qty']}+ : ¥{lp['price']:.4f}")
    else:
        err = r.get("error", "未知错误")
        lines.append(f"  错误  : {err}")
        lines.append(f"  结论  : 保留 AI 价格，建议用户自行确认")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Step 2: Playwright 实时点验（验证 AI 搜索价格）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("keyword", help="待验证的元器件型号")
    parser.add_argument("--ai-price", type=float, required=True,
                        help="Step 1 AI 搜索返回的价格")
    parser.add_argument("-j", "--json", action="store_true", dest="json_output",
                        help="JSON 格式输出")
    args = parser.parse_args()

    result = verify(args.keyword, args.ai_price)

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_format_text(result))

    # 退出码：verified=0, suspicious=1, unverified=2
    exit_code = {"verified": 0, "suspicious": 1, "unverified": 2}
    sys.exit(exit_code.get(result["confidence"], 2))


if __name__ == "__main__":
    main()
