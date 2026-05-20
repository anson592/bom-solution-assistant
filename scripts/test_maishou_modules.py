import requests
import json

MAISHOU_API = "https://appapi.maishou88.com/api/v1/homepage/searchList"
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"}
SOURCE_MAP = {1: "淘宝", 2: "京东", 3: "拼多多", 7: "抖音", 10: "1688"}

CAMERA_MODULES = [
    "OV2640 摄像头模组",
    "OV5640 摄像头模组",
    "OV7670 摄像头模组",
    "GC2053 摄像头模组",
    "IMX307 摄像头模组",
    "IMX335 摄像头模组",
    "SC2232 摄像头模组",
    "AR0230 摄像头模组",
    "GC1054 摄像头模组",
    "OV13850 摄像头模组",
]

SCREEN_MODULES = [
    "ST7789 LCD模组",
    "ILI9341 TFT液晶模组",
    "SSD1306 OLED屏模组",
    "1.44寸TFT液晶模组",
    "2.4寸TFT触摸屏模组",
    "3.5寸IPS LCD模组",
    "7寸HDMI显示屏模组",
    "SH1106 OLED模组",
    "HX8357 TFT屏模组",
    "NT35510 LCD模组",
]

def search_price(keyword: str) -> list:
    try:
        resp = requests.post(
            MAISHOU_API,
            data={
                "keyword": keyword,
                "openid": "564bdce0fa408fc9e1d5d42fd022ef0b",
                "sourceType": 0,
                "page": 1,
                "order": "asc",
                "isCoupon": 0
            },
            headers=HEADERS,
            timeout=15
        )
        raw = resp.json()
        if isinstance(raw, list):
            return raw
        data = raw.get("data", raw)
        if isinstance(data, list):
            return data
        return data.get("list", [])
    except Exception as e:
        return [{"_error": str(e)}]

def get_best(items: list) -> dict:
    valid = [x for x in items if x.get("actualPrice") and not x.get("_error")]
    if not valid:
        return {}
    return min(valid, key=lambda x: float(x.get("actualPrice", 9999)))

def fmt_item(item: dict, keyword: str) -> str:
    if item.get("_error"):
        return f"  ❌ 请求失败: {item['_error']}"
    if not item:
        return "  ⚠️  无结果"
    platform = item.get("platformName") or SOURCE_MAP.get(item.get("platformId"), "未知")
    price = item.get("actualPrice", "?")
    orig  = item.get("originalPrice", "?")
    title = item.get("title", "")[:45]
    shop  = item.get("shopName", "")
    sales = item.get("monthSales", "?")
    total = item.get("_total", "?")
    return (
        f"  平台: {platform}  实价: ¥{price}  原价: ¥{orig}  月销: {sales}\n"
        f"  标题: {title}...\n"
        f"  店铺: {shop}  (共{total}条结果)"
    )

def run_group(label: str, keywords: list):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    for kw in keywords:
        items = search_price(kw)
        best  = get_best(items)
        if best:
            best["_total"] = len(items)
        print(f"\n🔍 [{kw}]")
        print(fmt_item(best, kw))

if __name__ == "__main__":
    run_group("摄像头模组 × 10", CAMERA_MODULES)
    run_group("屏幕模组 × 10", SCREEN_MODULES)
    print(f"\n{'='*60}")
    print("  测试完成")
    print(f"{'='*60}\n")
