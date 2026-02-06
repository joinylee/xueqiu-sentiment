#!/usr/bin/env python3
"""
雪球个股讨论抓取 - 24小时自动翻页版
参考方案：访问首页拿Cookie → 翻页拉取 → 24小时截止
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import config

# 创建带Cookie保持的session
def create_session():
    """创建带重试和Cookie支持的session"""
    session = requests.Session()
    
    # 重试策略
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # 基础headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://xueqiu.com/',
    })
    
    return session


def init_cookie(session: requests.Session) -> bool:
    """
    访问雪球首页获取Cookie（关键步骤！绕过404反爬）
    """
    try:
        print("   🍪 访问首页获取Cookie...")
        resp = session.get('https://xueqiu.com/', timeout=10)
        
        # 检查是否设置了Cookie
        cookies = session.cookies.get_dict()
        if 'xq_a_token' in cookies or 'device_id' in cookies:
            print(f"   ✓ Cookie获取成功: {list(cookies.keys())[:3]}")
            return True
        else:
            print(f"   ⚠️ 可能未获取到完整Cookie，继续尝试...")
            return True  # 继续尝试
    except Exception as e:
        print(f"   ❌ 获取Cookie失败: {e}")
        return False


def fetch_page(session: requests.Session, symbol: str, max_id: Optional[int] = None, count: int = 20) -> Dict:
    """
    抓取单页讨论
    雪球翻页用 max_id（时间游标），不是 page=1,2,3
    """
    url = f'https://xueqiu.com/query/v1/symbol/search/status?symbol={symbol}&count={count}&comment=0'
    if max_id:
        url += f'&max_id={max_id}'
    
    try:
        resp = session.get(url, timeout=15)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                return data
            except json.JSONDecodeError:
                # 返回了HTML，可能是WAF
                if '<html' in resp.text[:100]:
                    print(f"   ⚠️ 被WAF拦截，返回了HTML")
                    return {'list': [], 'waf': True}
                return {'list': []}
        elif resp.status_code == 404:
            print(f"   ⚠️ 404 接口不存在")
            return {'list': []}
        else:
            print(f"   ⚠️ HTTP {resp.status_code}")
            return {'list': []}
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        return {'list': []}


def fetch_discussions_24h(symbol: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    """
    抓取24小时内的讨论（自动翻页）
    
    Args:
        symbol: 股票代码如 SH600118
        max_pages: 最大翻页数（防无限循环）
    
    Returns:
        标准化后的讨论列表
    """
    print(f"\n📡 抓取 {symbol} 的24小时讨论...")
    
    # 创建session并获取cookie
    session = create_session()
    if not init_cookie(session):
        return []
    
    # 手动设置已知的Cookie
    session.cookies.set('xq_a_token', config.COOKIES.get('xq_a_token', ''))
    session.cookies.set('u', config.COOKIES.get('u', ''))
    
    now = datetime.now().timestamp() * 1000  # 毫秒时间戳
    one_day_ms = 24 * 60 * 60 * 1000  # 24小时毫秒
    
    all_posts = []
    max_id = None
    page = 1
    
    while page <= max_pages:
        print(f"   📄 第 {page} 页 (max_id={max_id})...")
        
        data = fetch_page(session, symbol, max_id)
        
        # 检查WAF拦截
        if data.get('waf'):
            print(f"   🚫 被WAF拦截，停止抓取")
            break
        
        posts = data.get('list', [])
        if not posts:
            print(f"   ✓ 无更多数据")
            break
        
        # 处理本页数据
        stop_fetching = False
        for post in posts:
            ts = post.get('created_at', 0)
            
            # 检查是否超过24小时
            if now - ts > one_day_ms:
                print(f"   ⏰ 超过24小时，停止翻页")
                stop_fetching = True
                break
            
            all_posts.append(normalize_post(post, symbol))
        
        if stop_fetching:
            break
        
        # 下一页的max_id（最后一条的id）
        max_id = posts[-1].get('id')
        page += 1
        
        # 限速：1.2秒（防反爬）
        time.sleep(1.2)
    
    print(f"   ✅ 共抓取 {len(all_posts)} 条 (来自 {page} 页)")
    return all_posts


def normalize_post(post: Dict, symbol: str) -> Dict[str, Any]:
    """标准化单条讨论"""
    # 提取纯文本
    html_text = post.get('text', '')
    plain_text = re.sub(r'<[^>]+>', '', html_text)
    plain_text = plain_text.replace('&nbsp;', ' ').strip()
    
    # 用户信息
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
    """格式化时间戳为可读格式"""
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
    bullish = ['涨', '利好', '看好', '买入', '突破', '强势', '新高', '做多', '抄底', '低吸']
    bearish = ['跌', '利空', '看空', '卖出', '破位', '弱势', '新低', '做空', '割肉', '高抛']
    
    text = text.lower()
    bull_count = sum(1 for w in bullish if w in text)
    bear_count = sum(1 for w in bearish if w in text)
    
    if bull_count > bear_count:
        return "利多"
    elif bear_count > bull_count:
        return "利空"
    return "中性"


def batch_fetch(symbols: List[str]) -> Dict[str, List[Dict]]:
    """
    批量抓取多只股票
    
    Returns:
        {symbol: [posts...]}
    """
    results = {}
    
    for symbol in symbols:
        posts = fetch_discussions_24h(symbol)
        results[symbol] = posts
        
        # 股票间也限速
        time.sleep(0.5)
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python fetch_status_v2.py <股票代码>")
        print("示例: python fetch_status_v2.py SH600118")
        print("\n批量抓取: python fetch_status_v2.py SH600118 SZ002155")
        sys.exit(1)
    
    symbols = sys.argv[1:]
    
    print("="*60)
    print("🐧 雪球24小时舆情抓取")
    print("="*60)
    
    all_data = batch_fetch(symbols)
    
    # 保存结果
    output = {
        "fetch_time": datetime.now().isoformat(),
        "symbols": symbols,
        "data": all_data
    }
    
    with open('/tmp/xueqiu_24h_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 已保存到 /tmp/xueqiu_24h_data.json")
    
    # 显示统计
    print("\n📊 抓取统计:")
    for symbol, posts in all_data.items():
        print(f"   {symbol}: {len(posts)} 条")
        if posts:
            # 情绪统计
            emotions = {"利多": 0, "利空": 0, "中性": 0}
            for p in posts:
                emotions[emotion_analysis(p['text'])] += 1
            print(f"      利多:{emotions['利多']} 利空:{emotions['利空']} 中性:{emotions['中性']}")
            # 最新一条
            print(f"      最新: {posts[0]['text'][:40]}...")
