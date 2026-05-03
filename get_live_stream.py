# -*- coding: utf-8 -*-
import requests
import os
import sys
import time
import hashlib
from urllib.parse import urlparse
import re

# ================== Configuration ==================
# API 接口配置
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1', 'centerId': '9', 'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0', 'areaId': '907', 'appCenterId': '907', 'isTest': '0',
    'longitudeValue': '0', 'deviceVersionType': 'android', 'versionCodeGlobal': '5009037'
}
HEADERS = {'User-Agent': 'okhttp/3.12.12'}

# 远程数据源
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
LOCAL_TXT_PATH = "local.txt"
PRIORITY_SOURCE_URL = "https://lin.305362.xyz/migu66" # 高优先级源

# 签名配置 (如果需要处理加密链接)
SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2" 
BASE_DOMAIN = "https://ncpull.cnncw.cn"

# 输出配置
OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")
WHITELIST_TIMEOUT = 20
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

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

def generate_signature(path, timestamp):
    """生成防盗链签名"""
    raw_string = f"{SECRET_KEY}{path}{timestamp}"
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

def categorize_channel(name):
    """
    【核心修复】强制本地频道归类逻辑
    """
    name_lower = name.lower()
    
    # --- 🔴 强制规则：本地关键词优先匹配 ---
    # 只要包含这些词，强制归为“本地节目”，防止被省份规则截胡
    local_keywords = ['西充', '南充', '综合', '顺庆', '高坪', '嘉陵']
    if any(kw in name for kw in local_keywords):
        return "本地节目", name

    # --- 央视逻辑 ---
    if any(kw in name_lower for kw in ['cctv', '中央']):
        match = re.search(r'CCTV\D*(\d+)', name.upper())
        if match: return f"CCTV-{int(match.group(1))}", name
        return "央视", name
    
    # --- 卫视逻辑 ---
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower: return '卫视', name
    
    # --- 电影逻辑 ---
    has_movie_kw = any(kw.lower() in name_lower for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name_lower for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw: return '电影轮播', name
    if has_movie_kw: return '电影频道', name
    
    # --- 港澳台逻辑 ---
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name: return '港澳台', name
        
    # --- 省份逻辑 (此时已不会包含南充/西充) ---
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name: return prov, name
            
    return "其他", name

# ================== Data Sources ==================
def get_dynamic_stream():
    """获取API动态流，并尝试修复签名（如果失效）"""
    try:
        print(f"📡 正在请求西充API...")
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10, verify=False)
        data = response.json()
        
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            name = "西充综合"
            
            # 如果URL包含 auth_key 且可能过期，这里可以尝试重构，
            # 但通常直接返回即可，除非明确知道需要重新签名
            if url.startswith("http"):
                return (name, url, "本地节目", 0)
                
    except Exception as e: 
        print(f"❌ API 获取失败: {e}")
    return None

def load_priority_source():
    """加载高优先级源 (Migu66)"""
    channels = []
    try:
        print(f"📥 正在加载高优先级源: {PRIORITY_SOURCE_URL}")
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
                            channels.append((disp, url_line, cat, -1)) # 优先级 -1 (最高)
            else: i += 1
    except Exception as e: 
        print(f"❌ 加载优先级源失败: {e}")
    return channels<websource>source_group_web_1</websource>

def load_remote_whitelist():
    """加载白名单 -> 强制本地节目"""
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
                    # 这里的频道全部视为本地节目
                    channels.append((name, url, "本地节目", 1))
    except Exception as e: 
        print(f"❌ 加载白名单失败: {e}")
    return channels<websource>source_group_web_2</websource>

def load_tv_m3u():
    """加载通用 M3U"""
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
    return channels<websource>source_group_web_3</websource>

def load_local_txt():
    """加载本地文件"""
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
                name, url = parts.strip(), parts.strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    cat, disp = categorize_channel(name)
                    channels.append((disp, url, cat, 3))
    except Exception as e: 
        print(f"❌ 加载 local.txt 失败: {e}")
    return channels<websource>source_group_web_4</websource>

# ================== Main Logic ==================
def main():
    try:
        print("🚀 开始合并直播源...")
        all_channels = []
        
        # 1. 按优先级顺序加载数据
        all_channels.extend(load_priority_source()) # 优先级 -1 (最高)
        
        dynamic_channel = get_dynamic_stream()     # 优先级 0
        if dynamic_channel: all_channels.append(dynamic_channel)
        
        all_channels.extend(load_remote_whitelist()) # 优先级 1
        all_channels.extend(load_tv_m3u())           # 优先级 2
        all_channels.extend(load_local_txt())        # 优先级 3

        # 2. 数据去重 (保留优先级高的)
        unique_channels_map = {}
        for channel in all_channels:
            name = channel
            priority = channel
            # 如果名字不存在，或者新来的优先级数字更小（更高），则更新
            if name not in unique_channels_map or priority < unique_channels_map[name]:
                unique_channels_map[name] = channel
        
        unique_channels = list(unique_channels_map.values())
        print(f"✅ 去重完成，剩余频道数: {len(unique_channels)}")<websource>source_group_web_5</websource>

        # 3. 排序与输出 (强制本地节目置顶)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 提取所有唯一的分组名称
            all_groups = set(channel for channel in unique_channels)
            
            # 定义排序规则：'本地节目' 必须在最前面 (排序权重 0)，其他按字母序 (权重 1)
            sorted_groups = sorted(list(all_groups), key=lambda x: (0 if x == '本地节目' else 1, x))
            
            # 按排序后的分组写入文件
            for group in sorted_groups:
                group_channels = [ch for ch in unique_channels if ch == group]
                for channel in group_channels:
                    name, url, category, priority = channel
                    f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
                    f.write(f'{url}\n')<websource>source_group_web_6</websource>

        print(f"🎉 合并完成！文件路径: {os.path.abspath(OUTPUT_FILE)}")
        
    except Exception as e:
        print(f"❌ 主程序发生严重错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
