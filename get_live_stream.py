# get_live_stream.py —— 完整修复版（2025-12-22）
# 功能：聚合多源直播流，优先级：本地节目 > Guovin > 其他远程源 > local.txt

import requests
import os
from urllib.parse import urlparse
from datetime import datetime
from collections import Counter
import re

# ================== 配置（关键：使用代理绕过 GitHub 限制）==================
# 使用 ghproxy.com 代理确保 raw 内容可访问
REMOTE_WHITELIST_URL = "https://ghproxy.com/https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
GUOVIN_IPTV_URL = "https://ghproxy.com/https://raw.githubusercontent.com/Guovin/TV/main/output/result.txt"
BC_API_URL = "https://bc.188766.xyz/"
BC_PARAMS = {'ip': '', 'mima': 'bingchawusifengxian', 'json': 'true'}

LOCAL_TXT_PATH = "local.txt"

# 动态流（西充）
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1', 'centerId': '9', 'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0', 'areaId': '907', 'appCenterId': '907', 'isTest': '0',
    'longitudeValue': '0', 'deviceVersionType': 'android', 'versionCodeGlobal': '5009037'
}
HEADERS = {'User-Agent': 'okhttp/3.12.12'}

TIMEOUT = 10
CHECK_TIMEOUT = 5
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")

# ---------------- 分类配置（请根据你原有内容补全）----------------
PROVINCE_KEYWORDS = {
    "四川": ["四川", "成都", "川台", "康巴", "峨眉电影"],
    "广东": ["广东", "广州", "深圳", "珠江", "南方", "大湾区"],
    "湖南": ["湖南", "芒果", "金鹰", "快乐购"],
    "江苏": ["江苏", "南京", "苏州", "无锡", "扬州"],
    "浙江": ["浙江", "杭州", "宁波", "温州", "钱江"],
    "湖北": ["湖北", "武汉", "荆楚"],
    "山东": ["山东", "齐鲁", "济南", "青岛"],
    "河南": ["河南", "中原", "郑州"],
    "河北": ["河北", "燕赵", "石家庄"],
    "福建": ["福建", "东南", "厦门", "福州"],
    "广西": ["广西", "南宁", "漓江"],
    "云南": ["云南", "云视", "昆明"],
    "江西": ["江西", "赣", "南昌"],
    "辽宁": ["辽宁", "沈阳", "大连"],
    "山西": ["山西", "晋", "太原"],
    "陕西": ["陕西", "三秦", "西安"],
    "安徽": ["安徽", "皖", "合肥"],
    "黑龙江": ["黑龙江", "龙江", "哈尔滨"],
    "吉林": ["吉林", "长春", "长影"],
    "贵州": ["贵州", "黔", "贵阳"],
    "甘肃": ["甘肃", "兰州", "丝路"],
    "海南": ["海南", "三沙", "海口"],
    "内蒙古": ["内蒙古", "蒙", "呼和浩特"],
    "宁夏": ["宁夏", "银川"],
    "青海": ["青海", "西宁"],
    "新疆": ["新疆", "天山", "乌鲁木齐"],
    "西藏": ["西藏", "拉萨"],
}

CATEGORY_MAP = {
    "卫视": ["卫视", "卫星"],
    "电影频道": ["电影", "影院", "影视", "CHC", "佳片"],
    "港澳台": ["凤凰", "TVB", "翡翠", "明珠", "东森", "中天", "年代", "三立", "民视", "公视", "华视", "TVBS"],
    "经典剧场": ["经典", "怀旧", "老电影", "剧场"]
}

EXCLUDE_IF_HAS = ['少儿', '卡通', '动漫', '游戏', '购物', '轮播']

FOREIGN_KEYWORDS = ["HBO", "CNN", "BBC", "ESPN", "STAR", "AXN", "KBS", "NHK", "ARIRANG", "Al Jazeera"]
ALLOWED_FOREIGN = {'凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'}

CHINESE_ALIAS = {
    "CCTV1综合": "CCTV-1",
    "CCTV2财经": "CCTV-2",
    "CCTV3综艺": "CCTV-3",
    "CCTV4中文国际": "CCTV-4",
    "CCTV5体育": "CCTV-5",
    "CCTV5+体育赛事": "CCTV-5+",
    "CCTV6电影": "CCTV-6",
    "CCTV7国防军事": "CCTV-7",
    "CCTV8电视剧": "CCTV-8",
    "CCTV9纪录": "CCTV-9",
    "CCTV10科教": "CCTV-10",
    "CCTV11戏曲": "CCTV-11",
    "CCTV12社会与法": "CCTV-12",
    "CCTV13新闻": "CCTV-13",
    "CCTV14少儿": "CCTV-14",
    "CCTV15音乐": "CCTV-15",
    "CCTV16奥林匹克": "CCTV-16",
    "CCTV17农业农村": "CCTV-17",
}


# ================== 工具函数 ==================
def is_foreign_channel(name):
    name = str(name)
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    name_lower = name.lower()
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
    name = str(name).strip()
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
    name = str(name).strip()
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
        r = requests.head(url, timeout=timeout, headers=DEFAULT_HEADERS, allow_redirects=True)
        return r.status_code < 400
    except:
        try:
            r = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS, stream=True)
            return r.status_code < 400
        except:
            return False

# ================== 通用 M3U 解析器 ==================
def parse_m3u_content(text):
    lines = text.strip().splitlines()
    channels = []
    current_name = None
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            current_name = line.split(",", 1)[1].strip() if "," in line else "Unknown"
        elif line.startswith("http") and current_name:
            url = line.strip()
            if is_valid_url(url) and not is_foreign_channel(current_name):
                cat, disp = categorize_channel(current_name)
                channels.append((disp, url, cat))
            current_name = None
    return channels

