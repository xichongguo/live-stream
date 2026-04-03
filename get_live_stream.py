name: Update Live Streams

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

on:
  schedule:
    # 每天 UTC 23:00 和 09:00 (北京时间 07:00 和 17:00)
    - cron: '0 23,9 * * *' 
  workflow_dispatch:
  push:
    paths:
      - '.github/workflows/update-stream.yml'
      - 'get_live_stream.py'
      - 'whitelist.txt'

jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: 🔻 Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: ⚙️ Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: 📦 Install Dependencies
        run: pip install requests

      - name: 🐍 Run Generator Script
        run: |
          python get_live_stream.py
          
          # 🔍 调试：检查文件是否真的生成了
          echo "🔍 检查文件系统:"
          find . -type f # 列出所有文件，看是否有 ./live/current.m3u8
          echo "📄 文件内容预览:"
          cat live/current.m3u8 || echo "文件不存在或为空"

      - name: 📂 Ensure .nojekyll
        run: touch .nojekyll

      - name: 📤 Commit & Push Changes
        run: |
          # 检查是否有更改
          if git diff --quiet; then
            echo "ℹ️ 无更改需要提交"
            exit 0
          else
            git config --global user.name "github-actions[bot]"
            git config --global user.email "github-actions[bot]@users.noreply.github.com"
            # 显式添加 live 目录下的文件
            git add live/current.m3u8 .nojekyll
            git commit -m "🔄 自动更新直播源 [$(date +'%Y-%m-%d %H:%M:%S')]" || exit 0
            git push
          fi
