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
        
        print(f"🌍 运行环境：{time.strftime('%Y-%m-%d %A')} | 广东省 佛山市 (定制版)")

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
        # 在标准化之前先修复乱码
        name = self.fix_mojibake(name)
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
            
            # --- 核心修改：增加 JSON 响应的乱码修复 ---
            raw_text = response.content.decode('utf-8', errors='ignore')
            clean_text = self.fix_mojibake(raw_text)
            
            if response.status_code == 200:
                # 尝试解析修复后的文本
                import json
                data = json.loads(clean_text)
                prop_value = data.get("data", {})
                if isinstance(prop_value, list) and prop_value:
                    prop_value = prop_value[0]
                prop_value = prop_value.get("propValue", {})
                if isinstance(prop_value, list) and prop_value:
                    prop_value = prop_value[0]
                children_list = prop_value.get("children", [])
                items = children_list[0].get("dataList", []) if isinstance(children_list, list) and children_list else []
                print(f"✅ 私有源接口连接成功！共发现 {len(items)} 个频道流。")
                
                expire_time = int(time.time()) + 90000
                for i, item in enumerate(items):
                    original_title = item.get("title")
                    # --- 核心修改：修复 title 字段的乱码 ---
                    original_title = self.fix_mojibake(original_title)
                    
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
        headers = {
            'User-Agent': 'okhttp/3.12.12', 
            'Accept': 'application/json, text/plain, */*'
        }
        try:
            print(f"🚀 正在连接 lwydapi.xichongtv.cn 获取西充综合...")
            response = requests.get(api_url, headers=headers, verify=False, timeout=10)
            # --- 核心修改：增加此处的乱码修复 ---
            raw_text = response.content.decode('utf-8', errors='ignore')
            clean_text = self.fix_mojibake(raw_text)
            
            if response.status_code == 200:
                import json
                data = json.loads(clean_text)
                if 'data' in data and 'm3u8Url' in data['data']:
                    m3u8_url = data['data']['m3u8Url']
                    if m3u8_url:
                        print(f"✅ 成功获取西充综合直播流！")
                        channels.append(("西充综合", m3u8_url, '本地节目', -4))
        except Exception as e:
            print(f"❌ 西充频道处理异常: {e}")
        return channels

    def _rename_channel(self, index, original_title):
        rename_map = {
            0: "南充综合",
            1: "南充科教"
        }
        return rename_map.get(index, original_title)

    def _extract_channel_id(self, live_stream, name):
        path_parts = [p for p in live_stream.split("/") if p]
        if len(path_parts) >= 2:
            return path_parts[-2]
        return hashlib.md5(name.encode()).hexdigest()[:10]

    def categorize_channel(self, name):
        # 修复传入 name 的乱码
        name = self.fix_mojibake(name)
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
            
        if any(kw in name for kw in ['凤凰', 'TVB', '翡翠', '明珠', '东森', '澳亚', '星空']):
            return '港澳台', name
            
        if any(kw in name_lower for kw in ['体育', '赛事', 'nba', '足球', '篮球']):
            return '体育', name
            
        if any(kw in name_lower for kw in ['少儿', '卡通', '动画', '动漫', '哈哈炫动', '金鹰卡通', '卡酷']):
            return '少儿', name
            
        if any(kw in name_lower for kw in ['教育', '学习', '考试', '校园', '中学生']):
            return '教育', name
            
        if any(kw in name_lower for kw in ['纪录', '探索', '地理', '发现', '历史']):
            return '纪录片', name
            
        if any(kw in name_lower for kw in ['音乐', 'mtv', '声乐', '演唱会']):
            return '音乐', name
            
        if any(kw in name_lower for kw in ['生活', '科教', '科技', '农业', '纪实']):
            return '生活科教', name
            
        if any(kw in name_lower for kw in ['法治', '法制', '政法', '社会']):
            return '法治社会', name
            
        province_map = {
            '四川': ['四川', '成都', '峨眉'], 
            '广东': ['广东', '广州', '深圳', '珠海', '佛山', '东莞', '南方卫视'],
            '北京': ['北京'], 
            '上海': ['上海', '东方', '第一财经']
        }
        for prov, cities in province_map.items():
            if any(city in name for city in cities):
                return prov, name
                
        return "综合/其他", name

    # === 核心修复函数：解决 UTF-8 被误读为 Latin-1 产生的乱码 ===
    def fix_mojibake(self, text):
        """
        修复典型的乱码，例如：
        错误显示: "CCTV5: æ±åé¦è§"
        原理：将错误解码的字符串重新编码为错误编码的字节，再用正确编码解码。
        """
        if not isinstance(text, str):
            return text
            
        # 检查是否包含典型的乱码特征
        if re.search(r'[\xc0-\xff][\x80-\xbf]', text): # 简单检测双字节特征
            try:
                # 尝试修复：先用 latin-1 编码回字节，再用 utf-8 解码
                fixed = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                # 如果修复后的文本看起来更像中文（包含中文字符），则返回修复结果
                if len(re.findall(r'[\u4e00-\u9fa5]', fixed)) > len(re.findall(r'[\u4e00-\u9fa5]', text)):
                    print(f"🔧 乱码修复生效: '{text}' -> '{fixed}'")
                    return fixed
            except:
                pass
        return text

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
                    # --- 核心修改：使用 content 而不是 text，并应用 fix_mojibake ---
                    raw_text = response.content.decode('utf-8', errors='ignore')
                    clean_text = self.fix_mojibake(raw_text)
                    
                    # 检查是否包含有效频道信息
                    if len([line for line in clean_text.splitlines() if "#EXTINF" in line]) > 0:
                        content = clean_text
                        print(f"✅ 成功获取内容！(已应用乱码修复)")
                        break
                    else:
                        print("⚠️ 获取的内容格式异常，尝试下一个代理...")
                else:
                    print(f"⚠️ 代理返回状态码: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ 代理连接异常: {e}")
                continue
                
        return content

    # === 修改：Migu 源加载逻辑 (明确归类为普通源) ===
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
                    try:
                        # --- 核心修改：修复频道名乱码 ---
                        raw_name = lines[i].split(",", 1)[1].strip()
                        name = self.fix_mojibake(raw_name)
                    except:
                        continue
                        
                    if i + 1 < len(lines):
                        url = lines[i+1].strip()
                        if url.startswith("http") and self._is_valid_url(url):
                            std_name = self.normalize_channel_name(name)
                            cat, disp = self.categorize_channel(std_name)
                            # 🔴 明确归类为“普通源”
                            channels.append((std_name, url, '普通源', -1))
                            valid_count += 1
            print(f"✅ Migu 普通源解析完成，共获取 {valid_count} 个频道。")
        return channels

    # === 修改：高清源加载逻辑 ===
    def load_hd_source(self):
        channels = []
        try:
            print(f"🚀 正在连接 {self.HD_SOURCE_URL} 获取高清源...")
            response = requests.get(self.HD_SOURCE_URL, timeout=20, headers=self.DEFAULT_HEADERS)
            
            # --- 核心修改：同样应用乱码修复 ---
            raw_text = response.content.decode('utf-8', errors='ignore')
            content = self.fix_mojibake(raw_text)
            
            if content:
                lines = content.strip().splitlines()
                for i in range(len(lines)):
                    if lines[i].startswith("#EXTINF") and "," in lines[i]:
                        try:
                            raw_name = lines[i].split(",", 1)[1].strip()
                            name = self.fix_mojibake(raw_name)
                        except:
                            continue
                            
                        if i + 1 < len(lines):
                            url = lines[i+1].strip()
                            if url.startswith("http") and self._is_valid_url(url):
                                std_name = self.normalize_channel_name(name)
                                cat, disp = self.categorize_channel(std_name)
                                # 🔴 明确归类为“高清源”
                                channels.append((std_name, url, '高清源', -2))
                print(f"✅ 高清源加载完成，共获取 {len(channels)} 个频道流。")
        except Exception as e:
            print(f"❌ 加载高清源失败: {e}")
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
        all_channels.extend(self.fetch_xichong_channel())
        all_channels.extend(self.fetch_signed_channels())
        all_channels.extend(self.load_hd_source())
        all_channels.extend(self.load_migu_source())

        # 排序逻辑：高清源优先于普通源
        group_order = {
            '本地节目': 0,
            '央视': 1,
            '卫视': 2,
            '高清源': 3,
            '普通源': 4,
            '四川': 5,
            '广东': 6,
            '电影频道': 7,
            '电影轮播': 8,
            '体育': 9,
            '少儿': 10,
            '教育': 11,
            '纪录片': 12,
            '音乐': 13,
            '生活科教': 14,
            '法治社会': 15,
            '港澳台': 16,
            '综合/其他': 17
        }

        def sort_key(x):
            group = x[2] # 获取分类名称
            order = group_order.get(group, 99)
            return (order, group, x[0])

        all_channels.sort(key=sort_key)

        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml.gz"\n')
            for disp_name, url, cat, _ in all_channels:
                f.write(f'#EXTINF:-1 tvg-name="{disp_name}" group-title="{cat}",{disp_name}\n')
                f.write(f'{url}\n')
                
        print(f"🎉 完成！保存至: {os.path.abspath(self.OUTPUT_FILE)}")
        print(f"📊 统计: 共处理 {len(all_channels)} 个频道")

if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.merge_and_export()
