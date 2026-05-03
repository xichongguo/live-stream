# -*- coding: utf-8 -*-
import requests
import os
import sys
from urllib.parse import urlparse
import re
import hashlib
import time

# ================== Configuration (新增第一段代码的配置) ==================
# --- IPTVUpdater 相关配置 ---
IPTV_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
IPTV_SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"  # 你的核心密钥
IPTV_BASE_DOMAIN = "https://ncpull.cnncw.cn"

# --- 原第二段代码的配置 ---
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

# --- 新增配置：高优先级源 ---
PRIORITY_SOURCE_URL = "https://lin.305362.xyz/migu66"

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

# ================== Core Algorithm (第一段代码的核心逻辑) ==================
def generate_signature(path, timestamp, secret_key):
    """核心算法：MD5(密钥 + 路径 + 时间戳)"""
    raw_string = f"{secret_key}{path}{timestamp}"
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

def fetch_iptv_channels():
    """
    模拟第一段代码的逻辑，但返回数据结构供主程序处理。
    """
    channels = []
    try:
        print(f"🚀 正在连接 IPTV 服务器获取最新频道列表...")
        response = requests.get(IPTV_JSON_URL, headers=DEFAULT_HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("isSuccess"):
                # 解析 JSON 结构
                items = data["data"][0]["propValue"]["children"][0]["dataList"]
                print(f"✅ IPTV源获取成功！共发现 {len(items)} 个频道。")
                
                # 设置过期时间：当前时间 + 2小时 (7200秒)
                expire_time = int(time.time()) + 7200
                
                for item in items:
                    title = item.get("title")
                    # 简单清洗标题，去除可能的干扰字符
                    clean_title = re.sub(r'\s*[\(\[\{].*?[\)\]\}]$', '', title).strip()
                    
                    # 提取 ID (这里假设 liveStream 字段存在，或者你需要根据实际 JSON 结构调整)
                    # 如果没有 liveStream，可能需要直接使用 ID 字段，或者从其他地方获取
                    try:
                        channel_id = item.get("liveStream").split("/")[-2]
                    except:
                        # 如果解析失败，这里需要一个默认 ID 或者跳过
                        # 为了演示，我们假设 ID 是 title 的某种映射，或者直接使用一个占位符
                        # 在实际环境中，你需要根据 API_URL 返回的具体结构来修正这个提取逻辑
                        channel_id = hashlib.md5(title.encode()).hexdigest()[:16] 
                    
                    # 构造路径
                    path = f"/live/{channel_id}/playlist.m3u8"
                    
                    # 计算签名
                    ws_secret = generate_signature(path, expire_time, IPTV_SECRET_KEY)
                    
                    # 拼接最终地址
                    final_url = f"{IPTV_BASE_DOMAIN}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                    
                    # 分类 (可以根据 title 关键词调整，这里默认为 "IPTV源")
                    cat, disp_name = categorize_channel(clean_title)
                    
                    # 返回标准格式 (显示名, URL, 分类, 优先级)
                    # 优先级设为 0，仅次于高优先级源
                    channels.append((disp_name, final_url, cat, 0))
                    
            else:
                print("❌ IPTV API返回错误:", data.get("msg"))
        else:
            print(f"❌ IPTV 网络请求失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 获取 IPTV 源时发生异常: {e}")
    
    return channels

# ================== Data Sources (原第二段代码的逻辑) ==================
def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10, verify=False)
        data = response.json()
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if url.startswith("http"):
                name = "西充综合" 
                cat, disp = "本地节目", name
                return (disp, url, cat, -1) # 优先级 -1 (最高)
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
                try: name = line.split(",", 1)[1].strip()
                except: i += 1; continue
                i += 1
                if i < len(lines):
                    url_line = lines[i].strip()
                    if url_line.startswith("http") and is_valid_url(url_line):
                        if not is_foreign_channel(name):
                            cat, disp = categorize_channel(name)
                            channels.append((disp, url_line, cat, -2)) # 优先级 -2 (最高中的最高)
                            print(f" ✅ Priority: {name}")
            else: i += 1
    except Exception as e: print(f"❌ 加载优先级源失败: {e}")
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
                    channels.append((name, url, "白名单源", 1))
    except Exception as e: print(f"❌ 加载白名单失败: {e}")
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
                try: name = line.split(",", 1)[1].strip()
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
    return channels

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
                name, url = parts[0].strip(), parts[1].strip()
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    cat, disp = categorize_channel(name)
                    channels.append((disp, url, cat, 3))
    except Exception as e: print(f"❌ 加载 local.txt 失败: {e}")
    return channels

# ================== Main Logic ==================
def main():
    try:
        print("🚀 开始合并直播源...")
        all_channels = []
        
        # 1. 按优先级顺序加载数据
        # 优先级 -2: 特殊高优源
        all_channels.extend(load_priority_source()) 
        
        # 优先级 -1: 动态 API 源 (西充综合)
        dynamic_channel = get_dynamic_stream()     
        if dynamic_channel: all_channels.append(dynamic_channel)
        
        # 优先级 0: 整合进来的第一段代码源 (IPTVUpdater)
        all_channels.extend(fetch_iptv_channels()) 
        
        # 优先级 1: 白名单
        all_channels.extend(load_remote_whitelist()) 
        
        # 优先级 2: TV M3U
        all_channels.extend(load_tv_m3u())           
        
        # 优先级 3: 本地文件
        all_channels.extend(load_local_txt())       

        # 2. 数据去重 (保留优先级高的)
        # 字典键为 频道名，值为 该频道的数据和优先级
        unique_channels_map = {}
        for channel in all_channels:
            name = channel[0]
            priority = channel[3]
            # 如果名字没出现过，或者新出现的优先级更高(数字更小)，则替换
            if name not in unique_channels_map or priority < unique_channels_map[name][3]:
                unique_channels_map[name] = channel
        
        unique_channels = list(unique_channels_map.values())
        print(f"✅ 去重完成，剩余频道数: {len(unique_channels)}")

        # 3. 排序与输出 (强制本地节目置顶)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 提取所有唯一的分组名称
            all_groups = set(channel[2] for channel in unique_channels)
            
            # 定义排序规则：'本地节目' 和 '白名单源' 必须在最前面
            def sort_group_key(group_name):
                if group_name == '本地节目':
                    return (0, group_name)
                elif group_name == '白名单源':
                    return (1, group_name)
                else:
                    return (2, group_name)
            
            sorted_groups = sorted(list(all_groups), key=sort_group_key)
            
            # 按排序后的分组写入文件
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
