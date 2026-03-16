import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

# 爬虫配置
BASE_URL = "http://www.cjpmr.cn/ch/reader/"
ARCHIVE_URL = "http://www.cjpmr.cn/ch/reader/issue_browser.aspx"
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
    # 查找表格中的期号链接（根据提供的HTML结构，查找id为QueryUI的表格）
    table = soup.find("table", id="QueryUI")
    if not table:
        print("未找到过刊列表表格")
        return []
    
    # 查找所有期号链接
    for a in table.find_all("a", href=re.compile(r"issue_list\.aspx\?year_id=\d+&quarter_id=\d+")):
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
    # 提取年份和期号信息（从URL中）
    year_match = re.search(r"year_id=(\d+)", vol_url)
    quarter_match = re.search(r"quarter_id=(\d+)", vol_url)
    
    year = year_match.group(1) if year_match else "未知"
    issue = quarter_match.group(1) if quarter_match else "未知"
    volume = "未知"  # 新网站结构中未看到卷号信息
    
    # 查找所有PDF链接（修改正则表达式，使其能够匹配包含中文的file_no）
    pdf_a_elements = soup.find_all("a", href=re.compile(r"create_pdf\.aspx\?file_no="))
    print(f"找到 {len(pdf_a_elements)} 个PDF链接")
    
    for pdf_a in pdf_a_elements:
        href = pdf_a["href"]
        # 构建完整的PDF URL
        full_url = urljoin(BASE_URL, href)
        print(f"找到PDF链接: {full_url}")
        
        # 从PDF链接中提取file_no作为article_id（修改正则表达式，使其能够匹配包含中文的file_no）
        file_no_match = re.search(r"file_no=([^&]+)", href)
        if file_no_match:
            article_id = file_no_match.group(1)
            
            # 查找对应的文章标题和作者（从父元素tr中）
            title = "无标题"
            author = "无作者"
            
            # 找到包含该PDF链接的tr元素
            tr_element = pdf_a.find_parent("tr")
            if tr_element:
                # 提取文章信息
                td_elements = tr_element.find_all("td")
                if td_elements:
                    # 根据提供的HTML截图，第二个td包含文章信息
                    info_td = td_elements[1] if len(td_elements) > 1 else td_elements[0]
                    
                    if info_td:
                        # 提取文本内容
                        info_text = info_td.get_text(strip=True)
                        
                        # 清理文本，移除页码信息和链接标记
                        # 移除页码信息（如"2025(3):198-203"）
                        cleaned_text = re.sub(r'^\s*"\d+\(\d+\):\d+-\d+&nbsp;\[', '', info_text)
                        # 移除链接标记和尾部内容
                        cleaned_text = re.sub(r'\]\s*\[\s*\]\s*', '', cleaned_text)
                        # 移除PDF链接部分
                        cleaned_text = re.sub(r'\s*\[\s*.*?create_pdf\.aspx.*?\]\s*', '', cleaned_text)
                        # 移除摘要链接部分
                        cleaned_text = re.sub(r'\s*\[\s*.*?view_abstract\.aspx.*?\]\s*', '', cleaned_text)
                        # 移除HTML实体
                        cleaned_text = cleaned_text.replace('&nbsp;', ' ').strip()
                        
                        # 尝试分割标题和作者
                        if cleaned_text:
                            # 这里可以根据实际文本格式进行调整
                            # 假设标题和作者之间可能有分号等分隔符
                            title = cleaned_text.strip()
                            # 如果有作者信息，可能需要进一步解析
                            # 这里可以根据实际数据格式进行调整
                
                # 添加文章信息到列表
                pdfs.append({
                    "article_id": article_id,
                    "title": title,
                    "author": author,
                    "year": year,
                    "issue": issue,
                    "volume": volume,
                    "pdf_url": full_url
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
                # 从文章信息中构建期号URL（使用新的URL格式）
                vol_url = f"{BASE_URL}issue_list.aspx?year_id={row['year']}&quarter_id={row['issue']}"
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