# -*- coding: utf-8 -*-
import requests
import os
import sys
from urllib.parse import urlparse
import re
import time
import hashlib
import json

# ================== Configuration ==================
# --- 核心配置：南充/西充 API ---
NANCHONG_API_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2" 
BASE_DOMAIN = "https://ncpull.cnncw.cn"

# --- 其他数据源 ---
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

def generate_signature(path, timestamp):
    """核心算法：MD5(密钥 + 路径 + 时间戳)"""
    raw_string = f"{SECRET_KEY}{path}{timestamp}"
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

def categorize_channel(name):
    """
    【核心修复】精准分类逻辑
    1. 本地 -> 2. 央视 -> 3. 卫视 -> 4. 电影 -> 5. 省份
    """
    # --- 🔴 第一优先级：本地节目 ---
    local_keywords = ['西充', '南充']
    if any(kw in name for kw in local_keywords):
        return "本地节目", name

    # --- ⚪️ 第二优先级：央视 ---
    if any(kw in name.lower() for kw in ['cctv', '中央']):
        match = re.search(r'CCTV\D*(\d+)', name.upper())
        if match: 
            return f"CCTV-{int(match.group(1))}", name
        return "央视", name
    
    # --- 🛰️ 第三优先级：卫视 ---
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name.lower(): return '卫视', name
    
    # --- 🎬 第四优先级：电影 ---
    has_movie_kw = any(kw.lower() in name.lower() for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name.lower() for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw: return '电影轮播', name
    if has_movie_kw: return '电影频道', name
    
    # --- 🌏 第五优先级：港澳台 ---
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name: return '港澳台', name
        
    # --- 🗺️ 第六优先级：省份 ---
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name: return prov, name
            
    # --- 默认：其他 ---
    return "其他", name

# ================== Data Sources ==================
def get_nanchong_dynamic_stream():
    """
    使用 IPTVUpdater 逻辑获取南充/西充最新带签名链接
    """
    channels = []
    try:
        print(f"📡 正在请求南充API并生成签名...")
        response = requests.get(NANCHONG_API_URL, headers=DEFAULT_HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("isSuccess"):
                # 解析 JSON 结构
                items = data["data"][0]["propValue"]["children"][0]["dataList"]
                
                # 设置过期时间：当前时间 + 2小时 (7200秒)
                expire_time = int(time.time()) + 7200
                
                for item in items:
                    title = item.get("title")
                    # 尝试多种可能的ID字段名
                    channel_id = item.get("channelID") or item.get("id") or item.get("streamId")
                    
                    # 如果没有ID，尝试从 liveStream 字段提取 (兼容旧逻辑)
                    if not channel_id and item.get("liveStream"):
                        try:
                            channel_id = item.get("liveStream").split("/")[-2]
                        except: pass

                    if not channel_id:
                        continue
                        
                    # 构造路径
                    path = f"/live/{channel_id}/playlist.m3u8"
                    
                    # 计算签名
                    ws_secret = generate_signature(path, expire_time)
                    
                    # 拼接最终地址
                    final_url = f"{BASE_DOMAIN}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                    
                    cat, disp = categorize_channel(title)
                    channels.append((disp, final_url, cat, -2)) # 优先级 -2 (最高，确保覆盖旧链接)
                    print(f" ✅ 更新: {title} [{cat}]")
            else:
                print(f"❌ API返回错误: {data.get('msg')}")
        else:
            print(f"❌ 网络请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 获取南充流失败: {e}")
    return channels

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
        
        # 1. 按优先级顺序加载数据
        # 核心：先加载南充API（带签名），确保本地和央视是最新的
        all_channels.extend(get_nanchong_dynamic_stream()) 
        
        all_channels.extend(load_priority_source()) # 优先级 -1
        
        all_channels.extend(load_remote_whitelist()) # 优先级 1
        all_channels.extend(load_tv_m3u())           # 优先级 2
        all_channels.extend(load_local_txt())        # 优先级 3

        # 2. 数据去重与更新
        unique_channels_map = {}
        for channel in all_channels:
            name = channel[0]
            priority = channel[3]
            if name not in unique_channels_map or priority < unique_channels_map[name][3]:
                unique_channels_map[name] = channel
        
        unique_channels = list(unique_channels_map.values())
        print(f"✅ 去重完成，剩余频道数: {len(unique_channels)}")

        # 3. 输出文件
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 提取所有唯一的分组名称
            all_groups = set(channel[2] for channel in unique_channels)
            
            # 定义排序规则：'本地节目' 必须在最前面，其次是 '央视'，然后是其他
            def sort_key(x):
                if x == '本地节目': return 0
                if x == '央视': return 1
                if x == '卫视': return 2
                return 3
            
            sorted_groups = sorted(list(all_groups), key=sort_key)
            
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
