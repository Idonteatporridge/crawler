import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os
import uuid

# 爬虫配置
BASE_URL = "http://zhxhwkzz.xml-journal.net/"
ARCHIVE_URL = "http://zhxhwkzz.xml-journal.net/archive_list"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "author", "year", "issue", "volume", "pdf_url"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_soup(url):
    """获取指定URL的BeautifulSoup对象"""
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"获取页面失败 {url}: {e}")
        return None

def get_all_volumn_links():
    """从页面中提取所有期号链接"""
    # 使用Selenium加载页面，捕获动态生成的期号链接
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
    import time

    print("使用Selenium加载页面...")
    # 设置Chrome选项
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 无头模式，不显示浏览器窗口
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    # 初始化WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # 加载页面
        driver.get(ARCHIVE_URL)
        time.sleep(5)  # 等待页面完全加载
        
        # 打印页面标题
        print(f"Selenium加载的页面标题: {driver.title}")
        
        # 获取页面的完整HTML
        html = driver.page_source
        
        # 查找HTML中包含"/cn/article/"的链接
        print("\n查找期号链接:")
        import re
        # 使用正则表达式匹配期号链接，格式为/cn/article/年份/期号
        article_links = re.findall(r'href="(/cn/article/\d{4}/\d+)"', html)
        
        # 去重并排序
        unique_links = sorted(set(article_links))
        
        # 构建完整的URL
        full_links = []
        for link in unique_links:
            full_url = urljoin(BASE_URL, link)
            full_links.append(full_url)
            print(f"  期号链接: {full_url}")
        
        # 打印调试信息
        print(f"\n共找到 {len(full_links)} 个期号链接")
        print("article/ 出现次数：", html.count("/article/"))
        
        return full_links
            
    finally:
        # 关闭WebDriver
        driver.quit()
    
    # 然后尝试使用常规方法
    soup = get_soup(ARCHIVE_URL)
    if not soup:
        return []

    links = []
    html = soup.prettify()
    
    # 去重并排序
    links = sorted(set(links))
    
    # 打印调试信息
    print(f"\n共找到 {len(links)} 个期号链接")
    print("article/ 出现次数：", html.count("/article/"))
    
    # 打印前几个链接以便验证
    if links:
        print("前3个期号链接：", links[:3])
    
    return links




