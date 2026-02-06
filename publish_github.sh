#!/bin/bash
# GitHub 自动发布脚本

cd /Users/joinylee/Openclaw/xueqiu_sentiment

echo "🚀 发布雪球舆情报告到 GitHub..."

# 获取最新报告
LATEST_JSON=$(ls -t reports/xueqiu_*.json | head -1)
LATEST_MD=$(ls -t reports/report_*.md | head -1)

echo "📄 报告文件:"
echo "  - $LATEST_JSON"
echo "  - $LATEST_MD"

# 复制为最新版本
cp "$LATEST_MD" README.md

# Git 操作
git add -A
git commit -m "📊 雪球舆情报告更新: $(date '+%Y-%m-%d %H:%M')"
git push origin main

if [ $? -eq 0 ]; then
    echo "✅ 发布成功!"
    echo "📎 仓库地址: https://github.com/joinylee/xueqiu-sentiment"
else
    echo "❌ 发布失败"
fi
