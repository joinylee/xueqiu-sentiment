#!/usr/bin/env python3
"""
Telegram推送模块
"""

import requests
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """
    发送消息到Telegram
    
    Args:
        text: 消息内容
        parse_mode: 解析模式 (Markdown/HTML)
    
    Returns:
        bool: 是否发送成功
    """
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Telegram配置未设置")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        
        result = resp.json()
        if result.get("ok"):
            print("✅ Telegram发送成功")
            return True
        else:
            print(f"❌ Telegram发送失败: {result.get('description')}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram异常: {e}")
        return False

def build_top10_message(top10_data: list, title: str = "📡 A股舆情雷达 · 今日Top10") -> str:
    """
    构建Top10推送消息
    """
    if not top10_data:
        return f"{title}\n\n暂无舆情信号"
    
    lines = [f"*{title}*", ""]
    
    for item in top10_data:
        emoji = {
            "机会型": "🟢",
            "风险型": "🔴", 
            "验证型": "🟡",
            "关注型": "🟠",
        }.get(item.get("type", "普通"), "⚪")
        
        lines.append(f"{emoji} *{item['symbol']}* | {item['type']}")
        lines.append(f"   {item['reason']}")
        lines.append("")  # 空行分隔
    
    lines.append("—")
    lines.append("*只关注异常，不构成投资建议*")
    
    return "\n".join(lines)

def build_signal_message(signals: list, title: str = "🚨 舆情信号") -> str:
    """
    构建信号推送消息
    """
    if not signals:
        return f"{title}\n\n暂无信号"
    
    lines = [f"*{title}*", ""]
    
    for signal in signals:
        emoji = {
            "机会型": "🟢",
            "风险型": "🔴",
            "验证型": "🟡",
        }.get(signal.get("type", ""), "⚪")
        
        lines.append(f"{emoji} *{signal['symbol']}* | {signal['signal']}")
        lines.append(f"   {signal['reason']}")
        lines.append("")
    
    lines.append("—")
    lines.append("*只关注异常，不构成投资建议*")
    
    return "\n".join(lines)

def send_top10(top10_file: str = "/tmp/xueqiu_top10.json") -> bool:
    """
    发送Top10到Telegram
    """
    if not os.path.exists(top10_file):
        print("⚠️ Top10文件不存在")
        return False
    
    with open(top10_file, "r", encoding="utf-8") as f:
        top10 = json.load(f)
    
    from datetime import datetime
    title = f"📡 A股舆情雷达 · {datetime.now().strftime('%m/%d')}"
    
    message = build_top10_message(top10, title)
    return send_message(message)

def send_signals(signals_file: str = "/tmp/xueqiu_signals.json") -> bool:
    """
    发送信号到Telegram
    """
    if not os.path.exists(signals_file):
        print("⚠️ 信号文件不存在")
        return False
    
    with open(signals_file, "r", encoding="utf-8") as f:
        signals = json.load(f)
    
    message = build_signal_message(signals)
    return send_message(message)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram推送工具")
    parser.add_argument("--top10", action="store_true", help="发送Top10")
    parser.add_argument("--signals", action="store_true", help="发送信号")
    args = parser.parse_args()
    
    if args.top10:
        send_top10()
    elif args.signals:
        send_signals()
    else:
        print("用法: python send_telegram.py --top10 | --signals")
