import re
import requests

# 【核心新增】基于链接特征的频道重命名规则（模糊匹配，不区分大小写）
# 只要频道的播放链接里包含左边的关键词，就会被强制改名为右边的中文名
# 你可以根据实际抓取到的链接，在这里无限添加新的规则
URL_KEYWORD_MAP = {
    # --- 佛山及广东地方台示例 ---
    "foshan": "佛山综合",
    "nanhai": "南海电视台",
    "shunde": "顺德电视台",
    "gdzh": "广东综合",
    "gdgg": "广东公共",
    "gdys": "广东影视",
    "gdse": "广东少儿",
    "gdty": "广东体育",
    "gdxw": "广东新闻",
    "gdjj": "广东经济",
    "gdsh": "广东生活",
    # --- 其他常见备用/地方频道特征 ---
    "cctv1": "CCTV-1 综合",
    "cctv5": "CCTV-5 体育",
    "cctv5+": "CCTV-5+ 赛事",
    "fjzh": "福建综合",
    # 你可以在这里继续添加你发现的规律，例如 "备用": "备用频道1"
}

def robust_decode(content):
    """强制稳健解码：优先尝试 UTF-8，失败则尝试 GBK"""
    try:
        text = content.decode('utf-8')
        if not re.search(r'[\u4e00-\u9fa5]', text) and re.search(rb'[\x80-\xff]{2,}', content):
            raise UnicodeDecodeError('utf-8', b'', 0, 1, 'force gbk')
        return text
    except UnicodeDecodeError:
        try:
            return content.decode('gbk')
        except:
            return content.decode('utf-8', errors='ignore')

def parse_m3u_to_m3u8(m3u_content):
    """解析 M3U 内容，使用特征词强制重命名 noepg 频道"""
    text = robust_decode(m3u_content)
    lines = text.split('\n')
    channels = []
    groups = []
    tvg_url = None
    current_group = ""
    
    # 预编译正则表达式
    re_extinf = re.compile(r'#EXTINF:')
    re_tvg_id = re.compile(r'tvg-id="([^"]*)"')
    re_tvg_name = re.compile(r'tvg-name="([^"]*)"')
    re_logo = re.compile(r'tvg-logo="([^"]*)"')
    re_group = re.compile(r'group-title="([^"]*)"')
    re_url = re.compile(r'^(http://|https://|rtp://|rtsp://|udp://)')
    re_label = re.compile(r'\$([^$]+)$')

    for i in range(len(lines)):
        line = lines[i].strip()
        
        # 1. 处理 M3U 头部
        if line.startswith("#EXTM3U"):
            match = re.search(r'x-tvg-url="([^"]+)"', line)
            if match:
                tvg_url = match.group(1)
            continue
            
        # 2. 处理频道信息行
        if re_extinf.match(line):
            tvg_id_match = re_tvg_id.search(line)
            tvg_name_match = re_tvg_name.search(line)
            logo_match = re_logo.search(line)
            group_match = re_group.search(line)
            
            # 提取逗号后的原始名称
            raw_name_match = re.search(r',([^,]+)', line)
            raw_name = raw_name_match.group(1).strip() if raw_name_match else "Unknown"
            
            # 提取标签值
            tvg_name_val = tvg_name_match.group(1) if tvg_name_match else ""
            tvg_id_val = tvg_id_match.group(1) if tvg_id_match else ""
            
            # 【核心逻辑】智能提取频道名称
            if raw_name.lower() == "noepg":
                # 如果名称是 noepg，优先使用 tvg-name 或 tvg-id
                name = tvg_name_val if tvg_name_val else tvg_id_val
                name = name if name else "noepg"
            else:
                name = raw_name
            
            # 处理分组
            group_title = group_match.group(1) if group_match else ""
            if group_title and group_title not in groups:
                groups.append(group_title)
            current_group = group_title
            
        # 3. 处理链接行（在这里进行特征词匹配和重命名！）
        elif re_url.match(line):
            # 清理 URL (去掉 $ 后面的线路标签)
            clean_url = re_label.sub('', line).strip()
            
            # 【核心新增】根据 URL 里的关键词，强制覆盖频道名称
            # 只要链接里包含我们设定的关键词，就直接改名，彻底解决 noepg 问题
            for keyword, true_name in URL_KEYWORD_MAP.items():
                if keyword.lower() in clean_url.lower():
                    name = true_name
                    break # 匹配到第一个关键词就停止
            
            # 构建 M3U8 标准行
            extinf_parts = ['#EXTINF:-1']
            if tvg_id_match:
                extinf_parts.append(f'tvg-id="{tvg_id_match.group(1)}"')
            if tvg_name_match:
                extinf_parts.append(f'tvg-name="{tvg_name_match.group(1)}"')
            if logo_match:
                extinf_parts.append(f'tvg-logo="{logo_match.group(1)}"')
            if current_group:
                extinf_parts.append(f'group-title="{current_group}"')
            
            extinf_line = ' '.join(extinf_parts) + f',{name}'
            
            channels.append({'extinf': extinf_line, 'url': clean_url})
    
    return {"tvgUrl": tvg_url, "channels": channels, "groups": groups}

def fetch_and_save_m3u8(source_url, output_file="output.m3u8"):
    """主函数：获取数据并生成带 EPG 的 M3U8 文件"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'Accept': '*/*'
        }
        
        print(f"正在获取数据: {source_url} ...")
        response = requests.get(source_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        result = parse_m3u_to_m3u8(response.content)
        
        # 强制写入国内稳定的 EPG 节目单地址
        final_tvg_url = result["tvgUrl"] if result["tvgUrl"] else "http://epg.51zmt.top:8000/e.xml.gz"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f'#EXTM3U x-tvg-url="{final_tvg_url}"\n\n')
            for channel in result['channels']:
                f.write(channel['extinf'] + '\n')
                f.write(channel['url'] + '\n')
        
        print(f"✅ 成功! 已生成带 EPG 的 M3U8 文件: {output_file}")
        print(f"📊 共处理频道: {len(result['channels'])} 个")
        print(f"💡 已根据链接特征自动重命名了部分 noepg 频道。")

    except Exception as e:
        print(f"❌ 错误: {e}")

# --- 运行 ---
if __name__ == "__main__":
    # 请替换为你的实际 M3U 地址
    LIVE_SOURCE_URL = "http://119.164.222.242:5140/playlist.m3u" 
    fetch_and_save_m3u8(LIVE_SOURCE_URL)