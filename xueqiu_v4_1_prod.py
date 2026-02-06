#!/usr/bin/env python3
"""
雪球舆情监控 - V4.1 生产版
基于 V4 稳定版优化，增强错误处理
"""

import subprocess
import json
import re
import time
import os
from datetime import datetime
from typing import List, Dict

SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"),
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

OUTPUT_DIR = "/Users/joinylee/Openclaw/xueqiu_sentiment/reports"

def get_sentiment(text: str) -> str:
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '拉升']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪', '割了']
    text = text.lower()
    bull = sum(1 for w in bullish if w in text)
    bear = sum(1 for w in bearish if w in text)
    if bull > bear: return "🟢"
    elif bear > bull: return "🔴"
    return "⚪"

def parse_json_robust(json_str: str) -> Dict:
    """健壮的 JSON 解析"""
    # 尝试1: 直接解析
    try:
        return json.loads(json_str)
    except:
        pass
    
    # 尝试2: 去除控制字符
    try:
        cleaned = ''.join(c for c in json_str if ord(c) >= 32 or c in '\n\t\r')
        return json.loads(cleaned)
    except:
        pass
    
    # 尝试3: 修复转义
    try:
        # 替换未转义的引号（在字符串值内部）
        cleaned = json_str.replace('\\"', '\x00')  # 临时替换
        cleaned = cleaned.replace('"', '\\"')  # 转义所有引号
        cleaned = cleaned.replace('\x00', '"')  # 恢复
        return json.loads(cleaned)
    except:
        pass
    
    return {}

def fetch_one(symbol: str) -> List[Dict]:
    """抓取单页"""
    ts = int(time.time() * 1000)
    url = f"https://xueqiu.com/statuses/search.json?count=20&symbol={symbol}&page=1&_={ts}"
    
    try:
        # 打开
        r1 = subprocess.run(['openclaw', 'browser', 'open', url], 
            capture_output=True, text=True, timeout=30)
        
        m = re.search(r'id:\s*([A-F0-9]+)', r1.stdout)
        if not m: return []
        
        tid = m.group(1)
        time.sleep(2)
        
        # 快照
        r2 = subprocess.run(['openclaw', 'browser', 'snapshot', '--target-id', tid],
            capture_output=True, text=True, timeout=30)
        
        # 关闭
        subprocess.run(['openclaw', 'browser', 'close', '--target-id', tid],
            capture_output=True, timeout=10)
        
        # 解析
        line = r2.stdout.strip()
        if ': "' not in line: return []
        
        # 提取 JSON 字符串
        parts = line.split(': "', 1)
        json_str = parts[1]
        if json_str.endswith('"'):
            json_str = json_str[:-1]
        
        # 反转义
        json_str = json_str.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
        
        # 解析
        data = parse_json_robust(json_str)
        return data.get('list', [])
        
    except Exception as e:
        return []

def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - V4.1 生产版")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    all_data = {}
    
    for symbol, name in SYMBOLS:
        print(f"\n📈 {name} ({symbol})")
        
        posts = fetch_one(symbol)
        
        # 清洗数据
        cleaned = []
        for p in posts[:10]:  # 只取前10条
            text = re.sub(r'<[^>]+>', '', p.get('text', ''))
            text = text.replace('&nbsp;', ' ').replace('&quot;', '"').strip()
            if len(text) >= 5:
                ts = p.get('created_at', 0)
                cleaned.append({
                    'text': text[:100],
                    'author': p.get('user', {}).get('screen_name', '匿名'),
                    'time': datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M') if ts else '',
                    'sentiment': get_sentiment(text),
                })
        
        all_data[symbol] = cleaned
        bull = len([p for p in cleaned if p['sentiment'] == '🟢'])
        bear = len([p for p in cleaned if p['sentiment'] == '🔴'])
        
        print(f"   ✅ {len(cleaned)} 条 (🟢{bull} 🔴{bear})")
        
        if cleaned:
            for i, p in enumerate(cleaned[:2], 1):
                print(f"   {i}. {p['sentiment']} {p['text'][:40]}...")
        
        time.sleep(1)
    
    # 保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(f'{OUTPUT_DIR}/xueqiu_{ts}.json', 'w', encoding='utf-8') as f:
        json.dump({'time': datetime.now().isoformat(), 'data': all_data}, f, ensure_ascii=False, indent=2)
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 汇总")
    total = sum(len(v) for v in all_data.values())
    print(f"   总计: {total} 条")
    for symbol, name in SYMBOLS:
        print(f"   {name}: {len(all_data[symbol])} 条")
    print("=" * 60)

if __name__ == "__main__":
    main()
