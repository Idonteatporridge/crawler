import requests
from bs4 import BeautifulSoup
import csv
import re

BASE = "https://xuebao.smmu.edu.cn"
BROWSER_URL = BASE + "/ajsmmu/issue/browser"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_soup(url):
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")

# 修复后的核心函数
def get_issue_urls():
    soup = get_soup(BROWSER_URL)
    urls = []

    # 关键修改：去掉开头的斜杠
    for a in soup.find_all("a", href=re.compile(r"ajsmmu/article/issue/\d+_\d+_\d+")):
        href = a["href"]
        full_url = BASE + "/" + href if not href.startswith("http") else href
        if full_url not in urls:
            urls.append(full_url)
            print(f"发现期刊: {a.get_text(strip=True)} → {full_url}")

    print(f"\n共发现 {len(urls)} 期")
    return urls

def get_pdfs_from_issue(issue_url):
    soup = get_soup(issue_url)
    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "ajsmmu/article/pdf/" in href and "?st=article_issue" in href:
            pdf_url = BASE + "/" + href.lstrip("/")
            article_id = href.split("/")[-1].split("?")[0]
            title = a.get_text(strip=True) or "无标题"
            pdfs.append({
                "article_id": article_id,
                "title": title,
                "issue_url": issue_url,
                "pdf_url": pdf_url
            })
    print(f"  → 提取 {len(pdfs)} 篇 PDF")
    return pdfs

import os

# 主程序
def main():
    csv_file = "海军军医大学学报_全部PDF链接.csv"
    fieldnames = ["article_id", "title", "issue_url", "pdf_url"]
    
    # 1. 检查是否存在现有CSV文件，如果存在则读取已爬取的issue_url
    crawled_issues = set()
    if os.path.exists(csv_file):
        print(f"检查现有CSV文件: {csv_file}")
        try:
            with open(csv_file, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    crawled_issues.add(row["issue_url"])
            print(f"  已爬取 {len(crawled_issues)} 期")
        except Exception as e:
            print(f"  读取CSV文件出错: {e}")
            crawled_issues = set()
    
    # 2. 获取网站上所有的期数URL
    print("\n获取网站上所有期数...")
    all_issues = get_issue_urls()
    print(f"共发现 {len(all_issues)} 期")
    
    # 3. 筛选出未爬取的新期数
    new_issues = [url for url in all_issues if url not in crawled_issues]
    
    if not new_issues:
        print("\n✅ 没有发现新的期刊期数，无需爬取")
        return
    
    print(f"\n发现 {len(new_issues)} 期新内容需要爬取")
    
    # 4. 爬取新期数的PDF链接
    new_pdfs = []
    for i, url in enumerate(new_issues, 1):
        print(f"[{i:3d}/{len(new_issues)}] {url}")
        new_pdfs.extend(get_pdfs_from_issue(url))
    
    print(f"\n完成！共提取 {len(new_pdfs)} 篇新的PDF链接")
    
    # 5. 将新数据追加到CSV文件
    if new_pdfs:
        # 检查文件是否存在，决定是否需要写入表头
        file_exists = os.path.exists(csv_file)
        mode = "a" if file_exists else "w"
        
        with open(csv_file, mode, newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_pdfs)
        
        print(f"已追加到: {csv_file}")

if __name__ == "__main__":
    main()
    print("程序执行完毕")