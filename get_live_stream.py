# -*- coding: utf-8 -*-
import requests
import os
import sys
import hashlib
import time
import re
from urllib.parse import urlparse

class IPTVUpdater:
    def __init__(self):
        # === 1. 核心配置 (修复报错的关键部分) ===
        # 定义 Migu 源地址 (根据你的要求优先加载)
        self.MIGU_SOURCE_URL = "http://www.52top.com.cn:678/downloads/migu.txt"
        
        # 定义输出目录和文件
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")
        
        # 定义请求头，防止部分源站拒绝连接
        self.DEFAULT_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # 以下是你原有脚本中的其他配置 (保持不变)
        self.IPTV_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
        self.IPTV_SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
        self.IPTV_BASE_DOMAIN = "https://ncpull.cnncw.cn"
        
        # 辅助源配置
        # 🔽 已将此源优先级调低 (原为高优源 -2，现改为 9)
        self.PRIORITY_SOURCE_URL = "https://lin.305362.xyz/migu66" 
        
        self.REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
        
        # 🔽 已将此源优先级调低 (原为 2，现改为 10)
        self.TV_M3U_URL = "https://gh-proxy.com/https://raw.githubusercontent.com/xichongguo/xichongys2/refs/heads/main/output.m3u8"
        
        # ✅ 修改时间与地点
        print(f"🌍 运行环境：2026-06-01 星期一 | 广东省 佛山市 (定制版)")
        
        # 🔴 修改：频道别名映射表
        self.CHANNEL_ALIASES = {
            "CCTV1": ["CCTV1综合", "cctv1", "cctv-1", "中央1台", "中央一台", "cctv 1", "CCTV-1综合"],
            "CCTV2财经": ["cctv2", "cctv-2", "中央2台", "中央二台", "财经", "cctv 2"],
            "CCTV3综艺": ["cctv3", "cctv-3", "中央3台", "综艺", "cctv 3"],
            "CCTV4中文国际": ["cctv4", "cctv-4", "中央4台", "中文国际", "cctv 4"],
            "CCTV5体育": ["cctv5", "cctv-5", "中央5台", "体育", "cctv 5"],
            "CCTV5+体育赛事": ["cctv5+", "cctv-5+", "体育赛事", "cctv 5+"],
            "CCTV6电影": ["cctv6", "cctv-6", "中央6台", "电影", "cctv 6"],
            "湖南卫视": ["湖南卫视hd", "湖南卫视高清", "hunantv"],
            "南充综合": ["南充综合频道", "南充1台"],
            "西充综合": ["西充综合频道", "西充1台"],
        }

    def normalize_channel_name(self, name):
        name_lower = name.lower().strip()
        for standard_name, aliases in self.CHANNEL_ALIASES.items():
            if name_lower == standard_name.lower() or name_lower in [alias.lower() for alias in aliases]:
                return standard_name
        return name.strip()

    def generate_signature(self, path, timestamp):
        raw_string = f"{self.IPTV_SECRET_KEY}{path}{timestamp}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def fetch_signed_channels(self):
        channels = []
        try:
            print(f"🚀 正在连接 kstatic.sctvcloud.com 获取私有源...")
            response = requests.get(self.IPTV_JSON_URL, headers=self.DEFAULT_HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                prop_value = data.get("data", {})
                if isinstance(prop_value, list) and prop_value:
                    prop_value = prop_value[0]
                    prop_value = prop_value.get("propValue", {})
                if isinstance(prop_value, list) and prop_value:
                    prop_value = prop_value[0]
                children_list = prop_value.get("children", [])
                if isinstance(children_list, list) and children_list:
                    items = children_list[0].get("dataList", [])
                else:
                    items = []
                print(f"✅ 私有源接口连接成功！共发现 {len(items)} 个频道。")
                
                expire_time = int(time.time()) + 90000
                for i, item in enumerate(items):
                    original_title = item.get("title")
                    live_stream = item.get("liveStream", "")
                    final_name = self._rename_channel(i, original_title)
                    channel_id = self._extract_channel_id(live_stream, final_name)
                    path = f"/live/{channel_id}/playlist.m3u8"
                    ws_secret = self.generate_signature(path, expire_time)
                    final_url = f"{self.IPTV_BASE_DOMAIN}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                    cat, disp = self.categorize_channel(final_name)
                    std_name = self.normalize_channel_name(final_name)
                    channels.append((std_name, final_url, cat, -3))
            else:
                print(f"❌ 私有源网络请求失败: {response.status_code}")
        except Exception as e:
            print(f"❌ 私有源处理异常: {e}")
        return channels

    def fetch_xichong_channel(self):
        channels = []
        api_url = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
        headers = {'User-Agent': 'okhttp/3.12.12', 'Accept': 'application/json, text/plain, */*'}
        try:
            print(f"🚀 正在连接 lwydapi.xichongtv.cn 获取西充综合...")
            response = requests.get(api_url, headers=headers, verify=False, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'm3u8Url' in data['data']:
                    m3u8_url = data['data']['m3u8Url']
                    if m3u8_url:
                        print(f"✅ 成功获取西充综合直播流！")
                        channels.append(("西充综合", m3u8_url, '本地节目', -4))
        except Exception as e:
            print(f"❌ 西充频道处理异常: {e}")
        return channels

    def _rename_channel(self, index, original_title):
        rename_map = {0: "南充综合", 1: "南充科教"}
        return rename_map.get(index, original_title)

    def _extract_channel_id(self, live_stream, name):
        path_parts = [p for p in live_stream.split("/") if p]
        if len(path_parts) >= 2:
            return path_parts[-2]
        return hashlib.md5(name.encode()).hexdigest()[:10]

    def categorize_channel(self, name):
        name_lower = name.lower()
        local_keywords = ['西充', '南充', '顺庆', '高坪', '嘉陵', '阆中']
        if any(kw in name for kw in local_keywords):
            return '本地节目', name
        if any(kw.lower() in name_lower for kw in ['cctv', '中央']):
            if "CCTV" in name.upper():
                match = re.search(r'CCTV\D*(\d+)', name.upper())
                if match:
                    return '央视', f"CCTV-{int(match.group(1))}"
            return '央视', name
        major_satellites = ['卫视', '卫星', '湖南卫视', '浙江卫视', '江苏卫视', '东方卫视']
        if any(kw.lower() in name_lower for kw in major_satellites):
            return '卫视', name
        movie_keywords = ['电影', '影院', 'CHC', '动作', '喜剧']
        rotation_keywords = ['轮播', '回放']
        if any(kw.lower() in name_lower for kw in movie_keywords):
            if any(kw in name_lower for kw in rotation_keywords):
                return '电影轮播', name
            return '电影频道', name
        if any(kw in name for kw in ['凤凰', 'TVB', '翡翠', '明珠', '东森', '澳亚']):
            return '港澳台', name
        province_map = {
            '四川': ['四川', '成都'],
            '广东': ['广东', '广州', '深圳', '珠海', '佛山', '东莞'],
            '北京': ['北京'],
            '上海': ['上海']
        }
        for prov, cities in province_map.items():
            if any(city in name for city in cities):
                return prov, name
        return "其他", name

    def load_priority_source(self):
        channels = []
        try:
            response = requests.get(self.PRIORITY_SOURCE_URL, timeout=20, headers=self.DEFAULT_HEADERS)
            lines = response.text.strip().splitlines()
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF") and "," in lines[i]:
                    try:
                        name = lines[i].split(",", 1)[1].strip()
                    except:
                        continue
                    if i + 1 < len(lines):
                        url = lines[i+1].strip()
                        if url.startswith("http") and self._is_valid_url(url):
                            cat, disp = self.categorize_channel(name)
                            std_name = self.normalize_channel_name(name)
                            # 优先级已改为 9 (原为 -2)
                            channels.append((std_name, url, cat, 9)) 
        except Exception as e:
            print(f"❌ 加载高优源失败: {e}")
        return channels

    def load_remote_whitelist(self):
        channels = []
        try:
            print(f"🚀 正在连接远程白名单获取本地节目...")
            response = requests.get(self.REMOTE_WHITELIST_URL, timeout=20)
            for line in response.text.strip().splitlines():
                if "," in line:
                    parts = line.split(",", 1)
                    name, url = parts[0].strip(), parts[1].strip()
                    if name and url and self._is_valid_url(url):
                        cat, disp = self.categorize_channel(name)
                        std_name = self.normalize_channel_name(name)
                        channels.append((std_name, url, cat, 1))
            print(f"✅ 白名单加载完成。")
        except Exception as e:
            print(f"❌ 加载白名单失败: {e}")
        return channels

    def load_tv_m3u(self):
        channels = []
        try:
            response = requests.get(self.TV_M3U_URL, timeout=20, headers=self.DEFAULT_HEADERS)
            lines = response.text.strip().splitlines()
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF") and "," in lines[i]:
                    try:
                        name = lines[i].split(",", 1)[1].strip()
                    except:
                        continue
                    if i + 1 < len(lines):
                        url = lines[i+1].strip()
                        if url.startswith("http") and self._is_valid_url(url):
                            cat, disp = self.categorize_channel(name)
                            std_name = self.normalize_channel_name(name)
                            # 优先级已改为 10 (原为 2)
                            channels.append((std_name, url, cat, 10)) 
        except Exception as e:
            print(f"❌ 加载TV M3U失败: {e}")
        return channels

    def load_migu_source(self):
        channels = []
        try:
            print(f"🚀 正在连接 {self.MIGU_SOURCE_URL} 获取 Migu 源...")
            response = requests.get(self.MIGU_SOURCE_URL, timeout=20, headers=self.DEFAULT_HEADERS)
            lines = response.text.strip().splitlines()
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF") and "," in lines[i]:
                    try:
                        name = lines[i].split(",", 1)[1].strip()
                    except:
                        continue
                    if i + 1 < len(lines):
                        url = lines[i+1].strip()
                        if url.startswith("http") and self._is_valid_url(url):
                            cat, disp = self.categorize_channel(name)
                            std_name = self.normalize_channel_name(name)
                            # 🔴 保持高优先级 -10，确保 Migu 源排在最前面
                            channels.append((std_name, url, cat, -10)) 
            print(f"✅ Migu 源加载完成，共获取 {len(channels)} 个频道流。")
        except Exception as e:
            print(f"❌ 加载 Migu 源失败: {e}")
        return channels

    def _is_valid_url(self, url):
        try:
            result = urlparse(url.strip())
            return all([result.scheme in ('http', 'https'), result.netloc])
        except:
            return False

    def merge_and_export(self):
        print("🚀 开始合并直播源...")
        all_channels = []
        
        # 获取所有源的数据
        all_channels.extend(self.fetch_xichong_channel())
        all_channels.extend(self.fetch_signed_channels())
        
        # === 2. 插入 Migu 源 ===
        all_channels.extend(self.load_migu_source())
        
        # === 3. 加载其他辅助源 ===
        all_channels.extend(self.load_priority_source())
        all_channels.extend(self.load_remote_whitelist())
        all_channels.extend(self.load_tv_m3u())
        
        # --- 去重逻辑 ---
        unique_map = {}
        for name, url, cat, priority in all_channels:
            key = (name, url)
            if key not in unique_map or priority < unique_map[key][3]:
                unique_map[key] = (name, url, cat, priority)
                
        deduplicated_list = list(unique_map.values())
        print(f"✅ 去重完成，剩余 {len(deduplicated_list)} 个唯一频道流")
        
        # --- 排序与写入文件 ---
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 定义分组顺序
            group_order = {
                '本地节目': 0,
                '央视': 1,
                '卫视': 2,
                '电影频道': 6,
                '电影轮播': 7,
                '港澳台': 8,
                '四川': 3,
                '广东': 4
            }
            
            # 排序：先按分组顺序，再按组内名称
            deduplicated_list.sort(key=lambda x: (group_order.get(x[2], 99), x[2], x[0]))
            
            for disp_name, url, cat, _ in deduplicated_list:
                f.write(f'#EXTINF:-1 tvg-name="{disp_name}" group-title="{cat}",{disp_name}\n')
                f.write(f'{url}\n')
                
        print(f"🎉 完成！保存至: {os.path.abspath(self.OUTPUT_FILE)}")

    def run(self):
        try:
            self.merge_and_export()
        except Exception as e:
            print(f"❌ 严重错误: {e}")
            sys.exit(1)

if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.run()
