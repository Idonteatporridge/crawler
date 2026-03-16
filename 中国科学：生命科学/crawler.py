import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 爬虫配置
BASE_URL = "https://www.sciengine.com"
ARCHIVE_URL = "https://www.sciengine.com/SCLS/catalogue"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "year", "issue", "volume", "pages", "pdf_url", "doi", "volumn_page"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def get_soup(url):
    """使用Selenium获取指定URL的BeautifulSoup对象，支持JavaScript渲染"""
    try:
        # 设置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 无头模式，不显示浏览器窗口
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={headers['User-Agent']}")
        
        # 创建WebDriver实例
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        # 访问URL
        driver.get(url)
        print(f"成功获取页面 {url}")
        
        # 等待页面加载完成，根据页面类型等待不同元素
        wait = WebDriverWait(driver, 10)
        if "/SCLS/catalogue" in url:
            # 过刊浏览页面，等待archiveLists元素
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "archiveLists")))
        elif "/SCLS/issue/" in url:
            # 期号页面，等待list1Content元素
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "list1Content")))
        else:
            # 其他页面，等待body元素加载完成
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # 获取页面源代码
        page_source = driver.page_source
        
        # 关闭浏览器
        driver.quit()
        
        return BeautifulSoup(page_source, "html.parser")
    except Exception as e:
        print(f"获取页面失败 {url}: {e}")
        # 确保浏览器关闭
        try:
            driver.quit()
        except:
            pass
        return None

# 获取所有过刊链接
def get_all_volumn_links():
    """从过刊浏览页面提取所有期号的URL"""
    soup = get_soup(ARCHIVE_URL)
    if not soup:
        return []
    
    links = []
    # 查找所有期号链接
    for a in soup.find_all("a", class_="lssueText", href=re.compile(r"/SCLS/issue/\d+/\d+")):
        href = a["href"]
        full_url = urljoin(BASE_URL, href)
        links.append(full_url)
    
    # 去重并返回
    links = list(set(links))
    # 按URL排序，使爬取顺序更有序
    links.sort()
    return links

# 从每期提取PDF链接
def extract_pdfs_from_volumn(vol_url):
    """从指定期号页面提取所有PDF链接"""
    soup = get_soup(vol_url)
    if not soup:
        return []
    
    pdfs = []
    
    # 从URL中提取卷号和期号
    year = "未知"
    issue = "未知"
    volume = "未知"
    url_match = re.search(r"/SCLS/issue/(\d+)/(\d+)", vol_url)
    if url_match:
        volume = url_match.group(1)
        issue = url_match.group(2)
    
    # 查找所有文章列表项
    for article in soup.find_all("div", class_="list1Content"):
        # 提取标题
        title = "无标题"
        title_a = article.find("div", class_="title").find("a")
        if title_a:
            title = title_a.get_text(strip=True) or "无标题"
        
        # 提取PDF链接
        pdf_url = ""
        article_id = ""
        pdf_a = article.find("a", class_="pdfLink", href=re.compile(r"/doi/pdf/[0-9A-F]+", re.I))
        if pdf_a:
            pdf_href = pdf_a["href"]
            pdf_url = urljoin(BASE_URL, pdf_href)
            # 从PDF链接中提取article_id
            id_match = re.search(r"/doi/pdf/([0-9A-F]+)", pdf_href, re.I)
            if id_match:
                article_id = id_match.group(1)
        
        # 提取DOI
        doi = ""
        doi_a = article.find("div", class_="title").find("a", href=re.compile(r"/doi/10\.1007/"))
        if doi_a:
            doi_href = doi_a["href"]
            doi_match = re.search(r"/doi/(10\.1007/[\w./-]+)", doi_href)
            if doi_match:
                doi = doi_match.group(1)
        
        # 目前无法直接从页面中提取年份和页码信息，需要根据实际情况调整
        year = "未知"
        pages = ""
        
        pdfs.append({
            "article_id": article_id,
            "title": title,
            "year": year,
            "issue": issue,
            "volume": volume,
            "pages": pages,
            "pdf_url": pdf_url,
            "doi": doi,
            "volumn_page": vol_url
        })
    
    return pdfs

# 主程序
def main():
    print("开始爬取过刊PDF链接...")
    
    # 检查CSV文件是否存在，提取已爬取的期号URL
    existing_volumn_pages = set()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_volumn_pages.add(row["volumn_page"])
        print(f"已找到现有CSV文件，跳过 {len(existing_volumn_pages)} 个已爬取的期号")
    
    # 获取所有期号URL并筛选出新的期号URL
    volumn_urls = get_all_volumn_links()
    if not volumn_urls:
        print("未找到任何期号URL")
        return
    
    new_volumn_urls = [url for url in volumn_urls if url not in existing_volumn_pages]
    
    if not new_volumn_urls:
        print("没有新的期号需要爬取！")
        return
    
    print(f"找到 {len(new_volumn_urls)} 个新的期号需要爬取")
    
    # 爬取新期号的文章信息
    all_pdfs = []
    for vol_url in new_volumn_urls:
        print(f"爬取期号: {vol_url}")
        pdfs = extract_pdfs_from_volumn(vol_url)
        print(f"  该期包含 {len(pdfs)} 篇PDF")
        all_pdfs.extend(pdfs)
    
    if not all_pdfs:
        print("未找到任何PDF链接")
        return
    
    # 写入CSV文件
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerows(all_pdfs)
    
    print(f"爬取完成！共爬取了 {len(all_pdfs)} 篇文章，来自 {len(new_volumn_urls)} 个新期号。")
    print(f"结果已保存到 {CSV_FILE}")

if __name__ == "__main__":
    main()