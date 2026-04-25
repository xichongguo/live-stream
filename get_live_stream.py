# -*- coding: utf-8 -*-
import requests
import os
import sys
from urllib.parse import urlparse
import re

# ================== Configuration ==================
# API 接口配置 (用于获取动态流)
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1', 'centerId': '9', 'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0', 'areaId': '907', 'appCenterId': '907', 'isTest': '0',
    'longitudeValue': '0', 'deviceVersionType': 'android', 'versionCodeGlobal': '5009037'
}
HEADERS = {'User-Agent': 'okhttp/3.12.12'}

# 远程源配置
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
LOCAL_TXT_PATH = "local.txt"

# --- 核心需求配置：高优先级源 ---
PRIORITY_SOURCE_URL = "https://lin.305362.xyz/migu66"

# 输出配置
OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")
WHITELIST_TIMEOUT = 20
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# ================== Province Keywords (部分示例，实际使用建议保留完整列表) ==================
PROVINCE_KEYWORDS = {
    '四川': ['四川', '成都', '绵阳', '西充', '南充'],
    '广东': ['广东', '广州', '深圳', '佛山'],
    '北京': ['北京'], '上海': ['上海'], '天津': ['天津'], '重庆': ['重庆'],
    # ... 其他省份关键词请根据实际情况补充 ...
}

# ================== Category Mapping ==================
CATEGORY_MAP = {
    '卫视': ['卫视', '卫星', '东方卫视', '北京卫视', '湖南卫视', '浙江卫视', '江苏卫视'],
    '电影关键词': ['电影', '影院', 'CHC', '动作', '喜剧', '影视'],
    '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '三立'],
    '经典剧场': ['经典', '怀旧', '戏曲']
}

ROTATION_KEYWORDS = ['轮播', '回放', '测试']
FOREIGN_KEYWORDS = {'CNN', 'BBC', 'NHK', 'HBO', 'Fox', 'ESPN', 'Netflix'}
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
    # 简单的 CCTV 标准化逻辑
    if "CCTV" in name.upper():
        match = re.search(r'CCTV\D*(\d+)', name.upper())
        if match: return f"CCTV-{int(match.group(1))}"
    return name

def categorize_channel(name):
    name_lower = name.lower()
    # 1. 检查央视
    if any(kw in name_lower for kw in ['cctv', '中央']):
        return '央视', normalize_cctv_name(name)
    
    # 2. 检查卫视
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower: return '卫视', name
    
    # 3. 检查特定类型
    has_movie_kw = any(kw.lower() in name_lower for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name_lower for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw: return '电影轮播', name
    if has_movie_kw: return '电影频道', name
    
    # 4. 检查港澳台
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name: return '港澳台', name
        
    # 5. 检查省份
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name: return prov, name
            
    # 6. 默认归类
    return "其他", name

# ================== Data Sources ==================
def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10, verify=False)
        data = response.json()
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if url.startswith("http"):
                name = "西充综合" # 假设名称
                cat, disp = "本地节目", name
                return (disp, url, cat, 0) # 优先级 0
    except Exception as e: print(f"API 获取失败: {e}")
    return None

def load_priority_source():
    """加载 https://lin.305362.xyz/migu66 的数据"""
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
                            # 【关键】优先级设为 -1，确保此源的链接权重最高
                            channels.append((disp, url_line, cat, -1))
                            print(f" ✅ Priority: {name}")
            else: i += 1
    except Exception as e: print(f"❌ 加载优先级源失败: {e}")
    return channels<websource>source_group_web_1</websource>

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
                    channels.append((name, url, "本地节目", 1)) # 优先级 1
            else: i += 1
    except Exception as e: print(f"❌ 加载白名单失败: {e}")
    return channels<websource>source_group_web_2</websource>

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
                            channels.append((disp, url_line, cat, 2)) # 优先级 2
            else: i += 1
    except Exception as e: print(f"❌ 加载 TV M3U 失败: {e}")
    return channels<websource>source_group_web_3</websource>

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
                    channels.append((disp, url, cat, 3)) # 优先级 3
    except Exception as e: print(f"❌ 加载 local.txt 失败: {e}")
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
        # 字典 key 为频道名，value 为频道信息
        unique_channels_map = {}
        for channel in all_channels:
            name = channel
            priority = channel
            # 如果频道不存在，或者当前频道的优先级更高（数字更小），则更新
            if name not in unique_channels_map or priority < unique_channels_map[name]:
                unique_channels_map[name] = channel
        
        unique_channels = list(unique_channels_map.values())
        print(f"✅ 去重完成，剩余频道数: {len(unique_channels)}")<websource>source_group_web_5</websource>

        # 3. 排序与输出 (核心修改：强制本地节目置顶)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 提取所有唯一的分组名称
            all_groups = set(channel for channel in unique_channels)
            
            # 定义排序规则：'本地节目' 必须在最前面
            sorted_groups = sorted(list(all_groups), key=lambda x: (0 if x == '本地节目' else 1, x))
            
            # 按排序后的分组写入文件
            for group in sorted_groups:
                # 找出属于当前分组的所有频道
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
