# -*- coding: utf-8 -*-
import requests
import os
import sys
import io
import hashlib
import time
import re
from urllib.parse import urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class IPTVUpdater:
    def __init__(self):
        self.MIGU_SOURCE_URL = "http://fn.gcl.de5.net:5908/gsh950428"
        self.MIGU_LOCAL_FILE = "migu.txt"
        self.HD_SOURCE_URL = "http://119.164.222.242:5140/playlist.m3u"
        self.LOCAL_WHITELIST = "whitelist.txt"
        self.REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
        self.OUTPUT_DIR = "live"
        self.OUTPUT_FILE = os.path.join(self.OUTPUT_DIR, "current.m3u8")
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

    def fix_mojibake(self, text):
        if not isinstance(text, str):
            return text
        if re.search(r'[\xc0-\xff][\x80-\xbf]', text):
            try:
                fixed = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                if len(re.findall(r'[\u4e00-\u9fa5]', fixed)) > len(re.findall(r'[\u4e00-\u9fa5]', text)):
                    print(f"🔧 乱码修复: '{text}' -> '{fixed}'")
                    return fixed
            except:
                pass
        return text

    def normalize_channel_name(self, name):
        name = self.fix_mojibake(name)
        name_lower = name.lower().strip()
        for standard_name, aliases in self.CHANNEL_ALIASES.items():
            if name_lower == standard_name.lower() or name_lower in [alias.lower() for alias in aliases]:
                return standard_name
        return name.strip()

    def generate_signature(self, path, timestamp):
        raw_string = f"{self.IPTV_SECRET_KEY}{path}{timestamp}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def categorize_channel(self, name):
        name = self.fix_mojibake(name)
        name_lower = name.lower()
        if any(kw in name for kw in ['西充', '南充', '顺庆', '高坪', '嘉陵', '阆中']):
            return '本地节目', name
        if any(kw in name_lower for kw in ['cctv', '中央']):
            if "CCTV" in name.upper():
                match = re.search(r'CCTV\D*(\d+)', name.upper())
                if match:
                    return '央视', f"CCTV-{int(match.group(1))}"
            return '央视', name
        if any(kw in name_lower for kw in ['卫视', '卫星']):
            return '卫视', name
        movie_keywords = ['电影', '影院', 'CHC', '动作电影', '喜剧电影', '爱情电影', '科幻电影', '恐怖电影']
        if any(kw.lower() in name_lower for kw in movie_keywords):
            if '轮播' in name_lower or '回放' in name_lower:
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

    def _rename_channel(self, index, original_title):
        rename_map = {0: "南充综合", 1: "南充科教"}
        return rename_map.get(index, original_title)

    def _extract_channel_id(self, live_stream, name):
        path_parts = [p for p in live_stream.split("/") if p]
        if len(path_parts) >= 2:
            return path_parts[-2]
        return hashlib.md5(name.encode()).hexdigest()[:10]

    def _is_valid_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def fetch_signed_channels(self):
        channels = []
        try:
            print(f"🚀 正在连接 kstatic.sctvcloud.com 获取私有源...")
            response = requests.get(self.IPTV_JSON_URL, headers=self.DEFAULT_HEADERS, timeout=10)
            raw_text = response.content.decode('utf-8', errors='ignore')
            clean_text = self.fix_mojibake(raw_text)
            if response.status_code == 200:
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
                    original_title = self.fix_mojibake(item.get("title"))
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

    def fetch_m3u_via_proxy(self, url):
        proxies = [
            f"https://corsproxy.io/?{url}",
            f"https://api.codetabs.com/v1/proxy?quest={url}"
        ]
        headers = {'User-Agent': self.DEFAULT_HEADERS['User-Agent']}
        content = None
        for proxy_url in proxies:
            try:
                print(f"🚀 正在尝试通过代理获取: {proxy_url[:50]}...")
                response = requests.get(proxy_url, headers=headers, timeout=15)
                if response.status_code == 200:
                    raw_text = response.content.decode('utf-8', errors='ignore')
                    clean_text = self.fix_mojibake(raw_text)
                    if len([line for line in clean_text.splitlines() if "#EXTINF" in line]) > 0:
                        content = clean_text
                        print(f"✅ 成功获取内容！")
                        break
                    else:
                        print("⚠️ 内容格式异常，尝试下一个代理...")
            except Exception as e:
                print(f"❌ 代理连接异常: {e}")
                continue
        return content

    def load_whitelist(self):
        channels = []
        content = None
        if os.path.exists(self.LOCAL_WHITELIST):
            print(f"📂 发现本地白名单文件: {self.LOCAL_WHITELIST}，正在读取...")
            for enc in ['utf-8', 'gbk', 'gb2312']:
                try:
                    with open(self.LOCAL_WHITELIST, 'r', encoding=enc) as f:
                        content = f.read()
                    print(f"✅ 本地白名单读取成功 (编码: {enc})")
                    break
                except Exception as e:
                    continue
        if content is None:
            print(f"🌐 本地文件不可用，正在尝试从远程获取白名单...")
            try:
                response = requests.get(self.REMOTE_WHITELIST_URL, headers=self.DEFAULT_HEADERS, timeout=10)
                if response.status_code == 200:
                    content = response.text
                    print(f"✅ 远程白名单获取成功！")
                else:
                    print(f"❌ 远程白名单获取失败，状态码: {response.status_code}")
            except Exception as e:
                print(f"❌ 远程白名单连接异常: {e}")
        if content:
            if content.startswith('\ufeff'):
                content = content[1:]
            lines = content.strip().splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                name = None
                url = None
                if line.startswith("#EXTINF") and "," in line:
                    try:
                        name = line.split(",", 1)[1].strip()
                        if i + 1 < len(lines):
                            url = lines[i + 1].strip()
                    except:
                        pass
                elif "," in line and not line.startswith("#"):
                    parts = line.split(",", 1)
                    name = parts[0].strip()
                    url = parts[1].strip() if len(parts) > 1 else ""
                if name and url and url.startswith("http") and self._is_valid_url(url):
                    std_name = self.normalize_channel_name(name)
                    cat, _ = self.categorize_channel(std_name)
                    channels.append((std_name, url, cat, -5))
                i += 1
            print(f"✅ 白名单处理完成，共加载 {len(channels)} 个频道。")
        else:
            print(f"❌ 无法获取白名单内容。")
        return channels

    def load_migu_source(self):
        channels = []
        content = ""
        if os.path.exists(self.MIGU_LOCAL_FILE):
            print(f"📂 发现本地咪咕文件，尝试读取...")
            for enc in ['utf-8', 'gbk', 'gb2312']:
                try:
                    with open(self.MIGU_LOCAL_FILE, 'r', encoding=enc) as f:
                        content = f.read()
                    print(f"✅ 本地读取成功 (编码: {enc})")
                    break
                except:
                    continue
        if not content:
            print(f"🌐 本地无数据，正在联网获取...")
            content = self.fetch_m3u_via_proxy(self.MIGU_SOURCE_URL)
        if content:
            lines = content.strip().splitlines()
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF") and "," in lines[i]:
                    try:
                        name = lines[i].split(",", 1)[1].strip()
                        if i + 1 < len(lines):
                            url = lines[i + 1].strip()
                            if url.startswith("http") and self._is_valid_url(url):
                                std_name = self.normalize_channel_name(name)
                                cat, _ = self.categorize_channel(std_name)
                                channels.append((std_name, url, cat, -10))
                    except:
                        pass
            print(f"✅ 咪咕源解析完成，共获取 {len(channels)} 个频道流。")
        else:
            print(f"❌ 无法获取咪咕源内容。")
        return channels

    def load_hd_source(self):
        channels = []
        content = self.fetch_m3u_via_proxy(self.HD_SOURCE_URL)
        if content:
            lines = content.strip().splitlines()
            for i in range(len(lines)):
                if lines[i].startswith("#EXTINF") and "," in lines[i]:
                    try:
                        name = lines[i].split(",", 1)[1].strip()
                        if i + 1 < len(lines):
                            url = lines[i + 1].strip()
                            if url.startswith("http") and self._is_valid_url(url):
                                std_name = self.normalize_channel_name(name)
                                cat, _ = self.categorize_channel(std_name)
                                channels.append((std_name, url, cat, -5))
                    except:
                        pass
            print(f"✅ 高清源加载完成，共获取 {len(channels)} 个频道流。")
        else:
            print(f"❌ 加载高清源失败。")
        return channels

    def deduplicate_channels(self, channels):
        seen = set()
        unique_channels = []
        for name, url, cat, priority in channels:
            key = (name, url)
            if key not in seen:
                seen.add(key)
                unique_channels.append((name, url, cat, priority))
        return unique_channels

    def sort_channels(self, channels):
        cat_priority = {
            '本地节目': 0, '央视': 1, '卫视': 2, '电影频道': 3,
            '电影轮播': 4, '体育': 5, '少儿': 6, '港澳台': 7,
            '纪录片': 8, '音乐': 9, '教育': 10, '生活科教': 11,
            '法治社会': 12, '四川': 13, '广东': 14, '北京': 15,
            '上海': 16, '高清': 17, '综合/其他': 99
        }
        def get_sort_key(item):
            name, url, cat, priority = item
            base_prio = cat_priority.get(cat, 99)
            return (base_prio, priority, name)
        return sorted(channels, key=get_sort_key)

    def export_m3u8(self, channels):
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            for name, url, cat, priority in channels:
                f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n')
                f.write(f'{url}\n')
        print(f"✅ 输出文件已生成: {self.OUTPUT_FILE}")
        print(f"📊 总计 {len(channels)} 个频道")
        cats = {}
        for _, _, cat, _ in channels:
            cats[cat] = cats.get(cat, 0) + 1
        print("📂 分类统计:")
        for cat, count in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            print(f"   {cat}: {count} 个")

    def run(self):
        print("=" * 50)
        print("📺 IPTV 直播源合并工具 (完整版)")
        print("=" * 50)
        all_channels = []
        all_channels.extend(self.fetch_xichong_channel())
        all_channels.extend(self.fetch_signed_channels())
        all_channels.extend(self.load_hd_source())
        all_channels.extend(self.load_migu_source())
        all_channels.extend(self.load_whitelist())
        print(f"✅ 共收集 {len(all_channels)} 个频道流（含重复）")
        all_channels = self.deduplicate_channels(all_channels)
        print(f"✅ 去重后剩余 {len(all_channels)} 个频道流")
        all_channels = self.sort_channels(all_channels)
        self.export_m3u8(all_channels)
        print("=" * 50)
        print("🎉 全部完成！")
        print("=" * 50)

if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.run()
