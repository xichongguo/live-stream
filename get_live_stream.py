# File: get_live_stream.py
# Final version: 
#   - whitelist.txt → "本地节目" (top, no validation)
#   - Guovin IPTV → right after 本地节目
#   - other remote sources → with CCTV validation
#   - local.txt → normal category, no validation, appears last

import requests
import os
from urllib.parse import urlparse
from datetime import datetime
from collections import Counter
import re

# ================== Configuration ==================
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1',
    'centerId': '9',
    'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0',
    'areaId': '907',
    'appCenterId': '907',
    'isTest': '0',
    'longitudeValue': '0',
    'deviceVersionType': 'android',
    'versionCodeGlobal': '5009037'
}
HEADERS = {'User-Agent': 'okhttp/3.12.12'}

REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
GUOVIN_IPTV_URL = "https://cdn.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.txt"
BC_API_URL = "https://bc.188766.xyz/"
BC_PARAMS = {'ip': '', 'mima': 'bingchawusifengxian', 'json': 'true'}

LOCAL_TXT_PATH = "local.txt"

WHITELIST_TIMEOUT = 15
CHECK_TIMEOUT = 5
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")

# ---------------- 省份 & 分类映射 ----------------
PROVINCE_KEYWORDS = { ... }  # （此处省略，保留你原代码中的完整内容）
CATEGORY_MAP = { ... }       # （保留原内容）
EXCLUDE_IF_HAS = ['少儿', '卡通', '动漫', '游戏', '购物', '轮播']
FOREIGN_KEYWORDS = { ... }   # （保留原内容）
ALLOWED_FOREIGN = {'凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'}

# ================== Helper Functions ==================
def is_foreign_channel(name):
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    for kw in FOREIGN_KEYWORDS:
        if kw.lower() in name_lower:
            return True
    return False

def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

def normalize_cctv_name(name):
    CHINESE_ALIAS = { ... }  # （保留你原代码中的完整字典）
    if name in CHINESE_ALIAS:
        return CHINESE_ALIAS[name]
    for keyword, std in CHINESE_ALIAS.items():
        if keyword in name:
            return std
    match = re.search(r'CCTV\D*(\d+)', name.upper())
    if match:
        return f"CCTV-{int(match.group(1))}"
    return name

def categorize_channel(name):
    name_lower = name.lower()
    if any(kw in name_lower for kw in ['cctv', '中央']):
        return '央视', normalize_cctv_name(name)
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower:
            return '卫视', name
    for kw in CATEGORY_MAP['电影频道']:
        if kw.lower() in name_lower and not any(ex.lower() in name_lower for ex in EXCLUDE_IF_HAS):
            return '电影频道', name
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name:
            return '港澳台', name
    for kw in CATEGORY_MAP['经典剧场']:
        if kw in name:
            return '经典剧场', name
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name:
                return prov, name
    return "其他", name

def check_url_valid(url, timeout=CHECK_TIMEOUT):
    try:
        response = requests.head(url, timeout=timeout, headers=DEFAULT_HEADERS, allow_redirects=True)
        return response.status_code < 400
    except:
        try:
            response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS, stream=True)
            return response.status_code < 400
        except:
            return False

# ================== Load Sources ==================
def load_whitelist_as_local_program():
    print("👉 Loading whitelist.txt as '本地节目' (TOP)...")
    try:
        resp = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        lines = resp.text.strip().splitlines()
        channels = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2: continue
            name, url = parts[0], parts[1]
            if not name or not url or not is_valid_url(url): continue
            if is_foreign_channel(name): continue
            channels.append((name, url, "本地节目"))
        return channels
    except Exception as e:
        print(f"❌ Load whitelist.txt failed: {e}")
        return []