# ================== 数据源加载 ==================
def load_whitelist_as_local_program():
    print("👉 Loading whitelist.txt as '本地节目' (TOP)...")
    try:
        resp = requests.get(REMOTE_WHITELIST_URL, timeout=TIMEOUT, headers=DEFAULT_HEADERS)
        resp.encoding = 'utf-8'
        text = resp.text.strip()
        # 防御性检查：是否拿到 HTML？
        if text.startswith("<!DOCTYPE") or "<html" in text[:200]:
            print("   ❌ Received HTML instead of M3U. Check proxy URL.")
            return []
        raw_channels = parse_m3u_content(text)
        return [(name, url, "本地节目") for (name, url, _) in raw_channels]
    except Exception as e:
        print(f"❌ Load whitelist.txt failed: {e}")
        return []

def load_guovin_iptv():
    print("👉 Loading Guovin IPTV...")
    try:
        resp = requests.get(GUOVIN_IPTV_URL, timeout=TIMEOUT, headers=DEFAULT_HEADERS)
        resp.encoding = 'utf-8'
        text = resp.text.strip()
        lines = [line for line in text.splitlines() if line.strip() and not line.startswith("更新时间")]
        channels = []
        for line in lines:
            if "," not in line or line.startswith("#"): 
                continue
            parts = line.split(",", 1)
            if len(parts) < 2:
                continue
            name, url = parts[0].strip(), parts[1].strip()
            if name and url and is_valid_url(url) and not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                channels.append((disp, url, cat))
        return channels
    except Exception as e:
        print(f"❌ Load Guovin failed: {e}")
        return []

def load_tv_m3u():
    try:
        resp = requests.get(TV_M3U_URL, timeout=TIMEOUT, headers=DEFAULT_HEADERS)
        resp.encoding = 'utf-8'
        return parse_m3u_content(resp.text)
    except Exception as e:
        print(f"❌ Load tv.m3u failed: {e}")
        return []

def load_bc_api():
    try:
        resp = requests.get(BC_API_URL, params=BC_PARAMS, timeout=TIMEOUT, headers=DEFAULT_HEADERS)
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
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): 
                    continue
                if "," not in line:
                    continue
                name, url = line.split(",", 1)
                name, url = name.strip(), url.strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    cat, disp = categorize_channel(name)
                    channels.append((disp, url, cat))
    except Exception as e:
        print(f"❌ Read local.txt failed: {e}")
    return channels

# ================== 排序逻辑 ==================
def sort_channels(items):
    ORDER = [
        '本地节目',
        '央视', '卫视',
        '四川', '广东', '湖南', '湖北', '江苏', '浙江', '山东', '河南', '河北', '福建', '广西', '云南', '江西', '辽宁',
        '山西', '陕西', '安徽', '黑龙江', '内蒙古', '吉林', '贵州', '甘肃', '海南', '青海', '宁夏', '新疆', '西藏',
        '电影频道', '港澳台', '经典剧场', '其他'
    ]

    def cctv_order(name):
        match = re.search(r'CCTV-(\d+)', name)
        return int(match.group(1)) if match else 999

    def get_sort_key(item):
        name, url, group, source_type = item
        if source_type == "whitelist":
            return (0, 0, name)
        elif source_type == "guovin":
            return (1, 0, name)
        elif source_type == "remote":
            idx = ORDER.index(group) if group in ORDER else 999
            if group == '央视':
                return (2, idx, cctv_order(name), name)
            else:
                return (2, idx, name)
        else:  # local
            idx = ORDER.index(group) if group in ORDER else 999
            return (3, idx, name)

    return sorted(items, key=get_sort_key)

# ================== 主程序 ==================
def main():
    print("🚀 Generating playlist with correct priority...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_items = []

    # 1. whitelist → 本地节目（最高优先级）
    for name, url, group in load_whitelist_as_local_program():
        all_items.append((name, url, group, "whitelist"))

    # 2. Guovin
    for name, url, group in load_guovin_iptv():
        all_items.append((name, url, group, "guovin"))

    # 3. 其他远程源
    remote_sources = []
    remote_sources.extend(load_tv_m3u())
    remote_sources.extend(load_bc_api())
    remote_sources.extend(get_dynamic_stream())

    for name, url, group in remote_sources:
        if group == '央视':
            if check_url_valid(url):
                all_items.append((name, url, group, "remote"))
            else:
                print(f"❌ Skipped invalid CCTV: {name}")
        else:
            all_items.append((name, url, group, "remote"))

    # 4. local.txt（最后）
    for name, url, group in load_local_txt():
        all_items.append((name, url, group, "local"))

    # 排序
    sorted_items = sort_channels(all_items)

    # 统计
    stats = Counter(item[2] for item in sorted_items)
    print(f"\n📊 Total channels: {len(sorted_items)}")
    for cat, cnt in stats.most_common():
        print(f"   {cat:<10}: {cnt}")

    # 写入文件
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "#EXTM3U",
        f"# Generated at: {now}",
        'x-tvg-url="https://epg.51zmt.top/xmltv.xml"'
    ]
    for name, url, group, _ in sorted_items:
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        print(f"🎉 Output written to: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Write error: {e}")

    # 生成 .nojekyll（用于 GitHub Pages）
    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()

if __name__ == "__main__":
    main()
