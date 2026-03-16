import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://zhxbygxbzz.cma-cmc.com.cn/"
ARCHIVE_URL = "https://zhxbygxbzz.cma-cmc.com.cn//CN/article/showOldVolumn.do"
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

# 获取所有过刊链接
def get_all_volumn_links():
    """从过刊浏览页面提取所有期号的URL"""
    soup = get_soup(ARCHIVE_URL)
    if not soup:
        return []
    
    links = []
    # 查找表格中的期号链接
    table = soup.find("table", class_="table")
    if not table:
        print("未找到过刊列表表格")
        return []
    
    # 查找所有期号链接
    for a in table.find_all("a", href=re.compile(r"/CN/Y\d+/V\d+/I\d+")):
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
    # 提取年份、卷号和期号信息
    year_match = re.search(r"/Y(\d+)/", vol_url)
    volume_match = re.search(r"/V(\d+)/", vol_url)
    issue_match = re.search(r"/I(\d+)", vol_url)
    
    year = year_match.group(1) if year_match else "未知"
    volume = volume_match.group(1) if volume_match else "未知"
    issue = issue_match.group(1) if issue_match else "未知"
    
    # 直接查找所有class为pdf-a的元素
    pdf_a_elements = soup.find_all("a", class_="pdf-a")
    # print(f"找到 {len(pdf_a_elements)} 个class为pdf-a的元素")
    
    for pdf_a in pdf_a_elements:
        if "onclick" in pdf_a.attrs:
            # 从onclick事件中提取ID
            onclick_match = re.search(r"lsdy1\('PDF','(\d+)'\)", pdf_a["onclick"])
            if onclick_match:
                article_id = onclick_match.group(1)
                # 构建PDF下载链接
                pdf_url = f"{BASE_URL}/CN/article/downloadArticleFile.do?attachType=PDF&id={article_id}"
                
                # 查找对应的文章标题和作者（从父元素或兄弟元素中）
                title = "无标题"
                author = "无作者"
                
                # 找到包含该PDF链接的li元素
                li_element = pdf_a.find_parent("li")
                if li_element:
                    # 提取文章标题
                    title_div = li_element.find("div", class_="title")
                    if title_div:
                        title = title_div.get_text(strip=True)
                    
                    # 提取作者信息
                    author_div = li_element.find("div", class_="zuozhe")
                    if author_div:
                        author = author_div.get_text(strip=True)
                
                # 添加文章信息到列表
                pdfs.append({
                    "article_id": article_id,
                    "title": title,
                    "author": author,
                    "year": year,
                    "issue": issue,
                    "volume": volume,
                    "pdf_url": pdf_url
                })
    
    return pdfs

# 主程序
def main():
    print("开始爬取过刊PDF链接...")
    
    # 检查CSV文件是否存在，提取已爬取的期号URL
    existing_volumn_urls = set()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 从文章信息中构建期号URL
                vol_url = f"{BASE_URL}/CN/Y{row['year']}/V{row['volume']}/I{row['issue']}"
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