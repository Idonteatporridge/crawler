import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import os

BASE_URL = "http://gl.hmc.edu.cn"
LIST_URL = "http://gl.hmc.edu.cn/jlist.asp"
CSV_FILE = "gl_hmc_edu_all_pdfs.csv"
CSV_FIELDS = ["article_id", "title", "year", "issue", "volume", "pdf_url"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_soup(url, data=None):
    """获取指定URL的BeautifulSoup对象，支持GET和POST请求"""
    try:
        if data:
            r = requests.post(url, data=data, headers=headers, timeout=20)
        else:
            r = requests.get(url, headers=headers, timeout=20)
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"获取页面失败 {url}: {e}")
        return None

# 获取所有年份和期数的组合
def get_all_year_issue_combinations():
    """从页面中提取所有可用的年份和期数组合"""
    soup = get_soup(LIST_URL)
    if not soup:
        return []
    
    combinations = []
    
    # 查找年份下拉菜单
    year_select = soup.find("select", {"name": "y_id"})
    if not year_select:
        print("未找到年份下拉菜单")
        return []
    
    # 查找期数下拉菜单
    issue_select = soup.find("select", {"name": "p_id"})
    if not issue_select:
        print("未找到期数下拉菜单")
        return []
    
    # 提取所有年份选项
    year_options = []
    for year_opt in year_select.find_all("option"):
        year_value = year_opt["value"]
        year_text = year_opt.get_text(strip=True)
        year_options.append((year_value, year_text))
    
    # 提取所有期数选项
    issue_options = []
    for issue_opt in issue_select.find_all("option"):
        issue_value = issue_opt["value"]
        issue_text = issue_opt.get_text(strip=True)
        issue_options.append((issue_value, issue_text))
    
    # 生成所有组合
    for year_val, year_txt in year_options:
        for issue_val, issue_txt in issue_options:
            combinations.append({
                "year_value": year_val,
                "year_text": year_txt,
                "issue_value": issue_val,
                "issue_text": issue_txt
            })
    
    return combinations

# 从指定年份和期数提取PDF链接
def extract_pdfs_from_issue(year_value, year_text, issue_value, issue_text):
    """从指定年份和期数提取所有PDF链接"""
    # 构造表单数据
    data = {
        "y_id": year_value,
        "p_id": issue_value,
        "submitbutton": "查询"
    }
    
    soup = get_soup(LIST_URL, data)
    if not soup:
        return []
    
    pdfs = []
    
    # 提取卷号信息
    volume = "未知"
    title_div = soup.find("div", class_="title")
    if title_div:
        title_text = title_div.get_text(strip=True)
        volume_match = re.search(r"(\d+)卷", title_text)
        if volume_match:
            volume = volume_match.group(1)
    
    # 查找所有PDF下载链接
    for li in soup.select("div.ak_nr_list ul.list li"):
        # 提取PDF链接
        pdf_a_tags = li.find_all("a", href=re.compile(r"\.pdf$"))
        if not pdf_a_tags:
            continue
        
        # 使用第一个PDF链接
        pdf_href = pdf_a_tags[0]["href"]
        full_pdf_url = urljoin(BASE_URL, pdf_href)
        
        # 提取文章标题
        title = "无标题"
        span_tag = li.find("span", style=re.compile(r"margin:0"))
        if span_tag:
            title = span_tag.get_text(strip=True) or "无标题"
        else:
            # 尝试从其他位置提取标题
            text_content = li.get_text(strip=True)
            if text_content:
                # 去除PDF文件名部分
                title = re.sub(r"upload/files/\d+\.pdf", "", text_content).strip() or "无标题"
        
        # 生成文章ID
        article_id = f"{year_text}_{issue_text}_{len(pdfs) + 1}"
        
        pdfs.append({
            "article_id": article_id,
            "title": title,
            "year": year_text,
            "issue": issue_text,
            "volume": volume,
            "pdf_url": full_pdf_url
        })
    
    return pdfs

# 主程序
def main():
    print("开始爬取过刊PDF链接...")
    
    # 检查CSV文件是否存在，提取已爬取的文章ID
    existing_article_ids = set()
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_article_ids.add(row["article_id"])
        print(f"已找到现有CSV文件，跳过 {len(existing_article_ids)} 篇已爬取的文章")
    
    # 获取所有年份和期数组合
    combinations = get_all_year_issue_combinations()
    if not combinations:
        print("未找到任何年份和期数组合")
        return
    
    print(f"找到 {len(combinations)} 个年份和期数组合")
    
    # 爬取每个组合的文章信息
    all_pdfs = []
    total_new_articles = 0
    
    for combo in combinations:
        year_val = combo["year_value"]
        year_txt = combo["year_text"]
        issue_val = combo["issue_value"]
        issue_txt = combo["issue_text"]
        
        print(f"爬取: {year_txt}年 第{issue_txt}期")
        pdfs = extract_pdfs_from_issue(year_val, year_txt, issue_val, issue_txt)
        
        # 筛选出新的文章
        new_pdfs = []
        for pdf in pdfs:
            if pdf["article_id"] not in existing_article_ids:
                new_pdfs.append(pdf)
                existing_article_ids.add(pdf["article_id"])
        
        print(f"  该期包含 {len(pdfs)} 篇PDF，其中 {len(new_pdfs)} 篇是新的")
        all_pdfs.extend(new_pdfs)
        total_new_articles += len(new_pdfs)
    
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
    
    print(f"爬取完成！共爬取了 {total_new_articles} 篇新文章")
    print(f"结果已保存到 {CSV_FILE}")

if __name__ == "__main__":
    main()