def load_guovin_iptv():
    print("👉 Loading Guovin IPTV (high priority)...")
    try:
        resp = requests.get(GUOVIN_IPTV_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        resp.encoding = 'utf-8'
        lines = resp.text.strip().splitlines()
        channels = []
        for line in lines:
            line = line.strip()
            if line.startswith("#") or "," not in line: continue
            name, url = map(str.strip, line.split(",", 1))
            if not name or not url or not is_valid_url(url): continue
            if is_foreign_channel(name): continue
            cat, disp = categorize_channel(name)
            channels.append((disp, url, cat))
        return channels
    except Exception as e:
        print(f"❌ Load Guovin failed: {e}")
        return []

def load_tv_m3u():
    try:
        resp = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        lines = resp.text.strip().splitlines()
        channels = []
        current_name = None
        for line in lines:
            if line.startswith("#EXTINF"):
                current_name = line.split(",", 1)[1].strip() if "," in line else "Unknown"
            elif line.startswith("http") and current_name:
                if is_valid_url(line) and not is_foreign_channel(current_name):
                    cat, disp = categorize_channel(current_name)
                    channels.append((disp, line, cat))
                current_name = None
        return channels
    except Exception as e:
        print(f"❌ Load tv.m3u failed: {e}")
        return []

def load_bc_api():
    try:
        resp = requests.get(BC_API_URL, params=BC_PARAMS, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        data = resp.json()
        channels = []
        for item in data.get("data", []):
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if name and url and is_valid_url(url) and not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                channels.append((disp, url, cat))
        return channels
    except Exception as e:
        print(f"❌ Load BC API failed: {e}")
        return []

def get_dynamic_stream():
    try:
        resp = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
        data = resp.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            name, url = "西充综合", data['data']['m3u8Url']
            if not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                return [(disp, url, cat)]
    except:
        pass
    return []

def load_local_txt():
    if not os.path.exists(LOCAL_TXT_PATH):
        return []
    channels = []
    try:
        with open(LOCAL_TXT_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2: continue
            name, url = parts[0], parts[1]
            if not name or not url or not is_valid_url(url): continue
            if is_foreign_channel(name): continue
            cat, disp = categorize_channel(name)
            channels.append((disp, url, cat))
    except Exception as e:
        print(f"❌ Read local.txt failed: {e}")
    return channels

# ================== Sort Logic ==================
def sort_channels(channels_with_source):
    ORDER = [
        '央视', '卫视',
        '四川', '广东', '湖南', '湖北', '江苏', '浙江', '山东', '河南', '河北', '福建', '广西', '云南', '江西', '辽宁',
        '山西', '陕西', '安徽', '黑龙江', '内蒙古', '吉林', '贵州', '甘肃', '海南', '青海', '宁夏', '新疆', '西藏',
        '电影频道', '港澳台', '经典剧场', '其他'
    ]

    def cctv_order(name):
        match = re.search(r'CCTV-(\d+)', name)
        return int(match.group(1)) if match else 999

    def sort_key(item):
        name, url, group, source_type = item
        if source_type == "whitelist":
            return (0, 0, name)  # 最前
        elif source_type == "guovin":
            return (1, 0, name)  # 第二
        elif source_type == "remote":
            group_idx = ORDER.index(group) if group in ORDER else 999
            if group == '央视':
                return (2, group_idx, cctv_order(name), name)
            else:
                return (2, group_idx, name)
        else:  # local.txt
            group_idx = ORDER.index(group) if group in ORDER else 999
            return (3, group_idx, name)

    return sorted(channels_with_source, key=sort_key)

# ================== Main ==================
def main():
    print("🚀 Generating playlist with correct priority order...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_items = []

    # 1. whitelist → "本地节目" (source_type="whitelist")
    for name, url, group in load_whitelist_as_local_program():
        all_items.append((name, url, group, "whitelist"))

    # 2. Guovin → high priority (source_type="guovin")
    for name, url, group in load_guovin_iptv():
        all_items.append((name, url, group, "guovin"))

    # 3. Other remote sources (source_type="remote")
    remote_channels = []
    remote_channels.extend(load_tv_m3u())
    remote_channels.extend(load_bc_api())
    remote_channels.extend(get_dynamic_stream())

    # Filter foreign & validate only remote CCTV
    for name, url, group in remote_channels:
        if group == '央视':
            if check_url_valid(url):
                all_items.append((name, url, group, "remote"))
            else:
                print(f"❌ Skipped invalid remote CCTV: {name}")
        else:
            all_items.append((name, url, group, "remote"))

    # 4. local.txt → source_type="local"
    for name, url, group in load_local_txt():
        all_items.append((name, url, group, "local"))

    # Sort
    sorted_items = sort_channels(all_items)

    # Stats
    stats = Counter(item[2] for item in sorted_items)
    print(f"\n📊 Total channels: {len(sorted_items)}")
    for cat, cnt in stats.most_common():
        print(f"   {cat:<10}: {cnt}")

    # Write M3U8
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["#EXTM3U", f"# Generated at: {now}", 'x-tvg-url="https://epg.51zmt.top/xmltv.xml"']
    for name, url, group, _ in sorted_items:
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        print(f"🎉 Output written to: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Write error: {e}")

    # For GitHub Pages
    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()

if __name__ == "__main__":
    main()
