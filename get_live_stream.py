# get_live_stream.py
"""
Function: Use ORIGINAL group-title from any source.
         - whitelist.txt: support name,group,url or name,url
         - 海燕.txt: same
         - result.m3u: keep original
         - DO NOT FORCE '本地节目' or '网络电视'
Output: live/current.m3u8
"""

import requests
import os
from urllib.parse import unquote

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
EXTERNAL_IPTV_URL = "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u
HAIYAN_TXT_URL = "https://chuxinya.top/f/AD5QHE/东北虎.txt"

WHITELIST_TIMEOUT = 15


# ================== Utility Functions ==================
def is_url_valid(url):
    try:
        head = requests.head(url, timeout=5, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        return head.status_code < 400
    except Exception as e:
        print(f"⚠️  Failed to check {url}: {e}")
        return False


def get_dynamic_stream():
    print("👉 Fetching dynamic stream from API...")
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
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
    """Support: name,url OR name,group,url"""
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
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue

            if len(parts) == 2:
                name, url = parts
                group = None  # ✅ 不设置 group-title
            else:
                name, group, url = parts[0], parts[1], parts[2]

            if not name or not url:
                continue
            if not url.startswith(("http://", "https://")):
                continue

            channels.append((name, url, group))
            group_str = f" | Group: {group}" if group else " | No group"
            print(f"  ➕ Whitelist: {name}{group_str}")

        print(f"✅ Loaded {len(channels)} from whitelist")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []


def load_haiyan_txt():
    """Support: name,url OR name,group,url"""
    print(f"👉 Loading 海燕.txt: {HAIYAN_TXT_URL}")
    try:
        decoded_url = unquote(HAIYAN_TXT_URL)
        print(f"🔍 Decoded URL: {decoded_url}")

        response = requests.get(decoded_url, timeout=WHITELIST_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        response.encoding = 'utf-8'

        lines = response.text.strip().splitlines()
        channels = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("更新时间"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                print(f"⚠️ Line {line_num} skipped: {line}")
                continue

            if len(parts) == 2:
                name, url = parts
                group = None  # ✅ 不强制归类
            else:
                name, group, url = parts[0], parts[1], parts[2]

            if not name or not url:
                continue
            if not url.startswith(("http://", "https://")):
                continue

            channels.append((name, url, group))
            group_str = f" | Group: {group}" if group else " | No group"
            print(f"  ➕ 海燕.txt: {name}{group_str}")

        print(f"✅ Loaded {len(channels)} from 海燕.txt")
        return channels
    except Exception as e:
        print(f"❌ Load 海燕.txt failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_external_iptv():
    """Keep original group-title from M3U"""
    print(f"👉 Loading external IPTV: {EXTERNAL_IPTV_URL}")
    try:
        response = requests.get(EXTERNAL_IPTV_URL, timeout=WHITELIST_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        lines = response.text.strip().splitlines()

        if lines:
            print(f"⏭️ Skipping first line: {lines[0]}")
            lines = lines[1:]

        channels = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                extinf = line
                group = None
                tvg_name = "Unknown"
                display_name = "Unknown"

                if 'group-title=' in extinf:
                    start = extinf.find('group-title="') + 13
                    end = extinf.find('"', start)
                    if end > start:
                        group = extinf[start:end]

                if 'tvg-name=' in extinf:
                    start = extinf.find('tvg-name="') + 10
                    end = extinf.find('"', start)
                    if end > start:
                        tvg_name = extinf[start:end]

                if ',' in extinf:
                    display_name = extinf.split(',', 1)[1].strip()

                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    if url.startswith("http"):
                        final_name = tvg_name if tvg_name != "Unknown" else display_name
                        channels.append((final_name, url, group))
                        group_str = f" | Group: {group}" if group else " | No group"
                        print(f"  ➕ External: {final_name}{group_str}")
            i += 1

        print(f"✅ Loaded {len(channels)} from external M3U")
        return channels
    except Exception as e:
        print(f"❌ Load external M3U failed: {e}")
        return []


def merge_and_deduplicate(channels):
    seen = set()
    unique = []
    for name, url, group in channels:
        norm_url = url.lower().split('?')[0]
        if norm_url not in seen:
            seen.add(norm_url)
            unique.append((name, url, group))
        else:
            print(f"🔁 Skipped duplicate: {url}")
    print(f"✅ Final unique streams: {len(unique)}")
    return unique


def generate_m3u8_content(dynamic_url, channels):
    lines = [
        "#EXTM3U",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    if dynamic_url:
        # 仅这个是本地节目，其他按源数据
        lines.append('#EXTINF:-1 tvg-name="西充综合" group-title="本地节目",西充综合')
        lines.append(dynamic_url)

    for name, url, group in channels:
        # ✅ 只有当 group 存在时才写入 group-title
        if group:
            lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        else:
            lines.append(f'#EXTINF:-1 tvg-name="{name}",{name}')
        lines.append(url)

    return "\n".join(lines) + "\n"


def main():
    print("🚀 Starting playlist generation...")
    os.makedirs('live', exist_ok=True)
    print("📁 Ensured live/ directory")

    dynamic_url = get_dynamic_stream()
    all_channels = []

    all_channels.extend(load_whitelist_from_remote())
    all_channels.extend(load_haiyan_txt())
    all_channels.extend(load_external_iptv())

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

    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("📄 Created .nojekyll")

    print("✅ All tasks completed!")


if __name__ == "__main__":
    main()

