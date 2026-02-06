#!/usr/bin/env python3
"""
快速测试脚本
验证雪球舆情监控系统的基本功能
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config():
    """测试配置加载"""
    print("测试配置...")
    try:
        from config import SYMBOLS, HEADERS, COOKIES
        print(f"  ✓ 加载 {len(SYMBOLS)} 只股票")
        print(f"  ✓ Headers: {len(HEADERS)} 项")
        print(f"  ✓ Cookies: {len(COOKIES)} 项")
        
        # 检查Cookie是否已配置
        if COOKIES.get("xq_a_token") == "YOUR_XQ_A_TOKEN_HERE":
            print("  ⚠️ 请配置真实的Cookie！")
            return False
        
        return True
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return False

def test_imports():
    """测试模块导入"""
    print("\n测试模块导入...")
    modules = [
        ("fetch_status", "个股讨论"),
        ("fetch_livenews", "快讯"),
        ("normalize", "标准化"),
        ("analyze", "分析"),
        ("signals", "信号"),
        ("top10", "Top10"),
        ("send_telegram", "推送"),
    ]
    
    all_ok = True
    for name, desc in modules:
        try:
            __import__(name)
            print(f"  ✓ {desc}")
        except Exception as e:
            print(f"  ✗ {desc}: {e}")
            all_ok = False
    
    return all_ok

def test_openai():
    """测试OpenAI客户端"""
    print("\n测试OpenAI连接...")
    try:
        from openai import OpenAI
        client = OpenAI()
        # 简单测试
        print("  ✓ OpenAI客户端初始化成功")
        return True
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return False

def test_network():
    """测试网络连接"""
    print("\n测试网络...")
    try:
        import requests
        r = requests.get("https://xueqiu.com", timeout=10, allow_redirects=False)
        print(f"  ✓ 雪球可访问 (状态码: {r.status_code})")
        return True
    except Exception as e:
        print(f"  ✗ 网络失败: {e}")
        return False

def main():
    print("=" * 60)
    print("🐧 雪球舆情监控系统 - 快速测试")
    print("=" * 60)
    
    results = []
    
    results.append(("配置加载", test_config()))
    results.append(("模块导入", test_imports()))
    results.append(("OpenAI连接", test_openai()))
    results.append(("网络连接", test_network()))
    
    print("\n" + "=" * 60)
    print("📊 测试结果")
    print("=" * 60)
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n✅ 系统就绪！运行: python run.py --all")
    else:
        print("\n⚠️ 有测试未通过，请检查配置")

if __name__ == "__main__":
    main()
