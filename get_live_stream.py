# File: get_live_stream.py (Updated for "keep all, sort by source")
# Author: Assistant
# Date: 2025-11-16

import requests
import os
from urllib.parse import unquote, urlparse, parse_qs, urlunparse
from datetime import datetime
from collections import Counter, defaultdict
import time
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
HEADERS = {
    'User-Agent': 'okhttp/3.12.12',
}

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

# 来源优先级：数值越小，排序越靠前（但不去重！）
PRIORITY_LOCAL_TXT = 0      # 最靠前
PRIORITY_WHITELIST = 1
PRIORITY_DYNAMIC = 1
PRIORITY_OTHER = 1          # 所有非 local 都是 1

# 省份映射、分类规则、国外过滤等（保持不变，此处省略以节省篇幅）
# ⬇️ 以下为简化版，实际使用请保留完整映射表（见上一版本）
PROVINCE_KEYWORDS = { ... }  # 请从上一版本复制完整内容
CITY_TO_PROVINCE = {city: prov for prov, cities in PROVINCE_KEYWORDS.items() for city in cities}

CATEGORY_MAP = { ... }  # 请从上一版本复制
EXCLUDE_IF_HAS = [...]     # 请从上一版本复制
FOREIGN_KEYWORDS = {...}   # 请从上一版本复制
ALLOWED_FOREIGN = {...}    # 请从上一版本复制


def is_foreign_channel(name):
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    for keyword in FOREIGN_KEYWORDS:
        if keyword in name_lower:
            return True
    return False

def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

def normalize_cctv_name(name):
    CHINESE_ALIAS = {
        "中央一套": "CCTV-1", "综合频道": "CCTV-1",
        "中央二套": "CCTV-2", "财经频道": "CCTV-2",
        "中央三套": "CCTV-3", "综艺频道": "CCTV-3",
        "中央四套": "CCTV-4", "中文国际频道": "CCTV-4",
        "中央五套": "CCTV-5", "体育频道": "CCTV-5",
        "中央六套": "CCTV-6", "电影频道": "CCTV-6",
        "中央七套": "CCTV-7", "国防军事频道": "CCTV-7",
        "中央八套": "CCTV-8", "电视剧频道": "CCTV-8",
        "中央九套": "CCTV-9", "纪录频道": "CCTV-9",
        "中央十套": "CCTV-10", "科教频道": "CCTV-10",
        "中央十一套": "CCTV-11", "戏曲频道": "CCTV-11",
        "中央十二套": "CCTV-12", "社会与法频道": "CCTV-12",
        "中央十三套": "CCTV-13", "新闻频道": "CCTV-13",
        "中央十四套": "CCTV-14", "少儿频道": "CCTV-14",
        "中央十五套": "CCTV-15", "音乐频道": "CCTV-15",
        "中央十七套": "CCTV-17", "农业农村频道": "CCTV-17",
    }
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

# ========== 加载函数（全部返回四元组）==========
def load_whitelist():
    print(f"👉 Loading whitelist...")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        lines = response.text.strip().splitlines()
        channels = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2: continue
            name, url = parts[0], parts[1]
            if not name or not url or not is_valid_url(url): continue
            if is_foreign_channel(name): continue
            channels.append((name, url, "本地节目", PRIORITY_WHITELIST))
        return channels
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []

def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            name, url = "西充综合", data['data']['m3u8Url']
            if not is_foreign_channel(name):
                return (name, url, "本地节目", PRIORITY_DYNAMIC)
    except:
        pass
    return None

def load_tv_m3u():
    try:
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        lines = response.text.strip().splitlines()
        channels = []
        current_name = None
        for line in lines:
            if line.startswith("#EXTINF"):
                current_name = line.split(",", 1)[1].strip() if "," in line else "Unknown"
            elif line.startswith("http") and current_name:
                if is_valid_url(line) and not is_foreign_channel(current_name):
                    cat, disp = categorize_channel(current_name)
                    channels.append((disp, line, cat, PRIORITY_OTHER))
                current_name = None
        return channels
    except Exception as e:
        print(f"❌ Load tv.m3u failed: {e}")
        return []

