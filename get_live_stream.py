# -*- coding: utf-8 -*-
import requests
import os
import sys
from urllib.parse import urlparse
import re
import hashlib
import time

# ================== Configuration ==================
# --- IPTVUpdater 核心配置 (你的私有源) ---
IPTV_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
IPTV_SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
IPTV_BASE_DOMAIN = "https://ncpull.cnncw.cn"

# --- 其他公开源配置 ---
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1', 'centerId': '9', 'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0', 'areaId': '907', 'appCenterId': '907', 'isTest': '0',
    'longitudeValue': '0', 'deviceVersionType': 'android', 'versionCodeGlobal': '5009037'
}

REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
LOCAL_TXT_PATH = "local.txt"
PRIORITY_SOURCE_URL = "https://lin.305362.xyz/migu66"

OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")
WHITELIST_TIMEOUT = 20
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ================== Category Logic ==================
PROVINCE_KEYWORDS = {
    '四川': ['四川', '成都', '绵阳', '德阳', '南充', '宜宾', '泸州', '乐山', '达州', '内江', '自贡', '攀枝花', '广安', '遂宁', '资阳', '眉山', '雅安', '巴中', '阿坝', '甘孜', '凉山'],
    '广东': ['广东', '广州', '佛山', '东莞', '中山', '珠海', '惠州', '江门', '肇庆', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江', '云浮', '清远', '韶关', '河源'],
    '北京': ['北京'], '上海': ['上海', '东方'], '天津': ['天津'], '重庆': ['重庆'],
}

CATEGORY_MAP = {
    '卫视': ['卫视', '卫星', '东方卫视', '北京卫视', '湖南卫视', '浙江卫视', '江苏卫视'],
    '电影关键词': ['电影', '影院', 'CHC', '动作', '喜剧', '影视'],
    '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '三立'],
}
ROTATION_KEYWORDS = ['轮播', '回放', '测试']
FOREIGN_KEYWORDS = {'CNN', 'BBC', 'NHK', 'HBO', 'Fox', 'ESPN'}
ALLOWED_FOREIGN = {'凤凰', 'TVB', '翡翠', '明珠'}

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

def normalize_cctv_name(name):
    if "CCTV" in name.upper():
        match = re.search(r'CCTV\D*(\d+)', name.upper())
        if match: return f"CCTV-{int(match.group(1))}"
    return name

def categorize_channel(name):
    # --- 核心修改：强制将南充、西充归类为本地节目 ---
    if any(city in name for city in ['南充', '西充']):
        return '本地节目', name
        
    name_lower = name.lower()
    if any(kw in name_lower for kw in ['cctv', '中央']):
        return '央视', normalize_cctv_name(name)
    
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower: return '卫视', name
    
    has_movie_kw = any(kw.lower() in name_lower for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name_lower for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw: return '电影轮播', name
    if has_movie_kw: return '电影频道', name
        
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name: return prov, name
            
    return "其他", name

# ================== Data Sources ==================

# --- 你的核心代码段：带签名的私有源 ---
def fetch_signed_channels():
    channels = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"🚀 正在连接 kstatic.sctvcloud.com 获取私有源...")
        response = requests.get(IPTV_JSON_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # 增加了对不同层级结构的兼容性判断
            prop_value = data.get("data", {})
            if isinstance(prop_value, list): prop_value = prop_value[0]
            prop_value = prop_value.get("propValue", {})
            if isinstance(prop_value, list): prop_value = prop_value[0]
            
            children = prop_value.get("children", [])
            if isinstance(children, list) and len(children) > 0:
                items = children[0].get("dataList", [])
                
                print(f"✅ 私有源接口连接成功！共发现 {len(items)} 个频道。")
                expire_time = int(time.time()) + 7200
                
                for item in items:
                    title = item.get("title")
                    live_stream = item.get("liveStream", "")
                    
                    # 提取ID逻辑
                    path_parts = [p for p in live_stream.split("/") if p]
                    if len(path_parts) >= 2:
                        channel_id = path_parts[-2]
                    else:
                        channel_id = hashlib.md5(title.encode()).hexdigest()[:10]
                    
                    path = f"/live/{channel_id}/playlist.m3u8"
                    raw_string = f"{IPTV_SECRET_KEY}{path}{expire_time}"
                    ws_secret = hashlib.md5(raw_string.encode('utf-8')).hexdigest()
                    final_url = f"{IPTV_BASE_DOMAIN}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                    
                    if not is_foreign_channel(title):
                        cat, disp = categorize_channel(title)
                        channels.append((disp, final_url, cat, -3)) # 优先级 -3
            else:
                print("❌ 无法解析JSON结构，请检查接口返回内容")
        else:
            print(f"❌ 私有源网络请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 私有源处理异常: {e}")
    
    return channels

# --- 辅助源：公开M3U ---
def fetch_iptv_channels():
    channels = []
    try:
        print(f"🚀 正在从公开源获取频道列表...")
        response = requests.get("https://raw.githubusercontent.com/YuanHsing/FreeToPlay/main/m3u/iptv.m3u", headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 200:
            lines = response.text.strip().splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXTINF") and "," in line:
                    try: 
                        name = line.split(",", 1)[1].split(' tvg-')[0].strip()
                    except: 
                        i += 1; continue
                    
                    i += 1
                    if i < len(lines):
                        url_line = lines[i].strip()
                        if url_line.startswith("http") and is_valid_url(url_line):
                            if not is_foreign_channel(name):
                                cat, disp = categorize_channel(name)
                                channels.append((disp, url_line, cat, 0))
                i += 1
            print(f"✅ 公开源获取成功！")
    except Exception as e:
        print(f"❌ 公开源异常: {e}")
    return channels

# --- 辅助源：本地动态API ---
def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, timeout=10, verify=False)
        data = response.json()
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if url.startswith("http"):
                return ("西充综合", url, "本地节目", -1)
    except: pass
    return None

# --- 辅助源：高优源 ---
def load_priority_source():
    channels = []
    try:
        response = requests.get(PRIORITY_SOURCE_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        lines = response.text.strip().splitlines()
        for i in range(len(lines)):
            if lines[i].startswith("#EXTINF") and "," in lines[i]:
                try: name = lines[i].split(",", 1)[1].strip()
                except: continue
                if i + 1 < len(lines):
                    url = lines[i+1].strip()
                    if url.startswith("http") and is_valid_url(url) and not is_foreign_channel(name):
                        cat, disp = categorize_channel(name)
                        channels.append((disp, url, cat, -2))
    except Exception as e: print(f"❌ 加载高优源失败: {e}")
    return channels

# --- 辅助源：白名单 ---
def load_remote_whitelist():
    channels = []
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        for line in response.text.strip().splitlines():
            if "," in line:
                parts = line.split(",", 1)
                name, url = parts[0].strip(), parts[1].strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    channels.append((name, url, "本地节目", 1))
    except: pass
    return channels

# --- 辅助源：TV M3U ---
def load_tv_m3u():
    channels = []
    try:
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        lines = response.text.strip().splitlines()
        for i in range(len(lines)):
            if lines[i].startswith("#EXTINF") and "," in lines[i]:
                try: name = lines[i].split(",", 1)[1].strip()
                except: continue
                if i + 1 < len(lines):
                    url = lines[i+1].strip()
                    if url.startswith("http") and is_valid_url(url) and not is_foreign_channel(name):
                        cat, disp = categorize_channel(name)
                        channels.append((disp, url, cat, 2))
    except: pass
    return channels

# --- 辅助源：本地文件 ---
def load_local_txt():
    channels = []
    if not os.path.exists(LOCAL_TXT_PATH): return channels
    try:
        with open(LOCAL_TXT_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f.readlines():
                line = line.strip()
                if "," in line:
                    parts = line.split(",", 1)
                    name, url = parts[0].strip(), parts[1].strip()
                    if name and url and is_valid_url(url) and not is_foreign_channel(name):
                        cat, disp = categorize_channel(name)
                        channels.append((disp, url, cat, 3))
    except: pass
    return channels

# ================== Main Logic ==================
def main():
    all_channels = [] # 初始化列表
    
    try:
        print("🚀 开始合并直播源...")
        
        # 按优先级加载
        all_channels.extend(fetch_signed_channels())   # -3
        all_channels.extend(load_priority_source())    # -2
        dyn = get_dynamic_stream()                     # -1
        if dyn: all_channels.append(dyn)
        
        all_channels.extend(fetch_iptv_channels())     # 0
        all_channels.extend(load_remote_whitelist())   # 1
        all_channels.extend(load_tv_m3u())             # 2
        all_channels.extend(load_local_txt())          # 3

        # 去重
        unique_map = {}
        for ch in all_channels:
            name, priority = ch[0], ch[3]
            if name not in unique_map or priority < unique_map[name][3]:
                unique_map[name] = ch
        
        final_list = list(unique_map.values())
        print(f"✅ 去重完成，共 {len(final_list)} 个频道")

        # 输出
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            groups = set(ch[2] for ch in final_list)
            sorted_groups = sorted(list(groups), key=lambda x: (0 if x == '本地节目' else 1, x))
            
            for group in sorted_groups:
                for ch in final_list:
                    if ch[2] == group:
                        f.write(f'#EXTINF:-1 tvg-name="{ch[0]}" group-title="{ch[2]}",{ch[0]}\n')
                        f.write(f'{ch[1]}\n')

        print(f"🎉 完成！保存至: {os.path.abspath(OUTPUT_FILE)}")
        
    except Exception as e:
        print(f"❌ 严重错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
