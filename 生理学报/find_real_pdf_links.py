import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import csv
import os

# 配置
CSV_FILE = "all_pdfs.csv"
TEST_LIMIT = 3  # 测试前3个链接
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def find_real_pdf_link(pdf_url):
    """从pdf.php链接中找出真实的PDF下载链接"""
    print(f"\n查找真实PDF链接: {pdf_url}")
    
    try:
        # 发送GET请求获取HTML内容
        response = requests.get(pdf_url, headers=HEADERS, timeout=10, allow_redirects=True)
        
        # 检查HTTP状态码
        status_code = response.status_code
        print(f"  HTTP状态码: {status_code}")
        
        if status_code != 200:
            print(f"  错误: 链接返回非200状态码")
            return None
        
        # 检查Content-Type
        content_type = response.headers.get('Content-Type', '')
        print(f"  Content-Type: {content_type}")
        
        # 如果已经是PDF，直接返回
        if 'application/pdf' in content_type:
            print(f"  ✓ 已经是有效PDF链接")
            return pdf_url
        
        # 如果是HTML，尝试从中提取PDF链接
        if 'text/html' in content_type:
            print("  正在从HTML页面中提取PDF链接...")
            
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 查找可能的PDF链接
            base_url = response.url
            
            # 方法1: 查找所有a标签中的PDF链接
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(base_url, href)
                
                if full_url.endswith(".pdf"):
                    print(f"  ✓ 找到PDF链接: {full_url}")
                    return full_url
            
            # 方法2: 查找所有iframe标签中的PDF链接
            for iframe in soup.find_all("iframe", src=True):
                src = iframe["src"]
                full_url = urljoin(base_url, src)
                
                if full_url.endswith(".pdf"):
                    print(f"  ✓ 找到PDF链接: {full_url}")
                    return full_url
            
            # 方法3: 查找所有script标签中的PDF链接
            for script in soup.find_all("script"):
                script_content = script.get_text()
                # 使用正则表达式查找PDF链接
                pdf_matches = re.findall(r'https?://[^"\'\s]+\.pdf', script_content)
                for match in pdf_matches:
                    print(f"  ✓ 找到PDF链接: {match}")
                    return match
            
            # 方法3b: 查找script标签中的location.replace跳转
            for script in soup.find_all("script"):
                script_content = script.get_text()
                # 查找location.replace中的PDF路径 - 已在方法3c中实现
                continue
            
            # 方法3c: 另一种方式查找location.replace跳转
            for script in soup.find_all("script"):
                script_content = script.get_text()
                # 使用更简单的正则表达式
                pdf_path = re.search(r"location\.replace\('([^']+)\.pdf'\)", script_content)
                if not pdf_path:
                    pdf_path = re.search(r'location\.replace\("([^"]+)\.pdf"\)', script_content)
                
                if pdf_path:
                    full_url = urljoin(base_url, pdf_path.group(1) + ".pdf")
                    print(f"  ✓ 找到PDF链接: {full_url}")
                    return full_url
            
            # 方法4: 查找所有meta refresh标签中的PDF链接
            for meta in soup.find_all("meta", attrs={"http-equiv": "refresh"}):
                content = meta.get("content", "")
                refresh_matches = re.findall(r'url=([^\s"]+)', content)
                for match in refresh_matches:
                    full_url = urljoin(base_url, match)
                    if full_url.endswith(".pdf"):
                        print(f"  ✓ 找到PDF链接: {full_url}")
                        return full_url
            
            # 方法5: 查找所有可能包含PDF链接的元素
            # 查看页面内容的前2000个字符，了解页面结构
            print("  页面内容预览:")
            print(response.text[:2000] + "...")
            
            # 使用正则表达式在整个页面中查找PDF链接
            pdf_matches = re.findall(r'https?://[^"\'\s]+\.pdf', response.text)
            for match in pdf_matches:
                print(f"  ✓ 找到PDF链接: {match}")
                return match
            
            print("  ✗ 未找到PDF链接")
            return None
        
        print(f"  ✗ 未知Content-Type")
        return None
            
    except requests.RequestException as e:
        print(f"  ✗ 错误: {e}")
        return None

def update_csv_with_real_pdf_links():
    """更新CSV文件中的PDF链接为真实的下载链接"""
    if not os.path.exists(CSV_FILE):
        print(f"错误: 找不到文件 {CSV_FILE}")
        return
    
    print(f"开始更新 {CSV_FILE} 中的PDF链接...")
    
    # 读取CSV文件
    rows = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # 更新前N个链接
    updated_count = 0
    for i, row in enumerate(rows):
        if i >= TEST_LIMIT:
            break
            
        pdf_url = row.get("pdf_url", "")
        if not pdf_url:
            print(f"\n第 {i+1} 行: 缺少PDF链接")
            continue
        
        print(f"\n=== 处理第 {i+1} 个链接 ===")
        print(f"标题: {row.get('title', '无标题')}")
        
        real_pdf_url = find_real_pdf_link(pdf_url)
        if real_pdf_url:
            row["pdf_url"] = real_pdf_url
            updated_count += 1
    
    # 保存更新后的CSV文件
    updated_csv_file = "updated_all_pdfs.csv"
    with open(updated_csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n=== 更新完成 ===")
    print(f"处理总数: {TEST_LIMIT}")
    print(f"成功更新: {updated_count}")
    print(f"更新后的文件已保存到: {updated_csv_file}")

def main():
    """主函数"""
    update_csv_with_real_pdf_links()

if __name__ == "__main__":
    main()
