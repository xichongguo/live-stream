import requests
import os
from urllib.parse import urlparse
import re
import sys
import requests
import os
from urllib.parse import urlparse
import re
import sys

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

REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
MIGU_SOURCE_URLS = [
    "http://www.52top.com.cn:678/downloads/migu.txt",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/migu.txt",
    "https://live.zbds.top/tv/iptv4.txt"
]
BC_API_URL = "https://bc.188766.xyz/"
BC_PARAMS = {'ip': '', 'mima': 'bingchawusifengxian', 'json': 'true'}
LOCAL_TXT_PATH = "local.txt"
WHITELIST_TIMEOUT = 20
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
    '山西': ['山西', '太原', '大同', '阳泉', '长治', '晋城', '朔州', '晋中', '运城', '忻州', '吕梁'],
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

CATEGORY_MAP = {
    '卫视': ['卫视', '卫星', '东方', '北京卫视', '天津卫视', '河北卫视', '山西卫视', '内蒙古卫视', '辽宁卫视', '吉林卫视', '黑龙江卫视', '江苏卫视', '浙江卫视', '安徽卫视', '福建东南', '江西卫视', '山东卫视', '河南卫视', '湖北卫视', '湖南卫视', '广东卫视', '广西卫视', '海南卫视', '四川卫视', '重庆卫视', '贵州卫视', '云南卫视', '西藏卫视', '陕西卫视', '甘肃卫视', '青海卫视', '宁夏卫视', '新疆卫视'],
    '电影关键词': ['电影', '影院', 'CHC', '华数', '优酷', '爱奇艺', '腾讯', '芒果', '动作', '喜剧', '爱情', '科幻', '恐怖', '战争', '剧情', '影视'],
    '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', 'J2', 'HOY', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'],
    '经典剧场': ['经典', '怀旧', '老电影', '戏曲', '京剧']
}

ROTATION_KEYWORDS = ['轮播', '回放', '测试']
FOREIGN_KEYWORDS = {
    'CNN', 'BBC', 'NHK', 'KBS', 'MBC', 'SBS', 'Arirang', 'France', 'Deutsch', 'RTL', 'Sky', 'Al Jazeera', 'HBO', 'ESPN', 'Star Sports', 'Fox', 'Discovery', 'National Geographic', 'Cartoon Network', 'Nickelodeon', 'MTV', 'VH1', 'CNBC', 'Bloomberg', 'DW', 'RT', 'CGTN', 'ABS-CBN', 'GMA', 'TV5'
}
ALLOWED_FOREIGN = {'凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'} 

# ================== Helper Functions ==================
def is_foreign_channel(name):
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    for keyword in FOREIGN_KEYWORDS:
        if keyword.lower() in name_lower:
            return True
    return False

def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

def normalize_cctv_name(name):
    CHINESE_ALIAS = {
        "中央一套": "CCTV-1", "综合频道": "CCTV-1",
        "中央二套": "CCTV-2", "财经频道": "CCTV-2",
        "中央三套": "CCTV-3", "综艺频道": "CCTV-3",
        "中央四套": "CCTV-4", "中文国际频道": "CCTV-4",
        "中央五套": "CCTV-5", "体育频道": "CCTV-5",
        "中央六套": "CCTV-6", "电影频道": "CCTV-6",
        "中央七套": "CCTV-7", "国防军事频道": "CCTV-7",
        "中央八套": "CCTV-8", "电视剧频道": "CCTV-8",
        "中央九套": "CCTV-9", "纪录频道": "CCTV-9",
        "中央十套": "CCTV-10", "科教频道": "CCTV-10",
        "中央十一套": "CCTV-11", "戏曲频道": "CCTV-11",
        "中央十二套": "CCTV-12", "社会与法频道": "CCTV-12",
        "中央十三套": "CCTV-13", "新闻频道": "CCTV-13",
        "中央十四套": "CCTV-14", "少儿频道": "CCTV-14",
        "中央十五套": "CCTV-15", "音乐频道": "CCTV-15",
        "中央十七套": "CCTV-17", "农业农村频道": "CCTV-17",
    }
    if name in CHINESE_ALIAS:
        return CHINESE_ALIAS[name]
    for keyword, std in CHINESE_ALIAS.items():
        if keyword in name:
            return std
    match = re.search(r'CCTV\D*(\d+)', name.upper())
    if match:
        return f"CCTV-{int(match.group(1))}"
    return name

