import asyncio
from playwright.async_api import async_playwright
import csv
import re

async def capture_pdf_urls():
    async with async_playwright() as p:
        # 启动浏览器（设置为True可看到浏览器窗口）
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 设置请求拦截器来捕获PDF下载链接
        pdf_urls = set()
        
        async def handle_request(route):
            request = route.request
            url = request.url
            
            # 检查是否为PDF相关请求
            if 'pdf' in url.lower() or 'downloadpdf' in url.lower() or 'downloadPdf' in url.lower():
                print(f"捕获到PDF下载链接: {url}")
                pdf_urls.add(url)
            
            # 继续请求
            await route.continue_()
        
        # 正确设置请求拦截器
        await page.route("**/*", handle_request)
        
        # 导航到目标页面，不等待网络空闲状态以加快加载速度
        target_url = "https://www.jeom.org/cn/article/2025/9"
        print(f"正在打开页面: {target_url}")
        try:
            await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)  # 只等待DOM加载完成
            print("页面DOM已加载，准备捕获PDF下载链接...")
        except Exception as e:
            print(f"页面加载失败: {e}")
            await browser.close()
            return
        
        print("请立即手动点击PDF下载按钮...")
        print("程序将持续监听20秒以捕获下载链接...")
        
        # 等待20秒供您手动操作
        await asyncio.sleep(20)
        
        # 保存捕获到的URL到CSV文件
        if pdf_urls:
            filename = "captured_pdf_urls.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['PDF Download URLs'])  # 写入表头
                for url in pdf_urls:
                    writer.writerow([url])
            print(f"\n已捕获到 {len(pdf_urls)} 个PDF下载链接，已保存到 {filename}")
            print("捕获到的链接:")
            for url in pdf_urls:
                print(f"  {url}")
        else:
            print("\n未捕获到任何PDF下载链接，请确认是否点击了下载按钮")
        
        # 关闭浏览器
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_pdf_urls())