import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

BASE = "https://www.hxkqyxzz.net"
OLD_VOL_URL = BASE + "/CN/article/showOldVolumn.do"

headers = {"User-Agent": "Mozilla/5.0"}

def get_soup(url):
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")

# 获取所有过刊链接
def get_all_volumn_links():
    soup = get_soup(OLD_VOL_URL)
    links = []
    for a in soup.find_all("a", href=re.compile(r"../volumn/volumn_\d+\.shtml")):
        href = a["href"]
        # 去除 ../ 前缀，确保URL包含正确的 CN 路径
        if href.startswith("../"):
            href = href[3:]
        full_url = BASE + "/CN/" + href
        links.append(full_url)
    links = list(set(links))
    return links

# 从每期提取PDF链接
def extract_pdfs_from_volumn(vol_url):
    soup = get_soup(vol_url)
    pdfs = []
    pattern = re.compile(r"lsdy1\('PDF','(\d+)','([^']*)','(\d+)','(\d+)'\)")
    for a in soup.find_all("a", onclick=pattern):
        onclick = a["onclick"]
        m = pattern.search(onclick)
        if m:
            art_id, _, year, issue = m.groups()
            pdf_url = f"{BASE}/CN/article/downloadArticleFile.do?attachType=PDF&id={art_id}"
            # 尝试从h3标签提取标题，如果没有则使用a标签的文本
            h3_tag = a.find('h3', class_='abs-tit')
            if h3_tag:
                title = h3_tag.get_text(strip=True) or "无标题"
            else:
                title = a.get_text(strip=True) or "无标题"
            pdfs.append({
                "article_id": art_id,
                "title": title,
                "year": year,
                "issue": issue,
                "volumn_page": vol_url,
                "pdf_url": pdf_url
            })
    return pdfs



CSV_FILE = "hxkqyxzz_all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "year", "issue", "volumn_page", "pdf_url"]

# 检查CSV文件是否存在，提取已爬取的期号URL
existing_volumn_pages = set()
if os.path.exists(CSV_FILE):
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_volumn_pages.add(row["volumn_page"])

# 获取所有期号URL并筛选出新的期号URL
volumn_urls = get_all_volumn_links()
new_volumn_urls = [url for url in volumn_urls if url not in existing_volumn_pages]

if not new_volumn_urls:
    print("没有新的期号需要爬取！")
    exit()

# 爬取新期号的文章信息
all_pdfs = []
for vol_url in new_volumn_urls:
    print(f"爬取期号: {vol_url}")
    pdfs = extract_pdfs_from_volumn(vol_url)
    print(f"  该期包含 {len(pdfs)} 篇PDF")
    all_pdfs.extend(pdfs)

# 写入CSV文件
file_exists = os.path.exists(CSV_FILE)
with open(CSV_FILE, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
    if not file_exists:
        w.writeheader()
    w.writerows(all_pdfs)

print(f"爬取完成！共爬取了 {len(all_pdfs)} 篇文章，来自 {len(new_volumn_urls)} 个新期号。")