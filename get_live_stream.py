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
        # --- 核心配置 ---
        # 你的私有源配置
        self.IPTV_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
        self.IPTV_SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
        self.IPTV_BASE_DOMAIN = "https://ncpull.cnncw.cn"

        # 其他辅助源配置
        self.PRIORITY_SOURCE_URL = "https://lin.305362.xyz/migu66"
        self.REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
        self.TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
        
        # 输出配置
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")

        # 请求头
        self.DEFAULT_HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # --- 2026年广东佛山定制化配置 ---
        self.LOCATION = "广东佛山"
        print(f"🌍 运行环境：2026-05-05 | {self.LOCATION}")

    def generate_signature(self, path, timestamp):
        """核心算法：MD5(密钥 + 路径 + 时间戳)"""
        raw_string = f"{self.IPTV_SECRET_KEY}{path}{timestamp}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def fetch_signed_channels(self):
        """获取私有源频道（带签名）"""
        channels = []
        try:
            print(f"🚀 正在连接 kstatic.sctvcloud.com 获取私有源...")
            response = requests.get(self.IPTV_JSON_URL, headers=self.DEFAULT_HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # 兼容性解析
                prop_value = data.get("data", {})
                if isinstance(prop_value, list) and prop_value:
                    prop_value = prop_value[0]
                prop_value = prop_value.get("propValue", {})
                if isinstance(prop_value, list) and prop_value:
                    prop_value = prop_value[0]
                items = prop_value.get("children", [])[0].get("dataList", [])
                
                print(f"✅ 私有源接口连接成功！共发现 {len(items)} 个频道。")
                expire_time = int(time.time()) + 7200 # 2小时有效期

                for i, item in enumerate(items):
                    original_title = item.get("title")
                    live_stream = item.get("liveStream", "")
                    
                    # --- 重命名与ID提取 ---
                    final_name = self._rename_channel(i, original_title)
                    channel_id = self._extract_channel_id(live_stream, final_name)
                    
                    path = f"/live/{channel_id}/playlist.m3u8"
                    ws_secret = self.generate_signature(path, expire_time)
                    final_url = f"{self.IPTV_BASE_DOMAIN}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                    
                    # 分类
                    cat, disp = self.categorize_channel(final_name)
                    channels.append((disp, final_url, cat, -3)) # 优先级 -3
                    
            else:
                print(f"❌ 私有源网络请求失败: {response.status_code}")
        except Exception as e:
            print(f"❌ 私有源处理异常: {e}")
        return channels

    def _rename_channel(self, index, original_title):
        """根据索引重命名频道（示例逻辑）"""
        rename_map = {0: "南充综合", 1: "南充科教"}
        return rename_map.get(index, original_title)

    def _extract_channel_id(self, live_stream, name):
        """从链接提取ID，若失败则生成MD5"""
        path_parts = [p for p in live_stream.split("/") if p]
        if len(path_parts) >= 2:
            return path_parts[-2]
        return hashlib.md5(name.encode()).hexdigest()[:10]

    def categorize_channel(self, name):
        """
        频道分类器（已根据广东佛山优化）
        """
        name_lower = name.lower()
        
        # --- 2026年佛山定制逻辑 ---
        if any(city in name for city in ['佛山', '顺德', '南海', '三水', '高明', '禅城']):
            return '本地节目', name
            
        # 央视
        if any(kw in name_lower for kw in ['cctv', '中央']):
            # 智能标准化CCTV名称
            if "CCTV" in name.upper():
                match = re.search(r'CCTV\D*(\d+)', name.upper())
                if match:
                    return '央视', f"CCTV-{int(match.group(1))}"
            return '央视', name
            
        # 卫视
        major_satellites = ['卫视', '卫星', '湖南卫视', '浙江卫视', '江苏卫视', '东方卫视']
        if any(kw.lower() in name_lower for kw in major_satellites):
            return '卫视', name
            
        # 电影
        movie_keywords = ['电影', '影院', 'CHC', '动作', '喜剧']
        rotation_keywords = ['轮播', '回放']
        if any(kw.lower() in name_lower for kw in movie_keywords):
            if any(kw in name_lower for kw in rotation_keywords):
                return '电影轮播', name
            return '电影频道', name
            
        # 港澳台
        if any(kw in name for kw in ['凤凰', 'TVB', '翡翠', '明珠', '东森']):
            return '港澳台', name
            
        # 其他省份（可扩展）
        province_map = {
            '四川': ['四川', '成都', '南充'],
            '北京': ['北京'],
            '上海': ['上海'],
            '广东': ['广东', '广州', '深圳', '珠海', '佛山'] # 包含其他广东城市
        }
        for prov, cities in province_map.items():
            if any(city in name for city in cities):
                return prov, name

        return "其他", name

    def load_priority_source(self):
        """加载高优先级M3U源"""
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
                            channels.append((disp, url, cat, -2))
        except Exception as e:
            print(f"❌ 加载高优源失败: {e}")
        return channels

    def _is_valid_url(self, url):
        """基础URL验证"""
        try:
            result = urlparse(url.strip())
            return all([result.scheme in ('http', 'https'), result.netloc])
        except:
            return False

    def merge_and_export(self):
        """合并所有源并导出M3U8"""
        print("🚀 开始合并直播源...")
        all_channels = []
        
        # 按优先级加载
        all_channels.extend(self.fetch_signed_channels())      # 优先级 -3
        all_channels.extend(self.load_priority_source())      # 优先级 -2
        
        # --- 这里可以继续添加其他源 ---
        # all_channels.extend(self.fetch_other_sources())     # 优先级 0, 1, 2...
        
        # 去重逻辑（保留最高优先级）
        unique_map = {}
        for name, url, cat, priority in all_channels:
            if name not in unique_map or priority < unique_map[name][3]:
                unique_map[name] = (name, url, cat, priority)
        
        final_list = list(unique_map.values())
        print(f"✅ 去重完成，共 {len(final_list)} 个频道")

        # 写入文件
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            # 排序：本地节目优先，然后是央视、卫视，最后是其他
            group_order = {
                '本地节目': 0,
                '央视': 1,
                '卫视': 2,
                '电影频道': 3,
                '电影轮播': 4,
                '港澳台': 5
            }
            final_list.sort(key=lambda x: (group_order.get(x[2], 99), x[2], x[0]))

            for name, url, cat, _ in final_list:
                f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{cat}",{name}\n')
                f.write(f'{url}\n')
                
        print(f"🎉 完成！保存至: {os.path.abspath(self.OUTPUT_FILE)}")

    def run(self):
        """运行主程序"""
        try:
            self.merge_and_export()
        except Exception as e:
            print(f"❌ 严重错误: {e}")
            sys.exit(1)

if __name__ == "__main__":
    # 实例化并运行
    updater = IPTVUpdater()
    updater.run()
    
    print("\n💡 提示：按任意键退出...")
    input()
