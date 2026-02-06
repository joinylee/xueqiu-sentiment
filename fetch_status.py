#!/usr/bin/env python3
"""
雪球个股讨论抓取 - API方式
策略：
1. 优先使用 stock.xueqiu.com / statuses/search.json 接口
2. 自动处理 Cookie 和 User-Agent
3. 输出 JSON 原始数据 + 分析结果
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Any
import config

# 备用 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 备用 Cookie 池（示例，实际应从配置文件读取）
COOKIE_POOL = [
    {"xq_a_token": config.COOKIES["xq_a_token"], "u": config.COOKIES["u"]},
]


def fetch_discussions(symbol: str, max_retries: int = 3) -> List[Dict[str, Any]]:
    """
    抓取雪球个股讨论
    策略：
    1. 优先使用 stock.xueqiu.com / statuses/search.json 接口
    2. 自动处理 Cookie 和 User-Agent
    3. 输出 JSON 原始数据 + 分析结果
    """
    # 尝试多个 API 端点
    api_endpoints = [
        f"https://stock.xueqiu.com/v5/statuses/search.json?symbol={symbol}&count=50&source=全部",
        f"https://xueqiu.com/query/v1/symbol/search/status?symbol={symbol}&size=50&source=ALL",
    ]
    
    headers_list = [
        {
            'User-Agent': USER_AGENTS[0],
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://xueqiu.com/',
            'Cookie': f'xq_a_token={config.COOKIES["xq_a_token"]}; u={config.COOKIES["u"]}'
        },
        {
            'User-Agent': USER_AGENTS[2],
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://stock.xueqiu.com/',
            'Cookie': f'xq_a_token={config.COOKIES["xq_a_token"]}; u={config.COOKIES["u"]}'
        },
    ]
    
    for retry_count in range(max_retries):
        for endpoint_idx, url in enumerate(api_endpoints):
            headers = headers_list[endpoint_idx % len(headers_list)]
            
            print(f"   尝试 {retry_count + 1}/{max_retries}: {url[:60]}...")
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    # 检查是否是 JSON 响应
                    content_type = response.headers.get('content-type', '')
                    
                    if 'application/json' in content_type:
                        try:
                            data = response.json()
                            
                            # 保存原始 JSON 数据
                            raw_file = f"/tmp/xueqiu_raw_{symbol}.json"
                            with open(raw_file, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            print(f"   💾 原始JSON已保存: {raw_file}")
                            
                            # 提取讨论列表
                            posts = data.get('list', []) or data.get('statuses', [])
                            
                            if posts:
                                print(f"   ✓ 获取 {len(posts)} 条讨论")
                                return normalize_posts(posts, symbol)
                            else:
                                print(f"   ⚠️ 响应中无讨论数据")
                                continue
                                
                        except requests.exceptions.JSONDecodeError as e:
                            print(f"   ⚠️ JSON解析失败: {e}")
                            continue
                            
                    else:
                        # 返回 HTML，可能是 WAF 拦截
                        print(f"   ⚠️ 收到非JSON响应 ({content_type})，可能是WAF拦截")
                        
                        # 保存原始响应用于分析
                        raw_file = f"/tmp/xueqiu_waf_{symbol}_{endpoint_idx}.html"
                        with open(raw_file, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f"   💾 WAF响应已保存: {raw_file}")
                        continue
                        
                elif response.status_code == 404:
                    print(f"   ⚠️ 404 端点不可用，尝试下一个...")
                    continue
                    
                elif response.status_code == 401:
                    print(f"   ⚠️ 认证失败 (401)，尝试更换Cookie...")
                    # 尝试更换 Cookie
                    if endpoint_idx < len(COOKIE_POOL):
                        headers['Cookie'] = f'xq_a_token={COOKIE_POOL[endpoint_idx]["xq_a_token"]}; u={COOKIE_POOL[endpoint_idx]["u"]}'
                    continue
                    
                else:
                    print(f"   ⚠️ HTTP错误: {response.status_code}")
                    continue
                    
            except Exception as e:
                print(f"   ⚠️ 请求异常: {e}")
                continue
    
    print(f"   ❌ 所有尝试均失败")
    return []


def normalize_posts(posts: List[Dict], symbol: str) -> List[Dict[str, Any]]:
    """
    标准化讨论数据
    提取关键字段用于后续分析
    """
    normalized = []

    for post in posts:
        # 提取纯文本（去除HTML标签）
        html_text = post.get('text', '')
        plain_text = re.sub(r'<[^>]+>', '', html_text)
        plain_text = plain_text.replace('<br/>', '\n').strip()

        # 提取用户信息
        user = post.get('user', {})
        author = user.get('screen_name', '匿名用户')

        # 时间戳转换
        created_at = post.get('created_at', 0)
        time_str = format_time(created_at)

        # 浏览量
        view_count = post.get('view_count', 0)

        normalized.append({
            "id": post.get('id', 0),
            "text": plain_text,
            "author": author,
            "author_followers": user.get('followers_count', 0),
            "time": time_str,
            "timestamp": created_at,
            "views": view_count,
            "likes": post.get('like_count', 0),
            "comments": post.get('reply_count', 0),
            "retweets": post.get('retweet_count', 0),
            "source": post.get('source', ''),
            "symbol": symbol,
        })

    return normalized


def format_time(timestamp: int) -> str:
    """将时间戳转换为可读格式"""
    if not timestamp:
        return "未知时间"

    from datetime import datetime
    dt = datetime.fromtimestamp(timestamp / 1000)
    now = datetime.now()

    # 计算时间差
    diff = now - dt

    if diff.days == 0:
        # 同一天
        return dt.strftime("今天 %H:%M")
    elif diff.days == 1:
        return dt.strftime("昨天 %H:%M")
    elif diff.days < 7:
        return f"{diff.days}天前"
    else:
        return dt.strftime("%m-%d %H:%M")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python fetch_status.py <股票代码>")
        print("示例: python fetch_status.py SZ300456")
        sys.exit(1)

    symbol = sys.argv[1]
    print(f"📡 正在获取 {symbol} 的讨论...")

    posts = fetch_discussions(symbol)

    print(f"\n✅ 总共获取 {len(posts)} 条讨论")

    # 保存
    with open("/tmp/xueqiu_status_raw.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print("💾 已保存到 /tmp/xueqiu_status_raw.json")

    # 显示前几条
    for i, post in enumerate(posts[:3], 1):
        print(f"\n{i}. [{post['author']}] {post['time']}")
        print(f"   {post['text'][:80]}...")
