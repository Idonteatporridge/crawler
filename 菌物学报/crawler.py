from itertools import count
import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://manu40.magtech.com.cn/Jwxb"
ARCHIVE_URL = "https://manu40.magtech.com.cn/Jwxb/CN/home"
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
    # 首先尝试直接从首页获取
    soup = get_soup(ARCHIVE_URL)
    if not soup:
        return []
    
    links = []
    
    # 查找包含过刊链接的容器 - 处理不规范的HTML
    table_div = soup.find("div", class_=lambda x: x and "table-form" in x)
    
    # 如果找不到，尝试查找AJAX加载的页面
    if not table_div:
        # 查找AJAX页面组件，特别关注包含archive的URL
        ajax_divs = soup.find_all("div", attrs={"mag-component-type": "ajaxPage"})
        ajax_url = None
        
        for div in ajax_divs:
            if "mag-page-url" in div.attrs:
                url = div["mag-page-url"]
                if "archive" in url:
                    ajax_url = url
                    break
        
        # 如果没有找到包含archive的URL，检查所有AJAX URL
        if not ajax_url and ajax_divs:
            for i, div in enumerate(ajax_divs):
                if "mag-page-url" in div.attrs:
                    url = div["mag-page-url"]
                    print(f"备选AJAX URL {i+1}: {url}")
                    # 尝试第一个AJAX URL
                    ajax_url = url
                    break
        
        if ajax_url:
            print(f"检测到AJAX加载页面，尝试访问: {ajax_url}")
            ajax_soup = get_soup(ajax_url)
            if ajax_soup:
                table_div = ajax_soup.find("div", class_=lambda x: x and "table-form" in x)
    
    # 如果还是找不到，直接访问已知的过刊归档URL
    if not table_div:
        known_archive_url = "https://manu40.magtech.com.cn/Jwxb/CN/archive_by_years?forwardJsp=simple"
        print(f"尝试直接访问已知过刊归档URL: {known_archive_url}")
        archive_soup = get_soup(known_archive_url)
        if archive_soup:
            table_div = archive_soup.find("div", class_=lambda x: x and "table-form" in x)
    
    if not table_div:
        print("未找到过刊链接容器")
        # 调试：保存页面内容到文件以便分析
        with open("page_debug.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("页面内容已保存到page_debug.html供调试")
        return links
    
    # 查找所有期号链接
    for td in table_div.find_all("td"):
        a = td.find("a", href=True)
        if a:
            href = a["href"]
            # 检查链接格式
            if re.match(r"https?://manu40\.magtech\.com\.cn/Jwxb/CN/Y\d+/V\d+/I\d+", href):
                links.append(href)
            # 也检查相对链接
            elif href.startswith("/Jwxb/CN/Y"):
                full_url = f"https://manu40.magtech.com.cn{href}"
                links.append(full_url)
            # 调试：打印找到的链接
            print(f"找到链接: {href}")
    
    # 去重并返回
    links = list(set(links))
    # 按URL排序，使爬取顺序更有序
    links.sort()
    print(f"找到 {len(links)} 个过刊链接")
    return links

# 从每期提取PDF链接
def extract_pdfs_from_volumn(vol_url):
    """从指定期号页面提取所有PDF链接"""
    soup = get_soup(vol_url)
    if not soup:
        return []
    
    pdfs = []
    
    # 提取年份和期号信息
    year = "未知"
    issue = "未知"
    year_match = re.search(r"Y(\d+)", vol_url)
    issue_match = re.search(r"I(\d+)", vol_url)
    if year_match:
        year = year_match.group(1)
    if issue_match:
        issue = issue_match.group(1)
    
    # 查找所有文章列表项（假设j-title-1在li.noselectrow中）
    for li in soup.find_all("li", class_="noselectrow"):
        # 查找文章标题div
        title_div = li.find("div", class_="j-title-1")
        if not title_div:
            continue
            
        # 查找文章链接
        article_a = title_div.find("a", href=True, target="_blank")
        if not article_a:
            continue
        
        # 提取标题
        title = article_a.get_text(strip=True) or "无标题"
        
        # 提取文章ID和构建PDF下载URL
        art_id = ""
        href = article_a["href"]
        pdf_url = ""
        
        # 首先查找j-pdf元素并从onclick事件中提取ID
        pdf_a = li.find("a", class_="j-pdf")
        if pdf_a:
            onclick = pdf_a.get("onclick", "")
            # 从onclick事件中提取ID
            id_match = re.search(r"lsdy1\('[^']+'\s*,'([^']+)'\)", onclick)
            if id_match:
                art_id = id_match.group(1)
        
        # 检查链接是否为DOI格式
        doi_format = False
        if re.search(r"/\d+\.\d+/", href):
            doi_format = True
        
        # 构建PDF下载URL
        if doi_format:
            # 对于DOI格式的链接，直接在/CN/后面加上/PDF/
            pdf_url = href.replace("/CN/", "/CN/PDF/")
        else:
            # 对于非DOI格式，使用从onclick事件中提取的ID
            if art_id:
                pdf_url = f"{BASE_URL}/CN/PDF/{art_id}"
        
        # 如果PDF链接为空，跳过
        if not pdf_url:
            continue
            
        # 提取DOI
        doi = href if doi_format else ""
        
        pdfs.append({
            "article_id": art_id,
            "title": title,
            "year": year,
            "issue": issue,
            "volumn_page": vol_url,
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