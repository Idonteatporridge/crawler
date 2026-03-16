import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os
import time

BASE_URL = "https://mednexus.org/"
JOURNAL_CODE = "bls"
ARCHIVE_URL = f"{BASE_URL}loi/{JOURNAL_CODE}"
CSV_FILE = "all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "author", "issue_url", "pdf_url"]

driver = uc.Chrome()

def get_soup(url):
    """获取指定URL的BeautifulSoup对象"""
    try:
        driver.get(url)
        
        for i in range(10):
            time.sleep(2)
            html = driver.page_source
            if 'Just a moment' not in html and 'cf_chl_opt' not in html:
                break
        
        return BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"获取页面失败 {url}: {e}")
        return None

def get_all_year_links():
    """从首页提取所有年份页面的URL"""
    soup = get_soup(ARCHIVE_URL)
    if not soup:
        return []
    
    links = []
    for a in soup.find_all("a", href=re.compile(rf"/loi/{JOURNAL_CODE}/group/d\d+\.y\d+")):
        href = a["href"]
        full_url = urljoin(BASE_URL, href)
        links.append(full_url)
    
    links = list(set(links))
    links.sort(reverse=True)
    return links


def get_issue_links_from_year(year_url):
    """从年份页面提取所有卷期链接"""
    soup = get_soup(year_url)
    if not soup:
        return []
    
    issue_links = []
    # 查找所有卷期链接 /toc/pi/09/02
    for a in soup.find_all("a", class_="loi-volume__issue-dot"):
        href = a.get("href")
        if href:
            full_url = urljoin(BASE_URL, href)
            issue_links.append(full_url)
    
    return issue_links

def extract_pdfs_from_issue(issue_url):
    """从指定卷期页面提取所有PDF链接"""
    soup = get_soup(issue_url)
    if not soup:
        return []
    
    pdfs = []
    
    # 查找所有文章条目
    article_items = soup.find_all("div", class_="issue-item")
    if not article_items:
        article_items = soup.find_all("li", class_="issue-item")
    
    print(f"  找到 {len(article_items)} 个文章条目")
    
    for item in article_items:
        article_id = ""
        pdf_url = ""
        title = "无标题"
        author = "无作者"
        
        pdf_links = item.find_all("a", class_="issue-item__btn")
        for pdf_link in pdf_links:
            href = pdf_link.get("href", "")
            if "/doi/epdf/" in href:
                print(f"    找到PDF链接: {href}")
                doi_match = re.search(r"/doi/epdf/(10\.\d+/[^\s]+)", href)
                if doi_match:
                    article_id = doi_match.group(1)
                    pdf_url = f"{BASE_URL}doi/pdf/{article_id}?download=true"
                    print(f"    提取的article_id: {article_id}")
                else:
                    print(f"    正则匹配失败，尝试直接提取")
                    article_id = href.replace("/doi/epdf/", "")
                    pdf_url = f"{BASE_URL}doi/pdf/{article_id}?download=true"
                    print(f"    直接提取的article_id: {article_id}")
                break
        
        title_elem = item.find("a", class_="issue-item__title")
        if not title_elem:
            title_elem = item.find("h5", class_="issue-item__title")
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        author_elem = item.find("div", class_="issue-item__loa")
        if author_elem:
            author = author_elem.get_text(strip=True)
        
        if pdf_url:
            pdfs.append({
                "article_id": article_id,
                "title": title,
                "author": author,
                "issue_url": issue_url,
                "pdf_url": pdf_url
            })
    
    return pdfs

def main():
    print("开始爬取过刊PDF链接...")
    
    try:
        existing_issue_urls = set()
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_issue_urls.add(row['issue_url'])
            print(f"已找到现有CSV文件，包含 {len(existing_issue_urls)} 个已爬取的期号")
        
        year_urls = get_all_year_links()
        if not year_urls:
            print("未找到任何年份URL")
            return
        
        print(f"找到 {len(year_urls)} 个年份需要检查")
        
        all_issue_urls = []
        for year_url in year_urls:
            print(f"获取年份页面: {year_url}")
            issue_links = get_issue_links_from_year(year_url)
            print(f"  该年份包含 {len(issue_links)} 个期号")
            all_issue_urls.extend(issue_links)
        
        if not all_issue_urls:
            print("未找到任何期号URL")
            return
        
        print(f"共找到 {len(all_issue_urls)} 个期号")
        
        new_issue_urls = []
        for issue_url in all_issue_urls:
            if issue_url not in existing_issue_urls:
                new_issue_urls.append(issue_url)
        
        if not new_issue_urls:
            print("没有发现新的期号，爬取结束")
            return
        
        print(f"发现 {len(new_issue_urls)} 个新期号需要爬取")
        
        all_pdfs = []
        for issue_url in new_issue_urls:
            print(f"爬取期号: {issue_url}")
            pdfs = extract_pdfs_from_issue(issue_url)
            print(f"  该期包含 {len(pdfs)} 篇PDF")
            all_pdfs.extend(pdfs)
        
        if not all_pdfs:
            print("未找到任何新的PDF链接")
            return
        
        file_exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if not file_exists:
                w.writeheader()
            w.writerows(all_pdfs)
        
        print(f"爬取完成！共爬取了 {len(all_pdfs)} 篇新文章。")
        print(f"结果已保存到 {CSV_FILE}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()