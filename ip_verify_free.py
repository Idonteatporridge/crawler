#!/usr/bin/env python3
# quick_check_web.py
import asyncio, aiohttp, time, sys, random

# 使用国内可访问的代理源或备用源，优先选择提供HTTPS代理的源
PROXY_URLS = [
    'https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt',
    'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data.txt',
    'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt',
    'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt',
    'https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt',
    'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
    'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/https.txt',
    'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt'

]
TEST_URL  = 'http://httpbin.org/ip'
TIMEOUT   = aiohttp.ClientTimeout(total=10)  # 增加超时时间以提高成功率
CONCUR    = 50  # 进一步减少并发数，降低被目标网站屏蔽的风险

async def check(p, session):
    try:
        # 先测试HTTP
        t0 = time.perf_counter()
        
        # 测试HTTP
        async with session.get(TEST_URL, proxy=f'http://{p}', timeout=TIMEOUT) as r:
            if r.status == 200:
                # 尝试测试HTTPS，但如果失败也接受HTTP代理
                try:
                    async with session.get(TEST_URL.replace('http://'), proxy=f'http://{p}', timeout=TIMEOUT) as r_https:
                        if r_https.status == 200:
                            return p, int((time.perf_counter() - t0) * 1000), 'https'
                except:
                    pass
                # 如果HTTPS测试失败，仍然返回HTTP代理
                return p, int((time.perf_counter() - t0) * 1000), 'http'
    except Exception as e:
        # 只在调试时打印错误信息
        # print(f"验证 {p} 失败: {type(e).__name__}", file=sys.stderr)
        pass
    return None

async def fetch_proxies():
    """获取代理列表，尝试多个源并合并结果"""
    all_proxies = set()  # 使用集合避免重复
    
    for url in PROXY_URLS:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
                async with s.get(url) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        proxies = [l.strip() for l in text.splitlines() if l.strip() and ':' in l]
                        all_proxies.update(proxies)
                        print(f"从 {url} 获取到 {len(proxies)} 个代理", file=sys.stderr)
        except Exception as e:
            print(f"从 {url} 获取代理失败: {e}", file=sys.stderr)
    
    return list(all_proxies)

async def verify_proxies(proxies):
    """验证代理列表"""
    if not proxies:
        return []
    
    # 随机选择最多10000个代理
    max_proxies = 10000
    if len(proxies) > max_proxies:
        proxies = random.sample(proxies, max_proxies)
        print(f"随机选择 {max_proxies} 个代理进行验证...", file=sys.stderr)
    else:
        print(f"开始验证 {len(proxies)} 个代理...", file=sys.stderr)
    
    # 创建共享的ClientSession以提高效率
    async with aiohttp.ClientSession() as session:
        # 验证
        tasks = [asyncio.create_task(check(p, session)) for p in proxies]
        # 添加总超时控制，增加超时时间
        results = [r for r in await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=120) if r and not isinstance(r, Exception)]
    
    return results

async def main():
    try:
        max_retries = 3
        retry_count = 0
        valid_proxies = []
        
        while retry_count < max_retries and not valid_proxies:
            retry_count += 1
            
            # 拉列表
            proxies = await fetch_proxies()
            if not proxies:
                print(f"第 {retry_count} 次尝试: 无法获取代理列表", file=sys.stderr)
                if retry_count < max_retries:
                    print("等待3秒后重试...", file=sys.stderr)
                    await asyncio.sleep(3)
                continue
            
            print(f"第 {retry_count} 次尝试: 获取到 {len(proxies)} 个代理", file=sys.stderr)
            
            # 验证代理
            valid_proxies = await verify_proxies(proxies)
            
            if not valid_proxies:
                print(f"第 {retry_count} 次尝试: 未找到有效代理", file=sys.stderr)
                if retry_count < max_retries:
                    print("等待3秒后重试...", file=sys.stderr)
                    await asyncio.sleep(3)
        
        if valid_proxies:
            # 按响应时间排序并输出，标记代理类型
            for p, ms, proxy_type in sorted(valid_proxies, key=lambda x: x[1]):
                print(f'{p}  {ms}ms  {proxy_type}')
            print(f'\n有效: {len(valid_proxies)}/{min(len(proxies), 10000)}', file=sys.stderr)
            # 统计HTTPS和HTTP代理数量
            https_count = sum(1 for p in valid_proxies if p[2] == 'https')
            http_count = len(valid_proxies) - https_count
            print(f'其中HTTPS代理: {https_count} 个, HTTP代理: {http_count} 个', file=sys.stderr)
        else:
            print(f"经过 {max_retries} 次尝试，未找到有效代理", file=sys.stderr)
        
    except asyncio.TimeoutError:
        print("代理验证超时", file=sys.stderr)
    except Exception as e:
        print(f"程序错误: {e}", file=sys.stderr)

if __name__ == '__main__':
    asyncio.run(main())