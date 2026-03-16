import requests
from bs4 import BeautifulSoup
import csv
import re
import os
from urllib.parse import urljoin

BASE = "https://www.gjkqyxzz.cn"
OLD_VOL_URL = "https://www.gjkqyxzz.cn/CN/article/showOldVolumn.do"


def get_soup(url):
    r = requests.get(url, timeout=10)
    r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")

def get_all_volumn_links():
    print("正在加载全历史过刊列表（创刊至今）→", OLD_VOL_URL)
    soup = get_soup(OLD_VOL_URL)
    if not soup:
        raise Exception("无法访问过刊列表页，请检查网络或网站是否维护")

    vol_links = []

    # 精准定位：所有卷期链接都在 width="90" 的 td 里
    for td in soup.find_all("td", width="90"):
        a = td.find("a", href=re.compile(r"volumn/volumn_\d+\.shtml"))
        if not a:
            continue

        href = a["href"].strip()
        full_url = urljoin(OLD_VOL_URL, href)  # 自动处理 ../
        issue_text = a.get_text(strip=True)

        # 提取日期（如果有）
        date_td = td.find_next_sibling("td")
        date_str = date_td.get_text(strip=True) if date_td else ""

        vol_links.append(full_url)
        print(f"  发现: {issue_text:12} {date_str:12} → {full_url}")

    # 去重 + 按期号倒序（最新在前）
    vol_links = list(set(vol_links))
    vol_links.sort(key=lambda x: int(re.search(r"volumn_(\d+)", x).group(1)), reverse=True)

    print(f"\n成功获取 {len(vol_links)} 个卷期链接（创刊至今全历史）\n")
    return vol_links

def extract_pdfs_from_volumn(vol_url):
    print(f"  → 解析卷期: {vol_url}")
    soup = get_soup(vol_url)
    rows = []

    # onclick="lsdy1('PDF','10267','/CN','2024','404');return false;"
    onclick_items = soup.find_all(attrs={"onclick": True})

    for tag in onclick_items:
        onclick = tag["onclick"]

        m = re.search(
            r"lsdy1\('PDF','(\d+)','([^']*)','(\d+)','(\d+)'\)",
            onclick
        )
        if not m:
            continue

        art_id, basepath, year, issue = m.groups()

        pdf_url = f"{BASE}/CN/article/downloadArticleFile.do?attachType=PDF&id={art_id}"

        title = tag.get_text(strip=True)

        rows.append({
            "article_id": art_id,
            "title": title,
            "year": year,
            "issue": issue,
            "volumn_page": vol_url,
            "pdf_url": pdf_url,
        })

    print(f"    ✓ 共提取 {len(rows)} 篇文章")
    return rows


def main():
    csv_file = "gjkq_all_pdfs.csv"
    fieldnames = ["article_id", "title", "year", "issue", "volumn_page", "pdf_url"]
    
    # 1. 检查是否存在现有CSV文件，如果存在则读取已爬取的卷期链接
    crawled_volumns = set()
    if os.path.exists(csv_file):
        print(f"检查现有CSV文件: {csv_file}")
        try:
            with open(csv_file, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    crawled_volumns.add(row["volumn_page"])
            print(f"  已爬取 {len(crawled_volumns)} 个卷期")
        except Exception as e:
            print(f"  读取CSV文件出错: {e}")
            crawled_volumns = set()
    
    # 2. 获取网站上所有的卷期链接
    print("\n获取网站上所有卷期...")
    all_volumns = get_all_volumn_links()
    print(f"共发现 {len(all_volumns)} 个卷期")
    
    # 3. 筛选出未爬取的新卷期
    new_volumns = [url for url in all_volumns if url not in crawled_volumns]
    
    if not new_volumns:
        print("\n✅ 没有发现新的卷期，无需爬取")
        return
    
    print(f"\n发现 {len(new_volumns)} 个新卷期需要爬取")
    
    # 4. 爬取新卷期的PDF链接
    new_data = []
    for vurl in new_volumns:
        articles = extract_pdfs_from_volumn(vurl)
        new_data.extend(articles)
    
    print(f"\n完成！共提取 {len(new_data)} 篇新的PDF链接")
    
    # 5. 将新数据追加到CSV文件
    if new_data:
        # 检查文件是否存在，决定是否需要写入表头
        file_exists = os.path.exists(csv_file)
        mode = "a" if file_exists else "w"
        
        with open(csv_file, mode, newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_data)
        
        print(f"已{'追加' if file_exists else '保存'}: {csv_file}")


if __name__ == "__main__":
    main()
