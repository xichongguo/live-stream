# get_live_stream.py
"""
功能：从API获取直播流 + 合并白名单 → 生成 M3U8 播放列表
输出文件：live/current.m3u8
"""

import requests
import time
import json
import os
from urllib.parse import urlencode

# ================== 配置区 ==================

# 【1. 动态直播流 API 配置】
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
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# 【2. 白名单列表】
# 格式: [("名称", "M3U8地址")]
WHITELIST = [
    ("央视一套", "https://cctv1.live.com/index.m3u8"),
    ("湖南卫视", "https://hunantv.live.com/index.m3u8"),
    ("浙江卫视", "https://zjtv.live.com/index.m3u8"),
    ("江苏卫视", "https://jsbc.live.com/live.m3u8"),
    ("东方卫视", "https://dragon.tv/live.m3u8"),
    ("测试流", "http://devstreaming.apple.com/videos/streaming/examples/bipbop_4x3/gear1/prog_index.m3u8"),
]

# ================== 核心函数 ==================

def get_dynamic_stream():
    """
    从指定API获取直播流的m3u8地址并返回。
    """
    t = int(time.time())
    print("📡 正在请求直播源 API...")

    try:
        response = requests.get(
            API_URL,
            params=PARAMS,
            headers=HEADERS,
            verify=False,
            timeout=10
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
            print(f"✅ 成功获取动态直播流: {m3u8_url}")
            return m3u8_url
        else:
            print("❌ 错误：在返回的JSON数据中未找到 'data.m3u8Url' 字段。")
            print("完整返回数据：", json.dumps(data, ensure_ascii=False, indent=2))
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ 请求过程中发生错误: {e}")
        return None


def generate_m3u8_content(dynamic_url):
    """
    生成标准 M3U8 播放列表内容
    """
    lines = ["#EXTM3U"]

    if dynamic_url:
        lines.append("#EXTINF:-1,自动获取流")
        lines.append(dynamic_url)

    for name, url in WHITELIST:
        lines.append(f"#EXTINF:-1,白名单-{name}")
        lines.append(url)

    return "\n".join(lines) + "\n"


def main():
    """
    主函数：获取直播流、生成 M3U8、写入文件
    """
    print("🚀 开始生成直播源播放列表...")

        'areaId': '907',# 创建输出目录
        'appCenterId': '907',makedirs('live', exist_ok=True)
        'isTest': '0',print("📁 已确保 live/ 目录存在")

        'deviceVersionType': 'android',# 获取动态流
        'versionCodeGlobal': '5009037'get_dynamic_stream()

    # 生成 M3U8 内容
    headers = {generate_m3u8_content(dynamic_url)

        'Accept': 'application/json, text/plain, */*'# 写入文件
        'Accept-Encoding': 'gzip, deflate, br','live/current.m3u8'
        'Connection': 'keep-alive'try:
    }with open(output_path, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
    尝试:print(f"🎉 成功生成播放列表: {output_path}")
        响应 = requests.get(print(f"📊 总计包含 {len(WHITELIST) + (1 if dynamic_url else 0)} 个直播源")
            api_urlexcept Exception as e:
            params=params,print(f"❌ 写入文件失败: {e}")
            headers=headers,return

            超时=10# 确保 .nojekyll 文件存在（防止 GitHub Pages 构建错误）
        )'.nojekyll'
        response.raise_for_status()if not os.path.exists(nojekyll_path):
        try:
        data = response.json()open(nojekyll_path, 'w').close()
            print(f"✅ 已创建 {nojekyll_path} 文件")
        if 'data' in data and 'm3u8Url' in data['data']:except Exception as e:
            print(f"⚠️ 创建 .nojekyll 文件失败: {e}")

    print("✅ 所有任务完成！")


# ============ 运行程序 ============
if __name__ == "__main__":
    main()
