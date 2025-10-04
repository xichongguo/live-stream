# get_live_stream.py
'""'
功能：从API获取直播流 + 本地&远程白名单 → 生成 M3U8 播放列表
输出文件：live/current.m3u8
'""'

导入 请求
导入 json
导入 os

# ================== 配置区 ==================

# 【1. 动态直播流 API 配置】
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    '设备类型': '1',
    '中心ID': '9',
    '设备令牌': 'beb09666-78c0-4ae8-94e9-b0b4180a31be',
    'latitudeValue'：'0'，
    '区域ID': '907',
    'appCenterId': '907',
    'isTest'：'0'，
    'longitudeValue'：'0'，
    'deviceVersionType'：'android'，
    '版本号全局': '5009037'
}
标题 = {
    'User-Agent': 'okhttp/3.12.12',
    '接受': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    '连接': '保持活动状态',
}

# 【2. 远程白名单配置】
REMOTE_WHITELIST_URL = "https://raw.githubusercontent.com/xichongguo/live-stream/main/whitelist.txt"
WHITELIST_TIMEOUT = 10  # 请求超时时间（秒）

# 【3. 本地白名单】
本地白名单 = [
]

# ================== 工具函数 ==================

定义 is_url_valid(url):
    '""'
    检查 URL 是否可访问（HEAD 请求）
    「」
    尝试:
        head = requests.head(url, timeout=5, allow_redirects=True)
        返回 头.状态码 < 400
    除了 异常 之外 e:
        打印(f"⚠️ 检测URL失败 {url}: {e}")
        返回 假

定义 获取动态流():
    '""'
    从指定API获取直播流的m3u8地址并返回。
    「」
    打印("📡 正在请求直播源 API...")

    尝试:
        response = requests.get(
            API_URL
            params=PARAMS,
            headers=HEADERS,
            超时=10
        )
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            print("❌ 错误：API返回的内容不是有效的JSON格式。")
            print("返回内容预览：", response.text[:200])
            return None

        if 'data' in data and 'm3u8Url' in data['data']:
            m3u8_url = data['data']['m3u8Url']
            if is_url_valid(m3u8_url):
                print(f"✅ 成功获取动态直播流: {m3u8_url}")
                return m3u8_url
            else:
                print(f"❌ 动态流不可访问: {m3u8_url}")
                return None
        else:
            print("❌ 错误：在返回的JSON数据中未找到 'data.m3u8Url' 字段。")
            print("完整返回数据：", json.dumps(data, ensure_ascii=False, indent=2))
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ 请求过程中发生错误: {e}")
        return None

def load_whitelist_from_remote():
    """
    从远程 URL 加载白名单
    :return: [(name, url)] 列表
    """
    print(f"🌐 正在加载远程白名单: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=WHITELIST_TIMEOUT)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        whitelist = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # 跳过空行和注释
            if "," not in line:
                print(f"⚠️ 第 {line_num} 行格式错误（缺少逗号）: {line}")
                continue
            try:
                name, url = line.split(",", 1)
                name, url = name.strip(), url.strip()
                if not name or not url:
                    print(f"⚠️ 第 {line_num} 行名称或URL为空: {line}")
                    continue
                if not url.startswith(("http://", "https://")):
                    print(f"⚠️ 第 {line_num} 行URL无效: {url}")
                    continue
                whitelist.append((f"远程-{name}", url))
            except Exception as e:
                print(f"⚠️ 解析第 {line_num} 行失败: {e}")
        print(f"✅ 成功加载 {len(whitelist)} 个远程直播源")
        return whitelist
    except Exception as e:
        print(f"❌ 加载远程白名单失败: {e}")
        return []

def merge_and_deduplicate(whitelist):
    """
    合并并去重：基于 URL 去重，保留第一个
    """
    seen_urls = set()
    unique_list = []
    for name, url in whitelist:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_list.append((name, url))
        else:
            print(f"🔁 跳过重复地址: {url} ({name})")
    print(f"✅ 去重后保留 {len(unique_list)} 个唯一地址")
    return unique_list

def generate_m3u8_content(dynamic_url, whitelist):
    """
    生成标准 M3U8 播放列表内容
    """
    lines = [
        "#EXTM3U",
        "x-tvg-url=\"https://epg.51zmt.top/xmltv.xml\""
    ]

    # 添加动态流（西充综合）
    if dynamic_url:
        lines.append('#EXTINF:-1 tvg-name="西充综合" group-title="本地频道",西充综合')
        lines.append(dynamic_url)

    for name, url in whitelist:
        # 清理名称（去掉“远程-”“本地-”）
        name_clean = name.split("-", 1)[-1]
        # 自动分类
        group = "其他"
        if "CCTV" in name_clean:
            group = "央视"
        elif "卫视" in name_clean:
            group = "卫视"
        elif "凤凰" in name_clean or "TVB" in name_clean or "港" in name_clean or "台" in name_clean:
            group = "港台"
        elif "西充" in name_clean or "本地" in name_clean or "综合" in name_clean:
            group = "本地频道"

        lines.append(f'#EXTINF:-1 tvg-name="{name_clean}" group-title="{group}",{name_clean}')
        lines.append(url)

    return "\n".join(lines) + "\n"

def main():
    """
    主函数：获取直播流、合并白名单、生成 M3U8、写入文件
    """
    print("🚀 开始生成直播源播放列表...")

    # 创建输出目录
    os.makedirs('live', exist_ok=True)
    print("📁 已确保 live/ 目录存在")

    # 获取动态流
    dynamic_url = get_dynamic_stream()

    # 构建完整白名单列表
    full_whitelist = []

    # 1. 添加本地白名单
    print(f"💾 添加 {len(LOCAL_WHITELIST)} 个本地直播源")
    full_whitelist.extend(LOCAL_WHITELIST)

    # 2. 添加远程白名单
    remote_list = load_whitelist_from_remote()
    full_whitelist.extend(remote_list)

    # 3. 去重
    unique_whitelist = merge_and_deduplicate(full_whitelist)

    # 4. 生成 M3U8 内容
    m3u8_content = generate_m3u8_content(dynamic_url, unique_whitelist)

    # 5. 写入文件
    output_path = 'live/current.m3u8'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        print(f"🎉 成功生成播放列表: {output_path}")
        print(f"📊 总计包含 {len(unique_whitelist) + (1 if dynamic_url else 0)} 个直播源")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")
        return

    # 6. 确保 .nojekyll 文件存在
    nojekyll_path = '.nojekyll'
    if not os.path.exists(nojekyll_path):
        try:
            open(nojekyll_path, 'w').close()
            print(f"✅ 已创建 {nojekyll_path} 文件")
        except Exception as e:
            print(f"⚠️ 创建 .nojekyll 文件失败: {e}")

    print("✅ 所有任务完成！")


# ============ 运行程序 ============
if __name__ == "__main__":
    main()


