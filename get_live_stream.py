"""
File: get_live_stream.py
Function:
  - API & whitelist.txt -> group-title="本地节目"
  - 海燕.txt & 电视家.txt -> 自动分类: 央视 / 卫视 / 地方 / 其他
  - 过滤失效源 + 仅保留 IPv4 源
  - 取消 "网络节目"、"网络源2" 等泛分类
Output: live/current.m3u8
"""

import requests
import os
import socket
from urllib.parse import unquote, urlparse, parse_qs, urlunparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


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

# Remote sources
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
HAIYAN_TXT_URL = "https://chuxinya.top/f/AD5QHE/%E6%B5%B7%E7%87%95.txt"
DIANSHIJIA_TXT_URL = "https://gitproxy.click/https://github.com/wujiangliu/live-sources/blob/main/dianshijia_10.1.txt"

WHITELIST_TIMEOUT = 15
REQUEST_TIMEOUT = (5, 10)
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Channel category rules
CATEGORY_MAP = {
    '央视': ['cctv', '中央'],
    '卫视': [
        '卫视', '湖南', '浙江', '江苏', '东方', '北京', '广东', '深圳', '四川', '湖北', '辽宁',
        '东南', '天津', '重庆', '黑龙江', '山东', '安徽', '云南', '陕西', '甘肃', '新疆',
        '内蒙古', '吉林', '河北', '山西', '广西', '江西', '福建', '贵州', '海南'
    ],
    '地方': [
        '都市', '新闻', '综合', '公共', '生活', '影视频道', '影视', '电视剧', '娱乐',
        '少儿', '卡通', '体育', '财经', '纪实', '教育', '民生', '交通', '文艺', '音乐',
        '戏曲', '高尔夫', '网球'
    ]
}


# ================== Utility Functions ==================
def is_ipv4_address(ip):
    """Check if the given string is a valid IPv4 address."""
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except (socket.error, TypeError):
        return False


