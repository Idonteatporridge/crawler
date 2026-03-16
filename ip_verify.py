#!/usr/bin/env python3
# 使用付费代理的IP验证脚本
import requests, time, sys

# 用户提供的付费代理信息
TUNNEL = ""
USERNAME = ""
PASSWORD = ""

# 测试URL
TEST_URL = "http://httpbin.org/ip"
HTTPS_TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 10  # 超时时间（秒）


def verify_paid_proxy():
    """验证付费代理是否有效"""
    # 构建代理URL
    proxy_url = f"http://{USERNAME}:{PASSWORD}@{TUNNEL}"
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }
    
    print(f"正在验证付费代理: {TUNNEL}", file=sys.stderr)
    
    try:
        # 测试HTTP
        start_time = time.perf_counter()
        http_response = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT, headers={'Connection': 'close'})
        http_response.raise_for_status()
        
        # 测试HTTPS
        https_response = requests.get(HTTPS_TEST_URL, proxies=proxies, timeout=TIMEOUT, headers={'Connection': 'close'})
        https_response.raise_for_status()
        
        # 计算响应时间
        response_time = int((time.perf_counter() - start_time) * 1000)
        
        # 确定代理类型
        proxy_type = 'https'  # 能通过HTTPS测试，标记为HTTPS代理
        
        print(f"付费代理验证成功: {TUNNEL}  {response_time}ms  {proxy_type}", file=sys.stderr)
        return (TUNNEL, response_time, proxy_type)
        
    except requests.exceptions.RequestException as e:
        print(f"付费代理验证失败: {e}", file=sys.stderr)
        return None


def main():
    """主函数"""
    try:
        valid_proxies = []
        
        # 验证付费代理
        result = verify_paid_proxy()
        if result:
            valid_proxies.append(result)
        
        if valid_proxies:
            # 输出与原有格式兼容的结果
            for proxy_info in valid_proxies:
                print(f'{proxy_info[0]}  {proxy_info[1]}ms')
            
            print(f'\n有效: {len(valid_proxies)}/1', file=sys.stderr)
            print(f'其中HTTPS代理: {sum(1 for p in valid_proxies if p[2] == "https")} 个', file=sys.stderr)
        else:
            print("未找到有效代理", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"程序错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()