#!/bin/bash
# 雪球舆情监控 - Shell版本
# 使用方法: ./xueqiu_monitor.sh

SYMBOLS=("SH600118:中国卫星" "SZ002155:湖南黄金" "SZ300456:赛微电子" "SH600879:航天电子" "SZ002565:顺灏股份")
OUTPUT_DIR="/Users/joinylee/Openclaw/xueqiu_sentiment/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$OUTPUT_DIR"

echo "============================================================"
echo "🐧 雪球舆情监控 - Shell版"
echo "⏰ $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# 抓取单只股票
fetch_stock() {
    local symbol=$1
    local name=$2
    
    echo ""
    echo "📈 $name ($symbol)"
    echo "------------------------------------------------------------"
    
    local url="https://xueqiu.com/query/v1/symbol/search/status?symbol=${symbol}&count=10"
    
    # 打开页面获取ID
    local open_result=$(openclaw browser open "$url" 2>&1)
    local target_id=$(echo "$open_result" | grep -o 'id: [A-F0-9]*' | head -1 | cut -d' ' -f2)
    
    if [ -z "$target_id" ]; then
        echo "   ⚠️ 无法获取页面"
        return
    fi
    
    sleep 2
    
    # 获取快照并保存到临时文件
    local tmp_file="/tmp/xueqiu_${symbol}.txt"
    openclaw browser snapshot --target-id "$target_id" > "$tmp_file" 2>&1
    
    # 关闭页面
    openclaw browser close --target-id "$target_id" > /dev/null 2>&1
    
    # 解析JSON并提取前3条讨论
    python3 << EOF
import json
import re

with open("$tmp_file", "r") as f:
    content = f.read()

# 找到JSON部分
if 'generic [ref=' in content:
    # 提取 ": " 后面的JSON字符串
    parts = content.split('": "', 1)
    if len(parts) > 1:
        json_str = parts[1].strip()
        # 去掉末尾的 "
        if json_str.endswith('"'):
            json_str = json_str[:-1]
        
        try:
            data = json.loads(json_str)
            posts = data.get('list', [])
            
            count = 0
            for p in posts[:3]:
                text = p.get('text', '')
                # 去除HTML标签
                text = re.sub(r'<[^>]+>', '', text)
                text = text.replace('&nbsp;', ' ').replace('&quot;', '"')[:60]
                
                # 时间转换
                ts = p.get('created_at', 0)
                from datetime import datetime
                tm = datetime.fromtimestamp(ts/1000).strftime('%H:%M')
                
                author = p.get('user', {}).get('screen_name', '匿名')
                
                print(f"   {count+1}. [{tm}] {author}")
                print(f"      {text}...")
                count += 1
            
            if count == 0:
                print("   暂无数据")
        except Exception as e:
            print(f"   解析失败: {str(e)[:50]}")
    else:
        print("   未找到数据")
else:
    print("   格式错误")
EOF
    
    rm -f "$tmp_file"
}

# 主循环
for item in "${SYMBOLS[@]}"; do
    IFS=':' read -r symbol name <<< "$item"
    fetch_stock "$symbol" "$name"
    sleep 1.5
done

echo ""
echo "============================================================"
echo "✅ 监控完成!"
echo "============================================================"
