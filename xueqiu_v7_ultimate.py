#!/usr/bin/env python3
"""
雪球舆情监控 - V7 终极版
用正则直接提取关键字段，绕过 JSON 解析
"""

import subprocess
import re
import time
import os
from datetime import datetime

SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"), 
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

def get_sentiment(text):
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪']
    text = text.lower()
    bull = sum(1 for w in bullish if w in text)
    bear = sum(1 for w in bearish if w in text)
    if bull > bear: return "🟢"
    elif bear > bull: return "🔴"
    return "⚪"

def clean_text(text):
    """清洗文本"""
    # 反转义
    text = text.replace('\\n', '\n').replace('\\t', ' ').replace('\\"', '"')
    # 去除 HTML
    text = re.sub(r'<[^>]+>', ' ', text)
    # 去除股票标记
    text = re.sub(r'\$[^$]+\$', '', text)
    # 清理空格
    text = ' '.join(text.split())
    return text.strip()

def extract_posts(raw_text):
    """用正则从原始文本中提取帖子"""
    posts = []
    
    # 模式1: 提取 "text":"内容" 和 "created_at":时间戳
    # 找到 text 字段
    text_matches = list(re.finditer(r'"text":"(.*?)"[,}]', raw_text, re.DOTALL))
    time_matches = list(re.finditer(r'"created_at":(\d+)', raw_text))
    author_matches = list(re.finditer(r'"screen_name":"(.*?)"', raw_text))
    
    print(f"   找到 {len(text_matches)} 个文本, {len(time_matches)} 个时间, {len(author_matches)} 个作者")
    
    for i, tm in enumerate(text_matches[:15]):  # 只取前15条
        try:
            text = tm.group(1)
            text = clean_text(text)
            
            if len(text) < 5 or len(text) > 500:
                continue
            
            # 对应的时间
            ts = int(time_matches[i].group(1)) if i < len(time_matches) else 0
            # 对应的作者
            author = author_matches[i].group(1) if i < len(author_matches) else "匿名"
            author = author.replace('\\"', '"')
            
            posts.append({
                'text': text[:120],
                'author': author[:20],
                'time': datetime.fromtimestamp(ts/1000).strftime('%m-%d %H:%M') if ts else '',
                'sentiment': get_sentiment(text),
            })
        except Exception as e:
            continue
    
    return posts

def fetch_stock(symbol, name):
    """抓取单只股票"""
    print(f"\n📈 {name} ({symbol})")
    
    ts = int(time.time() * 1000)
    url = f"https://xueqiu.com/statuses/search.json?count=20&symbol={symbol}&page=1&_={ts}"
    
    try:
        # 打开
        r1 = subprocess.run(['openclaw', 'browser', 'open', url], 
            capture_output=True, text=True, timeout=30)
        
        m = re.search(r'id:\s*([A-F0-9]+)', r1.stdout)
        if not m: 
            print("   ❌ 无法打开")
            return []
        
        tid = m.group(1)
        time.sleep(2)
        
        # 快照
        r2 = subprocess.run(['openclaw', 'browser', 'snapshot', '--target-id', tid],
            capture_output=True, text=True, timeout=30)
        
        # 关闭
        subprocess.run(['openclaw', 'browser', 'close', '--target-id', tid],
            capture_output=True, timeout=10)
        
        # 提取原始 JSON
        line = r2.stdout.strip()
        
        # 找到 JSON 开始位置 - 格式: "{\"about\":... 或 "{...
        # 在 generic [ref=e2]: 后面
        if 'generic [ref=' not in line:
            print("   ❌ 不是 generic 格式")
            return []
        
        # 找到 : "{ 的位置
        marker = ': "'
        pos = line.find(marker)
        if pos < 0:
            print("   ❌ 找不到数据标记")
            return []
        
        start = pos + 2  # 跳过 : "
        
        # 找结束位置 - 最后一个 "}
        end = line.rfind('"')
        if end <= start:
            print("   ❌ 找不到结束标记")
            return []
        
        if start < 0 or end <= start:
            print("   ❌ 格式错误")
            return []
        
        raw = line[start+1:end+1]  # 去掉外层引号
        
        # 反转义
        raw = raw.replace('\\"', '"').replace('\\\\', '\\')
        
        # 提取帖子
        posts = extract_posts(raw)
        
        bull = len([p for p in posts if p['sentiment'] == '🟢'])
        bear = len([p for p in posts if p['sentiment'] == '🔴'])
        
        print(f"   ✅ {len(posts)} 条 (🟢{bull} 🔴{bear})")
        
        for i, p in enumerate(posts[:3], 1):
            print(f"   {i}. {p['sentiment']} {p['text'][:40]}...")
        
        return posts
        
    except Exception as e:
        print(f"   ❌ 错误: {str(e)[:40]}")
        return []

def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - V7 终极版")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    all_data = {}
    total = 0
    
    for symbol, name in SYMBOLS:
        posts = fetch_stock(symbol, name)
        all_data[symbol] = posts
        total += len(posts)
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print(f"📊 总计: {total} 条")
    print("=" * 60)
    
    for symbol, name in SYMBOLS:
        print(f"   {name}: {len(all_data[symbol])} 条")

if __name__ == "__main__":
    main()
