# get_live_stream.py
"""
Function: Fetch live stream from API + remote whitelist + external IPTV (M3U) -> Generate M3U8 playlist
Output file: live/current.m3u8
"""

import requests
import json
import os
from urllib.parse import urlparse

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
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# --- Updated to M3U file ---
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
EXTERNAL_IPTV_URL = "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u"  # ✅ Changed to .m3u

WHITELIST_TIMEOUT = 15

# ================== Utility Functions ==================

def is_url_valid(url):
    """Check if URL is accessible"""
    try:
        head = requests.head(url, timeout=5, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        return head.status_code < 400
    except Exception as e:
        print(f"⚠️  Failed to check {url}: {e}")
        return False

def get_dynamic_stream():
    """Get dynamic stream from API"""
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
            print("Raw:", response.text[:300])
    except Exception as e:
        print(f"❌ API request failed: {e}")
    return None

def load_whitelist_from_remote():
    """Load whitelist.txt -> (name, url, group=None)"""
    print(f"👉 Loading whitelist: {REMOTE_WHITELIST_URL}")
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
                print(f"⚠️ Parse whitelist failed: {line} | {e}")
        print(f"✅ Loaded {len(whitelist)} from whitelist")
        return whitelist
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []

def load_external_iptv():
    """Load result.m3u with standard M3U parsing"""
    print(f"👉 Loading external IPTV M3U: {EXTERNAL_IPTV_URL}")
    try:
        response = requests.get(EXTERNAL_IPTV_URL, timeout=WHITELIST_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        
        channels = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                # Parse EXTINF line
                extinf = line
                group = "Other"
                tvg_name = "Unknown"
                display_name = "Unknown"
                
                # Extract group-title
                if 'group-title=' in extinf:
                    start = extinf.find('group-title="') + 13
                    end = extinf.find('"', start)
                    if end > start:
                        group = extinf[start:end]
                
                # Extract tvg-name
                if 'tvg-name=' in extinf:
                    start = extinf.find('tvg-name="') + 10
                    end = extinf.find('"', start)
                    if end > start:
                        tvg_name = extinf[start:end]
                
                # Extract display name
                if ',' in extinf:
                    display_name = extinf.split(',', 1)[1].strip()
                
                # Next line is URL
                i += 1
                if i < len(lines):
                    url_line = lines[i].strip()
                    if url_line.startswith("http"):
                        final_name = tvg_name if tvg_name != "Unknown" else display_name
                        channels.append((f"External-{group}-{final_name}", url_line, group))
                        print(f"  ➕ Added: {final_name} | Group: {group}")
            i += 1
        
        print(f"✅ Successfully loaded {len(channels)} channels from external M3U")
        return channels
    except Exception as e:
        print(f"❌ Failed to load/parse external M3U: {e}")
        import traceback
        traceback.print_exc()
        return []

def merge_and_deduplicate(channels):
    """Deduplicate by normalized URL"""
    seen = set()
    unique = []
    for name, url, group in channels:
        norm_url = url.lower().split('?')[0]
        if norm_url not in seen:
            seen.add(norm_url)
            unique.append((name, url, group))
        else:
            print(f"🔁 Skipped duplicate: {url}")
    print(f"✅ Deduplicated: {len(unique)} unique streams")
    return unique

def generate_m3u8_content(dynamic_url, channels):
    """Generate final M3U8"""
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
    print("📁 Created live/ directory")
    
    dynamic_url = get_dynamic_stream()
    all_channels = []
    
    all_channels.extend(load_whitelist_from_remote())
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
    
    print("✅ All done!")

if __name__ == "__main__":
    main()
