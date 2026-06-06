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

# 设置标准输出编码为 UTF-8，防止中文乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# 屏蔽版本依赖警告
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

class IPTVUpdater:
    def __init__(self):
        # --- 数据源配置 ---
        self.NANCHONG_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
        
        # --- 咪咕视频源配置 ---
        self.MIGU_INTERFACE_URL = "https://develop202.github.io/migu_video/interface.txt"
        
        # --- 签名与域名配置 (南充源)---
        self.SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
        self.BASE_DOMAIN = "https://ncpull.cnncw.cn"
        
        # --- 输出配置 ---
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")
        
        # --- 新增：西充综合专用配置 ---
        self.XICHONG_API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
        self.XICHONG_HEADERS = {
            'User-Agent': 'okhttp/3.12.12',
            'Accept': 'application/json, text/plain, */*'
        }

    def fetch_xichong_channel_new(self):
        """使用参考代码逻辑获取西充综合频道"""
        print(f"🚀 正在连接 {self.XICHONG_API_URL} 获取【西充综合】...")
        channels = []
        try:
            # verify=False 忽略 SSL 证书错误
            response = requests.get(self.XICHONG_API_URL, headers=self.XICHONG_HEADERS, verify=False, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # 直接解析 JSON
                if data.get("status") == 200 and 'data' in data:
                    m3u8_url = data['data'].get('m3u8Url')
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
        """生成MD5签名"""
        raw_string = f"{self.SECRET_KEY}{path}{timestamp}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def find_datalist(self, obj, depth=0):
        """递归深度搜索JSON，寻找dataList"""
        if depth > 10: return None
        if isinstance(obj, dict):
            if "dataList" in obj and isinstance(obj["dataList"], list):
                return obj["dataList"]
            for value in obj.values():
                result = self.find_datalist(value, depth + 1)
                if result: return result
        elif isinstance(obj, list):
            for item in obj:
                result = self.find_datalist(item, depth + 1)
                if result: return result
        return None

    def fetch_nanchong_channels(self):
        """获取南充频道并重命名"""
        print(f"🚀 正在获取【南充】频道列表...")
        channels = []
        try:
            response = requests.get(self.NANCHONG_JSON_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("isSuccess"):
                    items = self.find_datalist(data)
                    if items:
                        expire_time = int(time.time()) + 86400 # 24小时有效
                        for item in items:
                            if not isinstance(item, dict): continue
                            title = item.get("title", "").strip()
                            if not title: continue
                            
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
                            if not stream_id: continue
                            
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
        """从指定URL获取咪咕直播源并分类"""
        print(f"📡 正在获取【咪咕/外部】直播源...")
        channels = []
        try:
            response = requests.get(self.MIGU_INTERFACE_URL, timeout=15)
            # 修复了之前把 200 写成 2OO 的致命错误
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
                        category = "其他频道"
                        group_match = re.search(r'group-title="([^"]+)"', line)
                        if group_match:
                            category = group_match.group(1)
                        if "超清" in category or "4K" in channel_name:
                            category = "超清频道"
                        elif "央视频道" in category or "CCTV" in channel_name or "中央" in channel_name:
                            category = "央视频道"
                        elif "卫视频道" in category or "卫视" in channel_name:
                            category = "卫视频道"
                        if i + 1 < len(lines):
                            url_line = lines[i + 1].strip()
                            if url_line.startswith('http'):
                                channels.append((channel_name, url_line, category))
                        i += 2
                        continue
                    except Exception as e:
                        print(f"❌ 解析行出错: {line[:30]}... 错误: {e}")
                i += 1
        except Exception as e:
            print(f"❌ 获取/解析咪咕源异常: {e}")
        print(f"✅ 成功获取 {len(channels)} 个咪咕/外部频道")
        return channels

    def load_whitelist(self):
        """ 加载白名单。"""
        print(f"📝 正在加载本地白名单...")
        channels = []
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
                        parts = line.split(',', maxsplit=1)
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
                            parts = line.split(',', maxsplit=1)
                            name = parts[0].strip()
                            url = parts[1].strip()
                            i += 1
                        else:
                            i += 1
                            continue
                            
                    if name and url and urlparse(url).scheme in ['http', 'https']:
                        channels.append((name, url, '本地节目'))
            except Exception as e:
                print(f"❌ 读取本地白名单文件异常: {e}")
        else:
            print("⚠️ 未找到本地 whitelist.txt 文件，跳过。")
        print(f"✅ 白名单处理完成，共加载 {len(channels)} 个频道")
        return channels

    def run(self):
        """主运行逻辑"""
        print("=" * 50)
        print("📺 IPTV 本地节目源更新工具")
        print("=" * 50)
        
        # 创建输出目录
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        all_channels = []
        
        # --- 执行获取任务 ---
        # 1. 获取南充频道 (本地节目)
        all_channels.extend(self.fetch_nanchong_channels())
        
        # 2. 获取西充综合频道 (使用修复后的新逻辑)
        all_channels.extend(self.fetch_xichong_channel_new())
        
        # 3. 获取原白名单内容 (分类为本地节目)
        all_channels.extend(self.load_whitelist())
        
        # 4. 获取新的咪咕/外部源
        all_channels.extend(self.fetch_migu_channels())
        
        if not all_channels:
            print("❌ 未能获取到任何频道数据。")
            return
            
        # --- 去重 ---
        seen = set()
        unique_channels = []
        for name, url, cat in all_channels:
            key = url
            if key not in seen:
                seen.add(key)
                unique_channels.append((name, url, cat))
                
        # --- 写入文件 ---
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="epg.xml"\n')
            for name, url, cat in unique_channels:
                f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
                f.write(f'{url}\n')
                
        print("-" * 50)
        print(f"🎉 生成完成！文件已保存至: {os.path.abspath(self.OUTPUT_FILE)}")
        print(f"📊 总计频道数: {len(unique_channels)}")
        print("=" * 50)

if __name__ == "__main__":
    print(f"🌍 运行环境：{time.strftime('%Y-%m-%d %A')} | 广东佛山")
    updater = IPTVUpdater()
    updater.run()
    
