#!/usr/bin/env python3
"""
雪球个股讨论抓取 - 浏览器绕过WAF版
使用 openclaw browser 工具绕过反爬
"""

import json
import subprocess
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import config


def fetch_with_browser(symbol: str, max_id: Optional[int] = None, count: int = 20) -> Dict:
    """
    使用 browser 工具抓取数据
    """
    url = f'https://xueqiu.com/query/v1/symbol/search/status?symbol={symbol}&count={count}&comment=0'
    if max_id:
        url += f'&max_id={max_id}'
    
    try:
        # 打开页面
        result = subprocess.run(
            ['openclaw', 'browser', 'open', url],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            print(f"   ⚠️ browser open 失败: {result.stderr}")
            return {'list': []}
        
        # 解析 targetId (格式: "id: xxx")
        import re
        match = re.search(r'id:\s*([A-F0-9]+)', result.stdout)
        if not match:
            print(f"   ⚠️ 无法获取 targetId")
            return {'list': []}
        
        target_id = match.group(1)
        
        # 等待页面加载
        time.sleep(2)
        
        # 获取页面内容
        result = subprocess.run(
            ['openclaw', 'browser', 'snapshot', '--target-id', target_id],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            print(f"   ⚠️ snapshot 失败: {result.stderr}")
            return {'list': []}
        
        # 关闭页面
        subprocess.run(
            ['openclaw', 'browser', 'close', '--target-id', target_id],
            capture_output=True, timeout=10
        )
        
        # 解析JSON数据（从页面内容中提取）
        output = result.stdout
        
        # 尝试从文本区域提取JSON
        textarea_match = re.search(r'<textarea[^>]*>(.*?)</textarea>', output, re.DOTALL)
        if textarea_match:
            content = textarea_match.group(1)
            try:
                data = json.loads(content)
                return data
            except:
                pass
        
        # 尝试直接解析整个输出
        try:
            # 找到JSON开始的位置
            json_start = output.find('{')
            if json_start >= 0:
                # 尝试解析
                data = json.loads(output[json_start:])
                if 'list' in data or 'statuses' in data:
                    return data
        except:
            pass
        
        # 最后尝试：查找页面中的JSON数据
        generic_match = re.search(r'generic \[ref=[^\]]+\]: "({.*?})"', output, re.DOTALL)
        if generic_match:
            try:
                # 需要处理转义
                json_str = generic_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                data = json.loads(json_str)
                return data
            except:
                pass
        
        print(f"   ⚠️ 无法解析响应数据")
        return {'list': []}
        
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return {'list': []}


def fetch_discussions_24h(symbol: str, max_pages: int = 5) -> List[Dict[str, Any]]:
    """
    抓取24小时内的讨论（自动翻页）
    """
    print(f"\n📡 抓取 {symbol} 的24小时讨论...")
    
    now = datetime.now().timestamp() * 1000
    one_day_ms = 24 * 60 * 60 * 1000
    
    all_posts = []
    max_id = None
    page = 1
    
    while page <= max_pages:
        print(f"   📄 第 {page} 页...")
        
        data = fetch_with_browser(symbol, max_id)
        posts = data.get('list', [])
        
        if not posts:
            print(f"   ✓ 无更多数据")
            break
        
        # 处理本页数据
        stop_fetching = False
        valid_count = 0
        for post in posts:
            ts = post.get('created_at', 0)
            
            # 检查是否超过24小时
            if now - ts > one_day_ms:
                print(f"   ⏰ 超过24小时")
                stop_fetching = True
                break
            
            all_posts.append(normalize_post(post, symbol))
            valid_count += 1
        
        print(f"      本页有效: {valid_count}/{len(posts)} 条")
        
        if stop_fetching or valid_count < len(posts):
            break
        
        # 下一页
        max_id = posts[-1].get('id')
        page += 1
        
        # 限速
        time.sleep(1.5)
    
    print(f"   ✅ 共 {len(all_posts)} 条")
    return all_posts


def normalize_post(post: Dict, symbol: str) -> Dict[str, Any]:
    """标准化单条讨论"""
    html_text = post.get('text', '')
    plain_text = re.sub(r'<[^>]+>', '', html_text)
    plain_text = plain_text.replace('&nbsp;', ' ').replace('&quot;', '"').strip()
    
    user = post.get('user', {})
    
    return {
        "id": post.get('id'),
        "symbol": symbol,
        "text": plain_text,
        "author": user.get('screen_name', '匿名'),
        "author_followers": user.get('followers_count', 0),
        "timestamp": post.get('created_at'),
        "time_str": format_timestamp(post.get('created_at')),
        "likes": post.get('like_count', 0),
        "comments": post.get('reply_count', 0),
        "views": post.get('view_count', 0),
        "source": post.get('source', ''),
    }


def format_timestamp(ts: int) -> str:
    """格式化时间戳"""
    if not ts:
        return "未知"
    
    dt = datetime.fromtimestamp(ts / 1000)
    now = datetime.now()
    diff = now - dt
    
    if diff.days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            minutes = diff.seconds // 60
            return f"{minutes}分钟前"
        return f"{hours}小时前"
    elif diff.days == 1:
        return "昨天"
    else:
        return f"{diff.days}天前"


def emotion_analysis(text: str) -> str:
    """简单情绪分析"""
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '低吸', '拉升']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '高抛', '跳水']
    
    text = text.lower()
    bull_count = sum(1 for w in bullish if w in text)
    bear_count = sum(1 for w in bearish if w in text)
    
    if bull_count > bear_count:
        return "利多"
    elif bear_count > bull_count:
        return "利空"
    return "中性"


def batch_fetch(symbols: List[str]) -> Dict[str, List[Dict]]:
    """批量抓取多只股票"""
    results = {}
    
    for symbol in symbols:
        posts = fetch_discussions_24h(symbol)
        results[symbol] = posts
        time.sleep(1)  # 股票间限速
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python fetch_status_browser.py <股票代码>")
        print("示例: python fetch_status_browser.py SH600118")
        sys.exit(1)
    
    symbols = sys.argv[1:]
    
    print("="*60)
    print("🐧 雪球24小时舆情抓取 (浏览器版)")
    print("="*60)
    
    all_data = batch_fetch(symbols)
    
    # 保存
    output = {
        "fetch_time": datetime.now().isoformat(),
        "symbols": symbols,
        "data": all_data
    }
    
    with open('/tmp/xueqiu_24h_browser.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 已保存到 /tmp/xueqiu_24h_browser.json")
    
    # 统计
    print("\n📊 抓取统计:")
    for symbol, posts in all_data.items():
        print(f"\n   {symbol}: {len(posts)} 条")
        if posts:
            emotions = {"利多": 0, "利空": 0, "中性": 0}
            for p in posts:
                emotions[emotion_analysis(p['text'])] += 1
            print(f"      情绪: 利多{emotions['利多']} 利空{emotions['利空']} 中性{emotions['中性']}")
            print(f"      最新: {posts[0]['text'][:50]}...")
