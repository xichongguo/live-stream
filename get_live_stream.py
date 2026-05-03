# -*- coding: utf-8 -*-
import requests
import os
import sys
from urllib.parse import urlparse
import re
import hashlib
import time

# ================== Configuration ==================
# --- IPTVUpdater 相关配置 ---
IPTV_JSON_URL = "https://raw.githubusercontent.com/YuanHsing/FreeToPlay/main/m3u/iptv.m3u"
IPTV_BASE_DOMAIN = "" 

# --- 原第二段代码的配置 (保留备用) ---
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
WHITELIST_TIMEOUT = 20
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")

# ================== Province Keywords (精简版) ==================
PROVINCE_KEYWORDS = {
    '四川': ['四川', '成都', '绵阳', '德阳', '南充', '宜宾', '泸州', '乐山', '达州', '内江', '自贡', '攀枝花', '广安', '遂宁', '资阳', '眉山', '雅安', '巴中', '阿坝', '甘孜', '凉山'],
    '广东': ['广东', '广州', '佛山', '东莞', '中山', '珠海', '惠州', '江门', '肇庆', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江', '云浮', '清远', '韶关', '河源'],
    '北京': ['北京'], '上海': ['上海', '东方'], '天津': ['天津'], '重庆': ['重庆'],
}

# ================== Category Mapping ==================
CATEGORY_MAP = {
    '卫视': ['卫视', '卫星', '东方卫视', '北京卫视', '湖南卫视', '浙江卫视', '江苏卫视'],
    '电影关键词': ['电影', '影院', 'CHC', '动作', '喜剧', '影视'],
    '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '三立'],
    '经典剧场': ['经典', '怀旧', '戏曲']
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

def normalize_cctv_name(name):
    if "CCTV" in name.upper():
        match = re.search(r'CCTV\D*(\d+)', name.upper())
        if match: return f"CCTV-{int(match.group(1))}"
    return name

def categorize_channel(name):
    name_lower = name.lower()
    
    # --- 核心逻辑：强制将南充、西充归类为本地节目 ---
    if any(city in name for city in ['南充', '西充']):
        return '本地节目', name
        
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

# --- 核心：集成你的IPTVUpdater代码段 ---
def fetch_signed_channels():
    """
    核心功能：从 kstatic.sctvcloud.com 获取频道ID，并拼接带签名的URL
    优先级设定为 -3 (最高优先级)
    """
    channels = []
    json_url = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
    secret_key = "5df6d8b743257e0e38b869a07d8819d2"
    base_domain = "https://ncpull.cnncw.cn"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"🚀 正在连接 kstatic.sctvcloud.com 获取私有源...")
        response = requests.get(json_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("isSuccess"):
                items = data["data"]["propValue"]["children"]["dataList"]
                print(f"✅ 私有源接口连接成功！共发现 {len(items)} 个频道。")
                
                # 设置过期时间：当前时间 + 2小时 (7200秒)
                expire_time = int(time.time()) + 7200
                
                for item in items:
                    title = item.get("title")
                    # 从 liveStream 字段中提取 channel_id
                    live_stream = item.get("liveStream", "")
                    path_parts = [p for p in live_stream.split("/") if p]
                    
                    if len(path_parts) >= 2:
                        channel_id = path_parts[-2]
                    else:
                        # 如果无法提取，使用哈希作为备用ID
                        channel_id = hashlib.md5(title.encode()).hexdigest()[:10]
                        print(f"⚠️ 无法从 {title} 提取ID，使用哈希替代")
                    
                    # 构造路径
                    path = f"/live/{channel_id}/playlist.m3u8"
                    
                    # 计算签名 MD5(密钥 + 路径 + 时间戳)
                    raw_string = f"{secret_key}{path}{expire_time}"
                    ws_secret = hashlib.md5(raw_string.encode('utf-8')).hexdigest()
                    
                    # 拼接最终地址
                    final_url = f"{base_domain}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                    
                    # 过滤掉非中文频道
                    if not is_foreign_channel(title):
                        cat, disp = categorize_channel(title)
                        # 优先级设为 -3 (最高)
                        channels.append((disp, final_url, cat, -3))
                        print(f" ✅ 已添加: {disp} -> [{cat}]")
            else:
                print(f"❌ 私有源API返回错误: {data.get('msg')}")
        else:
            print(f"❌ 私有源网络请求失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 私有源处理异常 (可能网络波动): {e}")
    
    return channels

# --- 原有的公开源获取函数 ---
def fetch_iptv_channels():
    channels = []
    try:
        print(f"🚀 正在从公开源获取频道列表...")
        response = requests.get(IPTV_JSON_URL, headers=DEFAULT_HEADERS, timeout=15)
        
        if response.status_code == 200:
            lines = response.text.strip().splitlines()
            i = 0
            count = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXTINF") and "," in line:
                    try: 
                        name_part = line.split(",", 1)
                        name = name_part.split(' tvg-').strip()
                    except: 
                        i += 1
                        continue
                    
                    i += 1
                    if i < len(lines):
                        url_line = lines[i].strip()
                        if url_line.startswith("http") and is_valid_url(url_line):
                            if not is_foreign_channel(name):
                                cat, disp_name = categorize_channel(name)
                                # 优先级设为 0 (低于私有源)
                                channels.append((disp_name, url_line, cat, 0))
                                count += 1
                i += 1
            print(f"✅ 公开源获取成功！共处理 {count} 个有效频道<websource>source_group_web_1</websource>。")
        else:
            print(f"❌ 公开源网络请求失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 获取公开源时发生异常: {e}")
    
    return channels

# --- 其他源 ---
def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10, verify=False)
        data = response.json()
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if url.startswith("http"):
                name = "西充综合" 
                cat, disp = "本地节目", name
                return (disp, url, cat, -1)
    except Exception as e: print(f"API 获取失败: {e}")
    return None

def load_priority_source():
    channels = []
    try:
        print(f"📥 正在加载高优先级源: https://lin.305362.xyz/migu66")
        response = requests.get("https://lin.305362.xyz/migu66", timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
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
                            channels.append((disp, url_line, cat, -2))
            else: i += 1
    except Exception as e: print(f"❌ 加载优先级源失败: {e}")
    return channels<websource>source_group_web_2</websource>

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
                name, url = parts.strip(), parts.strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    channels.append((name, url, "本地节目", 1))
    except Exception as e: print(f"❌ 加载白名单失败: {e}")
    return channels<websource>source_group_web_3</websource>

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
    except Exception as e: print(f"❌ 加载 TV M3U 失败: {e}")
    return channels<websource>source_group_web_4</websource>

def load_local_txt():
    channels = []
    if not os.path.exists(LOCAL_TXT_PATH):
        print(f"⚠️ 未找到本地文件: {LOCAL_TXT_PATH}")
        return channels
    try:
        with open(LOCAL_TXT_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "," in line:
                parts = line.split(",", 1)
                name, url = parts.strip(), parts.strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    cat, disp = categorize_channel(name)
                    channels.append((disp, url, cat, 3))
    except Exception as e: print(f"❌ 加载 local.txt 失败: {e}")
    return channels<websource>source_group_web_5</websource>

# ================== Main Logic ==================
def main():
    # --- 修复点：初始化列表变量 ---
    all_channels = []
    
    try:
        print("🚀 开始合并直播源...")
        
        # 1. 按优先级顺序加载数据
        all_channels.extend(fetch_signed_channels())   # 优先级 -3
        all_channels.extend(load_priority_source())    # 优先级 -2
        dynamic_channel = get_dynamic_stream()         # 优先级 -1
        if dynamic_channel: all_channels.append(dynamic_channel)
        
        all_channels.extend(fetch_iptv_channels())     # 优先级 0
        all_channels.extend(load_remote_whitelist())   # 优先级 1
        all_channels.extend(load_tv_m3u())             # 优先级 2
        all_channels.extend(load_local_txt())          # 优先级 3

        # 2. 数据去重 (保留优先级高的)
        unique_channels_map = {}
        for channel in all_channels:
            name = channel
            priority = channel
            if name not in unique_channels_map or priority < unique_channels_map[name]:
                unique_channels_map[name] = channel
        
        unique_channels = list(unique_channels_map.values())
        print(f"✅ 去重完成，剩余频道数: {len(unique_channels)}")<websource>source_group_web_6</websource>

        # 3. 排序与输出
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 提取所有唯一的分组名称
            all_groups = set(channel for channel in unique_channels)
            
            # 优化排序规则：'本地节目' 必须在最前面，其他分组按字母顺序排列
            sorted_groups = sorted(list(all_groups), key=lambda x: (0 if x == '本地节目' else 1, x))
            
            # 按排序后的分组写入文件
            for group in sorted_groups:
                group_channels = [ch for ch in unique_channels if ch == group]
                for channel in group_channels:
                    name, url, category, priority = channel
                    f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
                    f.write(f'{url}\n')<websource>source_group_web_7</websource>

        print(f"🎉 合并完成！文件路径: {os.path.abspath(OUTPUT_FILE)}")
        
    except Exception as e:
        print(f"❌ 主程序发生严重错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
