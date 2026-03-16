import os
import re
import time
import requests
import csv
from bs4 import BeautifulSoup

BASE = "http://xuebao.bjmu.edu.cn"
VOL_ROOT = f"{BASE}/CN/article/showOldVolumn.do"
VOL_PREFIX = f"{BASE}/CN/volumn/volumn_"
PDF_TEMPLATE = f"{BASE}/CN/article/downloadArticleFile.do?attachType=PDF&id={{}}"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# CSV配置
CSV_FILE = "pku_medical_papers_2.csv"
CSV_FIELDS = ["article_id", "year", "issue_url", "vol_id", "pdf_url"]


def get_all_volumn_ids():
    """从 showOldVolumn.do 获取所有 volumn_xxx.shtml 的 ID"""
    print("🔍 获取卷期列表…")

    html = requests.get(VOL_ROOT, headers=HEADERS).text
    ids = re.findall(r"volumn_(\d+)\.shtml", html)

    ids = sorted(list(set(ids)), key=lambda x: int(x))
    print(f"✔ 找到 {len(ids)} 个卷期")
    return ids


def parse_volumn(vol_id):
    """解析某一期页面，直接提取 onclick 参数"""
    issue_url = VOL_PREFIX + f"{vol_id}.shtml"
    print(f"\n📖解析卷期：{issue_url}")

    html = requests.get(issue_url, headers=HEADERS).text

    # 匹配 onclick="lsdy1('PDF','10267','http://xxx','2011','1202');"
    pattern = r"lsdy1\('PDF','(\d+)','[^']+','(\d+)','(\d+)'\)"
    results = re.findall(pattern, html)

    pdf_entries = []
    for article_id, year, _ in results:  # 不再需要issue参数
        pdf_url = PDF_TEMPLATE.format(article_id)
        pdf_entries.append({
            "article_id": article_id,
            "year": year,
            "issue_url": issue_url,  # 存储完整的期号URL
            "vol_id": vol_id,
            "pdf_url": pdf_url
        })

    print(f"  本期文章数：{len(pdf_entries)}")
    return pdf_entries


def main():
    vol_ids = get_all_volumn_ids()
    
    # 检查已有的CSV文件，获取已爬取的issue_url
    existing_issue_urls = set()
    csv_file_exists = os.path.isfile(CSV_FILE)
    
    if csv_file_exists:
        with open(CSV_FILE, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            existing_issue_urls = {row["issue_url"] for row in reader}
    
    # 准备写入CSV的新数据
    all_new_entries = []
    
    for vid in vol_ids:
        # 生成当前期号的URL
        current_issue_url = VOL_PREFIX + f"{vid}.shtml"
        
        # 检查该期号是否已爬取
        if current_issue_url in existing_issue_urls:
            print(f"\n🔍 期号 {vid} ({current_issue_url}) 已爬取，跳过")
            continue
        
        # 解析新的期号
        entries = parse_volumn(vid)
        
        if entries:
            all_new_entries.extend(entries)
            print(f"  本期新文章数：{len(entries)}")
        else:
            print(f"  本期无文章")
        
        time.sleep(0.5)
    
    # 如果没有新数据，直接返回
    if not all_new_entries:
        print("\n没有新的期号需要爬取。")
        return
    
    # 写入CSV文件
    with open(CSV_FILE, "a" if csv_file_exists else "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        
        # 如果是新文件，写入表头
        if not csv_file_exists:
            writer.writeheader()
        
        # 写入新数据
        writer.writerows(all_new_entries)
    
    print(f"\n🎯 完成爬取，共保存 {len(all_new_entries)} 条新记录到 {CSV_FILE}")


if __name__ == "__main__":
    main()
