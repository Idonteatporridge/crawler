#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import csv
import time
import os
from bs4 import BeautifulSoup

BASE = "https://jms.fudan.edu.cn"
ARCHIVE = f"{BASE}/CN/archive_by_years"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)"}
OUT_CSV = "jms_articles.csv"


def safe_get(url, retries=3, timeout=10):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.encoding = r.apparent_encoding
            if r.status_code == 200:
                return r.text
            else:
                time.sleep(0.5)
        except Exception:
            time.sleep(0.5)
    return ""


def get_all_issue_urls():
    """从 archive_by_years 提取所有 /CN/Yxxxx/Vxx/Ixx 卷期 URL"""
    html = safe_get(ARCHIVE)
    if not html:
        print("无法访问 archive_by_years")
        return []

    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.select("a[href]"):
        href = a["href"].strip()
        # match patterns like /CN/Y2025/V52/I05 or full absolute
        if re.match(r"^/CN/Y\d{4}/V\d+/I\d+$", href):
            urls.add(BASE + href)
        elif re.match(r"^https?://[^/]+/CN/Y\d{4}/V\d+/I\d+$", href):
            urls.add(href)
    urls = sorted(urls)
    print(f"发现 {len(urls)} 个卷期 URL")
    return urls


def parse_issue(issue_url):
    """解析某一期页面，返回 list of dicts with required fields"""
    html = safe_get(issue_url)
    if not html:
        print(f"无法获取期页面: {issue_url}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = []

    # each article node: li with id like art2633
    for li in soup.select("li[id^='art']"):
        art = {}

        # article_id from li id or fallback
        lid = li.get("id", "").strip()
        m = re.match(r"art(\d+)", lid)
        article_id = m.group(1) if m else ""

        # title and detail_url
        title_tag = li.select_one(".j-title-1 a")
        title = title_tag.get_text(strip=True) if title_tag else ""
        detail_url = ""
        if title_tag and title_tag.has_attr("href"):
            detail_href = title_tag["href"].strip()
            detail_url = detail_href if detail_href.startswith("http") else BASE + detail_href if detail_href.startswith("/") else detail_href

        # authors
        authors_tag = li.select_one(".j-author")
        authors = authors_tag.get_text(strip=True) if authors_tag else ""

        # doi: inside .j-volumn-doi .j-doi anchor text (full https://doi.org/...)
        doi = ""
        doi_tag = li.select_one(".j-volumn-doi .j-doi, a.j-doi")
        if doi_tag:
            doi = doi_tag.get_text(strip=True)

        # pdf_url: extract from onclick lsdy1('PDF','2633'...) if present
        pdf_url = ""
        pdf_a = li.find("a", onclick=re.compile(r"lsdy1\(\s*'PDF'"))
        if pdf_a and pdf_a.has_attr("onclick"):
            onclick = pdf_a["onclick"]
            m2 = re.search(r"lsdy1\(\s*'PDF'\s*,\s*'(\d+)'\s*(?:,|\\\))", onclick)
            if m2:
                pdf_id = m2.group(1)
                pdf_url = f"{BASE}/CN/article/downloadArticleFile.do?attachType=PDF&id={pdf_id}"
        # fallback: if no onclick but article_id present, use article_id
        if not pdf_url and article_id:
            pdf_url = f"{BASE}/CN/article/downloadArticleFile.do?attachType=PDF&id={article_id}"

        # prefer explicit article_id from onclick if available
        if not article_id and pdf_a and pdf_a.has_attr("onclick"):
            if m2:
                article_id = m2.group(1)

        # final sanity: if detail_url contains DOI, ensure doi extracted
        if not doi and detail_url:
            mdoi = re.search(r"(https?://doi\.org/[0-9A-Za-z\.\-]+)", detail_url)
            if mdoi:
                doi = mdoi.group(1)

        art["article_id"] = article_id
        art["title"] = title
        art["authors"] = authors
        art["doi"] = doi
        art["detail_url"] = detail_url
        art["pdf_url"] = pdf_url
        art["issue_url"] = issue_url  # 添加期数URL列

        items.append(art)

    return items


def main():
    fieldnames = ["article_id", "title", "authors", "doi", "detail_url", "pdf_url", "issue_url"]
    
    # 1. 检查是否存在现有CSV文件，如果存在则提取已爬取的期数URL
    crawled_issue_urls = set()
    csv_file_valid = False
    
    if os.path.exists(OUT_CSV):
        print(f"检查现有CSV文件: {OUT_CSV}")
        try:
            with open(OUT_CSV, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                # 检查CSV文件的字段是否与当前定义一致
                if set(reader.fieldnames) == set(fieldnames):
                    csv_file_valid = True
                    for row in reader:
                        issue_url = row.get("issue_url", "")
                        if issue_url:
                            crawled_issue_urls.add(issue_url)
                    print(f"  已爬取 {len(crawled_issue_urls)} 个期数的文章")
                else:
                    print(f"  CSV文件字段格式不一致，将重新创建")
        except Exception as e:
            print(f"  读取CSV文件出错: {e}")
            crawled_issue_urls = set()
    
    # 2. 获取网站上所有的期数URL
    print("\n获取网站上所有卷期...")
    all_issue_urls = get_all_issue_urls()
    if not all_issue_urls:
        return
    
    # 3. 筛选出未爬取的新期数
    new_issue_urls = []
    for issue_url in all_issue_urls:
        if issue_url not in crawled_issue_urls:
            new_issue_urls.append(issue_url)
    
    if not new_issue_urls:
        print("\n✅ 没有发现新的卷期，无需爬取")
        return
    
    print(f"\n发现 {len(new_issue_urls)} 个新卷期需要爬取")
    
    # 4. 爬取新期数的文章
    new_articles = []
    for idx, issue in enumerate(new_issue_urls, 1):
        print(f"[{idx}/{len(new_issue_urls)}] 解析 {issue}")
        rows = parse_issue(issue)
        print(f"  本期抓取到 {len(rows)} 篇文章")
        new_articles.extend(rows)
        time.sleep(0.5)
    
    if not new_articles:
        print("\n未抓到任何新文章")
        return
    
    # 5. 去重新爬取的文章
    seen = set()
    unique_new = []
    for a in new_articles:
        key = (a.get("article_id", ""), a.get("detail_url", ""))
        if key in seen:
            continue
        seen.add(key)
        unique_new.append(a)
    
    print(f"\n完成！共提取 {len(unique_new)} 篇新的文章")
    
    # 6. 写入新数据到CSV文件
    file_exists = os.path.exists(OUT_CSV)
    csv_file_valid = False
    
    if file_exists:
        try:
            with open(OUT_CSV, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                # 检查CSV文件是否包含所有必要的字段
                if set(fieldnames).issubset(set(reader.fieldnames)):
                    csv_file_valid = True
                else:
                    print("  CSV文件字段不完整，将重新创建")
        except Exception as e:
            print(f"  检查CSV文件结构出错: {e}，将重新创建文件")
    
    mode = "a" if file_exists and csv_file_valid else "w"
    
    with open(OUT_CSV, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        writer.writerows(unique_new)
    
    print(f"已{'追加' if mode == 'a' else '保存'}: {OUT_CSV}")


if __name__ == "__main__":
    main()
