# get_live_stream.py
"""
功能: 全自动直播源管理
- 获取动态流 + 本地/远程白名单
- 检测有效性 + 分组 + 图标
- 生成 M3U8 + HTML 播放器页面
输出:
  live/current.m3u8
  live/index.html
"""

导入 请求
导入 时间
导入 json
导入 os
从 urllib.parse 导入 urlencode, urlparse

# ================== 配置区 ==================

# 【1. 动态直播流 API】
API_URL = "https://lwydapi.xichongtv.cn/a/appLive/info/35137_b14710553f9b43349f46d33cc2b7fcfd"
PARAMS = {
    '设备类型': '1',
    'centerId'：'9'，
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

}

# 【2. 白名单配置】
"https://cdn.jsdelivr.net/gh/Guovin/iptv-api@gd/output/result.txt"
LOCAL_WHITELIST = [


输入：]

# 【3. 检测配置】
CHECK_TIMEOUT = 5      # 检测流是否有效的超时时间
CHECK_RETRIES = 1      # 重试次数


# 【4. 图标默认图】
"https://via.placeholder.com/16"

# ================== 核心函数 ==================


获取动态直播流

    try:
        response = requests.get(API_URL, params=PARAMS, headers=HEADERS, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()




        else:
            print("❌ API 返回缺少 m3u8Url")
    except Exception as e:
        print(f"❌ 动态流请求失败: {e}")
    return None

def load_remote_whitelist():
    """加载远程白名单（支持分组和图标）"""
    print(f"🌐 加载远程白名单: {REMOTE_WHITELIST_URL}")
    try:
        response = requests.get(REMOTE_WHITELIST_URL, timeout=10)
        response.raise_for_status()
        lines = response.text.strip().splitlines()
        result = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            # 格式: 名称,URL,分组,图标（后两个可选）
            if len(parts) < 2:
                continue
            name, url = parts[0], parts[1]
            group = parts[2] if len(parts) > 2 else "其他"
            logo = parts[3] if len(parts) > 3 else DEFAULT_LOGO
            if url.startswith(("http://", "https://")):
                result.append((f"远程-{name}", url, group, logo))
        print(f"✅ 加载 {len(result)} 个远程源")
        return result
    except Exception as e:
        print(f"❌ 远程白名单加载失败: {e}")
        return []

def is_stream_valid(url):
    """检测 m3u8 是否有效"""
    for _ in range(CHECK_RETRIES + 1):
        try:
            method = 'HEAD' if VALIDATION_METHOD == "HEAD" else 'GET'
            resp = requests.request(method, url, timeout=CHECK_TIMEOUT, 
                                  headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code < 400:
                return True
        except:
            pass
        time.sleep(0.5)
    return False

def validate_streams(stream_list):
    """批量检测流有效性"""
    print("🔍 正在检测直播流有效性...")
    valid_streams = []
    for name, url, group, logo in stream_list:
        if is_stream_valid(url):
            valid_streams.append((name, url, group, logo))
            print(f"✅ 有效: {name}")
        else:
            print(f"❌ 无效: {name}")
    return valid_streams

def generate_m3u8_content(streams):
    """生成 M3U8 播放列表"""
    lines = ["#EXTM3U"]
    current_group = None

    for name, url, group, logo in streams:
        if group != current_group:
            lines.append(f"#EXTGRP:{group}")
            current_group = group
        lines.append(f"#EXTINF:-1,{name}")
        lines.append(url)
        if logo:
            lines.append(f"#EXTVLCOPT:logo={logo}")
    return "\n".join(lines) + "\n"

def generate_html_page(streams):
    """生成可视化 index.html 页面"""
    html = """<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📺 直播源播放器</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }
        h1 { color: #333; text-align: center; }
        .player { width: 100%; height: 60vh; background: #000; margin: 20px 0; }
        video { width: 100%; height: 100%; object-fit: contain; }
        .list { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
        .item { padding: 10px; background: white; border-radius: 5px; cursor: pointer; }
        .item:hover { background: #f0f0f0; }
        .logo { width: 16px; height: 16px; vertical-align: middle; margin-right: 5px; }
    </style>
</head>
<body>
    <h1>📺 直播源播放器</h1>
    <div class="player">
        <video id="video" controls autoplay></video>
    </div>
    <div class="list">
"""
    for name, url, group, logo in streams:
        logo_img = f'<img class="logo" src="{logo}" onerror="this.src=\'{DEFAULT_LOGO}\';">' if logo else ""
        html += f'        <div class="item" onclick="play(\'{url}\', \'{name}\')">{logo_img}{name}</div>\n'

    html += """    </div>

    <script>
        const video = document.getElementById('video');
        function play(url, name) {
            if (Hls.isSupported()) {
                const hls = new Hls();
                hls.loadSource(url);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, () => {
                    video.play();
                    document.title = "📺 " + name;
                });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = url;
                video.addEventListener('loadedmetadata', () => {
                    video.play();
                    document.title = "📺 " + name;
                });
            }
        }
    </script>
</body>
</html>"""
    return html

def main():
    print("🚀 开始生成直播源系统...")

    # 创建目录
    os.makedirs('live', exist_ok=True)
    print("📁 已创建 live/ 目录")

    # 收集所有流
    all_streams = []

    # 1. 添加动态流
    dynamic = get_dynamic_stream()
    if dynamic:
        all_streams.append(dynamic)

    # 2. 添加本地白名单
    print(f"💾 添加 {len(LOCAL_WHITELIST)} 个本地源")
    all_streams.extend(LOCAL_WHITELIST)

    # 3. 添加远程白名单
    remote_list = load_remote_whitelist()
    all_streams.extend(remote_list)

    # 4. 去重（基于 URL）
    seen = set()
    unique_streams = []
    for item in all_streams:
        if item[1] not in seen:
            seen.add(item[1])
            unique_streams.append(item)

    print(f"📊 去重后共 {len(unique_streams)} 个源")

    # 5. 检测有效性
    valid_streams = validate_streams(unique_streams)

    if not valid_streams:
        print("❌ 所有流均无效，停止生成")
        return

    # 6. 生成 M3U8
    m3u8_content = generate_m3u8_content(valid_streams)
    with open('live/current.m3u8', 'w', encoding='utf-8') as f:
        f.write(m3u8_content)
    print("🎉 已生成 live/current.m3u8")

    # 7. 生成 HTML
    html_content = generate_html_page(valid_streams)
    with open('live/index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    print("🎉 已生成 live/index.html")

    # 8. .nojekyll
    if not os.path.exists('.nojekyll'):
        open('.nojekyll', 'w').close()
        print("✅ 已创建 .nojekyll")

    print("✅ 全部任务完成！访问 https://xichongguo.github.io/live-stream/live/index.html")

if __name__ == "__main__":
    main()


