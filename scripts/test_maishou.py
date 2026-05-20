import requests
import json

MAISHOU_API = "https://appapi.maishou88.com/api/v1/homepage/searchList"
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"}

SOURCE_MAP = {1: "淘宝", 2: "京东", 3: "拼多多", 7: "抖音", 10: "1688"}

def search_price(keyword: str, source_type: int = 0) -> list:
    resp = requests.post(
        MAISHOU_API,
        data={
            "keyword": keyword,
            "openid": "564bdce0fa408fc9e1d5d42fd022ef0b",
            "sourceType": source_type,
            "page": 1,
            "order": "asc",
            "isCoupon": 0
        },
        headers=HEADERS,
        timeout=15
    )
    raw = resp.json()
    # 兼容两种结构
    if isinstance(raw, list):
        return raw
    data = raw.get("data", raw)
    if isinstance(data, list):
        return data
    return data.get("list", [])

if __name__ == "__main__":
    kw = "STM32F103C8T6 单片机"
    print(f"搜索关键词: {kw}\n")
    items = search_price(kw)
    print(f"共返回 {len(items)} 条结果\n")

    # 打印前5条的关键字段
    print("=== 前5条结果（按价格升序） ===")
    for i, item in enumerate(items[:5], 1):
        platform_id = item.get("platformId", item.get("source"))
        platform_name = item.get("platformName") or SOURCE_MAP.get(platform_id, f"平台{platform_id}")
        actual_price = item.get("actualPrice", item.get("price"))
        original_price = item.get("originalPrice")
        title = item.get("title", "")[:40]
        sales = item.get("monthSales", item.get("sold", "N/A"))
        link = item.get("goodsUrl", item.get("url", ""))
        shop = item.get("shopName", "")

        print(f"[{i}] {platform_name} | 实际价: ¥{actual_price} (原价: ¥{original_price})")
        print(f"    标题: {title}...")
        print(f"    店铺: {shop} | 月销: {sales}")
        print(f"    链接: {link[:60] if link else '无'}")
        print()

    # 打印第一条完整字段（用于了解结构）
    print("=== 第1条完整字段 ===")
    if items:
        print(json.dumps(items[0], ensure_ascii=False, indent=2))
