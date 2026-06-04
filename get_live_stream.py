import requests
import os
import sys
import io
import hashlib
import time
import re
from urllib.parse import urlparse

# 强制将终端标准输出的编码设置为 UTF-8，防止控制台打印中文乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class IPTVUpdater:
    def __init__(self):
        # === 核心配置 ===
        self.MIGU_SOURCE_URL = "http://www.52top.com.cn:678/downloads/migu.txt"
        self.MIGU_LOCAL_FILE = "migu.txt" # 兜底方案：本地文件名
        self.HD_SOURCE_URL = "http://114.226.216.63:5140/playlist.m3u"
        
        # 定义输出目录和文件
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")
        
        # 定义请求头
        self.DEFAULT_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        
        self.IPTV_JSON_URL = "http://kstatic.sctvcloud.com/static/N1300/list/1835203958696394753.json"
        self.IPTV_SECRET_KEY = "5df6d8b743257e0e38b869a07d8819d2"
        self.IPTV_BASE_DOMAIN = "https://ncpull.cnncw.cn"
        
        # 移除了打印地理位置信息的代码
        print(f"🌍 运行环境：{time.strftime('%Y-%m-%d %A')}")

    # === 核心修复：通过代理获取内容，增加防乱码回退机制 ===
    def fetch_m3u_via_proxy(self, url):
        proxies = [
            f"https://corsproxy.io/?{url}",
            f"https://api.codetabs.com/v1/proxy?quest={url}"
        ]
        headers = {'User-Agent': self.DEFAULT_HEADERS['User-Agent']}
        content = None
        for proxy_url in proxies:
            try:
                print(f"🚀 正在尝试通过代理获取: {proxy_url[:40]}...")
                response = requests.get(proxy_url, headers=headers, timeout=15)
                if response.status_code == 200:
                    # 1. 优先参考你提供的代码，使用 apparent_encoding 自动推断
                    response.encoding = response.apparent_encoding
                    text_content = response.text
                    
                    # 2. 防乱码回退机制：如果推断出的文本包含大量乱码特征，强制使用 GBK 解码
                    if '\ufffd' in text_content or len(re.findall(r'[\u4e00-\u9fa5]', text_content)) < 5:
                        print("⚠️ 自动推断编码存在乱码，正在回退至 GBK 解码...")
                        content = response.content.decode('gbk', errors='ignore')
                    else:
                        content = text_content
                    print(f"✅ 成功获取内容！最终使用编码: {response.encoding if '\ufffd' not in content else 'GBK(回退)'}")
                    break
                else:
                    print(f"⚠️ 代理返回状态码: {response.status_code}")
            except Exception as e:
                print(f"❌ 代理连接异常: {e}")
                continue
        return content

    # === 修改：Migu 源加载逻辑 ===
    def load_migu_source(self):
        channels = []
        content = ""
        
        # 1. 优先读取本地文件
        if os.path.exists(self.MIGU_LOCAL_FILE):
            print(f"📂 发现本地文件，尝试读取...")
            for enc in ['utf-8', 'gbk', 'gb2312']:
                try:
                    with open(self.MIGU_LOCAL_FILE, 'r', encoding=enc) as f:
                        content = f.read()
                    print(f"✅ 本地读取成功 (编码: {enc})")
                    break
                except:
                    continue
        
        # 2. 本地没有则通过代理获取
        if not content:
            print(f"🌐 本地无数据，正在通过代理获取网络源...")
            content = self.fetch_m3u_via_proxy(self.MIGU_SOURCE_URL)
            if content:
                try:
                    with open(self.MIGU_LOCAL_FILE, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"💾 已更新本地缓存文件")
                except Exception as e:
                    print(f"⚠️ 无法保存本地缓存: {e}")

        # 3. 解析内容
        if content:
            if content.startswith('\ufeff'):
                content = content[1:]
            lines = content.strip().splitlines()
            valid_count = 0
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF") and "," in lines[i]:
                    # ✅ 修改点：直接从 #EXTINF 行的逗号后获取名称，不再进行复杂的正则提取和别名映射
                    try:
                        name = lines[i].split(",", 1)[1].strip()
                    except:
                        continue
                        
                    if i + 1 < len(lines):
                        url = lines[i+1].strip()
                        if url.startswith("http"):
                            # 直接使用获取到的 name，不再调用 normalize_channel_name 或 categorize_channel
                            channels.append((name, url, "普通源"))
                            valid_count += 1
            print(f"✅ Migu 源解析完成，共获取 {valid_count} 个频道。")
        return channels

    # === 修改：高清源加载逻辑 ===
    def load_hd_source(self):
        channels = []
        try:
            print(f"🚀 正在连接 {self.HD_SOURCE_URL} 获取高清源...")
            response = requests.get(self.HD_SOURCE_URL, timeout=20, headers=self.DEFAULT_HEADERS)
            response.encoding = response.apparent_encoding
            content = response.text
            if content:
                lines = content.strip().splitlines()
                for i in range(len(lines)):
                    if lines[i].startswith("#EXTINF") and "," in lines[i]:
                        # ✅ 修改点：直接从 #EXTINF 行的逗号后获取名称
                        try:
                            name = lines[i].split(",", 1)[1].strip()
                        except:
                            continue
                            
                        if i + 1 < len(lines):
                            url = lines[i+1].strip()
                            if url.startswith("http"):
                                channels.append((name, url, "高清源"))
                print(f"✅ 高清源加载完成，共获取 {len(channels)} 个频道流。")
        except Exception as e:
            print(f"❌ 加载高清源失败: {e}")
        return channels

    # === 移除了 fetch_signed_channels 和 fetch_xichong_channel 方法，因为参考代码中只处理了 m3u 源 ===

    def merge_and_export(self):
        print("🚀 开始合并直播源...")
        all_channels = []
        
        # 只保留通用的源加载
        all_channels.extend(self.load_hd_source())
        all_channels.extend(self.load_migu_source())

        # 简单排序：高清源在前，普通源在后
        def sort_key(x):
            group_order = {"高清源": 0, "普通源": 1}
            return (group_order.get(x[2], 2), x[0])
            
        all_channels.sort(key=sort_key)

        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            for name, url, cat in all_channels:
                f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{cat}",{name}\n')
                f.write(f'{url}\n')
                
        print(f"🎉 完成！保存至: {os.path.abspath(self.OUTPUT_FILE)}")
        print(f"📊 统计: 共处理 {len(all_channels)} 个频道")

if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.merge_and_export()