def get_soup_with_selenium(url):
    """使用Selenium获取页面的soup对象，支持动态加载内容"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    
    print(f"使用Selenium加载页面: {url}")
    
    # 设置Chrome选项
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式，不显示浏览器窗口
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # 设置User-Agent
    chrome_options.add_argument(f"user-agent={headers['User-Agent']}")
    
    try:
        # 初始化WebDriver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        # 加载页面
        driver.get(url)
        
        # 等待页面加载完成（最多等待10秒）
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # 获取页面HTML
        html = driver.page_source
        
        # 关闭WebDriver
        driver.quit()
        
        # 解析HTML
        soup = BeautifulSoup(html, "html.parser")
        return soup
        
    except Exception as e:
        print(f"使用Selenium加载页面时出错: {e}")
        try:
            driver.quit()
        except:
            pass
        return None


def extract_pdfs_from_volumn(vol_url):
    """从指定期号页面提取所有PDF链接"""
    print(f"\n爬取期号: {vol_url}")
    
    # 先尝试使用常规方法
    soup = get_soup(vol_url)
    
    # 如果常规方法失败，或者没有找到链接，使用Selenium
    if not soup:
        soup = get_soup_with_selenium(vol_url)
    
    if not soup:
        return []
    
    pdfs = []
    # 提取年份和期号信息（从URL中）
    url_match = re.search(r"/article/(\d+)/(\d+)", vol_url)
    
    year = url_match.group(1) if url_match else "未知"
    issue = url_match.group(2) if url_match else "未知"
    volume = "未知"  # 新网站结构中未看到卷号信息
    
    # 添加更多调试信息，查看页面结构
    print("=== 页面结构调试信息 ===")
    
    # 方法1：直接查找所有包含阿里云链接的a标签（重点关注）
    print("方法1：直接查找所有包含阿里云链接的a标签")
    aliyun_links = soup.find_all("a", href=re.compile(r"(https://boyuancaibian\.oss-cn-beijing\.aliyuncs\.com/|https://oss\.boyuanxc\.cn/)"))
    print(f"找到 {len(aliyun_links)} 个阿里云链接")
    
    if aliyun_links:
        for link in aliyun_links[:5]:
            print(f"  - {link.get('href')}")
    
    # 方法2：查找所有包含"pdf"的链接
    print("\n方法2：查找所有包含'pdf'的链接")
    pdf_links = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if href and "pdf" in href.lower() and "javascript:void(0)" not in href:
            pdf_links.append(href)
    
    print(f"找到 {len(pdf_links)} 个包含'pdf'的链接")
    if pdf_links:
        for link in pdf_links[:5]:
            print(f"  - {link}")
    
    # 方法3：查找页面中的所有script标签，寻找可能的PDF链接
    print("\n方法3：查找页面中的script标签，寻找可能的PDF链接")
    script_tags = soup.find_all("script")
    script_pdf_links = []

    for script in script_tags:
        script_content = script.string
        if script_content:
            # 查找可能的PDF链接
            pdf_matches = re.findall(r'https?://[^\s"\']+\.pdf', script_content)
            # 查找可能的阿里云链接
            aliyun_matches = re.findall(r'https?://(boyuancaibian\.oss-cn-beijing\.aliyuncs\.com|oss\.boyuanxc\.cn)/[^\s"\']+', script_content)
            script_pdf_links.extend(pdf_matches)
            script_pdf_links.extend(aliyun_matches)

    script_pdf_links = list(set(script_pdf_links))
    print(f"在script标签中找到 {len(script_pdf_links)} 个可能的PDF链接")
    if script_pdf_links:
        for link in script_pdf_links[:5]:
            print(f"  - {link}")
    
    # 方法4：查找所有class包含"article"的元素
    print("\n方法4：查找所有class包含'article'的元素")
    article_elements = []
    for elem in soup.find_all(True):  # 查找所有元素
        elem_class = elem.get("class", [])
        if any("article" in cls.lower() for cls in elem_class):
            article_elements.append(elem)
    
    print(f"找到 {len(article_elements)} 个包含'article'的元素")
    
    # 如果找到文章元素，查看其内部的链接
    if article_elements:
        print("前3个文章元素中的链接:")
        for elem in article_elements[:3]:
            links = elem.find_all("a")
            for link in links[:3]:
                href = link.get("href", "")
                if href:
                    print(f"  - {href}")
    
    # 合并所有找到的链接，去重
    all_pdf_links = []
    
    # 添加阿里云链接
    for link in aliyun_links:
        href = link.get("href", "")
        if href:
            all_pdf_links.append(href)
    
    # 添加PDF链接
    all_pdf_links.extend(pdf_links)
    
    # 添加script中的PDF链接
    all_pdf_links.extend(script_pdf_links)
    
    # 去重
    all_pdf_links = list(set(all_pdf_links))
    print(f"\n去重后共找到 {len(all_pdf_links)} 个PDF链接")
    
    # 处理每个PDF链接
    for pdf_link in all_pdf_links:
        print(f"找到PDF链接: {pdf_link}")
        
        # 从PDF链接中提取文件名作为article_id
        file_name_match = re.search(r'/([^/]+)\.pdf', pdf_link, re.IGNORECASE)
        if file_name_match:
            article_id = file_name_match.group(1)
        else:
            # 如果无法从URL中提取文件名，使用随机字符串作为article_id
            article_id = str(uuid.uuid4())[:8]
        
        # 查找对应的文章标题（从包含该链接的上下文中）
        title = "无标题"
        
        # 找到包含该PDF链接的a标签
        pdf_a = soup.find("a", href=pdf_link)
        if pdf_a:
            # 向上查找父元素，寻找标题
            parent = pdf_a.find_parent()
            while parent:
                # 查找可能的标题元素
                title_elem = parent.find(["h1", "h2", "h3", "h4", "h5", "h6", "div", "p"])
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    if title_text and len(title_text) > 5:  # 确保标题有一定长度
                        title = title_text
                        break
                
                # 继续向上查找
                parent = parent.find_parent()
        
        # 添加文章信息到列表
        pdfs.append({
            "article_id": article_id,
            "title": title,
            "author": "无作者",  # 新网站结构中未看到作者信息
            "year": year,
            "issue": issue,
            "volume": volume,
            "pdf_url": pdf_link
        })
    
    # 如果没有找到PDF链接，尝试查找文章详情页链接
    if not all_pdf_links:
        print("\n未找到直接的PDF链接，尝试查找文章详情页链接")
        
        # 查找可能的文章链接（通常包含article或content等关键词）
        article_links = []
        for a in soup.find_all("a"):
            href = a.get("href", "")
            # 查找可能的文章详情页链接
            if href and ("/article/" in href or "/content/" in href) and len(href) > 20:
                # 允许article/id/xxx格式的链接
                article_links.append(href)
        
        # 去重
        article_links = list(set(article_links))
        print(f"找到 {len(article_links)} 个可能的文章详情页链接")
        
        if article_links:
            print("前3个文章链接:")
            for link in article_links[:3]:
                print(f"  - {link}")
            
            # 访问每个文章详情页，查找PDF链接
            for article_link in article_links[:5]:  # 先只处理前5个文章，避免请求过多
                # 确保链接是完整的URL
                if not article_link.startswith("http"):
                    article_url = urljoin(vol_url, article_link)
                else:
                    article_url = article_link
                
                print(f"\n访问文章详情页: {article_url}")
                
                # 使用Selenium加载文章详情页
                article_soup = get_soup_with_selenium(article_url)
                if not article_soup:
                    continue
                
                # 在文章详情页中查找PDF链接
                article_pdf_links = []
                
                # 查找阿里云链接（包含两种域名格式）
                article_aliyun_links = article_soup.find_all("a", href=re.compile(r"(https://boyuancaibian\.oss-cn-beijing\.aliyuncs\.com/|https://oss\.boyuanxc\.cn/)"))
                article_pdf_links.extend([a.get("href") for a in article_aliyun_links])
                
                # 查找包含"pdf"的链接，过滤掉无效链接
                for a in article_soup.find_all("a"):
                    href = a.get("href", "")
                    if href and "pdf" in href.lower() and "javascript:void(0)" not in href:
                        article_pdf_links.append(href)
                
                # 查找script标签中的PDF链接
                article_script_tags = article_soup.find_all("script")
                for script in article_script_tags:
                    script_content = script.string
                    if script_content:
                        pdf_matches = re.findall(r'https?://[^\s"\']+\.pdf', script_content)
                        aliyun_matches = re.findall(r'https?://(boyuancaibian\.oss-cn-beijing\.aliyuncs\.com|oss\.boyuanxc\.cn)/[^\s"\']+', script_content)
                        article_pdf_links.extend(pdf_matches)
                        article_pdf_links.extend(aliyun_matches)
                
                # 查找所有下载按钮或链接
                print("\n在文章详情页查找下载按钮:")
                download_elements = []
                
                # 查找文本中包含"下载"的元素
                for elem in article_soup.find_all(["a", "button", "div", "span"]):
                    text = elem.get_text(strip=True).lower()
                    if any(keyword in text for keyword in ["下载", "download", "pdf", "全文"]):
                        download_elements.append(elem)
                
                # 查找class中包含"download"的元素
                for elem in article_soup.find_all(True):
                    elem_class = elem.get("class", [])
                    if any("download" in cls.lower() or "pdf" in cls.lower() for cls in elem_class):
                        if elem not in download_elements:
                            download_elements.append(elem)
                
                print(f"找到 {len(download_elements)} 个可能的下载元素")
                
                # 检查下载元素中的链接或相关属性
                for elem in download_elements:
                    # 检查元素本身是否是链接
                    if elem.name == "a":
                        href = elem.get("href", "")
                        if href and "javascript:void(0)" not in href:
                            print(f"  下载链接: {href}")
                            if href not in article_pdf_links:
                                article_pdf_links.append(href)
                    
                    # 检查元素的data属性
                    data_attrs = {k: v for k, v in elem.attrs.items() if k.startswith("data-")}
                    if data_attrs:
                        print(f"  数据属性: {data_attrs}")
                        # 检查data属性中是否包含PDF链接
                        for k, v in data_attrs.items():
                            if ("pdf" in v.lower() or "aliyun" in v.lower() or "oss.boyuanxc" in v) and "javascript:void(0)" not in v:
                                if v not in article_pdf_links:
                                    article_pdf_links.append(v)
                    
                    # 检查元素的onclick属性
                    onclick = elem.get("onclick", "")
                    if onclick:
                        print(f"  点击事件: {onclick}")
                        # 尝试从onclick中提取PDF链接
                        pdf_matches = re.findall(r'https?://[^\s"\']+\.pdf', onclick)
                        aliyun_matches = re.findall(r'https?://(boyuancaibian\.oss-cn-beijing\.aliyuncs\.com|oss\.boyuanxc\.cn)/[^\s"\']+', onclick)
                        article_pdf_links.extend(pdf_matches)
                        article_pdf_links.extend(aliyun_matches)
                
                # 去重并过滤掉无效链接
                article_pdf_links = [link for link in list(set(article_pdf_links)) if link and "javascript:void(0)" not in link]
                
                if article_pdf_links:
                    print(f"在文章详情页找到 {len(article_pdf_links)} 个PDF链接:")
                    for pdf_link in article_pdf_links:
                        print(f"  - {pdf_link}")
                        
                        # 从PDF链接中提取文件名作为article_id
                        file_name_match = re.search(r'/([^/]+)\.pdf', pdf_link, re.IGNORECASE)
                        if file_name_match:
                            article_id = file_name_match.group(1)
                        else:
                            article_id = str(uuid.uuid4())[:8]
                        
                        # 查找文章标题
                        title = "无标题"
                        title_elems = article_soup.find_all(["h1", "h2", "h3", "title"])
                        for elem in title_elems:
                            title_text = elem.get_text(strip=True)
                            if title_text and len(title_text) > 5:
                                title = title_text
                                break
                        
                        # 添加文章信息到列表
                        pdfs.append({
                            "article_id": article_id,
                            "title": title,
                            "author": "无作者",
                            "year": year,
                            "issue": issue,
                            "volume": volume,
                            "pdf_url": pdf_link
                        })
    
    print(f"  该期包含 {len(pdfs)} 篇PDF")
    return pdfs

def main():
    """主函数，爬取过刊PDF链接并保存到CSV文件"""
    print("开始爬取过刊PDF链接...")
    
    # 检查CSV文件是否存在，提取已爬取的期号URL
    existing_volumn_urls = set()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 从文章信息中构建期号URL（使用新的URL格式）
                vol_url = f"{BASE_URL}article/{row['year']}/{row['issue']}"
                existing_volumn_urls.add(vol_url)
        print(f"已找到现有CSV文件，包含 {len(existing_volumn_urls)} 个已爬取的期号")
    
    # 获取所有期号URL
    volumn_urls = get_all_volumn_links()
    if not volumn_urls:
        print("未找到任何期号URL")
        return
    
    print(f"找到 {len(volumn_urls)} 个期号需要检查")
    
    # 筛选出新的期号
    new_volumn_urls = []
    for vol_url in volumn_urls:
        if vol_url not in existing_volumn_urls:
            new_volumn_urls.append(vol_url)
    
    if not new_volumn_urls:
        print("没有发现新的期号，爬取结束")
        return
    
    print(f"发现 {len(new_volumn_urls)} 个新期号需要爬取")
    
    # 爬取新期号的文章信息
    all_pdfs = []
    for vol_url in new_volumn_urls:
        print(f"爬取期号: {vol_url}")
        pdfs = extract_pdfs_from_volumn(vol_url)
        print(f"  该期包含 {len(pdfs)} 篇PDF")
        all_pdfs.extend(pdfs)
    
    if not all_pdfs:
        print("未找到任何新的PDF链接")
        return
    
    # 写入CSV文件
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerows(all_pdfs)
    
    print(f"爬取完成！共爬取了 {len(all_pdfs)} 篇新文章。")
    print(f"结果已保存到 {CSV_FILE}")

if __name__ == "__main__":
    main()