#!/bin/bash
# 雪球舆情监控 - 定时任务脚本
# 每天抓取7页，生成报告

cd /Users/joinylee/Openclaw/xueqiu_sentiment

echo "===================================="
echo "🐧 雪球舆情监控 - 定时任务"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "===================================="

# 运行监控脚本
python3 xueqiu_v9_production.py > /tmp/xueqiu_cron.log 2>&1

# 检查结果
if [ $? -eq 0 ]; then
    echo "✅ 抓取成功"
    
    # 获取最新生成的报告
    LATEST_REPORT=$(ls -t reports/report_*.md | head -1)
    LATEST_JSON=$(ls -t reports/xueqiu_*.json | head -1)
    
    echo "📄 报告: $LATEST_REPORT"
    echo "📊 JSON: $LATEST_JSON"
    
    # 发送 Telegram 通知（可选）
    # 如果需要发送到 Telegram，可以在这里添加命令
else
    echo "❌ 抓取失败，查看日志: /tmp/xueqiu_cron.log"
fi

echo "===================================="
echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "===================================="
