import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://www.chinagp.net"
ARCHIVE_URL = "https://www.chinagp.net/CN/article/showOldVolumn.do"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "authors", "year", "issue", "volumn_page", "pdf_url", "doi"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
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
    
    # 查找表格中的所有期号链接
    table = soup.find("table")
    if not table:
        return links
    
    # 处理表格可能没有tbody元素的情况
    tbody = table.find("tbody")
    if tbody:
        rows = tbody.find_all("tr")
    else:
        rows = table.find_all("tr")
    
    # 正则表达式匹配期号链接
    link_pattern = re.compile(r"volumn_\d+\.shtml")
    
    for row in rows:
        for cell in row.find_all("td"):
            for link in cell.find_all("a"):
                href = link.get("href", "")
                if link_pattern.search(href):
                    # 处理href格式：../volumn/volumn_1225.shtml -> volumn/volumn_1225.shtml
                    clean_href = href.lstrip("../")
                    issue_url = f"{BASE_URL}/CN/{clean_href}"
                    links.append(issue_url)
    
    # 去重、排序并返回
    links = list(set(links))
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
    article_list = soup.find("form", id="AbstractList")
    if not article_list:
        return pdfs
    
    # 查找所有文章条目 - 每个div.noselectrow代表一篇文章
    for article_div in article_list.find_all("div", class_="noselectrow"):
        article_data = {
            "article_id": "未知",
            "title": "无标题",
            "authors": "",
            "year": "未知",
            "issue": "未知",
            "volumn_page": vol_url,
            "pdf_url": "",
            "doi": ""
        }
        
        # 提取文章ID
        art_id = article_div.get("id", "")
        if art_id and art_id.startswith("art"):
            article_data["article_id"] = art_id[3:]  # 去掉前缀"art"
        
        # 查找文章内容div
        content_div = article_div.find("div", class_="wenzhang")
        if not content_div:
            continue
        
        # 检查是否存在PDF下载链接元素
        has_pdf = False
        for a in content_div.find_all("a", class_="txt_zhaiyao1"):
            onclick_attr = a.get("onclick", "")
            if "lsdy1('PDF'" in onclick_attr:
                has_pdf = True
                break
        
        # 如果没有PDF链接，跳过该文章
        if not has_pdf:
            continue
        
        # 提取标题
        biaoti_div = content_div.find("div", class_="biaoti")
        if biaoti_div:
            title_a = biaoti_div.find("a", class_="biaoti")
            if title_a:
                article_data["title"] = title_a.get_text(strip=True)
        
        # 提取作者
        zuozhe_div = content_div.find("div", class_="zuozhe")
        if zuozhe_div:
            article_data["authors"] = zuozhe_div.get_text(strip=True)
        
        # 提取DOI和PDF链接
        kmnjq_div = content_div.find("div", class_="kmnjq")
        if kmnjq_div:
            doi_link = kmnjq_div.find("a")
            if doi_link:
                doi_href = doi_link.get("href", "")
                if doi_href.startswith("https://doi.org/"):
                    doi = doi_href.split("https://doi.org/")[1]
                    article_data["doi"] = doi
                    article_data["pdf_url"] = f"{BASE_URL}/CN/PDF/{doi}"
            
            # 提取年份和期号信息
            kmnjq_text = kmnjq_div.get_text(strip=True)
            year_match = re.search(r"^(\d{4}),", kmnjq_text)
            if year_match:
                article_data["year"] = year_match.group(1)
            # 提取卷期信息
            issue_match = re.search(r"\d{4}, (\d+)\((\d+)\)", kmnjq_text)
            if issue_match:
                volume = issue_match.group(1)
                issue_num = issue_match.group(2)
                article_data["issue"] = f"{volume}({issue_num})"
        
        # 从URL中提取期号信息（如果之前没有获取到）
        if article_data["issue"] == "未知":
            vol_match = re.search(r"volumn_(\d+)\.shtml", vol_url)
            if vol_match:
                vol_num = vol_match.group(1)
                article_data["issue"] = vol_num
        
        if article_data["pdf_url"]:
            pdfs.append(article_data)
    
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