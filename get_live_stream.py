# File: get_live_stream.py
# Description: 抓取多源直播流，智能分类 + 央视有效性检测 + 白名单优先
# Author: Assistant
# Date: 2025-11-03

import requests
import os
from urllib.parse import unquote, urlparse, parse_qs, urlunparse
from datetime import datetime
from collections import Counter
import time


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

# --- 源地址更新 ---
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
GUOVIN_IPTV_URL = "https://cdn.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.txt"

WHITELIST_TIMEOUT = 15
CHECK_TIMEOUT = 5
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")


# ---------------- 分类规则 ----------------
CATEGORY_MAP = {
    '央视': ['cctv', '中央'],
    '卫视': ['卫视', '湖南', '浙江', '江苏', '东方', '北京', '广东', '深圳', '四川', '湖北', '辽宁',
             '东南', '天津', '重庆', '黑龙江', '山东', '安徽', '云南', '陕西', '甘肃', '新疆',
             '内蒙古', '吉林', '河北', '山西', '广西', '江西', '福建', '贵州', '海南'],
    '轮播频道': [
        '电视剧', '电影', '影院', '影视频道', '影视', '精选', '轮播', '回看', '重温',
        '经典', '怀旧', '剧场', '大片', '热播', '点播', '虎牙', '斗鱼', '直播+',
        'LIVE', 'live', '4K', '8K', '超清', '高清', '标清', '频道', '测试',
        '变形金刚', '复仇者联盟', '速度与激情', '碟中谍', '哈利波特',
        '星球大战', '侏罗纪公园', '泰坦尼克号', '阿凡达', '盗梦空间',
        '西游记', '鹿鼎记', '寻秦记', '大唐双龙传', '天龙八部',
        '射雕英雄传', '神雕侠侣', '倚天屠龙记', '笑傲江湖', '雪山飞狐',
        '甄嬛传', '琅琊榜', '庆余年', '狂飙', '人民的名义'
    ],
    '地方': ['都市', '新闻', '综合', '公共', '生活', '娱乐',
             '少儿', '卡通', '体育', '财经', '纪实', '教育', '民生', '交通', '文艺', '音乐',
             '戏曲', '高尔夫', '网球']
}

EXCLUDE_IF_HAS = ['综合', '新闻', '生活', '少儿', '公共', '交通', '文艺', '音乐', '戏曲', '体育', '财经', '教育', '民生', '都市']


# ---------------- 国外过滤 ----------------
FOREIGN_KEYWORDS = {
    'cnn', 'bbc', 'fox', 'espn', 'disney', 'hbo', 'nat geo', 'national geographic',
    'animal planet', 'mtv', 'paramount', 'pluto tv', 'sky sports', 'eurosport',
    'al jazeera', 'france 24', 'rt', 'nhk', 'kbs', 'tvb', 'abema', 'tokyo',
    'discovery', 'history', 'lifetime', 'syfy', 'tnt', 'usa network',
    'nickelodeon', 'cartoon network', 'boomerang', 'babyfirst', 'first channel',
    'russia', 'germany', 'italy', 'spain', 'france', 'uk', 'united kingdom',
    'canada', 'australia', 'new zealand', 'india', 'pakistan', 'japan', 'south korea'
}

ALLOWED_FOREIGN = {
    '凤凰', '凤凰卫视', '凤凰中文', '凤凰资讯', 'ATV', '亚洲电视', '星空', 'Channel [V]',
    '华娱', 'CCTV大富', 'CCTV-4', 'CCTV4', '中国中央电视台', '国际台', 'CGTN', 'CCTV西班牙语', 'CCTV法语',
    '香港', '澳门', '台湾', 'TVB', '翡翠台', '明珠台', 'J2', '无线', '亚视', 'ATV',
    '中天', '东森', '三立', '民视', '公视', '台视', '中视'
}


# ================== Utility Functions ==================
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


def normalize_url(url):
    try:
        parsed = urlparse(url.strip().lower())
        if not parsed.scheme or not parsed.netloc:
            return ""
        safe_params = {}
        unsafe_keys = {'token', 't', 'ts', 'sign', 'auth_key', 'verify', 'session', 'key', 'pwd', 'stb', 'icpid', 'RTS', 'from', 'hms_devid', 'online', 'vqe', 'txSecret', 'txTime', 'stat', 'wsSecret', 'wsTime', 'j', 'authid', 'playlive'}
        for k, v_list in parse_qs(parsed.query).items():
            if k.lower() not in unsafe_keys and v_list and v_list[0]:
                safe_params[k] = v_list[0]
        new_query = '&'.join(f"{k}={v}" for k, v in safe_params.items())
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url.lower().split('?')[0]


def merge_and_deduplicate(channels):
    seen = set()
    unique = []
    for item in channels:
        name, url, group = item
        norm_url = normalize_url(url)
        if norm_url and norm_url not in seen:
            seen.add(norm_url)
            unique.append(item)
    print(f"✅ After dedup: {len(unique)} unique streams")
    return unique


def categorize_channel(name):
    name_lower = name.lower()

    # 强制央视
    if 'cctv' in name_lower or '中央' in name_lower:
        return '央视'

    # 匹配卫视
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower:
            return '卫视'

    # 匹配轮播，但排除“综合”等
    for kw in CATEGORY_MAP['轮播频道']:
        if kw.lower() in name_lower:
            if any(ex.lower() in name_lower for ex in EXCLUDE_IF_HAS):
                continue
            return '轮播频道'

    # 匹配地方
    for kw in CATEGORY_MAP['地方']:
        if kw.lower() in name_lower:
            return '地方'

    return "其他"


