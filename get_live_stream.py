# -*- coding: utf-8 -*-
import requests
import os
import sys
import re
import time
import hashlib
from urllib.parse import urlparse, unquote

# ================== 配置区域 ==================
# 数据源配置
SOURCES = {
    "priority": "https://lin.305362.xyz/migu66",          # 高优先级源 (如米咕)
    "whitelist": "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt", # 白名单
    "tv_m3u": "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u", # 通用 M3U
    "local_txt": "local.txt"                              # 本地文件
}

# 西充 API 专用配置 (参考之前的对话)
XC_API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
XC_PARAMS = {'deviceType': '1', 'centerId': '9', 'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be', 'areaId': '907'}
XC_HEADERS = {'User-Agent': 'okhttp/3.12.12'}

# 输出配置
OUTPUT_FILE = "current.m3u8"
EPG_URL = "https://live.fanmingming.com/e.xml.gz" # 节目单地址

# 请求头伪装
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ================== 核心分类与清洗逻辑 ==================

def clean_channel_name(name):
    """
    清洗频道名称，去除多余的空格和特殊符号
    """
    return re.sub(r'\s+', ' ', name.strip())

def get_category_and_display(name):
    """
    【核心功能】智能分类与显示名称处理
    目标：将 CCTV-1, cctv1, 中央一套 统一归类为 '央视'
    """
    name_clean = clean_channel_name(name)
    name_lower = name_clean.lower()

    # 1. 央视/CCTV 归一化处理
    # 匹配模式：CCTV-1, CCTV1, CCTV-13, 中央-1, 中央一套
    cctv_match = re.search(r'(?:cctv|中央)[\s\-_]*(\d+|[+\-]?)', name_lower)
    if cctv_match:
        num = cctv_match.group(1)
        # 统一显示名称格式：CCTV-X
        standard_name = f"CCTV-{num}" if num not in ['+', '-'] else f"CCTV{num}"
        return "央视", standard_name

    # 2. 卫视频道
    if "卫视" in name_lower:
        return "卫视", name_clean

    # 3. 本地/省份优先 (根据关键词)
    local_keywords = ['西充', '南充', '四川', '广东', '佛山']
    for kw in local_keywords:
        if kw in name_clean:
            return "本地节目", name_clean

    # 4. 电影/轮播
    if any(kw in name_lower for kw in ['电影', '影院', 'chc']):
        return "电影频道", name_clean
    
    # 5. 港澳台
    if any(kw in name_clean for kw in ['凤凰', 'TVB', '翡翠', '明珠', '东森']):
        return "港澳台", name_clean

    # 6. 默认其他
    return "其他", name_clean

def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

# ================== 数据获取模块 ==================

def fetch_xichong_api():
    """获取西充动态流"""
    channels = []
    try:
        print(f"📡 正在请求西充API...")
        response = requests.get(XC_API_URL, params=XC_PARAMS, headers=XC_HEADERS, timeout=10, verify=False)
        data = response.json()
        
        if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            name = "西充综合"
            if url.startswith("http"):
                # 强制归类为本地
                channels.append((name, url, "本地节目"))
                print(f"   ✅ 获取到: {name}")
    except Exception as e: 
        print(f"   ❌ API 获取失败: {e}")
    return channels

def parse_m3u_content(text, source_name):
    """解析 M3U/TXT 文本内容"""
    channels = []
    lines = text.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 处理 #EXTINF 行或 txt 格式的 "名称,URL" 行
        if line.startswith("#EXTINF"):
            try:
                # 提取名称：通常位于最后一个逗号之后
                name = line.split(",")[-1].strip()
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    if url.startswith("http") and is_valid_url(url):
                        cat, disp_name = get_category_and_display(name)
                        channels.append((disp_name, url, cat))
            except:
                pass
        elif "," in line and not line.startswith("#"):
            # 处理 txt 格式: 频道名,地址
            parts = line.split(",", 1)
            if len(parts) == 2:
                name, url = parts.strip(), parts.strip()
                if is_valid_url(url):
                    cat, disp_name = get_category_and_display(name)
                    channels.append((disp_name, url, cat))
        i += 1
    return channels<websource>source_group_web_1</websource>

def fetch_source(url, name):
    """通用网络源获取"""
    try:
        print(f"📥 正在加载: {name}...")
        response = requests.get(url, timeout=15, headers=DEFAULT_HEADERS)
        response.encoding = 'utf-8'
        return parse_m3u_content(response.text, name)
    except Exception as e:
        print(f"   ❌ 加载 {name} 失败: {e}")
        return []

def load_local_file(path):
    """加载本地文件"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return parse_m3u_content(f.read(), "本地文件")
    except Exception as e:
        print(f"   ❌ 读取本地文件失败: {e}")
        return []

# ================== 主程序 ==================

def main():
    print("🚀 开始合并与整理 IPTV 直播源...")
    all_channels = []

    # 1. 按顺序收集所有频道
    # 注意：这里不立即去重，而是收集所有，稍后根据优先级处理
    all_channels.extend(fetch_source(SOURCES["priority"], "高优先级源"))
    all_channels.extend(fetch_xichong_api()) # 插入 API 数据
    all_channels.extend(fetch_source(SOURCES["whitelist"], "白名单"))
    all_channels.extend(fetch_source(SOURCES["tv_m3u"], "TV M3U"))
    all_channels.extend(load_local_file(SOURCES["local_txt"]))

    print(f"\n🧹 正在进行智能去重与归类...")

    # 2. 智能去重逻辑
    # 规则：以“显示名称”为键。如果名称相同，保留最先出现的（因为 priority 源排在最前）
    # 这样可以确保 CCTV-1 的各种别名最终都指向高质量源
    unique_map = {}
    
    for name, url, category in all_channels:
        if name not in unique_map:
            unique_map[name] = (url, category)
        # 如果想让后面的源覆盖前面的，可以去掉上面的 if 判断，直接赋值

    # 3. 分组排序
    # 定义分组顺序：本地 -> 央视 -> 卫视 -> 电影 -> 港澳台 -> 其他
    group_order = ["本地节目", "央视", "卫视", "电影频道", "港澳台", "其他"]
    sorted_channels = []
    
    # 先按预定顺序排列已知组
    for group in group_order:
        group_items = [(name, url, cat) for name, (url, cat) in unique_map.items() if cat == group]
        # 组内按名称排序
        group_items.sort(key=lambda x: x)
        sorted_channels.extend(group_items)
    
    # 添加未预定义的组（如有）
    remaining_groups = set(cat for _, (_, cat) in unique_map.items()) - set(group_order)
    for group in remaining_groups:
        group_items = [(name, url, cat) for name, (url, cat) in unique_map.items() if cat == group]
        group_items.sort(key=lambda x: x)
        sorted_channels.extend(group_items)

    # 4. 写入文件
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            # 写入头部
            f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
            
            count = 0
            for name, url, category in sorted_channels:
                # 写入 EXTINF 信息
                # tvg-name 用于匹配 EPG，这里使用标准化后的名称
                f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
                f.write(f'{url}\n')
                count += 1
        
        print(f"\n✅ 处理完成！")
        print(f"📊 共收录频道: {count} 个")
        print(f"💾 文件已保存: {os.path.abspath(OUTPUT_FILE)}")
        
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")

if __name__ == "__main__":
    main()
