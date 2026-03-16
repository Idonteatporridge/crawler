import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "http://www.cjim.cn/zxyjhcn/zxyjhcn/ch/reader"
ARCHIVE_URL = "http://www.cjim.cn/zxyjhcn/zxyjhcn/ch/reader/issue_browser.aspx"
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
    
    # 查找包含过刊信息的表格
    query_ui_table = soup.find("table", id="QueryUI")
    if query_ui_table:
        # 查找表格中的所有链接
        for link in query_ui_table.find_all("a"):
            href = link.get("href", "")
            if href.startswith("issue_list.aspx?year_id="):
                # 确保正确构建URL，添加/reader路径
                issue_url = f"http://www.cjim.cn/zxyjhcn/zxyjhcn/ch/reader/{href}"
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
    # 解析URL：http://www.cjim.cn/zxyjhcn/zxyjhcn/ch/reader/issue_list.aspx?year_id=2025&quarter_id=1
    year_issue_match = re.search(r"year_id=(\d+)&quarter_id=(\d+)", vol_url)
    year = "未知"
    issue = "未知"
    if year_issue_match:
        year = year_issue_match.group(1)
        issue = year_issue_match.group(2)
    
    # 查找所有文章列表项 - 查找包含文章信息的表格
    # 假设文章信息在id为"table24"的表格中，或者在其他表格中
    article_tables = soup.find_all("table")
    
    for table in article_tables:
        # 查找表格中的所有行
        rows = table.find_all("tr")
        
        # 遍历行，寻找文章信息
        i = 0
        while i < len(rows):
            row = rows[i]
            # 查找包含文章标题的链接
            title_link = row.find("a", href=re.compile(r"view_abstract.aspx\?file_no="))
            
            if title_link:
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
                
                # 提取标题
                article_data["title"] = title_link.get_text(strip=True)
                
                # 提取file_no作为article_id
                file_no_match = re.search(r"file_no=(\d+)", title_link.get("href", ""))
                if file_no_match:
                    article_data["article_id"] = file_no_match.group(1)
                
                # 提取作者 - 通常在标题行的下一行
                if i + 1 < len(rows):
                    author_row = rows[i + 1]
                    author_td = author_row.find("td", colspan=None)
                    if author_td:
                        article_data["authors"] = author_td.get_text(strip=True)
                
                # 提取PDF下载链接 - 通常在标题行的下两行
                if i + 2 < len(rows):
                    pdf_row = rows[i + 2]
                    pdf_link = pdf_row.find("a", href=re.compile(r"create_pdf.aspx\?file_no="))
                    if pdf_link:
                        pdf_href = pdf_link.get("href", "")
                        # 确保正确构建PDF链接
                        if pdf_href.startswith("http"):
                            # 如果是完整URL，直接使用
                            article_data["pdf_url"] = pdf_href
                        else:
                            # 如果是相对路径，使用正确的基础URL构建
                            article_data["pdf_url"] = f"http://www.cjim.cn/zxyjhcn/zxyjhcn/ch/reader/{pdf_href}"
                
                if article_data["pdf_url"]:
                    pdfs.append(article_data)
                
                # 跳过已处理的行
                i += 3
            else:
                i += 1
    
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