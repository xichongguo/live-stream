# File: get_live_stream.py
# Description: 完全按你指定的分类与排序规则生成直播源，并标准化 CCTV 频道名
# Author: Assistant
# Date: 2025-11-06

import requests
import os
from urllib.parse import unquote, urlparse, parse_qs, urlunparse
from datetime import datetime
from collections import Counter, defaultdict
import time
import re

# ================== Configuration ==================
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    'deviceType': '1',
    'centerId': '9',
    'deviceToken': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue': '0',
    'areaId': '907',
    'appCenterId': '907',
    'isTest': '0',
    'longitudeValue': '0',
    'deviceVersionType': 'android',
    'versionCodeGlobal': '5009037'
}
HEADERS = {
    'User-Agent': 'okhttp/3.12.12',
}

# --- 源地址更新 ---
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
GUOVIN_IPTV_URL = "https://cdn.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.txt"

WHITELIST_TIMEOUT = 15
CHECK_TIMEOUT = 5
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

OUTPUT_DIR = "live"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current.m3u8")


# ---------------- 省份映射表 ----------------
PROVINCE_KEYWORDS = {
    '四川': ['四川', '成都', '绵阳', '德阳', '南充', '宜宾', '泸州', '乐山', '达州', '内江', '自贡', '攀枝花', '广安', '遂宁', '资阳', '眉山', '雅安', '巴中', '阿坝', '甘孜', '凉山'],
    '广东': ['广东', '广州', '深圳', '佛山', '东莞', '中山', '珠海', '惠州', '江门', '肇庆', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江', '云浮', '清远', '韶关', '河源'],
    '湖南': ['湖南', '长沙', '株洲', '湘潭', '衡阳', '邵阳', '岳阳', '常德', '张家界', '益阳', '郴州', '永州', '怀化', '娄底', '湘西'],
    '湖北': ['湖北', '武汉', '黄石', '十堰', '宜昌', '襄阳', '鄂州', '荆门', '孝感', '荆州', '黄冈', '咸宁', '随州', '恩施'],
    '江苏': ['江苏', '南京', '无锡', '徐州', '常州', '苏州', '南通', '连云港', '淮安', '盐城', '扬州', '镇江', '泰州', '宿迁'],
    '浙江': ['浙江', '杭州', '宁波', '温州', '嘉兴', '湖州', '绍兴', '金华', '衢州', '舟山', '台州', '丽水'],
    '山东': ['山东', '济南', '青岛', '淄博', '枣庄', '东营', '烟台', '潍坊', '济宁', '泰安', '威海', '日照', '临沂', '德州', '聊城', '滨州', '菏泽'],
    '河南': ['河南', '郑州', '开封', '洛阳', '平顶山', '安阳', '鹤壁', '新乡', '焦作', '濮阳', '许昌', '漯河', '三门峡', '南阳', '商丘', '信阳', '周口', '驻马店'],
    '河北': ['河北', '石家庄', '唐山', '秦皇岛', '邯郸', '邢台', '保定', '张家口', '承德', '沧州', '廊坊', '衡水'],
    '福建': ['福建', '福州', '厦门', '莆田', '三明', '泉州', '漳州', '南平', '龙岩', '宁德'],
    '广西': ['广西', '南宁', '柳州', '桂林', '梧州', '北海', '防城港', '钦州', '贵港', '玉林', '百色', '贺州', '河池', '来宾', '崇左'],
    '云南': ['云南', '昆明', '曲靖', '玉溪', '保山', '昭通', '丽江', '普洱', '临沧', '楚雄', '红河', '文山', '西双版纳', '大理', '德宏', '怒江', '迪庆'],
    '江西': ['江西', '南昌', '景德镇', '萍乡', '九江', '新余', '鹰潭', '赣州', '吉安', '宜春', '抚州', '上饶'],
    '辽宁': ['辽宁', '沈阳', '大连', '鞍山', '抚顺', '本溪', '丹东', '锦州', '营口', '阜新', '辽阳', '盘锦', '铁岭', '朝阳', '葫芦岛'],
    '山西': ['山西', '太原', '大同', '阳泉', '长治', '晋城', '朔州', '晋中', '运城', '忻州', '临汾', '吕梁'],
    '陕西': ['陕西', '西安', '铜川', '宝鸡', '咸阳', '渭南', '延安', '汉中', '榆林', '安康', '商洛'],
    '安徽': ['安徽', '合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城'],
    '黑龙江': ['黑龙江', '哈尔滨', '齐齐哈尔', '鸡西', '鹤岗', '双鸭山', '大庆', '伊春', '佳木斯', '七台河', '牡丹江', '黑河', '绥化'],
    '内蒙古': ['内蒙古', '呼和浩特', '包头', '乌海', '赤峰', '通辽', '鄂尔多斯', '呼伦贝尔', '巴彦淖尔', '乌兰察布', '兴安', '锡林郭勒', '阿拉善'],
    '吉林': ['吉林', '长春', '吉林市', '四平', '辽源', '通化', '白山', '松原', '白城', '延边'],
    '贵州': ['贵州', '贵阳', '六盘水', '遵义', '安顺', '毕节', '铜仁', '黔西南', '黔东南', '黔南'],
    '甘肃': ['甘肃', '兰州', '嘉峪关', '金昌', '白银', '天水', '武威', '张掖', '平凉', '酒泉', '庆阳', '定西', '陇南', '临夏', '甘南'],
    '海南': ['海南', '海口', '三亚', '三沙', '儋州', '五指山', '琼海', '文昌', '万宁', '东方', '定安', '屯昌', '澄迈', '临高', '白沙', '昌江', '乐东', '陵水', '保亭', '琼中'],
    '青海': ['青海', '西宁', '海东', '海北', '黄南', '海南', '果洛', '玉树', '海西'],
    '宁夏': ['宁夏', '银川', '石嘴山', '吴忠', '固原', '中卫'],
    '新疆': ['新疆', '乌鲁木齐', '克拉玛依', '吐鲁番', '哈密', '昌吉', '博尔塔拉', '巴音郭楞', '阿克苏', '克孜勒苏', '喀什', '和田', '伊犁', '塔城', '阿勒泰'],
    '西藏': ['西藏', '拉萨', '日喀则', '昌都', '林芝', '山南', '那曲', '阿里']
}

# 反向映射：城市 → 省份
CITY_TO_PROVINCE = {city: prov for prov, cities in PROVINCE_KEYWORDS.items() for city in cities}


# ---------------- 分类规则 ----------------
CATEGORY_MAP = {
    '央视': ['cctv', '中央'],
    '卫视': ['卫视', '湖南', '浙江', '江苏', '东方', '北京', '广东', '深圳', '四川', '湖北', '辽宁',
             '东南', '天津', '重庆', '黑龙江', '山东', '安徽', '云南', '陕西', '甘肃', '新疆',
             '内蒙古', '吉林', '河北', '山西', '广西', '江西', '福建', '贵州', '海南'],
    '电影频道': ['电影', '影院', '影视', '精选', '经典', '大片', '热播', '剧场', '虎牙', '斗鱼', 'LIVE', 'live', '4K', '8K'],
    '港澳台': ['香港', '澳门', '台湾', 'TVB', '翡翠台', '明珠台', 'J2', '无线', '亚视', 'ATV', '凤凰', '中天', '东森', '三立', '民视', '公视', '台视', '中视'],
    '经典剧场': ['西游记', '鹿鼎记', '寻秦记', '大唐双龙传', '天龙八部', '射雕英雄传', '神雕侠侣', '倚天屠龙记', '笑傲江湖', '雪山飞狐', '甄嬛传', '琅琊榜', '庆余年', '狂飙', '人民的名义']
}

EXCLUDE_IF_HAS = ['综合', '新闻', '生活', '少儿', '公共', '交通', '文艺', '音乐', '戏曲', '体育', '财经', '教育', '民生', '都市', '轮播', '回看', '重温']


# ---------------- 国外过滤 ----------------
FOREIGN_KEYWORDS = {
    'cnn', 'bbc', 'fox', 'espn', 'disney', 'hbo', 'nat geo', 'national geographic',
    'animal planet', 'mtv', 'paramount', 'pluto tv', 'sky sports', 'eurosport',
    'al jazeera', 'france 24', 'rt', 'nhk', 'kbs', 'abema', 'tokyo',
    'discovery', 'history', 'lifetime', 'syfy', 'tnt', 'usa network',
    'nickelodeon', 'cartoon network', 'boomerang', 'babyfirst', 'first channel',
    'russia', 'germany', 'italy', 'spain', 'france', 'uk', 'united kingdom',
    'canada', 'australia', 'new zealand', 'india', 'pakistan', 'japan', 'south korea'
}

ALLOWED_FOREIGN = {
    '凤凰', '凤凰卫视', '凤凰中文', '凤凰资讯', 'ATV', '亚洲电视', '星空', '华娱',
    'CCTV大富', 'CCTV-4', 'CCTV4', '中国中央电视台', '国际台', 'CGTN', 'CCTV西班牙语', 'CCTV法语',
    '香港', '澳门', '台湾', 'TVB', '翡翠台', '明珠台', 'J2', '无线', '亚视', 'ATV',
    '中天', '东森', '三立', '民视', '公视', '台视', '中视'
}


# ================== 新增：CCTV 标准化 ==================
def normalize_cctv_name(name):
    """
    将各种形式的 CCTV 名称标准化为 'CCTV-N'（N 无前导零）
    支持英文变体和中文别名
    """
    name = name.strip()
    if not name:
        return name

    # 中文别名映射
    CHINESE_ALIAS = {
        "中央一套": "CCTV-1",
        "综合频道": "CCTV-1",
        "中央二套": "CCTV-2",
        "财经频道": "CCTV-2",
        "中央三套": "CCTV-3",
        "综艺频道": "CCTV-3",
        "中央四套": "CCTV-4",
        "中文国际频道": "CCTV-4",
        "中央五套": "CCTV-5",
        "体育频道": "CCTV-5",
        "中央六套": "CCTV-6",
        "电影频道": "CCTV-6",
        "中央七套": "CCTV-7",
        "国防军事频道": "CCTV-7",
        "中央八套": "CCTV-8",
        "电视剧频道": "CCTV-8",
        "中央九套": "CCTV-9",
        "纪录频道": "CCTV-9",
        "中央十套": "CCTV-10",
        "科教频道": "CCTV-10",
        "中央十一套": "CCTV-11",
        "戏曲频道": "CCTV-11",
        "中央十二套": "CCTV-12",
        "社会与法频道": "CCTV-12",
        "中央十三套": "CCTV-13",
        "新闻频道": "CCTV-13",
        "中央十四套": "CCTV-14",
        "少儿频道": "CCTV-14",
        "中央十五套": "CCTV-15",
        "音乐频道": "CCTV-15",
        "中央十七套": "CCTV-17",
        "农业农村频道": "CCTV-17",
    }

    # 1. 精确匹配中文别名
    if name in CHINESE_ALIAS:
        return CHINESE_ALIAS[name]

    # 2. 模糊匹配关键词
    for keyword, std in CHINESE_ALIAS.items():
        if keyword in name:
            return std

    # 3. 匹配英文格式
    name_upper = name.upper()
    match = re.search(r'CCTV\D*(\d+)', name_upper)
    if match:
        number = str(int(match.group(1)))
        return f"CCTV-{number}"

    return name  # 无法识别则原样返回


# ================== Utility Functions ==================
def is_foreign_channel(name):
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    for keyword in FOREIGN_KEYWORDS:
        if keyword in name_lower:
            return True
    return False


def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False


def normalize_url(url):
    try:
        parsed = urlparse(url.strip().lower())
        if not parsed.scheme or not parsed.netloc:
            return ""
        safe_params = {}
        unsafe_keys = {'token', 't', 'ts', 'sign', 'auth_key', 'verify', 'session', 'key', 'pwd', 'stb', 'icpid', 'RTS', 'from', 'hms_devid', 'online', 'vqe', 'txSecret', 'txTime', 'stat', 'wsSecret', 'wsTime', 'j', 'authid', 'playlive'}
        for k, v_list in parse_qs(parsed.query).items():
            if k.lower() not in unsafe_keys and v_list and v_list[0]:
                safe_params[k] = v_list[0]
        new_query = '&'.join(f"{k}={v}" for k, v in safe_params.items())
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url.lower().split('?')[0]


def merge_and_deduplicate(channels):
    seen = set()
    unique = []
    for item in channels:
        name, url, group = item
        norm_url = normalize_url(url)
        if norm_url and norm_url not in seen:
            seen.add(norm_url)
            unique.append(item)
    print(f"✅ After dedup: {len(unique)} unique streams")
    return unique


def categorize_channel(name):
    name_lower = name.lower()

    # 央视
    if any(kw in name_lower for kw in ['cctv', '中央']):
        # 标准化名称
        std_name = normalize_cctv_name(name)
        return '央视', std_name

    # 卫视
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower:
            return '卫视', name

    # 电影频道
    for kw in CATEGORY_MAP['电影频道']:
        if kw.lower() in name_lower:
            if any(ex.lower() in name_lower for ex in EXCLUDE_IF_HAS):
                continue
            return '电影频道', name

    # 港澳台
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name:
            return '港澳台', name

    # 经典剧场
    for kw in CATEGORY_MAP['经典剧场']:
        if kw in name:
            return '经典剧场', name

    # 省份
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name:
                return prov, name

    return "其他", name


def check_url_valid(url, timeout=CHECK_TIMEOUT):
    """检测URL是否可访问（用于央视源）"""
    try:
        response = requests.head(url, timeout=timeout, headers=DEFAULT_HEADERS, allow_redirects=True)
        return response.status_code < 400
    except:
        try:
            response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS, stream=True)
            return response.status_code < 400
        except:
            return False


