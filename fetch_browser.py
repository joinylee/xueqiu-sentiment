#!/usr/bin/env python3
"""
雪球数据抓取 - 使用OpenClaw浏览器
"""

import subprocess
import json
import re
from datetime import datetime

def fetch_with_browser(symbol, market='SZ'):
    """
    使用浏览器获取雪球数据
    """
    # 股票代码转换
    code = symbol.replace('SH', '').replace('SZ', '')
    
    # 打开URL
    url = f"https://xueqiu.com/query/v1/symbol/search/status?symbol={symbol}&page=1&size=10"
    
    try:
        # 打开页面
        subprocess.run(
            ['openclaw', 'browser', 'open', url],
            capture_output=True, text=True, timeout=30
        )
        
        # 等待加载
        import time
        time.sleep(3)
        
        # 获取快照
        result = subprocess.run(
            ['openclaw', 'browser', 'snapshot'],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode == 0:
            # 快照开头是JSON数据
            snapshot = result.stdout.strip()
            
            # 尝试解析JSON
            if snapshot.startswith('{'):
                try:
                    data = json.loads(snapshot)
                    return data.get('list', [])
                except json.JSONDecodeError:
                    pass
            
            # 尝试从快照中提取JSON
            json_match = re.search(r'\{"[^{}]*"list"', snapshot)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    return data.get('list', [])
                except:
                    pass
    
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    return []

def main():
    symbols = ['SZ300456', 'SH600879', 'SZ300136', 'SZ301005']
    
    print("=" * 60)
    print("🐧 雪球数据抓取测试")
    print("=" * 60)
    
    all_posts = []
    
    for symbol in symbols:
        print(f"\n📡 获取 {symbol}...")
        posts = fetch_with_browser(symbol)
        print(f"   ✓ 获取 {len(posts)} 条")
        all_posts.extend(posts)
    
    print(f"\n✅ 总共 {len(all_posts)} 条数据")
    
    # 保存
    with open("/tmp/xueqiu_status_raw.json", "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)
    
    print("💾 已保存到 /tmp/xueqiu_status_raw.json")

if __name__ == "__main__":
    main()
