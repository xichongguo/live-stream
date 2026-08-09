import urllib.request
import urllib.error

SOURCE_URL = "http://www.52top.com.cn:678/downloads/migu.txt"
OUTPUT_FILE = "migu.m3u"

def main():
    print(f"正在获取: {SOURCE_URL}")
    try:
        req = urllib.request.Request(
            SOURCE_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        
        # 直接写入文件，因为源文件已经是正确的 M3U 格式
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(content)
            
        # 统计频道数量（计算 #EXTINF 行数）
        channel_count = content.count("#EXTINF")
        
        print(f"✅ 已生成 M3U 文件: {OUTPUT_FILE}")
        print(f"共写入 {channel_count} 个频道")
        
    except urllib.error.URLError as e:
        print(f"❌ 请求失败: {e}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")

if __name__ == "__main__":
    main()
