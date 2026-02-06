#!/usr/bin/env python3
"""
数据标准化模块
将不同来源的雪球数据统一成标准格式
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

def clean_text(text: str) -> str:
    """清理文本，移除HTML标签和特殊字符"""
    if not text:
        return ""
    
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 移除雪球特有表情标签
    text = re.sub(r'\[.*?\]', '', text)
    
    return text

def normalize_status(item: Dict, symbol: str) -> Dict:
    """
    标准化个股讨论数据
    
    Args:
        item: 原始数据
        symbol: 股票代码
    
    Returns:
        dict: 标准化后的数据
    """
    user = item.get("user", {})
    
    return {
        "id": str(item.get("id", "")),
        "symbol": symbol,
        "source": "xueqiu",
        "type": "status",
        "author": user.get("screen_name", ""),
        "author_id": user.get("id", ""),
        "text": clean_text(item.get("text", "")),
        "raw_text": item.get("text", ""),  # 保留原始文本用于调试
        "likes": item.get("like_count", 0),
        "comments": item.get("comment_count", 0),
        "reposts": item.get("repost_count", 0),
        "created_at": datetime.fromtimestamp(item.get("created_at", 0) / 1000).isoformat(),
        "timestamp": item.get("created_at", 0) // 1000,  # Unix时间戳
        "url": f"https://xueqiu.com/S/{symbol}/{item.get('id', '')}",
    }

def normalize_livenews(item: Dict) -> Dict:
    """
    标准化快讯数据
    
    Args:
        item: 原始数据
    
    Returns:
        dict: 标准化后的数据
    """
    return {
        "id": str(item.get("id", "")),
        "symbol": None,  # 快讯可能不关联特定股票
        "source": "xueqiu",
        "type": "livenews",
        "author": "雪球快讯",
        "author_id": "system",
        "text": clean_text(item.get("text", "")),
        "raw_text": item.get("text", ""),
        "likes": 0,
        "comments": 0,
        "reposts": 0,
        "created_at": datetime.fromtimestamp(item.get("created_at", 0) / 1000).isoformat(),
        "timestamp": item.get("created_at", 0) // 1000,
        "url": None,
    }

def normalize_all(status_data: List[Dict], livenews_data: List[Dict], symbols: List[str]) -> List[Dict]:
    """
    标准化所有数据
    
    Args:
        status_data: 个股讨论原始数据
        livenews_data: 快讯原始数据
        symbols: 股票代码列表（用于关联symbol）
    
    Returns:
        list: 标准化后的数据列表
    """
    normalized = []
    
    # 处理个股讨论
    for item in status_data:
        # 尝试获取关联的股票代码
        symbol = item.get("symbol", "")
        if not symbol:
            # 从链接中提取
            text = item.get("text", "")
            match = re.search(r'(SH|SZ)\d{6}', text)
            if match:
                symbol = match.group(0)
        
        normalized.append(normalize_status(item, symbol))
    
    # 处理快讯
    for item in livenews_data:
        normalized.append(normalize_livenews(item))
    
    # 按时间排序（最新的在前）
    normalized.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    return normalized

def load_raw_data(prefix: str = "/tmp/xueqiu") -> tuple:
    """
    加载原始数据
    
    Args:
        prefix: 文件前缀
    
    Returns:
        tuple: (status_data, livenews_data)
    """
    import os
    
    status_file = f"{prefix}_status_raw.json"
    livenews_file = f"{prefix}_livenews_raw.json"
    
    status_data = []
    livenews_data = []
    
    if os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
            status_data = json.load(f)
    
    if os.path.exists(livenews_file):
        with open(livenews_file, "r", encoding="utf-8") as f:
            livenews_data = json.load(f)
    
    return status_data, livenews_data

def save_normalized_data(data: List[Dict], filename: str = "/tmp/xueqiu_normalized.jsonl"):
    """
    保存标准化数据（JSONL格式，每行一条）
    
    Args:
        data: 标准化数据
        filename: 输出文件名
    """
    with open(filename, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    print(f"💾 已保存 {len(data)} 条标准化数据到 {filename}")

if __name__ == "__main__":
    from config import SYMBOLS
    
    print("=" * 60)
    print("🔧 数据标准化")
    print("=" * 60)
    
    # 加载原始数据
    status_data, livenews_data = load_raw_data()
    
    print(f"📥 加载原始数据:")
    print(f"  - 个股讨论: {len(status_data)} 条")
    print(f"  - 快讯: {len(livenews_data)} 条")
    
    if not status_data and not livenews_data:
        print("\n⚠️ 没有找到原始数据，请先运行 fetch_status.py 和 fetch_livenews.py")
    else:
        # 标准化
        normalized = normalize_all(status_data, livenews_data, SYMBOLS)
        print(f"\n✅ 标准化完成: {len(normalized)} 条")
        
        # 保存
        save_normalized_data(normalized)
