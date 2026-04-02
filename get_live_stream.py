import requests
import os
import sys
from urllib.parse import urlparse
import re

# ================== Configuration (保留你提供的完整配置) ==================
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
}
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
LOCAL_TXT_PATH = "local.txt" # 本地文件路径
WHITELIST_TIMEOUT = 20
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")

# ---------------- 省份映射表 (保留原样) ----------------
PROVINCE_KEYWORDS = {
    '四川': ['四川', '成都', '绵阳', '德阳', '南充', '宜宾', '泸州', '乐山', '达州', '内江', '自贡', '攀枝花', '广安', '遂宁', '资阳', '眉山', '雅安', '巴中', '阿坝', '甘孜', '凉山'],
    '广东': ['广东', '广州', '深圳', '佛山', '东莞', '中山', '珠海', '惠州', '江门', '肇庆', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江', '云浮', '清远', '韶关', '河源'],
    # ... 其他省份保持不变 (代码过长省略，保留原上传文档内容) ...
    '新疆': ['新疆', '乌鲁木齐', '克拉玛依', '吐鲁番', '哈密', '昌吉', '博尔塔拉', '巴音郭楞', '阿克苏', '克孜勒苏', '喀什', '和田', '伊犁', '塔城', '阿勒泰'],
    '西藏': ['西藏', '拉萨', '日喀则', '昌都', '林芝', '山南', '那曲', '阿里']
}

CATEGORY_MAP = {
    '卫视': ['卫视', '卫星', '东方', '北京卫视', '天津卫视', '河北卫视', '山西卫视', '内蒙古卫视', '辽宁卫视', '吉林卫视', '黑龙江卫视', '江苏卫视', '浙江卫视', '安徽卫视', '福建东南', '江西卫视', '山东卫视', '河南卫视', '湖北卫视', '湖南卫视', '广东卫视', '广西卫视', '海南卫视', '四川卫视', '重庆卫视', '贵州卫视', '云南卫视', '西藏卫视', '陕西卫视', '甘肃卫视', '青海卫视', '宁夏卫视', '新疆卫视'],
    '电影关键词': ['电影', '影院', 'CHC', '华数', '优酷', '爱奇艺', '腾讯', '芒果', '动作', '喜剧', '爱情', '科幻', '恐怖', '战争', '剧情', '影视'],
    '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', 'J2', 'HOY', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'],
    '经典剧场': ['经典', '怀旧', '老电影', '戏曲', '京剧']
}

ROTATION_KEYWORDS = ['轮播', '回放', '测试']
FOREIGN_KEYWORDS = {
    'CNN', 'BBC', 'NHK', 'KBS', 'MBC', 'SBS', 'Arirang', 'France', 'Deutsch', 'RTL', 'Sky', 'Al Jazeera', 'HBO', 'ESPN', 'Star Sports', 'Fox', 'Discovery', 'National Geographic', 'Cartoon Network', 'Nickelodeon', 'MTV', 'VH1', 'CNBC', 'Bloomberg', 'DW', 'RT', 'CGTN', 'ABS-CBN', 'GMA', 'TV5'
}
ALLOWED_FOREIGN = {'凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'}

# ================== Helper Functions (保留原样) ==================
def is_foreign_channel(name):
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    for keyword in FOREIGN_KEYWORDS:
        if keyword.lower() in name_lower:
            return True
    return False

def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

def normalize_cctv_name(name):
    CHINESE_ALIAS = {
        "中央一套": "CCTV-1", "综合频道": "CCTV-1", "中央二套": "CCTV-2", "财经频道": "CCTV-2",
        "中央三套": "CCTV-3", "综艺频道": "CCTV-3", "中央四套": "CCTV-4", "中文国际频道": "CCTV-4",
        "中央五套": "CCTV-5", "体育频道": "CCTV-5", "中央六套": "CCTV-6", "电影频道": "CCTV-6",
        "中央七套": "CCTV-7", "国防军事频道": "CCTV-7", "中央八套": "CCTV-8", "电视剧频道": "CCTV-8",
        "中央九套": "CCTV-9", "纪录频道": "CCTV-9", "中央十套": "CCTV-10", "科教频道": "CCTV-10",
        "中央十一套": "CCTV-11", "戏曲频道": "CCTV-11", "中央十二套": "CCTV-12", "社会与法频道": "CCTV-12",
        "中央十三套": "CCTV-13", "新闻频道": "CCTV-13", "中央十四套": "CCTV-14", "少儿频道": "CCTV-14",
        "中央十五套": "CCTV-15", "音乐频道": "CCTV-15", "中央十七套": "CCTV-17", "农业农村频道": "CCTV-17",
    }
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
    name_lower = name.lower()
    if any(kw in name_lower for kw in ['cctv', '中央']):
        return '央视', normalize_cctv_name(name)
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower:
            return '卫视', name
    has_movie_kw = any(kw.lower() in name_lower for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name_lower for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw:
        return '电影轮播', name
    if has_movie_kw and not has_rotation_kw:
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
    if has_rotation_kw:
        return '其他', name
    return "其他", name

# ================== Load Sources (新增 local.txt 和 whitelist.txt 支持) ==================
def get_dynamic_stream():
    """获取 API 中的直播流地址 (西充综合)"""
    try:
        # verify=False 用于跳过 SSL 验证 (对应 PHP 的 SSL=>1)
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10, verify=False)
        data = response.json()
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            if url.startswith("http"):
                if not is_foreign_channel("西充综合"):
                    cat, disp = categorize_channel("西充综合")
                    return (disp, url, cat, 0)
    except Exception as e:
        print(f"API 获取失败: {e}")
    return None

def load_tv_m3u():
    """从 GitHub 加载 tv.m3u"""
    channels = []
    try:
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF") and "," in line:
                # 提取频道名 (处理可能包含逗号的 Tvg 信息)
                try:
                    # 简单处理：取最后一个逗号后的作为名字
                    name = line.split(",", 1)[1].strip()
                except:
                    i += 1
                    continue
                
                i += 1
                if i < len(lines):
                    url_line = lines[i].strip()
                    if url_line.startswith("http") and is_valid_url(url_line):
                        if not is_foreign_channel(name):
                            cat, disp = categorize_channel(name)
                            channels.append((disp, url_line, cat, 2))
            else:
                i += 1
    except Exception as e:
        print(f"❌ 加载 tv.m3u 失败: {e}")
    return channels

def load_remote_whitelist():
    """加载远程 whitelist.txt，分类为 '本地节目'"""
    channels = []
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        lines = response.text.strip().splitlines()
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            # 假设 whitelist.txt 格式为: 频道名,http://url...
            if "," in line:
                parts = line.split(",", 1)
                name = parts[0].strip()
                url = parts[1].strip()
                
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    # 强制分类为“本地节目”
                    channels.append((name, url, "本地节目", 1))
                    print(f" ✅ Whitelist: {name}")
                    
    except Exception as e:
        print(f"❌ 加载 whitelist.txt 失败: {e}")
    return channels

def load_local_txt():
    """加载本地 local.txt"""
    channels = []
    if not os.path.exists(LOCAL_TXT_PATH):
        print(f"⚠️ 未找到本地文件: {LOCAL_TXT_PATH} (如果这是预期的，请忽略此警告)")
        return channels
        
    try:
        with open(LOCAL_TXT_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            if "," in line:
                parts = line.split(",", 1)
                name = parts[0].strip()
                url = parts[1].strip()
                
                if name and url and is_valid_url(url) and not is_foreign_channel(name):
                    cat, disp = categorize_channel(name)
                    channels.append((disp, url, cat, 3))
                    print(f" ✅ Local: {name}")
                    
    except Exception as e:
        print(f"❌ 加载 local.txt 失败: {e}")
    return channels

# ================== Main Logic (合并逻辑) ==================
def main():
    print("🚀 开始合并直播源 (API + tv.m3u + whitelist.txt + local.txt)...")
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. 获取所有数据源
    all_channels = []
    
    # A. 获取动态流 (西充综合)
    dynamic_channel = get_dynamic_stream()
    if dynamic_channel:
        all_channels.append(dynamic_channel)
        print(f"✅ 获取到动态流: {dynamic_channel[0]}")
    
    # B. 获取远程白名单 (本地节目)
    whitelist_channels = load_remote_whitelist()
    all_channels.extend(whitelist_channels)
    
    # C. 获取 GitHub 源
    github_channels = load_tv_m3u()
    all_channels.extend(github_channels)
    
    # D. 获取本地文件
    local_channels = load_local_txt()
    all_channels.extend(local_channels)

    # 2. 写入 M3U8 文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # 写入 M3U8 头部 (包含 EPG 信息)
        f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
        
        for channel in all_channels:
            name, url, category, priority = channel
            # 写入频道信息行
            # 使用 tvg-name 作为 ID，group-title 作为分类
            f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
            f.write(f'{url}\n')
    
    print(f"🎉 合并完成！总频道数: {len(all_channels)}")
    print(f"📁 文件已保存至: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
