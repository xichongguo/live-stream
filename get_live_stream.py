# -*- coding: utf-8 -*-
import requests
import os
import sys
import io
import hashlib
import time
import re
from urllib.parse import urlparse

# 🔧 强制将终端标准输出的编码设置为 UTF-8，防止控制台打印中文乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class IPTVUpdater:
    def __init__(self):
        # === 1. 核心配置 ===
        self.MIGU_SOURCE_URL = "http://www.52top.com.cn:678/downloads/migu.txt"
        self.MIGU_LOCAL_FILE = "migu.txt" # 兜底方案：本地文件名
        self.HD_SOURCE_URL = "https://raw.githubusercontent.com/xichongguo/xichongys2/refs/heads/main/output.m3u8"
        
        # 定义输出目录和文件
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")
        
        # 定义请求头
        self.DEFAULT_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        self.IPTV_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
        self.IPTV_SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
        self.IPTV_BASE_DOMAIN = "https://ncpull.cnncw.cn"
        # 这个白名单IP在GitHub服务器上极易造成网络阻塞，已将其加载顺序挪到最后
        self.REMOTE_WHITELIST_URL = "http://114.226.216.63:5140/playlist.m3u"
        
        print(f"🌍 运行环境：2026-06-02 星期二 | 广东省 佛山市 (定制版)")
        
        # 🔴 频道别名映射表
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
            response = requests.get(self.IPTV_JSON_URL, headers=self.DEFAULT_HEADERS, timeout=10, verify=False)
            response.encoding = response.apparent_encoding
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
                print(f"✅ 私有源接口连接成功！共发现 {len(items)} 个频道流。")
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
            print(f"⚠️ 私有源连接超时或失败(GitHub服务器可能无法访问国内接口)，已自动跳过: {e}")
        return channels

    def fetch_xichong_channel(self):
        channels = []
        api_url = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
        headers = {'User-Agent': 'okhttp/3.12.12', 'Accept': 'application/json, text/plain, */*'}
        try:
            print(f"🚀 正在连接 lwydapi.xichongtv.cn 获取西充综合...")
            response = requests.get(api_url, headers=headers, verify=False, timeout=10)
            response.encoding = response.apparent_encoding
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'm3u8Url' in data['data']:
                    m3u8_url = data['data']['m3u8Url']
                    if m3u8_url:
                        print(f"✅ 成功获取西充综合直播流！")
                        channels.append(("西充综合", m3u8_url, '本地节目', -4))
        except Exception as e:
            print(f"⚠️ 西充频道连接超时或失败(GitHub服务器可能无法访问国内接口)，已自动跳过: {e}")
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
        
        # 1. 本地节目
        local_keywords = ['西充', '南充', '顺庆', '高坪', '嘉陵', '阆中']
        if any(kw in name for kw in local_keywords):
            return '本地节目', name
            
        # 2. 央视
        if any(kw.lower() in name_lower for kw in ['cctv', '中央']):
            if "CCTV" in name.upper():
                match = re.search(r'CCTV\D*(\d+)', name.upper())
                if match:
                    return '央视', f"CCTV-{int(match.group(1))}"
            return '央视', name
            
        # 3. 卫视
        major_satellites = ['卫视', '卫星', '湖南卫视', '浙江卫视', '江苏卫视', '东方卫视']
        if any(kw.lower() in name_lower for kw in major_satellites):
            return '卫视', name
            
        # 4. 电影
        movie_keywords = ['电影', '影院', 'CHC', '动作', '喜剧']
        rotation_keywords = ['轮播', '回放']
        if any(kw.lower() in name_lower for kw in movie_keywords):
            if any(kw in name_lower for kw in rotation_keywords):
                return '电影轮播', name
            return '电影频道', name
            
        # 5. 港澳台
        if any(kw in name for kw in ['凤凰', 'TVB', '翡翠', '明珠', '东森', '澳亚', '星空']):
            return '港澳台', name
            
        # 6. 体育
        if any(kw in name_lower for kw in ['体育', '赛事', 'nba', '足球', '篮球']):
            return '体育', name
            
        # 7. 少儿/动画
        if any(kw in name_lower for kw in ['少儿', '卡通', '动画', '动漫', '哈哈炫动', '金鹰卡通', '卡酷']):
            return '少儿', name
            
        # 8. 教育/学习
        if any(kw in name_lower for kw in ['教育', '学习', '考试', '校园', '中学生']):
            return '教育', name
            
        # 9. 纪录片/地理
        if any(kw in name_lower for kw in ['纪录', '探索', '地理', '发现', '历史']):
            return '纪录片', name
            
        # 10. 音乐
        if any(kw in name_lower for kw in ['音乐', 'mtv', '声乐', '演唱会']):
            return '音乐', name
            
        # 11. 生活/科教
        if any(kw in name_lower for kw in ['生活', '科教', '科技', '农业', '纪实']):
            return '生活科教', name
            
        # 12. 法治/社会
        if any(kw in name_lower for kw in ['法治', '法制', '政法', '社会']):
            return '法治社会', name
            
        # 13. 省份归类
        province_map = {
            '四川': ['四川', '成都', '峨眉'],
            '广东': ['广东', '广州', '深圳', '珠海', '佛山', '东莞', '南方卫视'],
            '北京': ['北京'],
            '上海': ['上海', '东方', '第一财经']
        }
        for prov, cities in province_map.items():
            if any(city in name for city in cities):
                return prov, name
                
        # 14. 兜底分类
        return "综合/其他", name

    def load_hd_source(self):
        channels = []
        try:
            print(f"🚀 正在连接 {self.HD_SOURCE_URL} 获取高清源...")
            response = requests.get(self.HD_SOURCE_URL, timeout=20, headers=self.DEFAULT_HEADERS)
            response.encoding = response.apparent_encoding
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
                            std_name = self.normalize_channel_name(name)
                            channels.append((std_name, url, '高清节目', -5))
            print(f"✅ 高清源加载完成，共获取 {len(channels)} 个频道流。")
        except Exception as e:
            print(f"❌ 加载高清源失败: {e}")
        return channels

    def load_migu_source(self):
        channels = []
        content = ""
        
        # 1. 优先尝试读取本地文件
        if os.path.exists(self.MIGU_LOCAL_FILE):
            print(f"📂 发现本地 Migu 文件: {self.MIGU_LOCAL_FILE}，直接读取...")
            try:
                with open(self.MIGU_LOCAL_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                print(f"✅ 本地 Migu 文件读取成功 (UTF-8)。")
            except UnicodeDecodeError:
                try:
                    with open(self.MIGU_LOCAL_FILE, 'r', encoding='gbk') as f:
                        content = f.read()
                    print(f"✅ 本地 Migu 文件读取成功 (GBK 转码)。")
                except Exception as e:
                    print(f"❌ 读取本地 Migu 文件失败: {e}")
        
        # 2. 如果本地没有，再尝试网络抓取
        if not content:
            print(f"🌍 本地无文件，正在尝试联网获取 Migu 源...")
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    print(f"🚀 第 {attempt + 1} 次尝试连接 {self.MIGU_SOURCE_URL}...")
                    response = requests.get(self.MIGU_SOURCE_URL, timeout=10, headers=self.DEFAULT_HEADERS, verify=False)
                    
                    detected_encoding = response.apparent_encoding
                    try:
                        content = response.content.decode(detected_encoding)
                    except:
                        content = response.content.decode('gbk')
                    
                    print(f"✅ Migu 源网络抓取成功！")
                    break
                except Exception as e:
                    print(f"⚠️ 第 {attempt + 1} 次尝试失败 (GitHub服务器可能无法访问该国内HTTP接口): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)

        # 3. 解析内容
        if content:
            temp_file = "temp_migu.m3u"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            with open(temp_file, 'r', encoding='utf-8') as f:
                lines = f.read().strip().splitlines()
            
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF") and "," in lines[i]:
                    try:
                        name = lines[i].split(",", 1)[1].strip()
                    except:
                        continue
                    if i + 1 < len(lines):
                        url = lines[i+1].strip()
                        if url.startswith("http") and self._is_valid_url(url):
                            std_name = self.normalize_channel_name(name)
                            cat, disp = self.categorize_channel(std_name)
                            if 'cctv' in std_name.lower() or '中央' in std_name:
                                cat = '央视'
                            elif '卫视' in std_name:
                                cat = '卫视'
                            channels.append((std_name, url, cat, -10))
            
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            print(f"✅ Migu 源解析完成，共获取 {len(channels)} 个频道流。")
        else:
            print(f"⚠️ 无法获取 Migu 源内容。")
        return channels

    # 优化了白名单的加载逻辑，缩短超时时间，防止阻塞主流程
    def load_remote_whitelist(self):
        channels = []
        try:
            print(f"🚀 正在连接远程白名单获取本地节目...")
            # 缩短超时时间，并忽略SSL验证，避免长时间阻塞
            response = requests.get(self.REMOTE_WHITELIST_URL, timeout=8, verify=False)
            response.encoding = response.apparent_encoding
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
            print(f"⚠️ 加载白名单失败或超时 (该IP在GitHub服务器上极易被拦截，已自动跳过): {e}")
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
        # ⚠️ 核心修复：将容易阻塞网络的 load_remote_whitelist 挪到了最后执行
        all_channels.extend(self.fetch_xichong_channel())
        all_channels.extend(self.fetch_signed_channels())
        all_channels.extend(self.load_hd_source())
        all_channels.extend(self.load_migu_source()) 
        all_channels.extend(self.load_remote_whitelist()) # 放在最后，即使失败也不影响前面的源
        
        print(f"✅ 跳过去重，共收集 {len(all_channels)} 个频道流（含重复）")
        
        # --- 排序与写入文件 ---
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            
            group_order = {
                '本地节目': 0, '央视': 1, '高清节目': 2, '卫视': 3, '四川': 4, '广东': 5,
                '电影频道': 6, '电影轮播': 7, '体育': 8, '少儿': 9, '教育': 10,
                '纪录片': 11, '音乐': 12, '生活科教': 13, '法治社会': 14,
                '港澳台': 15, '综合/其他': 16
            }
            
            def sort_key(x):
                group = x[2]
                order = group_order.get(group, 99)
                return (order, group, x[0])
                
            all_channels.sort(key=sort_key)
            
            for disp_name, url, cat, _ in all_channels:
                f.write(f'#EXTINF:-1 tvg-name="{disp_name}" group-title="{cat}",{disp_name}\n')
                f.write(f'{url}\n')
                
        print(f"🎉 完成！保存至: {os.path.abspath(self.OUTPUT_FILE)}")

    def run(self):
        try:
            self.merge_and_export()
        except Exception as e:
            print(f"❌ 严重错误: {e}")
            sys.exit(1)

# --- 程序入口 ---
if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.run()
