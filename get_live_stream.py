# get_live_stream.py
"""
Function:
  - API stream & whitelist.txt -> group-title="本地节目"
  - 海燕.txt & 电视家.txt -> group-title="网络节目"
  - NO other sources
Output: live/current.m3u8
"""

import requests
import os
from urllib.parse import unquote
from datetime import datetime

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

# 远程源地址
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
HAIYAN_TXT_URL = "https://chuxinya.top/f/AD5QHE/%E6%B5%B7%E7%87%95.txt"
DIANSHIJIA_TXT_URL = "https://gitproxy.click/https://raw.githubusercontent.com/wujiangliu/live-sources/main/dianshijia_10.1.txt"

WHITELIST_TIMEOUT = 15
REQUEST_TIMEOUT = (5, 10)  # (connect, read)

# User-Agent for general requests
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


# ================== Utility Functions ==================
def is_url_valid(url):
    """Check if URL is accessible"""
    try:
        head = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=DEFAULT_HEADERS)
        return 200 <= head.status_code < 400
    except Exception as e:
        print(f"⚠️  Failed to check {url}: {e}")
        return False


def get_dynamic_stream():
    """Get dynamic stream from API"""
    print("👉 Fetching dynamic stream from API...")
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if is_url_valid(url):
                print(f"✅ Dynamic stream OK: {url}")
                return url
            else:
                print(f"❌ Stream not accessible: {url}")
        else:
            print("❌ m3u8Url not found in API response")
    except Exception as e:
        print(f"❌ API request failed: {e}")
    return None


def load_whitelist_from_remote():
    """All channels from whitelist.txt -> group-title="本地节目" """
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
            parts = [p.strip() for p in line.split(",", 1)]  # Split on first comma only
            if len(parts) < 2:
                continue

            name, url = parts[0], parts[1]
            if not name or not url:
                continue
            if not url.startswith(("http://", "https://")):
                continue

            channels.append((name, url, "本地节目"))
            print(f"  ➕ Whitelist: {name} -> 本地节目")

        print(f"✅ Loaded {len(channels)} from whitelist")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []


def load_haiyan_txt():
    """All channels from 海燕.txt -> group-title="网络节目" """
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

                channels.append((name, url, "网络节目"))
                print(f"  ➕ 海燕.txt: {name} -> 网络节目")

            except Exception as e:
                print(f"⚠️ Parse failed at line {line_num}: {line} | {e}")

        print(f"✅ Loaded {len(channels)} from 海燕.txt")
        return channels
    except Exception as e:
        print(f"❌ Load 海燕.txt failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_dianshijia_txt():
    """All channels from 电视家.txt -> group-title="网络节目" """
    print(f"👉 Loading 电视家.txt: {DIANSHIJIA_TXT_URL}")
    try:
        decoded_url = unquote(DIANSHIJIA_TXT_URL)
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

                channels.append((name, url, "网络节目"))
                print(f"  ➕ 电视家.txt: {name} -> 网络节目")

            except Exception as e:
                print(f"⚠️ Parse failed at line {line_num}: {line} | {e}")

        print(f"✅ Loaded {len(channels)} from 电视家.txt")
        return channels
    except Exception as e:
        print(f"❌ Load 电视家.txt failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def normalize_url(url):
    """Normalize URL for deduplication (remove token/timestamp)"""
    from urllib.parse import urlparse, parse_qs, urlunparse
    try:
        parsed = urlparse(url.lower())
        # Keep base path, remove volatile query params
        safe_params = {}
        for k, v in parse_qs(parsed.query).items():
            # Keep only stable params, remove token, t, ts, sign, etc.
            if k.lower() not in ['token', 't', 'ts', 'sign', 'auth_key', 'verify', 'session']:
                safe_params[k] = v[0] if v else ''
        new_query = '&'.join(f"{k}={v}" for k, v in safe_params.items() if v)
        return urlunparse(parsed._replace(query=new_query))
    except:
        return url.lower().split('?')[0]


def merge_and_deduplicate(channels):
    seen = set()
    unique = []
    for name, url, group in channels:
        norm_url = normalize_url(url)
        if norm_url not in seen:
            seen.add(norm_url)
            unique.append((name, url, group))
        else:
            print(f"🔁 Skipped duplicate: {url}")
    print(f"✅ Final unique streams: {len(unique)}")
    return unique


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

    all_channels.extend(load_whitelist_from_remote())  # -> 本地节目
    all_channels.extend(load_haiyan_txt())            # -> 网络节目
    all_channels.extend(load_dianshijia_txt())        # -> 网络节目

    unique_channels = merge_and_deduplicate(all_channels)
    m3u8_content = generate_m3u8_content(dynamic_url, unique_channels)

    output_path = 'live/current.m3u8'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 Successfully generated: {output_path}")
        print(f"📊 Total streams: {len(unique_channels) + (1 if dynamic_url else 0)}")
    except Exception as e:
        print(f"❌ Write failed: {e}")
        return

    # Ensure .nojekyll for GitHub Pages
    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("📄 Created .nojekyll")

    print("✅ All tasks completed!")


if __name__ == "__main__":
    main()
