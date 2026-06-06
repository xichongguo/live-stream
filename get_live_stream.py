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
        
        # --- 西充源配置 (已恢复) ---
        self.XICHONG_API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
        self.XICHONG_FALLBACK_URL = "http://60.255.240.247:8090/live/xczh_2000.m3u8" # 备用组播
        
        # --- 咪咕视频源配置 (新增) ---
        self.MIGU_INTERFACE_URL = "https://develop202.github.io/migu_video/interface.txt"
        
        # --- 签名与域名配置 (南充源)---
        self.SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
        self.BASE_DOMAIN = "https://ncpull.cnncw.cn"
        
        # --- 输出配置 ---
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")
        
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

    def fix_mojibake(self, text):
        """简单的乱码修复函数"""
        if not isinstance(text, str): return text
        if re.search(r'[\xc0-\xff][\x80-\xbf]', text):
            try:
                fixed = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                if len(re.findall(r'[\u4e00-\u9fa5]', fixed)) > len(re.findall(r'[\u4e00-\u9fa5]', text)):
                    return fixed
            except:
                pass
        return text

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
                            if "综合频道" in title: title = "南充综合"
                            elif "科教生活" in title: title = "南充科教生活"
                            
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

    def fetch_xichong_channels(self):
        """
        获取西充综合频道
        策略：优先尝试动态API获取，失败则回退到备用组播源
        """
        print(f"📡 正在获取【西充综合】频道 (优先尝试API)...")
        channels = []
        
        # --- 第一优先级：尝试从 API 动态获取 ---
        try:
            headers = { 
                'User-Agent': 'okhttp/3.12.12', 
                'Accept': 'application/json, text/plain, */*'
            }
            response = requests.get(self.XICHONG_API_URL, headers=headers, verify=False, timeout=10)
            
            if response.status_code == 0: # 有些代理或网络环境可能返回0
                raise Exception("网络连接异常")
                
            if response.status_code == 200:
                raw_text = response.content.decode('utf-8', errors='ignore')
                # 尝试修复可能的乱码
                clean_text = self.fix_mojibake(raw_text)
                data = json.loads(clean_text)
                
                # 核心提取逻辑
                if 'data' in data and 'm3u8Url' in data['data']:
                    m3u8_url = data['data']['m3u8Url']
                    if m3u8_url and m3u8_url.startswith('http'):
                        channels.append(("西充综合", m3u8_url, '本地节目'))
                        print(f"✅ 【成功-动态API】获取到西充综合流。")
                        return channels # 成功则直接返回
            
            print(f"⚠️ API 请求未成功(状态码: {response.status_code})，即将使用备用源。")
            
        except Exception as e:
            print(f"❌ API 获取失败: {e}，将使用备用源。")

        # --- 第二优先级：API失败，使用备用组播源 ---
        try:
            # 简单验证备用源是否可达
            test_response = requests.head(self.XICHONG_FALLBACK_URL, timeout=5)
            if test_response.status_code < 400:
                channels.append(("西充综合", self.XICHONG_FALLBACK_URL, '本地节目'))
                print(f"✅ 【回退-备用源】API失效，已启用备用组播源。")
            else:
                print(f"❌ 备用源似乎也失效了 (状态码: {test_response.status_code})")
                
        except Exception as e:
            print(f"❌ 备用源连接失败: {e}")

        return channels

    def fetch_migu_channels(self):
        """从指定URL获取咪咕直播源并分类"""
        print(f"🌐 正在获取【咪咕/外部】直播源...")
        channels = []
        try:
            # 获取文件内容
            response = requests.get(self.MIGU_INTERFACE_URL, timeout=15)
            if response.status_code != 200:
                print(f"❌ 获取远程列表失败，状态码: {response.status_code}")
                return channels
                
            content = response.text
            lines = content.splitlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # 识别频道信息行 (#EXTINF)
                if line.startswith("#EXTINF") and 'group-title' in line:
                    try:
                        # 提取 tvg-name 或 逗号后的名称
                        name_match = re.search(r'tvg-name="([^"]+)"', line)
                        if not name_match:
                            # 如果没有tvg-name，取逗号后面的名字
                            name_match = re.search(r',([^,]+)$', line)
                        if not name_match:
                            i += 1
                            continue
                            
                        channel_name = name_match.group(1).strip()
                        
                        # 确定分类 (优先使用原文件的 group-title，否则根据名字判断)
                        group_match = re.search(r'group-title="([^"]+)"', line)
                        if group_match:
                            raw_group = group_match.group(1)
                            # 规范化分类名称
                            if "超清" in raw_group or "4K" in raw_group:
                                category = "超清频道"
                            elif "央视频道" in raw_group or "CCTV" in raw_group:
                                category = "央视频道"
                            elif "卫视频道" in raw_group or "卫视" in raw_group:
                                category = "卫视频道"
                            else:
                                category = "其他频道"
                        else:
                            # 如果原文件没写group-title，根据名字判断
                            if "CCTV" in channel_name or "中央" in channel_name:
                                category = "央视频道"
                            elif "卫视" in channel_name:
                                category = "卫视频道"
                            elif "超清" in channel_name or "4K" in channel_name:
                                category = "超清频道"
                            else:
                                category = "其他频道"
                        
                        # 获取下一行的URL
                        if i + 1 < len(lines):
                            url_line = lines[i + 1].strip()
                            if url_line.startswith('http'):
                                channels.append((channel_name, url_line, category))
                        
                        i += 2 # 跳过URL行
                        continue
                    except Exception as e:
                        print(f"解析行出错: {line[:30]}... 错误: {e}")
                
                i += 1
                
        except Exception as e:
            print(f"❌ 获取/解析咪咕源异常: {e}")
        
        print(f"✅ 成功获取 {len(channels)} 个咪咕/外部频道")
        return channels

    def load_whitelist(self):
        """
        加载白名单。
        注意：根据你的需求，原白名单内容现在被归类为“本地节目”。
        """
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
                        # 简单解析白名单中的名称
                        parts = line.split(',', maxsplit=1)
                        if len(parts) == 2:
                            name = parts[1].strip()
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line.startswith('http'):
                                    url = next_line
                                    i += 2
                                else:
                                    i += 1
                            else:
                                i += 1
                    else:
                        # 纯文本格式: 名称,URL
                        if ',' in line:
                            parts = line.split(',', maxsplit=1)
                            name = parts[0].strip()
                            url = parts[1].strip()
                            i += 1
                        else:
                            i += 1
                            continue
                    
                    if name and url and urlparse(url).scheme in ['http', 'https']:
                        channels.append((name, url, '本地节目')) # 强制分类为本地节目
                        continue
                    
                    i += 1
                    
            except Exception as e:
                print(f"❌ 读取本地白名单文件异常: {e}")
        else:
            print("ℹ️ 未找到本地 whitelist.txt 文件，跳过。")
            
        print(f"✅ 白名单处理完成，共加载 {len(channels)} 个频道")
        return channels

    def run(self):
        """主运行逻辑"""
        print("=" * 50)
        print("📺 IPTV 直播源更新工具")
        print("=" * 50)
        
        # 创建输出目录
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        all_channels = []
        
        # --- 执行获取任务 ---
        
        # 1. 获取南充频道 (本地节目)
        all_channels.extend(self.fetch_nanchong_channels())
        
        # 2. 获取西充综合 (本地节目)
        all_channels.extend(self.fetch_xichong_channels())
        
        # 3. 获取原白名单内容 (分类为本地节目)
        all_channels.extend(self.load_whitelist())
        
        # 4. 获取新的咪咕/外部源 (分类为央视频道、卫视频道等)
        all_channels.extend(self.fetch_migu_channels())

        if not all_channels:
            print("❌ 未能获取到任何频道数据。")
            return

        # --- 去重 ---
        seen = set()
        unique_channels = []
        for name, url, cat in all_channels:
            # 根据 URL 去重
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
    print(f"🌍 运行环境：{time.strftime('%Y-%m-%d %A')}")
    updater = IPTVUpdater()
    updater.run()
    print("\n💡 提示：脚本运行完毕，按回车键退出...")
    input()
