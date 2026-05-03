# -*- coding: utf-8 -*-
import requests
import os
import sys
from urllib.parse import urlparse
import re
import hashlib
import time

# ================== Configuration ==================
# --- 原有配置保持不变 ---
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
    
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name: return '港澳台', name
        
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name: return prov, name
            
    return "其他", name

# ================== 🔴 新增核心函数：南充直播源生成器 ==================
def get_nanchong_streams():
    """
    集成之前的代码逻辑，自动生成南充直播源
    """
    channels = []
    
    # --- 1. 获取频道列表 (JSON接口) ---
    JSON_API_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
    SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2" # 你的密钥
    BASE_DOMAIN = "https://ncpull.cnncw.cn"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://rmt.cnncw.cn/'
    }
    
    try:
        print("🚀 正在获取南充频道列表...")
        response = requests.get(JSON_API_URL, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("isSuccess"):
                items = data["data"][0]["propValue"]["children"][0]["dataList"]
                
                # 设置过期时间 (当前时间 + 2小时)
                EXPIRE_TIME = int(time.time()) + 7200
                
                for item in items:
                    title = item.get("title")
                    live_stream = item.get("liveStream", "")
                    
                    # 从 liveStream URL 中提取 streamId (正则匹配)
                    import re
                    match = re.search(r'/live/([^/]+)/playlist\.m3u8', live_stream)
                    if not match:
                        continue
                    stream_id = match.group(1)
                    
                    # --- 2. 签名生成逻辑 (wsSecret) ---
                    # 拼接参数: expire + streamId + secretKey
                    sign_str = f"{EXPIRE_TIME}{stream_id}{SECRET_KEY}"
                    ws_secret = hashlib.md5(sign_str.encode()).hexdigest()
                    
                    # --- 3. 构造最终 URL ---
                    # 基础 URL
                    base_url = f"{BASE_DOMAIN}/live/{stream_id}/playlist.m3u8"
                    # 参数
                    query_params = (
                        f"wsSecret={ws_secret}"
                        f"&wsTime={EXPIRE_TIME}"
                        f"&wsSession=9797c937e9fc6fdb2348696d-177648249365193" # 这里使用了网页3中的固定格式，实际可动态生成但没必要
                        f"&wsIPSercert=9a35ccfbc12d563402ca4334487c10dd"
                        f"&wsiphost=local"
                        f"&wsBindIP=1"
                    )
                    final_url = f"{base_url}?{query_params}"
                    
                    # --- 4. 分类处理 ---
                    # 这里的 title 是 "南充综合" 或 "南充科教"
                    # 我们将其归类为 "本地节目"，优先级设为 -2 (最高优先级)
                    cat, disp = "本地节目", title
                    
                    channels.append((disp, final_url, cat, -2))
                    print(f" ✅ 生成南充频道: {title}")
                    
    except Exception as e:
        print(f"❌ 生成南充源失败: {e}")
    
    return channels

# ================== Data Sources (原有函数保持不变) ==================
def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10, verify=False)
        data = response.json()
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if url.startswith("http"):
                name = "西充综合" 
                cat, disp = "本地节目", name
                return (disp, url, cat, 0)
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
                            channels.append((disp, url_line, cat, -1)) # 优先级 -1 
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
                    channels.append((name, url, "本地节目", 1))
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

# ================== Main Logic (修改排序逻辑) ==================
def main():
    try:
        print("🚀 开始合并直播源...")
        all_channels = []
        
        # 1. 按优先级顺序加载数据
        # 🔴 新增：南充直播源 (优先级 -2，最高)
        all_channels.extend(get_nanchong_streams()) 
        
        # 原有优先级源 (优先级 -1)
        all_channels.extend(load_priority_source()) 
        
        # 动态源 (优先级 0)
        dynamic_channel = get_dynamic_stream()     
        if dynamic_channel: all_channels.append(dynamic_channel)
        
        # 其他源...
        all_channels.extend(load_remote_whitelist()) # 优先级 1
        all_channels.extend(load_tv_m3u())           # 优先级 2
        all_channels.extend(load_local_txt())        # 优先级 3

        # 2. 数据去重 (保留优先级高的)
        unique_channels_map = {}
        for channel in all_channels:
            name = channel[0]
            priority = channel[3]
            if name not in unique_channels_map or priority < unique_channels_map[name][3]:
                unique_channels_map[name] = channel
        
        unique_channels = list(unique_channels_map.values())
        print(f"✅ 去重完成，剩余频道数: {len(unique_channels)}")

        # 3. 排序与输出 (强制本地节目置顶，然后是央视、卫视)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 提取所有唯一的分组名称
            all_groups = set(channel[2] for channel in unique_channels)
            
            # 定义排序规则：
            # 1. 本地节目 (最前)
            # 2. 央视
            # 3. 卫视
            # 4. 其他 (按字母排序)
            priority_order = {'本地节目': 0, '央视': 1, '卫视': 2}
            sorted_groups = sorted(list(all_groups), key=lambda x: (priority_order.get(x, 99), x))
            
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
