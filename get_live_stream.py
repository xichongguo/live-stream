# File: get_live_stream.py
# 功能：
#   - 无任何检测（不测可用性、不判断IPv4）
#   - 自动分类（央视/卫视/省份/港澳台）
#   - 过滤国外频道（保留港澳台）
#   - 去重（基于URL归一化）
#   - 加载顺序：tv.m3u → 白名单 → 海燕（海燕排最后）
#   - 输出 live/current.m3u8

import requests
import os
from urllib.parse import unquote, urlparse, parse_qs, urlunparse
from datetime import datetime


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

# Remote sources（已移除电视家）
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
HAIYAN_TXT_URL = "https://chuxinya.top/f/AD5QHE/%E6%B5%B7%E7%87%95.txt"

WHITELIST_TIMEOUT = 15
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


# ---------------- 分类规则 ----------------
CATEGORY_MAP = {
    '央视': ['cctv', '中央'],
    '卫视': [
        '卫视', '湖南', '浙江', '江苏', '东方', '北京', '广东', '深圳', '四川', '湖北', '辽宁',
        '东南', '天津', '重庆', '黑龙江', '山东', '安徽', '云南', '陕西', '甘肃', '新疆',
        '内蒙古', '吉林', '河北', '山西', '广西', '江西', '福建', '贵州', '海南'
    ],
    '地方': [
        '都市', '新闻', '综合', '公共', '生活', '影视频道', '影视', '电视剧', '娱乐',
        '少儿', '卡通', '体育', '财经', '纪实', '教育', '民生', '交通', '文艺', '音乐',
        '戏曲', '高尔夫', '网球'
    ],
    # --- 省份分类 ---
    '四川': ['四川', '成都', '绵阳', '德阳', '泸州', '南充', '宜宾', '达州', '内江', '乐山', '自贡', '攀枝花', '广元', '遂宁', '巴中', '雅安', '眉山', '资阳'],
    '广东': ['广东', '广州', '深圳', '佛山', '东莞', '中山', '珠海', '惠州', '江门', '汕头', '湛江', '茂名', '肇庆', '揭阳', '潮州', '清远', '韶关', '汕尾', '阳江', '河源'],
    '江苏': ['江苏', '南京', '苏州', '无锡', '常州', '徐州', '南通', '扬州', '盐城', '泰州', '镇江', '淮安', '连云港', '宿迁'],
    '浙江': ['浙江', '杭州', '宁波', '温州', '嘉兴', '绍兴', '金华', '台州', '湖州', '衢州', '丽水', '舟山'],
    '山东': ['山东', '济南', '青岛', '烟台', '潍坊', '淄博', '临沂', '济宁', '泰安', '威海', '德州', '聊城', '滨州', '菏泽', '枣庄'],
    '河南': ['河南', '郑州', '洛阳', '开封', '新乡', '南阳', '许昌', '安阳', '商丘', '信阳', '平顶山', '周口', '驻马店', '焦作', '濮阳', '漯河', '三门峡', '鹤壁'],
    '湖北': ['湖北', '武汉', '宜昌', '襄阳', '黄冈', '荆州', '孝感', '十堰', '咸宁', '荆门', '随州', '恩施', '黄石', '鄂州'],
    '湖南': ['湖南', '长沙', '株洲', '湘潭', '衡阳', '岳阳', '常德', '张家界', '怀化', '郴州', '娄底', '邵阳', '益阳', '永州'],
    '河北': ['河北', '石家庄', '唐山', '保定', '秦皇岛', '邯郸', '邢台', '张家口', '沧州', '衡水', '承德'],
    '安徽': ['安徽', '合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '安庆', '阜阳', '宿州', '六安', '亳州', '黄山', '滁州', '淮北', '宣城', '池州'],
    '福建': ['福建', '福州', '厦门', '泉州', '漳州', '莆田', '宁德', '三明', '南平', '龙岩'],
    '辽宁': ['辽宁', '沈阳', '大连', '鞍山', '抚顺', '本溪', '丹东', '锦州', '营口', '阜新', '辽阳', '铁岭', '朝阳', '盘锦'],
    '陕西': ['陕西', '西安', '宝鸡', '咸阳', '渭南', '汉中', '榆林', '延安', '安康', '商洛'],
    '山西': ['山西', '太原', '大同', '阳泉', '长治', '晋城', '朔州', '晋中', '运城', '忻州', '临汾', '吕梁'],
    '江西': ['江西', '南昌', '九江', '赣州', '上饶', '宜春', '吉安', '抚州', '萍乡', '新余', '鹰潭'],
    '云南': ['云南', '昆明', '大理', '丽江', '玉溪', '曲靖', '保山', '红河', '临沧', '西双版纳', '楚雄', '文山', '普洱', '昭通', '迪庆', '怒江'],
    '贵州': ['贵州', '贵阳', '遵义', '六盘水', '安顺', '毕节', '铜仁', '黔东南', '黔南', '黔西南'],
    '广西': ['广西', '南宁', '柳州', '桂林', '梧州', '北海', '玉林', '钦州', '贵港', '百色', '贺州', '河池', '来宾', '崇左'],
    '甘肃': ['甘肃', '兰州', '天水', '白银', '庆阳', '定西', '武威', '张掖', '平凉', '酒泉', '陇南', '临夏', '甘南'],
    '新疆': ['新疆', '乌鲁木齐', '克拉玛依', '吐鲁番', '哈密', '库尔勒', '阿克苏', '喀什', '和田', '伊宁', '石河子'],
    '内蒙古': ['内蒙古', '呼和浩特', '包头', '赤峰', '通辽', '鄂尔多斯', '呼伦贝尔', '巴彦淖尔', '乌兰察布', '锡林郭勒', '兴安盟'],
    '吉林': ['吉林', '长春', '吉林市', '四平', '辽源', '通化', '白山', '松原', '白城'],
    '黑龙江': ['黑龙江', '哈尔滨', '齐齐哈尔', '牡丹江', '佳木斯', '大庆', '绥化', '鹤岗', '鸡西', '双鸭山', '七台河', '黑河', '大兴安岭'],
    '海南': ['海南', '海口', '三亚', '儋州', '琼海', '万宁', '东方', '五指山', '文昌', '乐东', '澄迈', '定安'],
    '香港': ['香港', 'HK', 'RTHK', 'TVB', 'ATV'],
    '澳门': ['澳门', 'Macao', 'TDM'],
    '台湾': ['台湾', 'Taiwan', '台視', '中視', '華視', '民視', '公視', 'TVBS', '三立', '东森', '中天']
}

# ---------------- 国外关键词过滤 ----------------
FOREIGN_KEYWORDS = {
    'cnn', 'bbc', 'fox', 'abc', 'nbc', 'cbc', 'pbs', 'sky', 'disney',
    'nick', 'mtv', 'espn', 'hbo', 'paramount', 'warner', 'pluto',
    'france', 'deutsch', 'german', 'italia', 'spain', 'espanol',
    'japan', 'tokyo', 'nhk', 'korea', 'seoul', 'sbs', 'kbs', 'mbc',
    'india', 'bollywood', 'russia', 'moscow', 'turkey', 'egypt',
    'arab', 'qatar', 'dubai', 'australia', 'sydney', 'canada',
    'mexico', 'brazil', 'argentina', 'chile', 'south africa',
    'singapore', 'malaysia', 'thailand', 'vietnam', 'philippines', 'indonesia',
    'pakistan', 'iran', 'iraq', 'israel', 'sweden', 'norway', 'denmark',
    'switzerland', 'austria', 'belgium', 'netherlands', 'poland', 'ukraine',
    'greece', 'portugal', 'finland', 'ireland', 'new zealand'
}

ALLOWED_FOREIGN = {'香港', '澳门', '台湾', 'HK', 'Macao', 'Taiwan', 'TVB', 'ATV', 'TDM', '台視', '中視', '華視', '民視', '公視'}


# ================== Utility Functions ==================
def is_foreign_channel(name):
    """判断是否为国外频道（排除港澳台）"""
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    for keyword in FOREIGN_KEYWORDS:
        if keyword in name_lower:
            return True
    return False


def normalize_url(url):
    """Remove tracking/query params for deduplication."""
    try:
        parsed = urlparse(url.lower())
        safe_params = {}
        unsafe_keys = {'token', 't', 'ts', 'sign', 'auth_key', 'verify', 'session', 'key', 'pwd', 'stb', 'icpid', 'RTS', 'from', 'hms_devid', 'online', 'vqe'}
        for k, v in parse_qs(parsed.query).items():
            if k.lower() not in unsafe_keys:
                if v and v[0]:
                    safe_params[k] = v[0]
        new_query = '&'.join(f"{k}={v}" for k, v in safe_params.items())
        return urlunparse(parsed._replace(query=new_query))
    except:
        return url.lower().split('?')[0]


def merge_and_deduplicate(channels):
    """Remove duplicates based on normalized URL (keep first occurrence)"""
    seen = set()
    unique = []
    for item in channels:
        name, url, group = item
        norm_url = normalize_url(url)
        if norm_url not in seen:
            seen.add(norm_url)
            unique.append(item)
        else:
            print(f"🔁 Skipped duplicate: {url}")
    print(f"✅ After dedup: {len(unique)} unique streams")
    return unique


def categorize_channel(name):
    """Auto categorize channel by name."""
    name_lower = name.lower()
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                return category
    return "其他"


def load_tv_m3u():
    """Load tv.m3u -> auto categorize"""
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
                if current_name and line.startswith(("http://", "https://")):
                    if is_foreign_channel(current_name):
                        print(f"🌍 Skipped foreign (tv.m3u): {current_name}")
                    else:
                        category = categorize_channel(current_name)
                        channels.append((current_name, line, category))
                        print(f"  ➕ tv.m3u: {current_name} -> {category}")
                current_name = None
        print(f"✅ Loaded {len(channels)} from tv.m3u")
        return channels
    except Exception as e:
        print(f"❌ Failed to load tv.m3u: {e}")
        return []


def load_whitelist_from_remote():
    """Load whitelist -> 本地节目 (trusted, no test)"""
    print(f"👉 Loading trusted whitelist: {REMOTE_WHITELIST_URL}")
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
            if not name or not url or not url.startswith(("http://", "https://")):
                continue
            if is_foreign_channel(name):
                print(f"🌍 Skipped foreign (whitelist): {name}")
                continue
            channels.append((name, url, "本地节目"))
            print(f"  ➕ Whitelist: {name} -> 本地节目")
        print(f"✅ Loaded {len(channels)} from whitelist")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist failed: {e}")
        return []


def load_haiyan_txt():
    """Load 海燕.txt -> auto categorize"""
    print(f"👉 Loading 海燕.txt: {HAIYAN_TXT_URL}")
    try:
        decoded_url = unquote(HAIYAN_TXT_URL)
        response = requests.get(decoded_url, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'
        lines = response.text.strip().splitlines()
        channels = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("更新时间") or line.startswith("TV"):
                continue
            if "," not in line:
                continue
            try:
                name, url = map(str.strip, line.split(",", 1))
                if not name or not url or not url.startswith(("http://", "https://")):
                    continue
                if is_foreign_channel(name):
                    print(f"🌍 Skipped foreign (海燕.txt): {name}")
                    continue
                category = categorize_channel(name)
                channels.append((name, url, category))
                print(f"  ➕ 海燕.txt: {name} -> {category}")
            except Exception as e:
                print(f"⚠️ Parse failed at line {line_num}: {line} | {e}")
        print(f"✅ Loaded {len(channels)} from 海燕.txt")
        return channels
    except Exception as e:
        print(f"❌ Load 海燕.txt failed: {e}")
        return []


def get_dynamic_stream():
    """Fetch dynamic stream from API."""
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
            category = categorize_channel(name)
            print(f"✅ Dynamic stream added: {name}")
            return (name, url, category)
        else:
            print("❌ m3u8Url not found in API response")
    except Exception as e:
        print(f"❌ API request failed: {e}")
    return None


def generate_m3u8_content(channels):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "#EXTM3U",
        f"# Generated at: {now}",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    for name, url, group in channels:
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)

    return "\n".join(lines) + "\n"


def main():
    print("🚀 Starting playlist generation...")
    os.makedirs('live', exist_ok=True)
    print("📁 Ensured live/ directory")

    all_channels = []

    # 1. 获取动态流（如西充综合）
    dynamic_item = get_dynamic_stream()
    if dynamic_item:
        all_channels.append(dynamic_item)

    # 2. 加载 tv.m3u（优先）
    all_channels.extend(load_tv_m3u())

    # 3. 加载白名单（免检）
    all_channels.extend(load_whitelist_from_remote())

    # 4. 最后加载海燕直播源
    all_channels.extend(load_haiyan_txt())

    print(f"📥 Total raw streams: {len(all_channels)}")

    # 去重
    unique_channels = merge_and_deduplicate(all_channels)

    # 过滤国外（双重保险）
    final_channels = [item for item in unique_channels if not is_foreign_channel(item[0])]
    print(f"✅ Final playlist size: {len(final_channels)} channels (after foreign filter)")

    'isTest': '0'# 生成 M3U8
    '经度值': '0',generate_m3u8_content(final_channels)

    'versionCodeGlobal': '5009037'# 写入文件
    output_path = 'live/current.m3u8'
HEADERS = {try:
    'User-Agent': 'okhttp/3.12.12',with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 Successfully generated: {output_path}")
    except Exception as e:
        print(f"❌ Write failed: {e}")
        return

    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("📄 Created .nojekyll")

    print("✅ All tasks completed!")


if __name__ == "__main__":
    main()
