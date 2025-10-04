# get_live_stream.py
"""
Function: Fetch live stream from API + remote whitelist -> Generate M3U8 playlist (all under '本地节目')
Output file: live/current.m3u8
"""

import requests
import json
import os

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

# [2. Remote Whitelist Configuration]
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
WHITELIST_TIMEOUT = 10  # Request timeout (seconds)

# ================== Utility Functions ==================

def is_url_valid(url):
    """
    Check if URL is accessible (HEAD request)
    """
    try:
        head = requests.head(url, timeout=5, allow_redirects=True)
        return head.status_code < 400
    except Exception as e:
        print(f"Warning: Failed to check URL {url}: {e}")
        return False

def get_dynamic_stream():
    """
    Get m3u8 address from specified API and return.
    """
    print("Sending request to live stream API...")

    try:
        response = requests.get(
            API_URL,
            params=PARAMS,
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            print("Error: API response is not valid JSON format.")
            print("Response preview:", response.text[:200])
            return None

        if 'data' in data and 'm3u8Url' in data['data']:
            m3u8_url = data['data']['m3u8Url']
            if is_url_valid(m3u8_url):
                print(f"Successfully obtained dynamic stream: {m3u8_url}")
                return m3u8_url
            else:
                print(f"Dynamic stream is not accessible: {m3u8_url}")
                return None
        else:
            print("Error: 'data.m3u8Url' field not found in returned JSON data.")
            print("Full response data:", json.dumps(data, ensure_ascii=False, indent=2))
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None

def load_whitelist_from_remote():
    """
    Load whitelist from remote URL
    :return: [(name, url)] list
    """
    print(f"Loading remote whitelist: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        whitelist = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # Skip empty lines and comments
            if "," not in line:
                print(f"Warning: Line {line_num} has wrong format (missing comma): {line}")
                continue
            try:
                name, url = line.split(",", 1)
                name, url = name.strip(), url.strip()
                if not name or not url:
                    print(f"Warning: Line {line_num} has empty name or URL: {line}")
                    continue
                if not url.startswith(("http://", "https://")):
                    print(f"Warning: Line {line_num} has invalid URL: {url}")
                    continue
                whitelist.append((f"Remote-{name}", url))
            except Exception as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
        print(f"Successfully loaded {len(whitelist)} remote streams")
        return whitelist
    except Exception as e:
        print(f"Failed to load remote whitelist: {e}")
        return []

def merge_and_deduplicate(whitelist):
    """
    Merge and deduplicate: based on URL, keep first one
    """
    seen_urls = set()
    unique_list = []
    for name, url in whitelist:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_list.append((name, url))
        else:
            print(f"Skipping duplicate address: {url} ({name})")
    print(f"After deduplication, {len(unique_list)} unique addresses remain")
    return unique_list

def generate_m3u8_content(dynamic_url, whitelist):
    """
    Generate standard M3U8 playlist content with all channels under '本地节目'
    """
    lines = [
        "#EXTM3U",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    # Add dynamic stream (Xichong Comprehensive) - explicitly in "本地节目" group
    if dynamic_url:
        lines.append('#EXTINF:-1 tvg-name="西充综合" group-title="本地节目",西充综合')
        lines.append(dynamic_url)

    for name, url in whitelist:
        # Clean name (remove "Remote-")
        name_clean = name.split("-", 1)[-1]
        
        # All channels in "本地节目" group
        lines.append(f'#EXTINF:-1 tvg-name="{name_clean}" group-title="本地节目",{name_clean}')
        lines.append(url)

    return "\n".join(lines) + "\n"

def main():
    """
    Main function: Fetch live stream, load remote whitelist, generate M3U8, write file
    """
    print("Starting to generate live stream playlist...")

    # Create output directory
    os.makedirs('live', exist_ok=True)
    print("Ensured live/ directory exists")

    # Get dynamic stream
    dynamic_url = get_dynamic_stream()

    # Build whitelist from remote only
    full_whitelist = []

    # Load remote whitelist
    remote_list = load_whitelist_from_remote()
    full_whitelist.extend(remote_list)

    # Deduplicate
    unique_whitelist = merge_and_deduplicate(full_whitelist)

    # Generate M3U8 content
    m3u8_content = generate_m3u8_content(dynamic_url, unique_whitelist)

    # Write file
    output_path = 'live/current.m3u8'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"Successfully generated playlist: {output_path}")
        print(f"Total includes {len(unique_whitelist) + (1 if dynamic_url else 0)} streams")
    except Exception as e:
        print(f"Failed to write file: {e}")
        return

    # Ensure .nojekyll file exists
    nojekyll_path = '.nojekyll'
    if not os.path.exists(nojekyll_path):
        try:
            open(nojekyll_path, 'w').close()
            print(f"Created {nojekyll_path} file")
        except Exception as e:
            print(f"Failed to create .nojekyll file: {e}")

    print("All tasks completed!")


# ============ Run Program ============
if __name__ == "__main__":
    main()
