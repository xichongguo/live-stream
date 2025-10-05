# get_live_stream.py
"""
Function: Fetch live stream from API + remote whitelist + external IPTV -> Generate M3U8 playlist (keep original groups)
Output file: live/current.m3u8
"""

import requests
import json
import os
from urllib.parse import urlparse, parse_qs

# ================== Configuration Section ==================

# [1. Dynamic Live Stream API Configuration]
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
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# [2. Remote Whitelist & External IPTV]
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
EXTERNAL_IPTV_URL = "https://cdn.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.txt"

WHITELIST_TIMEOUT = 15  # Increased timeout

# ================== Utility Functions ==================

def is_url_valid(url):
    """Check if URL is accessible (HEAD request)"""
    try:
        head = requests.head(url, timeout=5, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        return head.status_code < 400
    except Exception as e:
        print(f"Warning: Failed to check URL {url}: {e}")
        return False

def get_dynamic_stream():
    """Get m3u8 address from API"""
    print("👉 Sending request to live stream API...")
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            m3u8_url = data['data']['m3u8Url']
            if is_url_valid(m3u8_url):
                print(f"✅ Dynamic stream OK: {m3u8_url}")
                return m3u8_url
            else:
                print(f"❌ Dynamic stream not accessible: {m3u8_url}")
        else:
            print("❌ 'data.m3u8Url' not found in API response")
            print("Raw response:", response.text[:500])
    except Exception as e:
        print(f"❌ API request failed: {e}")
    return None

def load_whitelist_from_remote():
    """Load whitelist.txt -> (name, url, group=None)"""
    print(f"👉 Loading remote whitelist: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        whitelist = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "," not in line:
                continue
            try:
                name, url = map(str.strip, line.split(",", 1))
                if not name or not url:
                    continue
                if not url.startswith(("http://", "https://")):
                    continue
                whitelist.append((f"Remote-{name}", url, None))
            except Exception as e:
                print(f"⚠️ Parse whitelist line failed: {line} | {e}")
        print(f"✅ Loaded {len(whitelist)} from whitelist")
        return whitelist
    except Exception as e:
        print(f"❌ Failed to load whitelist: {e}")
        return []

def load_external_iptv():
    """Load result.txt with robust M3U parsing"""
    print(f"👉 Loading external IPTV: {EXTERNAL_IPTV_URL}")
    try:
        # Use raw.githubusercontent.com for faster access
        raw_url = EXTERNAL_IPTV_URL.replace("cdn.jsdelivr.net/gh", "raw.githubusercontent.com").replace("@", "/")
        print(f"Using raw URL: {raw_url}")
        response = requests.get(raw_url, timeout=WHITELIST_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()

        lines = response.text.strip().splitlines()
        channels = []
        current_group = "Other"
        current_tvg_name = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                # Extract group-title and tvg-name
                extinf = line
                group = "Other"
                tvg_name = None
                display_name = ""

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

                # Extract channel name after comma
                if ',' in extinf:
                    display_name = extinf.split(',', 1)[1].strip()

                # Look ahead for URL
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    if url.startswith("http"):
                        # Use tvg-name > display_name > fallback
                        final_name = tvg_name or display_name or "Unknown"
                        channels.append((f"External-{group}-{final_name}", url, group))
                        print(f"  ➕ Added: {final_name} | Group: {group} | {url[:60]}...")
            i += 1

        print(f"✅ Loaded {len(channels)} channels from external IPTV")
        return channels
    except Exception as e:
        print(f"❌ Failed to load or parse external IPTV: {e}")
        import traceback
        traceback.print_exc()
        return []

def merge_and_deduplicate(channels):
    """Deduplicate by URL (ignore case and params)"""
    seen_urls = set()
    unique_list = []
    for name, url, group in channels:
        # Normalize URL: lowercase, remove params if needed
        normalized = url.lower().split('?')[0]
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            unique_list.append((name, url, group))
        else:
            print(f"🔁 Skipped duplicate: {url}")
    print(f"✅ After deduplication: {len(unique_list)} unique streams")
    return unique_list

def generate_m3u8_content(dynamic_url, channels):
    """Generate M3U8 content"""
    lines = [
        "#EXTM3U",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    if dynamic_url:
        lines.append('#EXTINF:-1 tvg-name="西充综合" group-title="本地节目",西充综合')
        lines.append(dynamic_url)

    for name, url, group in channels:
        clean_name = name.split("-", 2)[-1] if name.count("-") >= 2 else name
        group = group or "其他"
        lines.append(f'#EXTINF:-1 tvg-name="{clean_name}" group-title="{group}",{clean_name}')
        lines.append(url)

    return "\n".join(lines) + "\n"

def main():
    print("🚀 Starting playlist generation...")

    os.makedirs('live', exist_ok=True)
    print("📁 Ensured live/ directory exists")

    dynamic_url = get_dynamic_stream()

    all_channels = []

    # Load sources
    all_channels.extend(load_whitelist_from_remote())
    all_channels.extend(load_external_iptv())

    unique_channels = merge_and_deduplicate(all_channels)

    m3u8_content = generate_m3u8_content(dynamic_url, unique_channels)

    output_path = 'live/current.m3u8'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 Successfully wrote {output_path}")
        print(f"📊 Total streams: {len(unique_channels) + (1 if dynamic_url else 0)}")
    except Exception as e:
        print(f"❌ Failed to write file: {e}")
        return

    # Create .nojekyll
    nojekyll = '.nojekyll'
    if not os.path.exists(nojekyll):
        open(nojekyll, 'w').close()
        print(f"📄 Created {nojekyll}")

    print("✅ All tasks completed!")

if __name__ == "__main__":
    main()
