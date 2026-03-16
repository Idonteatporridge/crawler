import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://www.jsczz.cn"
ARCHIVE_URL = "https://www.jsczz.cn/CN/article/showOldVolumn.do"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "year", "issue", "volume", "pages", "pdf_url", "doi"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.jsczz.cn/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
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
    # 查找所有期号链接（新的页面结构）
    table = soup.find("table", class_="table")
    if table:
        tbody = table.find("tbody")
        if tbody:
            for a in tbody.find_all("a", href=re.compile(r"\.\./volumn/volumn_\d+\.shtml")):
                href = a["href"]
                # 转换相对路径为绝对路径
                full_url = href.replace("../", f"{BASE_URL}/CN/")
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
    
    # 查找所有文章列表项（新的页面结构）
    for article in soup.find_all("div", class_="noselectrow"):
        # 提取article_id
        article_id = article.get("id", "")
        if article_id.startswith("art"):
            article_id = article_id[3:]  # 去掉前缀"art"
        
        # 提取标题
        title = "无标题"
        wenzhang = article.find("div", class_="wenzhang")
        if wenzhang:
            dl = wenzhang.find("dl")
            if dl:
                dqml_gbwz = dl.find("div", class_="dqml_gbwz")
                if dqml_gbwz:
                    dt = dqml_gbwz.find("dt")
                    if dt:
                        title = dt.get_text(strip=True) or "无标题"
        
        # 提取年份、卷号、期号、页码和DOI信息
        year = "未知"
        volume = "未知"
        issue = "未知"
        pages = "未知"
        doi = ""
        
        kmnjq = article.find("dd", class_="kmnjq")
        if kmnjq:
            # 提取年份、卷号、期号和页码
            kmnjq_text = kmnjq.get_text(strip=True)
            # 匹配格式：2023, 41(6): 653-668; doi: 10.12140/j.issn.1000-7423.2023.06.001
            info_match = re.search(r"(\d{4}),\s*(\d+)\((\d+)\):\s*(\d+)-(\d+)" , kmnjq_text)
            if info_match:
                year = info_match.group(1)
                volume = info_match.group(2)
                issue = info_match.group(3)
                pages = f"{info_match.group(4)}-{info_match.group(5)}"
            
            # 提取DOI
            doi_a = kmnjq.find("a", href=re.compile(r"https://doi.org/"))
            if doi_a:
                doi = doi_a.get_text(strip=True)
        
        # 构建PDF下载URL
        pdf_url = ""
        if doi:
            # 有DOI的文章，使用DOI构建PDF链接
            pdf_url = f"{BASE_URL}/CN/PDF/{doi}"
        else:
            # 没有DOI的文章，使用article_id构建PDF链接
            pdf_url = f"{BASE_URL}/CN/PDF/{article_id}"
        
        pdfs.append({
            "article_id": article_id,
            "title": title,
            "year": year,
            "issue": issue,
            "volume": volume,
            "pages": pages,
            "pdf_url": pdf_url,
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
                # 使用article_id作为唯一标识来避免重复爬取
                existing_volumn_pages.add(row["article_id"])
        print(f"已找到现有CSV文件，跳过 {len(existing_volumn_pages)} 个已爬取的文章")
    
    # 获取所有期号URL
    volumn_urls = get_all_volumn_links()
    if not volumn_urls:
        print("未找到任何期号URL")
        return
    
    # 爬取所有期号的文章信息
    all_pdfs = []
    for vol_url in volumn_urls:
        print(f"爬取期号: {vol_url}")
        pdfs = extract_pdfs_from_volumn(vol_url)
        print(f"  该期包含 {len(pdfs)} 篇PDF")
        all_pdfs.extend(pdfs)
    
    # 筛选出新的文章，避免重复爬取
    new_pdfs = []
    for pdf in all_pdfs:
        if pdf["article_id"] not in existing_volumn_pages:
            new_pdfs.append(pdf)
    
    if not new_pdfs:
        print("没有新的文章需要爬取！")
        return
    
    print(f"找到 {len(new_pdfs)} 篇新的文章需要爬取")
    all_pdfs = new_pdfs
    
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
    
    print(f"爬取完成！共爬取了 {len(all_pdfs)} 篇文章，来自 {len(volumn_urls)} 个新期号。")
    print(f"结果已保存到 {CSV_FILE}")

if __name__ == "__main__":
    main()