import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://actaps.sinh.ac.cn"
ARCHIVE_URL = "https://actaps.sinh.ac.cn/archive.php"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "year", "issue", "volumn_page", "pdf_url", "doi"]

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

# 获取所有过刊链接
def get_all_volumn_links():
    """从过刊浏览页面提取所有期号的URL"""
    soup = get_soup(ARCHIVE_URL)
    if not soup:
        return []
    
    links = []
    # 查找所有期号链接
    for row in soup.find_all("div", class_="row"):
        for col in row.find_all("div", class_=["col-lg-2", "col-md-2", "col-sm-4", "col-xs-4"]):
            a = col.find("a")
            if not a:
                continue
            href = a["href"]
            if href.startswith("issue.php?id="):
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
    
    # 查找所有文章列表项
    for li in soup.find_all("li"):
        # 查找文章链接
        article_a = li.find("a", href=re.compile(r"article\.php\?id=\d+"))
        if not article_a:
            continue
        
        # 提取article_id
        href = article_a["href"]
        art_id_match = re.search(r"article\.php\?id=(\d+)", href)
        if not art_id_match:
            continue
        art_id = art_id_match.group(1)
        
        # 提取标题
        title = article_a.get_text(strip=True) or "无标题"
        
        # 提取年份、期号和卷号信息
        year = "未知"
        issue = "未知"
        
        # 查找包含年份和期号的span元素
        span = li.find("span")
        if span:
            span_text = span.get_text(strip=True)
            # 匹配格式：生理学报 2024; 76 (1): 12-32
            volumn_match = re.search(r"生理学报\s+(\d{4});\s+(\d+)\s*\((\d+)\)", span_text)
            if volumn_match:
                year = volumn_match.group(1)
                issue = volumn_match.group(3)
        
        # 提取DOI - 新网站可能没有DOI信息，暂时留空
        doi = ""
        
        # 构建PDF下载URL
        pdf_url = urljoin(BASE_URL, href.replace("article.php", "pdf.php"))
        
        # 获取真实的PDF链接（处理JavaScript跳转）
        real_pdf_url = pdf_url
        try:
            # 发送GET请求获取HTML内容
            response = requests.get(pdf_url, headers=headers, timeout=10, allow_redirects=True)
            
            # 检查Content-Type
            content_type = response.headers.get('Content-Type', '')
            
            # 如果是HTML，尝试从中提取PDF链接
            if 'text/html' in content_type:
                # 使用正则表达式查找location.replace跳转
                script_content = response.text
                pdf_path = re.search(r"location\.replace\('([^']+)\.pdf'\)", script_content)
                if not pdf_path:
                    pdf_path = re.search(r'location\.replace\("([^"]+)\.pdf"\)', script_content)
                
                if pdf_path:
                    real_pdf_url = urljoin(response.url, pdf_path.group(1) + ".pdf")
        except Exception as e:
            print(f"  获取真实PDF链接失败 {pdf_url}: {e}")
        
        pdfs.append({
            "article_id": art_id,
            "title": title,
            "year": year,
            "issue": issue,
            "volumn_page": vol_url,
            "pdf_url": real_pdf_url,
            "doi": doi
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