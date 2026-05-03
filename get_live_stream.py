# -*- coding: utf-8 -*-
import requests
import os
import sys
from urllib.parse import urlparse
import re

# ================== Configuration ==================
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1', 'centerId': '9', 'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0', 'areaId': '907', 'appCenterId': '907', 'isTest': '0',
    'longitudeValue': '0', 'deviceVersionType': 'android', 'versionCodeGlobal': '5009037'
}
HEADERS = {'User-Agent': 'okhttp/3.12.12'}

REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
LOCAL_TXT_PATH = "local.txt"
PRIORITY_SOURCE_URL = "https://lin.305362.xyz/migu66"

OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")
WHITELIST_TIMEOUT = 20
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ================== Province Keywords ==================
PROVINCE_KEYWORDS = {
    '四川': ['四川', '成都', '绵阳', '德阳', '南充', '宜宾', '泸州', '乐山', '达州', '内江', '自贡', '攀枝花', '广安', '遂宁', '资阳', '眉山', '雅安', '巴中', '阿坝', '甘孜', '凉山'],
    '广东': ['广东', '广州', '深圳', '佛山', '东莞', '中山', '珠海', '惠州', '江门', '肇庆', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江', '云浮', '清远', '韶关', '河源'],
    '北京': ['北京'], '上海': ['上海', '东方'], '天津': ['天津'], '重庆': ['重庆'],
}

# ================== Category Mapping ==================
CATEGORY_MAP = {
    '卫视': ['卫视', '卫星', '东方卫视', '北京卫视', '湖南卫视', '浙江卫视', '江苏卫视'],
    '电影关键词': ['电影', '影院', 'CHC', '动作', '喜剧', '影视'],
    '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '三立'],
}

ROTATION_KEYWORDS = ['轮播', '回放', '测试']
FOREIGN_KEYWORDS = {'CNN', 'BBC', 'NHK', 'HBO', 'Fox', 'ESPN'}
ALLOWED_FOREIGN = {'凤凰', 'TVB', '翡翠', '明珠'}

# ================== Helper Functions ==================
def is_foreign_channel(name):
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name: return False
    for keyword in FOREIGN_KEYWORDS:
        if keyword.lower() in name_lower: return True
    return False

def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except: return False

def categorize_channel(name):
    """
    【核心修复】强制本地频道归类逻辑
    """
    # --- 🔴 强制规则：本地关键词优先匹配 ---
    local_keywords = ['西充', '南充', '综合', '顺庆', '高坪', '嘉陵']
    if any(kw in name for kw in local_keywords):
        return "本地节目", name

    # --- 央视逻辑 ---
    if any(kw in name.lower() for kw in ['cctv', '中央']):
        match = re.search(r'CCTV\D*(\d+)', name.upper())
        if match: return f"CCTV-{int(match.group(1))}", name
        return "央视", name
    
    # --- 卫视逻辑 ---
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name.lower(): return '卫视', name
    
    # --- 电影逻辑 ---
    has_movie_kw = any(kw.lower() in name.lower() for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name.lower() for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw: return '电影轮播', name
    if has_movie_kw: return '电影频道', name
    
    # --- 港澳台逻辑 ---
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name: return '港澳台', name
        
    # --- 省份逻辑 ---
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name: return prov, name
            
    return "其他", name

# ================== Data Sources ==================
def get_dynamic_stream():
    try:
        print(f"📡 正在请求西充API...")
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10, verify=False)
        data = response.json()
        
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            name = "西充综合"
            if url.startswith("http"):
                return (name, url, "本地节目", 0)
    except Exception as e: 
        print(f"❌ API 获取失败: {e}")
    return None

def load_priority_source():
    channels = []
    try:
        print(f"📥 正在加载高优先级源...")
        response = requests.get(PRIORITY_SOURCE_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF") and "," in line:
                try: name = line.split(",", 1).strip()
                except: i += 1; continue
                
                i += 1
                if i < len(lines):
                    url_line = lines[i].strip()
                    if url_line.startswith("http") and is_valid_url(url_line):
                        if not is_foreign_channel(name):
                            cat, disp = categorize_channel(name)
                            channels.append((disp, url_line, cat, -1))
            else: i += 1
    except Exception as e: 
        print(f"❌ 加载优先级源失败: {e}")
    return channels

def load_remote_whitelist():
    channels = []
    try:
        print(f"📥 正在加载白名单...")
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        lines = response.text.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "," in line:
                parts = line.split(",", 1)
                name, url = parts[0].strip(), parts[1].strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    # 强制归类为本地节目
                    channels.append((name, url, "本地节目", 1))
    except Exception as e: 
        print(f"❌ 加载白名单失败: {e}")
    return channels

def load_tv_m3u():
    channels = []
    try:
        print(f"📥 正在加载 TV M3U...")
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF") and "," in line:
                try: name = line.split(",", 1).strip()
                except: i += 1; continue
                i += 1
                if i < len(lines):
                    url_line = lines[i].strip()
                    if url_line.startswith("http") and is_valid_url(url_line):
                        if not is_foreign_channel(name):
                            cat, disp = categorize_channel(name)
                            channels.append((disp, url_line, cat, 2))
            else: i += 1
    except Exception as e: 
        print(f"❌ 加载 TV M3U 失败: {e}")
    return channels

def load_local_txt():
    channels = []
    if not os.path.exists(LOCAL_TXT_PATH):
        return channels
    try:
        with open(LOCAL_TXT_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "," in line:
                parts = line.split(",", 1)
                name, url = parts[0].strip(), parts[1].strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    cat, disp = categorize_channel(name)
                    channels.append((disp, url, cat, 3))
    except Exception as e: 
        print(f"❌ 加载 local.txt 失败: {e}")
    return channels

# ================== Main Logic ==================
def main():
    try:
        print("🚀 开始合并直播源...")
        all_channels = []
        
        # 1. 加载数据
        all_channels.extend(load_priority_source())
        
        dynamic_channel = get_dynamic_stream()
        if dynamic_channel: all_channels.append(dynamic_channel)
        
        all_channels.extend(load_remote_whitelist())
        all_channels.extend(load_tv_m3u())
        all_channels.extend(load_local_txt())

        # 2. 去重
        unique_channels_map = {}
        for channel in all_channels:
            name = channel[0]
            priority = channel[3]
            if name not in unique_channels_map or priority < unique_channels_map[name][3]:
                unique_channels_map[name] = channel
        
        unique_channels = list(unique_channels_map.values())
        print(f"✅ 去重完成，剩余频道数: {len(unique_channels)}")

        # 3. 输出
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 提取分组
            all_groups = set(channel[2] for channel in unique_channels)
            
            # 排序：本地节目置顶
            sorted_groups = sorted(list(all_groups), key=lambda x: (0 if x == '本地节目' else 1, x))
            
            for group in sorted_groups:
                group_channels = [ch for ch in unique_channels if ch[2] == group]
                for channel in group_channels:
                    name, url, category, priority = channel
                    f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
                    f.write(f'{url}\n')

        print(f"🎉 合并完成！文件路径: {os.path.abspath(OUTPUT_FILE)}")
        
    except Exception as e:
        print(f"❌ 主程序发生严重错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