def load_whitelist():
    """加载白名单，作为“本地节目”，保留原始顺序"""
    print(f"👉 Loading whitelist: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        channels = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2:
                continue
            name, url = parts[0], parts[1]
            if not name or not url or not is_valid_url(url):
                continue
            if is_foreign_channel(name):
                print(f"🌍 Skipped foreign (whitelist): {name}")
                continue
            channels.append((name, url, "本地节目"))
        print(f"✅ Loaded {len(channels)} from whitelist (as '本地节目')")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []


def load_tv_m3u():
    print(f"👉 Loading tv.m3u: {TV_M3U_URL}")
    try:
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        channels = []
        current_name = None

        for line in lines:
            line = line.strip()
            if line.startswith("#EXTINF"):
                try:
                    name_part = line.split(",", 1)
                    if len(name_part) > 1:
                        current_name = name_part[1].strip()
                except:
                    current_name = "Unknown"
            elif line.startswith("http"):
                if current_name and is_valid_url(line):
                    if is_foreign_channel(current_name):
                        print(f"🌍 Skipped foreign (tv.m3u): {current_name}")
                    else:
                        category, display_name = categorize_channel(current_name)
                        channels.append((display_name, line, category))
                current_name = None
        print(f"✅ Loaded {len(channels)} from tv.m3u")
        return channels
    except Exception as e:
        print(f"❌ Failed to load tv.m3u: {e}")
        return []


def load_guovin_iptv():
    """加载 Guovin 的 result.txt"""
    print(f"👉 Loading Guovin IPTV: {GUOVIN_IPTV_URL}")
    try:
        response = requests.get(GUOVIN_IPTV_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        channels = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "," not in line:
                continue
            try:
                name, url = map(str.strip, line.split(",", 1))
                if not name or not url or not is_valid_url(url):
                    continue
                if is_foreign_channel(name):
                    print(f"🌍 Skipped foreign (Guovin): {name}")
                    continue
                category, display_name = categorize_channel(name)
                channels.append((display_name, url, category))
            except Exception as e:
                print(f"⚠️ Parse failed: {line} | {e}")
        print(f"✅ Loaded {len(channels)} from Guovin")
        return channels
    except Exception as e:
        print(f"❌ Load Guovin failed: {e}")
        return []


def get_dynamic_stream():
    print("👉 Fetching dynamic stream from API...")
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            url = data['data']['m3u8Url']
            name = "西充综合"
            if is_foreign_channel(name):
                print("🌍 Skipped foreign (API)")
                return None
            print(f"✅ Dynamic stream added: {name}")
            return (name, url, "本地节目")
        else:
            print("❌ m3u8Url not found in API response")
    except Exception as e:
        print(f"❌ API request failed: {e}")
    return None


def check_cctv_validity(channels):
    """检测所有央视源是否有效，无效则跳过"""
    print("🔍 Checking CCTV stream validity...")
    valid_channels = []
    cctv_count = 0
    for item in channels:
        name, url, group = item
        if group == '央视':
            cctv_count += 1
            if check_url_valid(url):
                valid_channels.append(item)
                print(f"  ✅ Valid: {name}")
            else:
                print(f"  ❌ Invalid: {name}")
        else:
            valid_channels.append(item)
    print(f"✅ {cctv_count} CCTV streams checked.")
    return valid_channels


def sort_channels(channels):
    """自定义排序"""
    ORDER = [
        '本地节目', '央视', '卫视',
        '四川', '广东', '湖南', '湖北', '江苏', '浙江', '山东', '河南', '河北', '福建', '广西', '云南', '江西', '辽宁', '山西', '陕西', '安徽', '黑龙江', '内蒙古', '吉林', '贵州', '甘肃', '海南', '青海', '宁夏', '新疆', '西藏',
        '电影频道', '港澳台', '经典剧场'
    ]

    LOCAL_PRIORITY = {
        "西充综合": 0,
        "南充综合": 1,
        "南充科教生活": 2
    }

    def get_cctv_number(name):
        match = re.search(r'CCTV-(\d+)', name)
        return int(match.group(1)) if match else float('inf')

    def sort_key(item):
        name, url, group = item

        if group == '本地节目':
            if name in LOCAL_PRIORITY:
                return (ORDER.index(group), LOCAL_PRIORITY[name], name)
            else:
                return (ORDER.index(group), 999, name)

        elif group == '央视':
            # 央视内部按数字排序
            num = get_cctv_number(name)
            return (ORDER.index(group), num, name)

        else:
            group_order = ORDER.index(group) if group in ORDER else 999
            return (group_order, name)

    return sorted(channels, key=sort_key)


def generate_m3u8_content(channels):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "#EXTM3U",
        f"# Generated at: {now}",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    sorted_channels = sort_channels(channels)

    for name, url, group in sorted_channels:
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)

    return "\n".join(lines) + "\n"


def print_stats(channels):
    stats = Counter(item[2] for item in channels)
    print("\n📊 分类统计：")
    for cat, cnt in stats.most_common():
        print(f"   {cat:<10} : {cnt}")
    print(f"   {'总计':<10} : {sum(stats.values())}")


def main():
    print("🚀 Starting playlist generation...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_channels = []

    # === 1. 加载白名单（本地节目）===
    whitelist_channels = load_whitelist()
    all_channels.extend(whitelist_channels)

    # === 2. 动态流（也归为本地）===
    dynamic_item = get_dynamic_stream()
    if dynamic_item:
        all_channels.append(dynamic_item)

    # === 3. 其他源 ===
    all_channels.extend(load_tv_m3u())
    all_channels.extend(load_guovin_iptv())

    print(f"📥 Total raw streams: {len(all_channels)}")

    # 去重
    unique_channels = merge_and_deduplicate(all_channels)

    # 过滤国外
    filtered_channels = [item for item in unique_channels if not is_foreign_channel(item[0])]

    # 检测央视有效性
    final_channels = check_cctv_validity(filtered_channels)

    print(f"✅ Final playlist size: {len(final_channels)} channels")

    print_stats(final_channels)

    m3u8_content = generate_m3u8_content(final_channels)

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 Successfully generated: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Write failed: {e}")
        return

    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("📄 Created .nojekyll")

    print("✅ All tasks completed!")


if __name__ == "__main__":
    main()
