#!/usr/bin/env python3
"""
雪球舆情监控 - V3 最终版
基于 GitHub 开源方案优化
"""

import requests
import json
import re
import time
import os
from datetime import datetime
from typing import List, Dict, Optional

# ============ 配置 ============
SYMBOLS = [
    ("SH600118", "中国卫星"),
    ("SZ002155", "湖南黄金"),
    ("SZ300456", "赛微电子"),
    ("SH600879", "航天电子"),
    ("SZ002565", "顺灏股份"),
]

OUTPUT_DIR = "/Users/joinylee/Openclaw/xueqiu_sentiment/reports"
MAX_PAGES = 3  # 每只股票最大页数
COOKIES = {
    "xq_a_token": "601797f192b2540dd1885fc7d1cddc7b48374a0b",
    "u": "2274226566",
}

# ============ 情绪分析 ============
def analyze_sentiment(text: str) -> str:
    """简单情绪分析"""
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '拉升', '反弹']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '汪汪', '割了', '打压']
    
    text = text.lower()
    bull = sum(1 for w in bullish if w in text)
    bear = sum(1 for w in bearish if w in text)
    
    if bull > bear:
        return "🟢 利多"
    elif bear > bull:
        return "🔴 利空"
    return "⚪ 中性"

# ============ 核心抓取函数 ============
def fetch_posts(symbol: str, page: int = 1) -> List[Dict]:
    """
    抓取雪球讨论
    API: https://xueqiu.com/statuses/search.json
    """
    timestamp = int(time.time() * 1000)
    
    url = f"https://xueqiu.com/statuses/search.json"
    params = {
        "count": 20,
        "comment": 0,
        "symbol": symbol,
        "hl": 0,
        "source": "user",
        "sort": "time",
        "page": page,
        "_": timestamp,
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://xueqiu.com/S/{symbol}",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    try:
        session = requests.Session()
        
        # 先访问主页获取 cookie
        session.get("https://xueqiu.com/", headers=headers, timeout=10)
        
        # 设置已知 cookie
        for key, value in COOKIES.items():
            session.cookies.set(key, value)
        
        # 请求 API
        resp = session.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                return data.get("list", [])
            except json.JSONDecodeError:
                print(f"   ⚠️ JSON解析失败")
                return []
        elif resp.status_code == 403:
            print(f"   ⚠️ 403 需要验证")
            return []
        else:
            print(f"   ⚠️ HTTP {resp.status_code}")
            return []
            
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        return []

def fetch_stock_discussions(symbol: str, name: str) -> List[Dict]:
    """抓取单只股票24小时内的讨论"""
    print(f"\n📡 {name} ({symbol})")
    print("-" * 60)
    
    now_ts = datetime.now().timestamp() * 1000
    one_day_ms = 24 * 60 * 60 * 1000
    
    all_posts = []
    
    for page in range(1, MAX_PAGES + 1):
        print(f"   抓取第 {page} 页...", end=" ")
        
        posts = fetch_posts(symbol, page)
        if not posts:
            print("无数据")
            break
        
        valid_count = 0
        stop_fetch = False
        
        for post in posts:
            ts = post.get("created_at", 0)
            
            # 检查24小时
            if now_ts - ts > one_day_ms:
                stop_fetch = True
                break
            
            # 清洗文本
            text = re.sub(r'<[^>]+>', '', post.get("text", ""))
            text = text.replace("&nbsp;", " ").replace("&quot;", '"').strip()
            
            if len(text) < 5:
                continue
            
            all_posts.append({
                "text": text,
                "author": post.get("user", {}).get("screen_name", "匿名"),
                "time": datetime.fromtimestamp(ts/1000).strftime("%m-%d %H:%M"),
                "sentiment": analyze_sentiment(text),
                "likes": post.get("like_count", 0),
                "comments": post.get("reply_count", 0),
            })
            valid_count += 1
        
        print(f"{valid_count} 条")
        
        if stop_fetch:
            print(f"   ⏰ 超出24小时，停止")
            break
        
        time.sleep(1)  # 限速
    
    print(f"   ✅ 总计: {len(all_posts)} 条")
    return all_posts

# ============ 生成报告 ============
def generate_markdown(all_data: Dict) -> str:
    """生成 Markdown 报告"""
    now = datetime.now()
    report = f"""# 📊 雪球舆情监控报告

**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}
**监控股票**: {len(SYMBOLS)} 只

---

"""
    
    for symbol, name in SYMBOLS:
        posts = all_data.get(symbol, [])
        
        # 统计
        bull = len([p for p in posts if "利多" in p["sentiment"]])
        bear = len([p for p in posts if "利空" in p["sentiment"]])
        
        report += f"""## 📈 {name} ({symbol})

**统计**: 共 {len(posts)} 条 | 🟢 {bull} | 🔴 {bear}

"""
        
        if posts:
            report += "### 最新讨论\n\n"
            for i, p in enumerate(posts[:5], 1):
                report += f"{i}. {p['sentiment']} **{p['time']}** | {p['author']}\n"
                report += f"   > {p['text'][:80]}{'...' if len(p['text']) > 80 else ''}\n\n"
        else:
            report += "*暂无数据*\n\n"
        
        report += "---\n\n"
    
    return report

def save_results(all_data: Dict, report: str):
    """保存结果"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # JSON
    json_file = os.path.join(OUTPUT_DIR, f'xueqiu_{timestamp}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({"time": datetime.now().isoformat(), "data": all_data}, f, ensure_ascii=False, indent=2)
    
    # Markdown
    md_file = os.path.join(OUTPUT_DIR, f'report_{timestamp}.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n💾 已保存:")
    print(f"   JSON: {json_file}")
    print(f"   报告: {md_file}")

# ============ 主程序 ============
def main():
    print("=" * 60)
    print("🐧 雪球舆情监控 - V3 最终版")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_data = {}
    
    for symbol, name in SYMBOLS:
        posts = fetch_stock_discussions(symbol, name)
        all_data[symbol] = posts
    
    # 生成报告
    print("\n" + "=" * 60)
    print("📊 生成报告...")
    print("=" * 60)
    
    report = generate_markdown(all_data)
    save_results(all_data, report)
    
    # 打印摘要
    print("\n📈 监控摘要:")
    print("-" * 60)
    for symbol, name in SYMBOLS:
        posts = all_data.get(symbol, [])
        bull = len([p for p in posts if "利多" in p["sentiment"]])
        bear = len([p for p in posts if "利空" in p["sentiment"]])
        print(f"   {name}: {len(posts)}条 (🟢{bull} 🔴{bear})")
    
    print("\n" + "=" * 60)
    print("✅ 监控完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