def check_url_valid(url, timeout=CHECK_TIMEOUT):
    """检测URL是否可访问（用于央视源）"""
    try:
        response = requests.head(url, timeout=timeout, headers=DEFAULT_HEADERS, allow_redirects=True)
        return response.status_code < 400
    except:
        try:
            response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS, stream=True)
            return response.status_code < 400
        except:
            return False


def load_whitelist():
    """加载白名单，直接作为“本地节目”，保留原始顺序"""
    print(f"👉 Loading whitelist: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        channels = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2:
                continue
            name, url = parts[0], parts[1]
            if not name or not url or not is_valid_url(url):
                continue
            if is_foreign_channel(name):
                print(f"🌍 Skipped foreign (whitelist): {name}")
                continue
            channels.append((name, url, "本地节目"))  # 直接分类
        print(f"✅ Loaded {len(channels)} from whitelist (as '本地节目')")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []


def load_tv_m3u():
    print(f"👉 Loading tv.m3u: {TV_M3U_URL}")
    try:
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        channels = []
        current_name = None

        for line in lines:
            line = line.strip()
            if line.startswith("#EXTINF"):
                try:
                    name_part = line.split(",", 1)
                    if len(name_part) > 1:
                        current_name = name_part[1].strip()
                except:
                    current_name = "Unknown"
            elif line.startswith("http"):
                if current_name and is_valid_url(line):
                    if is_foreign_channel(current_name):
                        print(f"🌍 Skipped foreign (tv.m3u): {current_name}")
                    else:
                        category = categorize_channel(current_name)
                        channels.append((current_name, line, category))
                current_name = None
        print(f"✅ Loaded {len(channels)} from tv.m3u")
        return channels
    except Exception as e:
        print(f"❌ Failed to load tv.m3u: {e}")
        return []


def load_guovin_iptv():
    """加载 Guovin 的 result.txt"""
    print(f"👉 Loading Guovin IPTV: {GUOVIN_IPTV_URL}")
    try:
        response = requests.get(GUOVIN_IPTV_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        channels = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "," not in line:
                continue
            try:
                name, url = map(str.strip, line.split(",", 1))
                if not name or not url or not is_valid_url(url):
                    continue
                if is_foreign_channel(name):
                    print(f"🌍 Skipped foreign (Guovin): {name}")
                    continue
                category = categorize_channel(name)
                channels.append((name, url, category))
            except Exception as e:
                print(f"⚠️ Parse failed: {line} | {e}")
        print(f"✅ Loaded {len(channels)} from Guovin")
        return channels
    except Exception as e:
        print(f"❌ Load Guovin failed: {e}")
        return []


def get_dynamic_stream():
    print("👉 Fetching dynamic stream from API...")
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            name = "西充综合"
            if is_foreign_channel(name):
                print("🌍 Skipped foreign (API)")
                return None
            print(f"✅ Dynamic stream added: {name}")
            return (name, url, "本地节目")  # 动态流也归为本地
        else:
            print("❌ m3u8Url not found in API response")
    except Exception as e:
        print(f"❌ API request failed: {e}")
    return None


def check_cctv_validity(channels):
    """检测所有央视源是否有效，无效则跳过"""
    print("🔍 Checking CCTV stream validity...")
    valid_channels = []
    cctv_count = 0
    for item in channels:
        name, url, group = item
        if group == '央视':
            cctv_count += 1
            if check_url_valid(url):
                valid_channels.append(item)
                print(f"  ✅ Valid: {name}")
            else:
                print(f"  ❌ Invalid: {name}")
        else:
            valid_channels.append(item)
    print(f"✅ {cctv_count} CCTV streams checked.")
    return valid_channels


def generate_m3u8_content(channels):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "#EXTM3U",
        f"# Generated at: {now}",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    # 自定义排序权重
    ORDER = {
        '本地节目': 0,
        '央视': 1,
        '卫视': 2,
        '轮播频道': 3,
        '其他': 4,
        '地方': 5
    }

    def sort_key(item):
        group = item[2]
        order = ORDER.get(group, 99)
        return (order, group, item[0])  # 按组排序，组内按名称排序

    sorted_channels = sorted(channels, key=sort_key)

    for name, url, group in sorted_channels:
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)

    return "\n".join(lines) + "\n"


def print_stats(channels):
    stats = Counter(item[2] for item in channels)
    print("\n📊 分类统计：")
    for cat, cnt in stats.most_common():
        print(f"   {cat:<10} : {cnt}")
    print(f"   {'总计':<10} : {sum(stats.values())}")


def main():
    print("🚀 Starting playlist generation...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_channels = []

    # === 1. 加载白名单（本地节目，保留顺序）===
    whitelist_channels = load_whitelist()
    all_channels.extend(whitelist_channels)

    # === 2. 动态流（也归为本地）===
    dynamic_item = get_dynamic_stream()
    if dynamic_item:
        all_channels.append(dynamic_item)

    # === 3. 其他源 ===
    all_channels.extend(load_tv_m3u())
    all_channels.extend(load_guovin_iptv())

    print(f"📥 Total raw streams: {len(all_channels)}")

    # 去重
    unique_channels = merge_and_deduplicate(all_channels)

    # 过滤国外
    filtered_channels = [item for item in unique_channels if not is_foreign_channel(item[0])]

    # 检测央视有效性
    final_channels = check_cctv_validity(filtered_channels)

    print(f"✅ Final playlist size: {len(final_channels)} channels")

    print_stats(final_channels)

    m3u8_content = generate_m3u8_content(final_channels)

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 Successfully generated: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Write failed: {e}")
        return

    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("📄 Created .nojekyll")

    print("✅ All tasks completed!")


if __name__ == "__main__":
    main()