def categorize_channel(name):
    name_lower = name.lower()
    if any(kw in name_lower for kw in ['cctv', '中央']):
        return '央视', normalize_cctv_name(name)
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower:
            return '卫视', name
    has_movie_kw = any(kw.lower() in name_lower for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name_lower for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw:
        return '电影轮播', name
    if has_movie_kw and not has_rotation_kw:
        return '电影频道', name
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name:
            return '港澳台', name
    for kw in CATEGORY_MAP['经典剧场']:
        if kw in name:
            return '经典剧场', name
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name:
                return prov, name
    if has_rotation_kw:
        return '其他', name
    return "其他", name

# ================== Load Sources ==================
def load_whitelist_as_local_program():
    print(f"👉 Loading whitelist.txt as '本地节目' (TOP)...")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        lines = response.text.strip().splitlines()
        channels = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2:
                continue
            name, url = parts, parts
            if not name or not url or not is_valid_url(url):
                continue
            if is_foreign_channel(name):
                continue
            channels.append((name, url, "本地节目", 0))
        print(f" ✅ Loaded {len(channels)} channels from whitelist.")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist.txt failed: {e}")
        return []<websource>source_group_web_1</websource>

def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            name, url = "西充综合", data['data']['m3u8Url']
            if not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                return (disp, url, cat, 2)
    except:
        pass
    return None

def load_tv_m3u():
    try:
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        lines = response.text.strip().splitlines()
        channels = []
        current_name = None
        for line in lines:
            if line.startswith("#EXTINF"):
                current_name = line.split(",", 1).strip() if "," in line else "Unknown"
            elif line.startswith("http") and current_name:
                if is_valid_url(line) and not is_foreign_channel(current_name):
                    cat, disp = categorize_channel(current_name)
                    channels.append((disp, line, cat, 2))
                current_name = None
        print(f" ✅ Loaded {len(channels)} channels from tv.m3u.")
        return channels
    except Exception as e:
        print(f"❌ Load tv.m3u failed: {e}")
        return []<websource>source_group_web_2</websource>

def load_guovin_iptv():
    channels = []
    success_url = None
    for url in MIGU_SOURCE_URLS:
        print(f"👉 Trying source: {url} ...")
        try:
            response = requests.get(url, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
            if response.status_code == 200 and len(response.text.strip()) > 100:
                success_url = url
                content = response.text
                try:
                    response.encoding = 'utf-8'
                    content = response.text
                except:
                    pass
                lines = content.strip().splitlines()
                current_name = None
                parsed_count = 0
                skipped_count = 0
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#EXTINF"):
                        if "," in line:
                            current_name = line.split(",", 1).strip()
                        else:
                            current_name = "Unknown"
                    elif line.startswith("http") and current_name:
                        if is_valid_url(line):
                            if not is_foreign_channel(current_name):
                                cat, disp = categorize_channel(current_name)
                                channels.append((disp, line, cat, 2))
                                parsed_count += 1
                            else:
                                skipped_count += 1
                        current_name = None
                print(f" ✅ SUCCESS! Loaded {parsed_count} channels from: {url}")
                print(f" (Skipped {skipped_count} foreign/invalid)")
                break
            else:
                print(f" ⚠️ Failed (Status: {response.status_code} or empty), trying next...")
        except Exception as e:
            print(f" ⚠️ Connection error ({str(e)[:50]}...), trying next...")
            continue
    if not success_url:
        print(f" ❌ ERROR: All Migu source URLs failed.")
    return channels<websource>source_group_web_3</websource>

def load_bc_api():
    try:
        response = requests.get(BC_API_URL, params=BC_PARAMS, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        data = response.json()
        channels = []
        for item in data.get("data", []):
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if name and url and is_valid_url(url) and not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                channels.append((disp, url, cat, 2))
        print(f" ✅ Loaded {len(channels)} channels from BC API.")
        return channels
    except Exception as e:
        print(f"❌ Load BC API failed: {e}")
        return []

def load_local_txt():
    if not os.path.exists(LOCAL_TXT_PATH):
        return []
    channels = []
    try:
        with open(LOCAL_TXT_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2:
                continue
            name, url = parts, parts
            if not name or not url or not is_valid_url(url):
                continue
            if is_foreign_channel(name):
                continue
            cat, disp = categorize_channel(name)
            channels.append((disp, url, cat, 2))
        print(f" ✅ Loaded {len(channels)} channels from local.txt.")
        return channels
    except Exception as e:
        print(f"❌ Load local.txt failed: {e}")
        return []<websource>source_group_web_4</websource>

# ================== Main Logic ==================
def main():
    # 1. 检查是否为跳转模式
    if len(sys.argv) > 1 and sys.argv == 'redirect':
        print("🚀 正在启动极速跳转模式...")
        stream = get_dynamic_stream()
        if stream:
            name, url, category, priority = stream
            print("Status: 302 Found")
            print(f"Location: {url}")
            print() # HTTP Header 结束符
            print(f"Redirecting to {name}...")
            sys.exit(0)
        else:
            print("Status: 503 Service Unavailable")
            print("Content-Type: text/plain;charset=UTF-8")
            print()
            print("无法获取直播源")
            sys.exit(1)<websource>source_group_web_5</websource>

    # 2. 默认模式：生成 M3U
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

REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
TV_M3U_URL = "https://raw.githubusercontent.com/wwb521/live/refs/heads/main/tv.m3u"
MIGU_SOURCE_URLS = [
    "http://www.52top.com.cn:678/downloads/migu.txt",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/migu.txt",
    "https://live.zbds.top/tv/iptv4.txt"
]
BC_API_URL = "https://bc.188766.xyz/"
BC_PARAMS = {'ip': '', 'mima': 'bingchawusifengxian', 'json': 'true'}
LOCAL_TXT_PATH = "local.txt"
WHITELIST_TIMEOUT = 20
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
    '山西': ['山西', '太原', '大同', '阳泉', '长治', '晋城', '朔州', '晋中', '运城', '忻州', '吕梁'],
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

CATEGORY_MAP = {
    '卫视': ['卫视', '卫星', '东方', '北京卫视', '天津卫视', '河北卫视', '山西卫视', '内蒙古卫视', '辽宁卫视', '吉林卫视', '黑龙江卫视', '江苏卫视', '浙江卫视', '安徽卫视', '福建东南', '江西卫视', '山东卫视', '河南卫视', '湖北卫视', '湖南卫视', '广东卫视', '广西卫视', '海南卫视', '四川卫视', '重庆卫视', '贵州卫视', '云南卫视', '西藏卫视', '陕西卫视', '甘肃卫视', '青海卫视', '宁夏卫视', '新疆卫视'],
    '电影关键词': ['电影', '影院', 'CHC', '华数', '优酷', '爱奇艺', '腾讯', '芒果', '动作', '喜剧', '爱情', '科幻', '恐怖', '战争', '剧情', '影视'],
    '港澳台': ['凤凰', 'TVB', '翡翠', '明珠', 'J2', 'HOY', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'],
    '经典剧场': ['经典', '怀旧', '老电影', '戏曲', '京剧']
}

ROTATION_KEYWORDS = ['轮播', '回放', '测试']
FOREIGN_KEYWORDS = {
    'CNN', 'BBC', 'NHK', 'KBS', 'MBC', 'SBS', 'Arirang', 'France', 'Deutsch', 'RTL', 'Sky', 'Al Jazeera', 'HBO', 'ESPN', 'Star Sports', 'Fox', 'Discovery', 'National Geographic', 'Cartoon Network', 'Nickelodeon', 'MTV', 'VH1', 'CNBC', 'Bloomberg', 'DW', 'RT', 'CGTN', 'ABS-CBN', 'GMA', 'TV5'
}
ALLOWED_FOREIGN = {'凤凰', 'TVB', '翡翠', '明珠', '东森', '中天', '年代', '三立', '民视', '公视', '华视', 'TVBS'} 

# ================== Helper Functions ==================
def is_foreign_channel(name):
    name_lower = name.lower()
    for allowed in ALLOWED_FOREIGN:
        if allowed in name:
            return False
    for keyword in FOREIGN_KEYWORDS:
        if keyword.lower() in name_lower:
            return True
    return False

def is_valid_url(url):
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

def normalize_cctv_name(name):
    CHINESE_ALIAS = {
        "中央一套": "CCTV-1", "综合频道": "CCTV-1",
        "中央二套": "CCTV-2", "财经频道": "CCTV-2",
        "中央三套": "CCTV-3", "综艺频道": "CCTV-3",
        "中央四套": "CCTV-4", "中文国际频道": "CCTV-4",
        "中央五套": "CCTV-5", "体育频道": "CCTV-5",
        "中央六套": "CCTV-6", "电影频道": "CCTV-6",
        "中央七套": "CCTV-7", "国防军事频道": "CCTV-7",
        "中央八套": "CCTV-8", "电视剧频道": "CCTV-8",
        "中央九套": "CCTV-9", "纪录频道": "CCTV-9",
        "中央十套": "CCTV-10", "科教频道": "CCTV-10",
        "中央十一套": "CCTV-11", "戏曲频道": "CCTV-11",
        "中央十二套": "CCTV-12", "社会与法频道": "CCTV-12",
        "中央十三套": "CCTV-13", "新闻频道": "CCTV-13",
        "中央十四套": "CCTV-14", "少儿频道": "CCTV-14",
        "中央十五套": "CCTV-15", "音乐频道": "CCTV-15",
        "中央十七套": "CCTV-17", "农业农村频道": "CCTV-17",
    }
    if name in CHINESE_ALIAS:
        return CHINESE_ALIAS[name]
    for keyword, std in CHINESE_ALIAS.items():
        if keyword in name:
            return std
    match = re.search(r'CCTV\D*(\d+)', name.upper())
    if match:
        return f"CCTV-{int(match.group(1))}"
    return name

def categorize_channel(name):
    name_lower = name.lower()
    if any(kw in name_lower for kw in ['cctv', '中央']):
        return '央视', normalize_cctv_name(name)
    for kw in CATEGORY_MAP['卫视']:
        if kw.lower() in name_lower:
            return '卫视', name
    has_movie_kw = any(kw.lower() in name_lower for kw in CATEGORY_MAP['电影关键词'])
    has_rotation_kw = any(kw in name_lower for kw in ROTATION_KEYWORDS)
    if has_movie_kw and has_rotation_kw:
        return '电影轮播', name
    if has_movie_kw and not has_rotation_kw:
        return '电影频道', name
    for kw in CATEGORY_MAP['港澳台']:
        if kw in name:
            return '港澳台', name
    for kw in CATEGORY_MAP['经典剧场']:
        if kw in name:
            return '经典剧场', name
    for prov, cities in PROVINCE_KEYWORDS.items():
        for city in cities:
            if city in name:
                return prov, name
    if has_rotation_kw:
        return '其他', name
    return "其他", name

def check_url_valid(url, timeout=CHECK_TIMEOUT):
    try:
        response = requests.head(url, timeout=timeout, headers=DEFAULT_HEADERS, allow_redirects=True)
        return response.status_code < 400
    except:
        try:
            response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS, stream=True)
            return response.status_code < 400
        except:
            return False

# ================== Load Sources ==================
def load_whitelist_as_local_program():
    print(f"👉 Loading whitelist.txt as '本地节目' (TOP)...")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        lines = response.text.strip().splitlines()
        channels = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2:
                continue
            name, url = parts, parts
            if not name or not url or not is_valid_url(url):
                continue
            if is_foreign_channel(name):
                continue
            channels.append((name, url, "本地节目", 0))
        print(f" ✅ Loaded {len(channels)} channels from whitelist.")
        return channels
    except Exception as e:
        print(f"❌ Load whitelist.txt failed: {e}")
        return []<websource>source_group_web_1</websource>

def get_dynamic_stream():
    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=10)
        data = response.json()
        if 'data' in data and 'm3u8Url' in data['data']:
            name, url = "西充综合", data['data']['m3u8Url']
            if not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                return (disp, url, cat, 2)
    except:
        pass
    return None

def load_tv_m3u():
    try:
        response = requests.get(TV_M3U_URL, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        lines = response.text.strip().splitlines()
        channels = []
        current_name = None
        for line in lines:
            if line.startswith("#EXTINF"):
                current_name = line.split(",", 1).strip() if "," in line else "Unknown"
            elif line.startswith("http") and current_name:
                if is_valid_url(line) and not is_foreign_channel(current_name):
                    cat, disp = categorize_channel(current_name)
                    channels.append((disp, line, cat, 2))
                current_name = None
        print(f" ✅ Loaded {len(channels)} channels from tv.m3u.")
        return channels
    except Exception as e:
        print(f"❌ Load tv.m3u failed: {e}")
        return []<websource>source_group_web_2</websource>

def load_guovin_iptv():
    channels = []
    success_url = None
    for url in MIGU_SOURCE_URLS:
        print(f"👉 Trying source: {url} ...")
        try:
            response = requests.get(url, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
            if response.status_code == 200 and len(response.text.strip()) > 100:
                success_url = url
                content = response.text
                try:
                    response.encoding = 'utf-8'
                    content = response.text
                except:
                    pass
                lines = content.strip().splitlines()
                current_name = None
                parsed_count = 0
                skipped_count = 0
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#EXTINF"):
                        if "," in line:
                            current_name = line.split(",", 1).strip()
                        else:
                            current_name = "Unknown"
                    elif line.startswith("http") and current_name:
                        if is_valid_url(line):
                            if not is_foreign_channel(current_name):
                                cat, disp = categorize_channel(current_name)
                                channels.append((disp, line, cat, 2))
                                parsed_count += 1
                            else:
                                skipped_count += 1
                        current_name = None
                print(f" ✅ SUCCESS! Loaded {parsed_count} channels from: {url}")
                print(f" (Skipped {skipped_count} foreign/invalid)")
                break
            else:
                print(f" ⚠️ Failed (Status: {response.status_code} or empty), trying next...")
        except Exception as e:
            print(f" ⚠️ Connection error ({str(e)[:50]}...), trying next...")
            continue
    if not success_url:
        print(f" ❌ ERROR: All Migu source URLs failed.")
    return channels<websource>source_group_web_3</websource>

def load_bc_api():
    try:
        response = requests.get(BC_API_URL, params=BC_PARAMS, timeout=WHITELIST_TIMEOUT, headers=DEFAULT_HEADERS)
        data = response.json()
        channels = []
        for item in data.get("data", []):
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if name and url and is_valid_url(url) and not is_foreign_channel(name):
                cat, disp = categorize_channel(name)
                channels.append((disp, url, cat, 2))
        print(f" ✅ Loaded {len(channels)} channels from BC API.")
        return channels
    except Exception as e:
        print(f"❌ Load BC API failed: {e}")
        return []

def load_local_txt():
    if not os.path.exists(LOCAL_TXT_PATH):
        return []
    channels = []
    try:
        with open(LOCAL_TXT_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) < 2:
                continue
            name, url = parts, parts
            if not name or not url or not is_valid_url(url):
                continue
            if is_foreign_channel(name):
                continue
            cat, disp = categorize_channel(name)
            channels.append((disp, url, cat, 2))
        print(f" ✅ Loaded {len(channels)} channels from local.txt.")
        return channels
    except Exception as e:
        print(f"❌ Load local.txt failed: {e}")
        return []<websource>source_group_web_4</websource>

# ================== Main Logic ==================
def main():
    # 1. 检查是否为跳转模式
    if len(sys.argv) > 1 and sys.argv == 'redirect':
        print("🚀 正在启动极速跳转模式...")
        stream = get_dynamic_stream()
        if stream:
            name, url, category, priority = stream
            print("Status:<websource>source_group_web_5</websource>
