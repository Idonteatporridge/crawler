import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://www.jebm.cn"
ARCHIVE_URL = "https://www.jebm.cn/archive_list.htm"
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
    
    # 查找包含过刊信息的主要容器
    archive_div = soup.find("div", id="archive")
    if archive_div:
        # 查找所有期号链接
        for link in archive_div.find_all("a"):
            href = link.get("href", "")
            if href.startswith("/cn/article/"):
                issue_url = urljoin(BASE_URL, href)
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
    
    # 从URL中提取年份和期号信息
    # 解析URL：https://www.jebm.cn/cn/article/2025/4
    year_issue_match = re.search(r"/cn/article/(\d+)/(\d+)", vol_url)
    year = "未知"
    issue = "未知"
    if year_issue_match:
        year = year_issue_match.group(1)
        issue = year_issue_match.group(2)
    
    # 查找所有文章列表项
    for article_div in soup.find_all("div", class_="article-list"):
        article_data = {
            "article_id": "未知",
            "title": "无标题",
            "authors": "",
            "year": year,
            "issue": issue,
            "volumn_page": vol_url,
            "pdf_url": "",
            "doi": ""
        }
        
        # 提取文章ID
        art_id = article_div.get("article_id", "")
        if art_id:
            article_data["article_id"] = art_id
        else:
            # 从id属性提取
            div_id = article_div.get("id", "")
            if div_id:
                article_data["article_id"] = div_id
        
        # 提取标题和DOI
        title_div = article_div.find("div", class_="article-list-title")
        if title_div:
            title_a = title_div.find("a")
            if title_a:
                article_data["title"] = title_a.get_text(strip=True)
                # 提取DOI
                doi_href = title_a.get("href", "")
                if doi_href.startswith("/article/doi/"):
                    doi_match = re.search(r"/article/doi/(10\..+)", doi_href)
                    if doi_match:
                        article_data["doi"] = doi_match.group(1)
        
        # 提取作者
        author_div = article_div.find("div", class_="article-list-author")
        if author_div:
            article_data["authors"] = author_div.get_text(strip=True)
        
        # 提取PDF下载链接
        btn_div = article_div.find("div", class_="article-list-zy article-list-btn clear")
        if btn_div:
            for a in btn_div.find_all("a"):
                onclick_attr = a.get("onclick", "")
                if "downloadpdf('" in onclick_attr:
                    # 匹配PDF ID: downloadpdf('d53503d2-5561-44de-9815-f219d1f11df8')
                    pdf_id_match = re.search(r"downloadpdf\('([^']+)'\)", onclick_attr)
                    if pdf_id_match:
                        pdf_id = pdf_id_match.group(1)
                        article_data["pdf_url"] = f"{BASE_URL}/article/exportPdf?id={pdf_id}"
                        # 如果之前art_id未知，使用pdf_id作为art_id
                        if article_data["article_id"] == "未知":
                            article_data["article_id"] = pdf_id
                        break
        
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