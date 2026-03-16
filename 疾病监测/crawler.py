import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://www.jbjc.org"
ARCHIVE_URL = "https://www.jbjc.org/archive_list.htm"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "year", "issue", "volumn_page", "pdf_url"]

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
    # 查找过刊列表区域
    archive_div = soup.find("div", id="archive")
    if not archive_div:
        print("未找到过刊列表区域")
        return []
    print(archive_div)
    # 查找所有期号链接
    for a in archive_div.find_all("a", href=re.compile(r"/cn/article/\d+/\d+")):
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
    # 提取年份和期号信息
    year_match = re.search(r"/article/(\d+)/", vol_url)
    issue_match = re.search(r"/(\d+)$", vol_url)
    year = year_match.group(1) if year_match else "未知"
    issue = issue_match.group(1) if issue_match else "未知"
    
    # 查找所有PDF下载链接
    pattern = re.compile(r"downloadpdf\('([^']+)'\)")
    for a in soup.find_all("a", onclick=pattern):
        onclick = a["onclick"]
        m = pattern.search(onclick)
        if m:
            art_id = m.group(1)
            # 构建PDF下载URL，使用正确的格式
            pdf_url = f"{BASE_URL}/article/exportPdf?id={art_id}"
            
            # 提取文章标题
            # 先查找父级article-list容器
            article_list = a.find_parent("div", class_="article-list")
            title = "无标题"
            
            if article_list:
                # 尝试从不同位置提取标题
                # 1. 查找可能包含标题的span或其他标签
                title_span = article_list.find("span", class_="article-title")
                if title_span:
                    title = title_span.get_text(strip=True) or "无标题"
                else:
                    # 2. 查找所有文本内容，尝试提取标题
                    text_content = article_list.get_text(strip=True)
                    if text_content and "PDF" in text_content:
                        # 去除PDF相关文本
                        title = text_content.replace("PDF", "").strip() or "无标题"
            
            pdfs.append({
                "article_id": art_id,
                "title": title,
                "year": year,
                "issue": issue,
                "volumn_page": vol_url,
                "pdf_url": pdf_url
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