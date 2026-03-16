import os
import re
import time
import csv
import requests
from bs4 import BeautifulSoup

BASE = "http://www.fyxzz.cn"
VOL_ROOT = f"{BASE}/CN/article/showOldVolumn.do"
VOL_PREFIX = f"{BASE}/CN/volumn/volumn_"
PDF_TEMPLATE = f"{BASE}/CN/article/downloadArticleFile.do?attachType=PDF&id={{}}"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# 新增：CSV相关配置
CSV_FILE = "法医学杂志_PDF链接.csv"
CSV_FIELDS = ["article_id", "year", "issue_url", "pdf_url"]


def get_all_volumn_ids():
    """从 showOldVolumn.do 抓出所有卷期 ID"""
    print("🔍 正在获取卷期列表…")

    html = requests.get(VOL_ROOT, headers=HEADERS).text

    # 匹配 volumn_XXXX.shtml
    ids = re.findall(r"volumn_(\d+)\.shtml", html)

    ids = sorted(list(set(ids)), key=lambda x: int(x))
    print(f"✔ 找到 {len(ids)} 个卷期")
    return ids


def parse_volumn(vol_id):
    """从某一期页面抓出所有 PDF 下载参数，返回字典列表"""
    issue_url = VOL_PREFIX + f"{vol_id}.shtml"
    print(f"\n📖正在解析卷期：{issue_url}")

    html = requests.get(issue_url, headers=HEADERS).text

    # 匹配 onclick="lsdy1('PDF','20491','http://www.fyxzz.cn','2024','1281')"
    pattern = r"lsdy1\('PDF','(\d+)','[^']+','(\d+)','(\d+)'\)"
    matches = re.findall(pattern, html)

    pdf_items = []
    for article_id, year, issueId in matches:
        pdf_url = PDF_TEMPLATE.format(article_id)
        pdf_items.append({
            "article_id": article_id,
            "year": year,
            "issue_url": issue_url,  # 改为存储卷期URL
            "pdf_url": pdf_url
        })

    print(f"  📄 本期发现文章数：{len(pdf_items)}")
    return pdf_items


def main():
    # 1. 检查是否存在现有CSV文件，如果存在则提取已爬取的卷期URL
    crawled_issue_urls = set()
    csv_file_valid = False
    
    if os.path.exists(CSV_FILE):
        print(f"检查现有CSV文件: {CSV_FILE}")
        try:
            with open(CSV_FILE, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                # 检查CSV文件的字段是否与当前定义一致
                if set(reader.fieldnames) == set(CSV_FIELDS):
                    csv_file_valid = True
                    for row in reader:
                        issue_url = row.get("issue_url", "")
                        if issue_url:
                            crawled_issue_urls.add(issue_url)
                    print(f"  已爬取 {len(crawled_issue_urls)} 个卷期")
                else:
                    print(f"  CSV文件字段格式不一致，将重新创建")
        except Exception as e:
            print(f"  读取CSV文件出错: {e}")
    
    # 2. 获取所有卷期ID
    vol_ids = get_all_volumn_ids()
    if not vol_ids:
        print("❌ 未找到任何卷期")
        return
    
    # 3. 筛选出未爬取的新卷期
    new_vol_ids = []
    for vol_id in vol_ids:
        issue_url = VOL_PREFIX + f"{vol_id}.shtml"
        if issue_url not in crawled_issue_urls:
            new_vol_ids.append(vol_id)
    
    if not new_vol_ids:
        print(f"\n✅ 没有发现新的卷期，无需更新")
        return
    
    print(f"\n发现 {len(new_vol_ids)} 个新卷期需要爬取")
    
    # 4. 遍历新卷期，解析并收集PDF信息
    new_pdf_items = []
    for vid in new_vol_ids:
        pdf_items = parse_volumn(vid)
        new_pdf_items.extend(pdf_items)
        time.sleep(0.5)
    
    if not new_pdf_items:
        print(f"\n❌ 未从新卷期中抓取到任何文章")
        return
    
    print(f"\n共抓取到 {len(new_pdf_items)} 篇新文章")
    
    # 5. 去重（防止同一篇文章出现在多个卷期）
    seen = set()
    unique_new_items = []
    for item in new_pdf_items:
        if item["article_id"] in seen:
            continue
        seen.add(item["article_id"])
        unique_new_items.append(item)
    
    print(f"去重后剩余 {len(unique_new_items)} 篇新文章")
    
    # 6. 写入新数据到CSV文件
    file_exists = os.path.exists(CSV_FILE)
    mode = "w"  # 默认重新创建
    
    if file_exists and csv_file_valid:
        mode = "a"  # 格式对应则追加
        print(f"\n将新数据追加到现有CSV文件: {CSV_FILE}")
    else:
        print(f"\n{CSV_FILE}" + ("存在但格式不对应，将重新创建" if file_exists else "不存在，将创建新文件"))
    
    with open(CSV_FILE, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if mode == "w":
            writer.writeheader()
        writer.writerows(unique_new_items)
    
    print(f"\n✅ 完成！已{'追加' if mode == 'a' else '保存'} {len(unique_new_items)} 篇文章的信息到 {CSV_FILE}")


if __name__ == "__main__":
    main()
