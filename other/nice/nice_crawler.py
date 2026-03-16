import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from tqdm import tqdm

BASE = "https://www.nice.org.uk"
GUIDANCE_INDEX = "https://www.nice.org.uk/guidance/published?sp=on"#"https://www.nice.org.uk/guidance/published?sp=on&ps=9999"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NICE-GuideCrawler/1.0)"}

DOWNLOAD_FOLDER = "pdfs"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def get_guidance_links_from_index():
    resp = requests.get(GUIDANCE_INDEX, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.select("a[href^='https://www.nice.org.uk/guidance/']"):
        href = a["href"]
        parts = href.split("/")
        if len(parts) == 5 or len(parts) == 4:
            guid = parts[4] if len(parts) >= 5 else parts[-1]
            links.append((guid.lower(), "https://www.nice.org.uk/guidance/" + guid.lower()))
    links = list(set(links))
    print(f"✅ 从目录页解析出 {len(links)} 条 guidance 链接")
    return links

def get_pdf_links_from_guidance(guidance_id, guidance_url):
    try:
        resp = requests.get(guidance_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        pdfs = []
        for a in soup.select("a[href]"):
            href = a["href"]
            if "pdf-" in href or href.lower().endswith(".pdf"):
                if href.startswith("/"):
                    href = BASE + href
                pdfs.append(href)
        return list(set(pdfs))
    except Exception as e:
        print(f"⚠️ 解析 guidance {guidance_id} 页失败: {e}")
        return []

def download_pdf(guidance_id, pdf_url):
    try:
        response = requests.get(pdf_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        # 尝试从 URL 获取文件名
        filename = pdf_url.split("/")[-1].split("?")[0]  # 去掉参数
        # 如果没有 .pdf 后缀，强制加上
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # 避免重复文件名
        filename = f"{guidance_id}_{filename}"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        return filepath
    except Exception as e:
        print(f"⚠️ 下载 PDF 失败: {pdf_url}, {e}")
        return None

def main():
    guidance_links = get_guidance_links_from_index()
    data = []
    for guid, url in tqdm(guidance_links, desc="遍历每个 guidance"):
        pdfs = get_pdf_links_from_guidance(guid, url)
        for p in pdfs:
            filepath = download_pdf(guid, p)
            data.append({
                "Guidance_ID": guid,
                "Guidance_URL": url,
                "PDF_URL": p,
                "PDF_Path": filepath
            })

    df = pd.DataFrame(data)
    df.to_excel("nice_pdf_links_from_index.xlsx", index=False)
    print(f"\n✅ 完成，提取并下载 {len(df)} 个 PDF，保存信息在 nice_pdf_links_from_index.xlsx")

if __name__ == "__main__":
    main()