def load_guovin_iptv():
    try:
        response = requests.get(GUOVIN_IPTV_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        channels = []
        for line in lines:
            if line.strip().startswith("#") or "," not in line: continue
            name, url = map(str.strip, line.split(",", 1))
            if is_valid_url(url) and not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                channels.append((disp, url, cat, PRIORITY_OTHER))
        return channels
    except Exception as e:
        print(f"❌ Load Guovin failed: {e}")
        return []

def load_bc_api():
    try:
        response = requests.get(BC_API_URL, params=BC_PARAMS, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        data = response.json()
        channels = []
        for item in data.get("data", []):
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if name and url and is_valid_url(url) and not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                channels.append((disp, url, cat, PRIORITY_OTHER))
        return channels
    except Exception as e:
        print(f"❌ Load BC API failed: {e}")
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
            channels.append((disp, url, cat, PRIORITY_LOCAL_TXT))
    except Exception as e:
        print(f"❌ Read local.txt failed: {e}")
    return channels

# ========== 关键：排序（不去重！）==========
def sort_channels_with_priority(channels):
    ORDER = [
        '本地节目', '央视', '卫视',
        '四川', '广东', '湖南', '湖北', '江苏', '浙江', '山东', '河南', '河北', '福建', '广西', '云南', '江西', '辽宁', '山西', '陕西', '安徽', '黑龙江', '内蒙古', '吉林', '贵州', '甘肃', '海南', '青海', '宁夏', '新疆', '西藏',
        '电影频道', '港澳台', '经典剧场'
    ]

    LOCAL_PRIORITY = {"西充综合": 0, "南充综合": 1, "南充科教生活": 2}

    def get_cctv_number(name):
        match = re.search(r'CCTV-(\d+)', name)
        return int(match.group(1)) if match else float('inf')

    def sort_key(item):
        name, url, group, priority = item
        group_order = ORDER.index(group) if group in ORDER else 999

        if group == '本地节目':
            local_order = LOCAL_PRIORITY.get(name, 999)
            return (priority, group_order, local_order, name)
        elif group == '央视':
            return (priority, group_order, get_cctv_number(name), name)
        else:
            return (priority, group_order, name)

    return sorted(channels, key=sort_key)

# ========== 主流程 ==========
def main():
    print("🚀 Starting playlist generation (keep all, sort by source)...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_channels = []

    # 加载所有源（全部保留）
    all_channels.extend(load_whitelist())
    dynamic = get_dynamic_stream()
    if dynamic: all_channels.append(dynamic)
    all_channels.extend(load_tv_m3u())
    all_channels.extend(load_guovin_iptv())
    all_channels.extend(load_bc_api())
    all_channels.extend(load_local_txt())  # 这些会被排到最前

    # 过滤国外（二次保险）
    filtered = [item for item in all_channels if not is_foreign_channel(item[0])]

    # 检测央视有效性（可选：你也可以跳过这步以保留更多源）
    valid_channels = []
    for item in filtered:
        name, url, group, priority = item
        if group == '央视':
            if check_url_valid(url):
                valid_channels.append(item)
            else:
                print(f"❌ Skipped invalid CCTV: {name}")
        else:
            valid_channels.append(item)

    # 排序：local.txt 优先
    sorted_channels = sort_channels_with_priority(valid_channels)

    # 统计
    stats = Counter(item[2] for item in sorted_channels)
    print(f"\n📊 Total channels: {len(sorted_channels)}")
    for cat, cnt in stats.most_common():
        print(f"   {cat:<10}: {cnt}")

    # 生成 M3U8（只取前三字段）
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["#EXTM3U", f"# Generated at: {now}", 'x-tvg-url="https://epg.51zmt.top/xmltv.xml"']
    for name, url, group, _ in sorted_channels:
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        print(f"🎉 Output written to: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Write error: {e}")

    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()

if __name__ == "__main__":
    main()