def get_ip_version(url):
    """
    Resolve domain in URL to IP, return 'ipv4' or 'ipv6'
    Returns 'unknown' if failed.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.split(':')[0]  # Remove port
        addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
        for info in addr_info:
            ip = info[4][0]
            if is_ipv4_address(ip):
                return 'ipv4'
        return 'ipv6'  # Should not reach here if only AF_INET
    except Exception as e:
        print(f"⚠️ DNS resolve failed for {url}: {e}")
        return 'unknown'


def is_url_valid(url, check_ipv4=True):
    """
    Check if stream is accessible AND (optionally) uses IPv4.
    Returns (is_valid, ip_version)
    """
    try:
        # Step 1: Check IPv4
        if check_ipv4:
            ip_ver = get_ip_version(url)
            if ip_ver != 'ipv4':
                print(f"🚫 IPv6 or DNS fail: {url} -> {ip_ver}")
                return False, ip_ver

        # Step 2: HEAD request
        head = requests.head(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers=DEFAULT_HEADERS
        )
        success = 200 <= head.status_code < 400
        if success:
            print(f"✅ Live OK: {url}")
        else:
            print(f"❌ Stream dead ({head.status_code}): {url}")
        return success, 'ipv4' if success else 'unknown'

    except Exception as e:
        print(f"❌ Failed to play {url}: {e}")
        return False, 'unknown'


def normalize_url(url):
    """Remove tracking/query params for deduplication."""
    try:
        parsed = urlparse(url.lower())
        safe_params = {}
        unsafe_keys = {'token', 't', 'ts', 'sign', 'auth_key', 'verify', 'session', 'key', 'pwd'}
        for k, v in parse_qs(parsed.query).items():
            if k.lower() not in unsafe_keys:
                safe_params[k] = v[0] if v else ''
        new_query = '&'.join(f"{k}={v}" for k, v in safe_params.items() if v)
        return urlunparse(parsed._replace(query=new_query))
    except:
        return url.lower().split('?')[0]


def merge_and_deduplicate(channels):
    """Remove duplicates based on normalized URL."""
    seen = set()
    unique = []
    for name, url, group in channels:
        norm_url = normalize_url(url)
        if norm_url not in seen:
            seen.add(norm_url)
            unique.append((name, url, group))
        else:
            print(f"🔁 Skipped duplicate: {url}")
    print(f"✅ After dedup: {len(unique)} unique streams")
    return unique


def categorize_channel(name):
    """Auto categorize channel by name."""
    name_lower = name.lower()
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                return category
    return "其他"


def load_whitelist_from_remote():
    """Load whitelist -> 本地节目"""
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
            if not name or not url or not url.startswith(("http://", "https://")):
                continue
            channels.append((name, url, "本地节目"))
            print(f"  ➕ Whitelist: {name} -> 本地节目")
        print(f"✅ Loaded {len(channels)} from whitelist")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []


def load_haiyan_txt():
    """Load 海燕.txt -> auto categorize"""
    print(f"👉 Loading 海燕.txt: {HAIYAN_TXT_URL}")
    try:
        decoded_url = unquote(HAIYAN_TXT_URL)
        print(f"🔍 Decoded URL: {decoded_url}")
        response = requests.get(decoded_url, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        channels = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("更新时间") or line.startswith("TV"):
                continue
            if "," not in line:
                print(f"⚠️ Line {line_num} skipped (no comma): {line}")
                continue

            try:
                name, url = map(str.strip, line.split(",", 1))
                if not name or not url:
                    continue
                if not url.startswith(("http://", "https://")):
                    continue
                category = categorize_channel(name)
                channels.append((name, url, category))
                print(f"  ➕ 海燕.txt: {name} -> {category}")
            except Exception as e:
                print(f"⚠️ Parse failed at line {line_num}: {line} | {e}")

        print(f"✅ Loaded {len(channels)} from 海燕.txt")
        return channels
    except Exception as e:
        print(f"❌ Load 海燕.txt failed: {e}")
        return []


def load_dianshijia_txt():
    """Load 电视家.txt -> auto categorize"""
    print(f"👉 Loading 电视家.txt: {DIANSHIJIA_TXT_URL}")
    try:
        raw_url = DIANSHIJIA_TXT_URL.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        print(f"🔧 Converting to raw URL: {raw_url}")
        response = requests.get(raw_url, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        channels = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("更新时间") or line.startswith("TV"):
                continue
            if "," not in line:
                print(f"⚠️ Line {line_num} skipped (no comma): {line}")
                continue

            try:
                name, url = map(str.strip, line.split(",", 1))
                if not name or not url:
                    continue
                if not url.startswith(("http://", "https://")):
                    continue
                category = categorize_channel(name)
                channels.append((name, url, category))
                print(f"  ➕ 电视家.txt: {name} -> {category}")
            except Exception as e:
                print(f"⚠️ Parse failed at line {line_num}: {line} | {e}")

        print(f"✅ Loaded {len(channels)} from 电视家.txt")
        return channels
    except Exception as e:
        print(f"❌ Load 电视家.txt failed: {e}")
        return []


def filter_and_test_streams(channels, max_workers=10):
    """Concurrently test streams and keep only valid IPv4 ones."""
    print(f"🔍 Testing {len(channels)} streams (IPv4 + alive check)...")
    valid_channels = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(is_url_valid, url, True): (name, url, group)
            for name, url, group in channels
        }

        for future in as_completed(future_to_item):
            (name, url, group) = future_to_item[future]
            try:
                is_valid, ip_ver = future.result()
                if is_valid:
                    valid_channels.append((name, url, group))
            except Exception as e:
                print(f"⚠️ Exception during test {url}: {e}")

    print(f"✅ After testing: {len(valid_channels)} valid IPv4 streams")
    return valid_channels


def generate_m3u8_content(dynamic_url, channels):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "#EXTM3U",
        f"# Generated at: {now}",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    if dynamic_url:
        lines.append('#EXTINF:-1 tvg-name="西充综合" group-title="本地节目",西充综合')
        lines.append(dynamic_url)

    for name, url, group in channels:
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)

    return "\n".join(lines) + "\n"


def main():
    print("🚀 Starting playlist generation...")
    os.makedirs('live', exist_ok=True)
    print("📁 Ensured live/ directory")

    dynamic_url = get_dynamic_stream()
    all_channels = []

    all_channels.extend(load_whitelist_from_remote())  # 本地节目
    all_channels.extend(load_haiyan_txt())            # 自动分类
    all_channels.extend(load_dianshijia_txt())        # 自动分类

    print(f"📥 Total raw streams: {len(all_channels)}")

    # ✅ Step 1: 去重
    unique_channels = merge_and_deduplicate(all_channels)

    # ✅ Step 2: 检测有效性 + 过滤 IPv4
    valid_ipv4_channels = filter_and_test_streams(unique_channels, max_workers=15)

    # ✅ 生成 M3U8
    m3u8_content = generate_m3u8_content(dynamic_url, valid_ipv4_channels)

    output_path = 'live/current.m3u8'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 Successfully generated: {output_path}")
        print(f"📊 Total valid IPv4 streams: {len(valid_ipv4_channels) + (1 if dynamic_url else 0)}")
    except Exception as e:
        print(f"❌ Write failed: {e}")
        return

    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("📄 Created .nojekyll")

    print("✅ All tasks completed!")


def get_dynamic_stream():
    """Fetch dynamic stream from API."""
    print("👉 Fetching dynamic stream from API...")
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if is_url_valid(url)[0]:
                print(f"✅ Dynamic stream OK: {url}")
                return url
            else:
                print(f"❌ Stream not accessible: {url}")
        else:
            print("❌ m3u8Url not found in API response")
    except Exception as e:
        print(f"❌ API request failed: {e}")
    return None


if __name__ == "__main__":
    main()
