import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "https://www.zgxfzz.com"
ARCHIVE_URL = "https://www.zgxfzz.com/CN/1005-6661/home.shtml"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "year", "issue", "volumn_page", "pdf_url", "doi"]

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
    # 由于过刊链接是动态加载的，我们采用基于观察到的模式生成链接的方式
    # 根据要求，使用固定范围从 1100 到 1300
    
    links = []
    
    # 设置固定的期号范围（从 1100 到 1300）
    start_vol = 1100
    end_vol = 1300
    
    print(f"生成从 {start_vol} 到 {end_vol} 的期号链接")
    for vol_num in range(start_vol, end_vol+1):
        # 构建完整URL
        vol_url = f"{BASE_URL}/CN/volumn/volumn_{vol_num}.shtml"
        links.append(vol_url)
    
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
    articles_div = soup.find("div", class_="articles")
    if not articles_div:
        return pdfs
    
    # 查找所有文章条目
    for div in articles_div.find_all("div", class_="noselectrow"):
        # 提取标题
        title_a = div.find("a", class_="biaoti")
        title = title_a.get_text(strip=True) if title_a else "无标题"
        
        # 提取PDF链接
        pdf_a = div.find("a", class_="txt_zhaiyao1", onclick=re.compile(r"lsdy1\('PDF',\s*'\d+'"))
        if not pdf_a:
            continue
        
        # 从onclick事件中提取文章ID
        onclick_attr = pdf_a.get("onclick", "")
        pdf_id_match = re.search(r"lsdy1\('PDF',\s*'(\d+)',", onclick_attr)
        if not pdf_id_match:
            continue
            
        pdf_id = pdf_id_match.group(1)
        # 构建完整PDF URL
        pdf_url = f"{BASE_URL}/CN/PDF/{pdf_id}"
        
        # 提取article_id
        art_id = pdf_id
        
        # 提取年份、卷号和期号信息
        year = "未知"
        issue = "未知"
        volume = "未知"
        
        # 从URL中提取卷号信息
        vol_match = re.search(r"volumn_(\d+)\.shtml", vol_url)
        if vol_match:
            issue = vol_match.group(1)
        
        # 从onclick事件中提取年份信息
        year_match = re.search(r"lsdy1\('PDF',\s*'\d+',\s*'[^']+',\s*'(\d+)',", onclick_attr)
        if year_match:
            year = year_match.group(1)
        
        # 提取DOI
        doi = ""
        
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