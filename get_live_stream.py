# get_live_stream.py
"""
Live Stream Generator
- Fetch dynamic stream from API
- Load local and remote whitelist
- Validate stream availability
- Generate M3U8 playlist with groups and logos
- Generate HTML player page
Outputs:
  live/current.m3u8
  live/index.html
"""

import requests
import time
import json
import os
from urllib.parse import urlparse

# ================== Configuration ==================

# [1] Dynamic stream API
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

# [2] Whitelist URLs
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"

# [3] Local whitelist (name, url, group, logo)
LOCAL_WHITELIST = [
    ("Local-Test", "http://example.com/test.m3u8", "Test", "https://via.placeholder.com/16"),
    ("Apple-HLS", "http://devstreaming.apple.com/videos/streaming/examples/bipbop_4x3/gear1/prog_index.m3u8", "Demo", "https://devstreaming-cdn.apple.com/images/logo.png"),
]

# [4] Stream validation settings
CHECK_TIMEOUT = 5
CHECK_RETRIES = 1
VALIDATION_METHOD = "HEAD"  # HEAD or GET
DEFAULT_LOGO = "https://via.placeholder.com/16"

# ================== Core Functions ==================

def get_dynamic_stream():
    """Fetch dynamic stream from API"""
    print("📡 Fetching dynamic stream from API...")
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            print(f"✅ Dynamic stream fetched: {url}")
            return ("Dynamic-Stream", url, "Dynamic", "https://cdn-icons-png.flaticon.com/16/126/126472.png")
        else:
            print("❌ API response missing m3u8Url field")
    except Exception as e:
        print(f"❌ Failed to fetch dynamic stream: {e}")
    return None

def load_remote_whitelist():
    """Load remote whitelist: name,url,group,logo (last two optional)"""
    print(f"🌐 Loading remote whitelist: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=10)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        result = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                print(f"⚠️ Line {line_num} invalid (need at least name,url): {line}")
                continue
            name, url = parts[0], parts[1]
            group = parts[2] if len(parts) > 2 else "Other"
            logo = parts[3] if len(parts) > 3 else DEFAULT_LOGO
            if url.startswith(("http://", "https://")):
                result.append((f"Remote-{name}", url, group, logo))
        print(f"✅ Loaded {len(result)} remote streams")
        return result
    except Exception as e:
        print(f"❌ Failed to load remote whitelist: {e}")
        return []

def is_stream_valid(url):
    """Check if stream is accessible"""
    for _ in range(CHECK_RETRIES + 1):
        try:
            method = 'HEAD' if VALIDATION_METHOD == "HEAD" else 'GET'
            resp = requests.request(
                method, url,
                timeout=CHECK_TIMEOUT,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            if resp.status_code < 400:
                return True
        except Exception as e:
            pass
        time.sleep(0.5)
    return False

def validate_streams(stream_list):
    """Validate all streams and return only valid ones"""
    print("🔍 Validating stream URLs...")
    valid_streams = []
    for name, url, group, logo in stream_list:
        if is_stream_valid(url):
            valid_streams.append((name, url, group, logo))
            print(f"✅ Valid: {name}")
        else:
            print(f"❌ Invalid: {name}")
    return valid_streams

def generate_m3u8_content(streams):
    """Generate M3U8 content with EXTGRP and EXTVLCOPT"""
    lines = ["#EXTM3U"]
    current_group = None

    for name, url, group, logo in streams:
        if group != current_group:
            lines.append(f"#EXTGRP:{group}")
            current_group = group
        lines.append(f"#EXTINF:-1,{name}")
        lines.append(url)
        if logo:
            lines.append(f"#EXTVLCOPT:logo={logo}")
    return "\n".join(lines) + "\n"

def generate_html_page(streams):
    """Generate HTML5 player page with HLS.js"""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📺 Live Stream Player</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }
        h1 { color: #333; text-align: center; }
        .player { width: 100%; height: 60vh; background: #000; margin: 20px 0; }
        video { width: 100%; height: 100%; object-fit: contain; }
        .list { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
        .item { padding: 10px; background: white; border-radius: 5px; cursor: pointer; }
        .item:hover { background: #f0f0f0; }
        .logo { width: 16px; height: 16px; vertical-align: middle; margin-right: 5px; }
    </style>
</head>
<body>
    <h1>📺 Live Stream Player</h1>
    <div class="player">
        <video id="video" controls autoplay></video>
    </div>
    <div class="list">
'''
    for name, url, group, logo in streams:
        safe_logo = logo.replace("'", "\\'")
        safe_name = name.replace("'", "\\'")
        logo_img = f'<img class="logo" src="{safe_logo}" onerror="this.src=\'{DEFAULT_LOGO}\';">' if logo else ""
        html += f'        <div class="item" onclick="play(\'{url}\', \'{safe_name}\')">{logo_img}{safe_name}</div>\n'

    html += '''    </div>
    <script>
        const video = document.getElementById('video');
        function play(url, name) {
            if (video.src) video.src = "";
            if (Hls.isSupported()) {
                const hls = new Hls();
                hls.loadSource(url);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    video.play().catch(e => console.log("Autoplay blocked:", e));
                    document.title = "📺 " + name;
                });
            } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
                video.src = url;
                video.addEventListener("loadedmetadata", () => {
                    video.play().catch(e => console.log("Autoplay blocked:", e));
                    document.title = "📺 " + name;
                });
            }
        }
    </script>
</body>
</html>'''
    return html

def main():
    """Main function"""
    print("🚀 Starting live stream generator...")

    os.makedirs('live', exist_ok=True)
    print("📁 Created live/ directory")

    all_streams = []

    # 1. Add dynamic stream
    dynamic = get_dynamic_stream()
    if dynamic:
        all_streams.append(dynamic)

    # 2. Add local whitelist
    print(f"💾 Adding {len(LOCAL_WHITELIST)} local streams")
    all_streams.extend(LOCAL_WHITELIST)

    # 3. Add remote whitelist
    remote_list = load_remote_whitelist()
    all_streams.extend(remote_list)

    # 4. Deduplicate by URL
    seen_urls = set()
    unique_streams = []
    for item in all_streams:
        if item[1] not in seen_urls:
            seen_urls.add(item[1])
            unique_streams.append(item)

    print(f"📊 Deduplicated: {len(unique_streams)} unique streams")

    # 5. Validate streams
    valid_streams = validate_streams(unique_streams)
    if not valid_streams:
        print("❌ No valid streams found. Exiting.")
        return

    # 6. Generate M3U8
    m3u8_content = generate_m3u8_content(valid_streams)
    with open('live/current.m3u8', 'w', encoding='utf-8') as f:
        f.write(m3u8_content)
    print("🎉 Generated: live/current.m3u8")

    # 7. Generate HTML
    html_content = generate_html_page(valid_streams)
    with open('live/index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    print("🎉 Generated: live/index.html")

    # 8. Create .nojekyll
    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("✅ Created .nojekyll")

    print("✅ All tasks completed!")
    print("🌐 View player at: https://xichongguo.github.io/live-stream/live/index.html")

if __name__ == "__main__":
    main()
