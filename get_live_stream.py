import requests
import hashlib
import time
import warnings
import os
import json
import re
from urllib.parse import urlparse
import io
import sys

# 设置标准输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

class IPTVUpdater:
    def __init__(self):
        # --- 数据源配置 ---
        self.NANCHONG_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
        # --- 咪咕视频源配置 ---
        self.MIGU_INTERFACE_URL = "https://develop2027.github.io/migu_video/interface.txt"
        # --- 签名与域名配置 (南充源)---
        self.SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
        self.BASE_DOMAIN = "https://ncpull.cnncw.cn"
        # --- 输出配置 ---
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")
        # --- 西充综合专用配置 ---
        self.XICHONG_API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
        self.XICHONG_HEADERS = {
            'User-Agent': 'okhttp/3.12.12',
            'Accept': 'application/json, text/plain, */*'
        }
        # --- 电影/电视剧轮播源配置 ---
        self.MOVIE_TXT_URL = "https://gh-proxy.com/https://raw.githubusercontent.com/xichongguo/live-stream/refs/heads/main/lbt.m3u"
        # --- 自定义视频源配置 ---
        self.CUSTOM_M3U_URL = "http://47.94.6.170/TV/tv.m3u"
        # --- 白名单配置 ---
        self.REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"

        # --- 分类排序权重（数字越小越靠前） ---
        self.CATEGORY_ORDER = {
            "本地节目": 0,
            "咪咕央视": 1,
            "咪咕卫视": 2,
            "咪咕其他": 3,
            "央视频道": 4,
            "卫视频道": 5,
            "少儿频道": 6,
            "体育频道": 7,
            "地方频道": 8,
            "电影/电视剧": 9,
            "其他频道": 10,
        }

    def classify_channel(self, channel_name, default_group="其他频道"):
        """
        全局智能分类函数：根据频道名称自动归类（不含咪咕分类）
        """
        name_upper = channel_name.upper()

        # 1. 央视频道
        if re.search(r'CCTV|中央', name_upper):
            return "央视频道"

        # 2. 卫视频道
        if "卫视" in channel_name:
            return "卫视频道"

        # 3. 少儿/动画
        if any(keyword in channel_name for keyword in ["少儿", "卡通", "动画", "童"]):
            return "少儿频道"

        # 4. 体育频道
        if any(keyword in channel_name for keyword in ["体育", "赛事", "ESPN"]):
            return "体育频道"

        # 5. 省级/地方频道
        provinces = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
                     "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                     "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
                     "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]
        for prov in provinces:
            if prov in channel_name:
                return "地方频道"

        # 6. 电影/电视剧
        if any(keyword in channel_name for keyword in ["电影", "影院", "剧场", "影视"]):
            return "电影/电视剧"

        # 如果都不匹配，返回默认分类
        return default_group

    def classify_migu_channel(self, channel_name):
        """
        咪咕源专用分类：咪咕央视、咪咕卫视、咪咕其他
        """
        name_upper = channel_name.upper()
        if re.search(r'CCTV|中央', name_upper):
            return "咪咕央视"
        if "卫视" in channel_name:
            return "咪咕卫视"
        return "咪咕其他"

    def fetch_movie_channels(self):
        """ 获取电影电视剧轮播源 """
        print(f"🎬 正在获取【电影/电视剧轮播】源...")
        channels = []
        try:
            response = requests.get(self.MOVIE_TXT_URL, timeout=15)
            if response.status_code != 200:
                print(f"❌ 获取电影源失败，状态码: {response.status_code}")
                return channels

            content = response.text
            lines = content.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXTINF"):
                    try:
                        channel_name = ""
                        name_match = re.search(r'tvg-name="([^"]+)"', line)
                        if name_match:
                            channel_name = name_match.group(1).strip()
                        else:
                            comma_split = line.split(',', 1)
                            if len(comma_split) == 2:
                                channel_name = comma_split[1].strip()

                        if not channel_name:
                            i += 1
                            continue

                        category = self.classify_channel(channel_name, "电影/电视剧")

                        if i + 1 < len(lines):
                            url = lines[i + 1].strip()
                            if url.startswith('http'):
                                channels.append((channel_name, url, category))
                                i += 2
                                continue
                    except Exception as e:
                        print(f"❌ 解析电影源行出错: {line[:30]}... 错误: {e}")
                    i += 1
                i += 1
        except Exception as e:
            print(f"❌ 获取/解析电影源异常: {e}")

        print(f"✅ 成功获取 {len(channels)} 个电影/电视剧频道")
        return channels

    def fetch_custom_channels(self):
        """ 获取自定义视频源 """
        print(f"🔗 正在获取【自定义视频源】...")
        channels = []
        try:
            response = requests.get(self.CUSTOM_M3U_URL, timeout=15)
            if response.status_code != 200:
                print(f"❌ 获取自定义源失败，状态码: {response.status_code}")
                return channels

            content = response.text
            lines = content.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXTINF"):
                    try:
                        channel_name = ""
                        name_match = re.search(r'tvg-name="([^"]+)"', line)
                        if name_match:
                            channel_name = name_match.group(1).strip()
                        else:
                            comma_split = line.split(',', 1)
                            if len(comma_split) == 2:
                                channel_name = comma_split[1].strip()

                        if not channel_name:
                            i += 1
                            continue

                        smart_category = self.classify_channel(channel_name, None)
                        if smart_category:
                            category = smart_category
                        else:
                            group_match = re.search(r'group-title="([^"]+)"', line)
                            category = group_match.group(1) if group_match else "其他频道"

                        if i + 1 < len(lines):
                            url = lines[i + 1].strip()
                            if url.startswith('http'):
                                channels.append((channel_name, url, category))
                                i += 2
                                continue
                    except Exception as e:
                        print(f"❌ 解析自定义源行出错: {line[:30]}... 错误: {e}")
                    i += 1
                i += 1
        except Exception as e:
            print(f"❌ 获取/解析自定义源异常: {e}")

        print(f"✅ 成功获取 {len(channels)} 个自定义频道")
        return channels

    def fetch_xichong_channel(self):
        """ 获取西充综合频道 """
        print(f"🚀 正在连接 {self.XICHONG_API_URL} 获取【西充综合】...")
        channels = []
        try:
            response = requests.get(self.XICHONG_API_URL, headers=self.XICHONG_HEADERS, verify=False, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 200 and 'data' in data and 'm3u8Url' in data['data']:
                    m3u8_url = data['data']['m3u8Url']
                    if m3u8_url:
                        print(f"✅ 成功获取西充综合直播流！")
                        channels.append(("西充综合", m3u8_url, '本地节目'))
                    else:
                        print(f"❌ 西充API返回数据中缺少 m3u8Url")
                else:
                    print(f"❌ 西充API返回失败: {data.get('message', '未知错误')}")
            else:
                print(f"❌ 西充API请求失败: {response.status_code}")
        except Exception as e:
            print(f"❌ 西充频道处理异常: {e}")
        return channels

    def generate_signature(self, path, timestamp):
        raw_string = f"{self.SECRET_KEY}{path}{timestamp}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def find_datalist(self, obj, depth=0):
        if depth > 10:
            return None
        if isinstance(obj, dict):
            if "dataList" in obj and isinstance(obj["dataList"], list):
                return obj["dataList"]
            for value in obj.values():
                result = self.find_datalist(value, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self.find_datalist(item, depth + 1)
                if result:
                    return result
        return None

    def fetch_nanchong_channels(self):
        print(f"🚀 正在获取【南充】频道列表...")
        channels = []
        try:
            response = requests.get(self.NANCHONG_JSON_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("isSuccess"):
                    items = self.find_datalist(data)
                    if items:
                        expire_time = int(time.time()) + 86400
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            title = item.get("title", "").strip()
                            if not title:
                                continue
                            # --- 名称映射逻辑 ---
                            if "综合频道" in title:
                                title = "南充综合"
                            elif "科教生活" in title:
                                title = "南充科教生活"

                            stream_id = item.get("liveStreamId")
                            if not stream_id:
                                stream_url = item.get("liveStream", "")
                                if stream_url:
                                    path_parts = urlparse(stream_url).path.rstrip('/').split('/')
                                    if len(path_parts) >= 2:
                                        stream_id = path_parts[-2]
                            if not stream_id:
                                continue

                            path = f"/live/{stream_id}/playlist.m3u8"
                            ws_secret = self.generate_signature(path, expire_time)
                            final_url = f"{self.BASE_DOMAIN}{path}?wsSecret={ws_secret}&wsTime={expire_time}"
                            channels.append((title, final_url, '本地节目'))
                else:
                    print(f"❌ 南充API返回失败: {data.get('msg')}")
            else:
                print(f"❌ 南充API请求状态码异常: {response.status_code}")
        except Exception as e:
            print(f"❌ 获取南充频道异常: {e}")
        print(f"✅ 成功获取 {len(channels)} 个南充频道")
        return channels

    def fetch_migu_channels(self):
        """ 获取咪咕直播源，使用咪咕专用分类 """
        print(f"📡 正在获取【咪咕/外部】直播源...")
        channels = []
        try:
            response = requests.get(self.MIGU_INTERFACE_URL, timeout=15)
            if response.status_code != 200:
                print(f"❌ 获取远程列表失败，状态码: {response.status_code}")
                return channels

            content = response.text
            lines = content.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXTINF"):
                    try:
                        channel_name = None
                        name_match = re.search(r'tvg-name="([^"]+)"', line)
                        if name_match:
                            channel_name = name_match.group(1).strip()
                        else:
                            comma_split = line.split(',', 1)
                            if len(comma_split) == 2:
                                channel_name = comma_split[1].strip()

                        if not channel_name:
                            i += 1
                            continue

                        # 咪咕源使用专用分类函数
                        category = self.classify_migu_channel(channel_name)

                        if i + 1 < len(lines):
                            url_line = lines[i + 1].strip()
                            if url_line.startswith('http'):
                                channels.append((channel_name, url_line, category))
                                i += 2
                                continue
                    except Exception as e:
                        print(f"❌ 解析行出错: {line[:30]}... 错误: {e}")
                    i += 1
                i += 1
        except Exception as e:
            print(f"❌ 获取/解析咪咕源异常: {e}")

        print(f"✅ 成功获取 {len(channels)} 个咪咕频道")
        return channels

    def load_whitelist(self):
        """ 加载本地及远程白名单，统一归类为【本地节目】 """
        print(f"📝 正在加载白名单 (本地 & 远程)...")
        channels = []

        # 1. 加载本地 whitelist.txt
        local_file = "whitelist.txt"
        if os.path.exists(local_file):
            try:
                with open(local_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if not line or line.startswith('#'):
                            i += 1
                            continue
                        name = url = None
                        if line.startswith("#EXTINF"):
                            parts = line.split(',', 1)
                            if len(parts) == 2:
                                name = parts[1].strip()
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line.startswith('http'):
                                    url = next_line
                                    i += 2
                                    continue
                        else:
                            if ',' in line:
                                parts = line.split(',', 1)
                                name = parts[0].strip()
                                url = parts[1].strip()
                        i += 1
                        if name and url and urlparse(url).scheme in ['http', 'https']:
                            # 白名单统一归类为本地节目
                            channels.append((name, url, '本地节目'))
            except Exception as e:
                print(f"❌ 读取本地白名单文件异常: {e}")
        else:
            print("⚠️ 未找到本地 whitelist.txt 文件，跳过。")

        # 2. 加载远程白名单
        try:
            print(f"🚀 正在获取远程白名单: {self.REMOTE_WHITELIST_URL}")
            response = requests.get(self.REMOTE_WHITELIST_URL, timeout=10)
            response.raise_for_status()
            for line in response.text.strip().splitlines():
                line = line.strip()
                if not line or line.startswith('#') or ',' not in line:
                    continue
                parts = line.split(',', 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if name and url and urlparse(url).scheme in ['http', 'https']:
                    # 远程白名单也统一归类为本地节目
                    channels.append((name, url, '本地节目'))
        except Exception as e:
            print(f"❌ 获取远程白名单异常: {e}")

        print(f"✅ 成功加载 {len(channels)} 个白名单频道")
        return channels

    def sort_channels(self, all_channels):
        """ 按分类权重排序，同分类内保持原有顺序 """
        return sorted(all_channels, key=lambda x: self.CATEGORY_ORDER.get(x[2], 99))

    def save_to_m3u8(self, all_channels):
        """ 保存为 M3U8 文件（按分类排序输出） """
        if not os.path.exists(self.OUTPUT_DIR):
            os.makedirs(self.OUTPUT_DIR)

        # 先排序
        sorted_channels = self.sort_channels(all_channels)

        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for name, url, category in sorted_channels:
                f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
                f.write(f'{url}\n')

        # 打印分类统计
        category_count = {}
        for _, _, cat in sorted_channels:
            category_count[cat] = category_count.get(cat, 0) + 1

        print(f"\n🎉 任务完成！共生成 {len(sorted_channels)} 个频道。")
        print(f"📄 文件已保存至: {self.OUTPUT_FILE}")
        print(f"📊 分类统计:")
        for cat in sorted(category_count.keys(), key=lambda x: self.CATEGORY_ORDER.get(x, 99)):
            print(f"   {cat}: {category_count[cat]} 个")

    def run(self):
        print("🔄 开始更新直播源...")
        all_channels = []
        # 按顺序获取各个源的频道
        all_channels.extend(self.fetch_nanchong_channels())
        all_channels.extend(self.fetch_xichong_channel())
        all_channels.extend(self.fetch_movie_channels())
        all_channels.extend(self.fetch_custom_channels())
        all_channels.extend(self.fetch_migu_channels())
        all_channels.extend(self.load_whitelist())
        # 保存文件（内部自动排序）
        self.save_to_m3u8(all_channels)

if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.run()
