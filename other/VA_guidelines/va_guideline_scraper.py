#!/usr/bin/env python3
"""VA/DoD 臨床指引網站爬蟲。

此腳本會抓取 https://www.healthquality.va.gov/guidelines/ 下的各分類頁面，
整理以下資訊並輸出至 Excel：

1. 分類頁面網址
2. 分類頁面的第一段敘述文字
3. 標題（<h2 class="page-title">）
4. 下載該頁面中「Guideline Links」、「Patient Provider Tools」、「Related Guidelines」底下的所有 PDF，
   並將 PDF 名稱、來源區塊與儲存路徑一併寫入 Excel。

使用方式：
    python va_guideline_scraper.py --output-xlsx ./va_guidelines.xlsx --download-dir ./va_pdfs

依賴：requests、beautifulsoup4、pandas、openpyxl。
"""

from __future__ import annotations

import argparse
import logging
import re
import sys 
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag
from requests import Response
from requests.exceptions import RequestException


BASE_URL = "https://www.healthquality.va.gov/guidelines/"
def normalize_section_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


SECTION_NAME_MAP = {
    normalize_section_label("Guideline Links"): "Guideline Links",
    normalize_section_label("Guidelines"): "Guideline Links",
    normalize_section_label("Patient Provider Tools"): "Patient Provider Tools",
    normalize_section_label("Patient Provider Tool"): "Patient Provider Tools",
    normalize_section_label("Patient/Provider Tools"): "Patient Provider Tools",
    normalize_section_label("Patient/Provider Tool"): "Patient Provider Tools",
    normalize_section_label("Patient-Provider Tools"): "Patient Provider Tools",
    normalize_section_label("Patient-Provider Tool"): "Patient Provider Tools",
    normalize_section_label("Related Guidelines"): "Related Guidelines",
}


@dataclass
class PdfEntry:
    section: str
    name: str
    url: str


@dataclass
class CategoryMetadata:
    url: str
    title: str
    intro: str
    pdfs: List[PdfEntry]


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def fetch_html(session: requests.Session, url: str) -> BeautifulSoup:
    logging.debug("Fetching HTML: %s", url)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(fragment="").geturl()
    if clean.endswith("/"):
        return clean
    if parsed.path and parsed.path.endswith("/"):
        return clean
    if "." in Path(parsed.path).name:
        return clean
    return clean + "/"


def is_category_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc != urlparse(BASE_URL).netloc:
        return False
    if not parsed.path.lower().startswith("/guidelines/"):
        return False
    if parsed.path.lower().endswith(".pdf"):
        return False
    if parsed.path.lower().endswith(".asp"):
        return False
    parts = [part for part in parsed.path.split("/") if part]
    # 期望格式為 guidelines/<領域>/<主題>
    if len(parts) < 3:
        return False
    return True


def extract_category_links(soup: BeautifulSoup) -> List[str]:
    links: List[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()
        if not href:
            continue
        full_url = urljoin(BASE_URL, href)
        if not is_category_url(full_url):
            continue
        normalized = normalize_url(full_url)
        if normalized not in links:
            links.append(normalized)
    logging.info("偵測到 %d 個分類頁面", len(links))
    return links


def extract_title(soup: BeautifulSoup) -> str:
    heading = soup.select_one("h2.page-title")
    if heading:
        title = heading.get_text(strip=True)
        if title:
            return title
    fallback = soup.find("title")
    return fallback.get_text(strip=True) if fallback else ""


def extract_intro_paragraph(soup: BeautifulSoup) -> str:
    heading = soup.select_one("h2.page-title")
    if heading:
        for sibling in heading.next_siblings:
            if isinstance(sibling, str):
                continue
            if sibling.name == "p":
                text = normalize_whitespace(sibling.get_text(separator=" ", strip=True))
                if text:
                    return text
            if sibling.name and sibling.name.startswith("h"):
                break

    main_candidates = [
        "main",
        "article",
        "div.entry-content",
        "div#content",
        "div.region-content",
        "div.content",
    ]
    paragraphs: List[str] = []
    for selector in main_candidates:
        container = soup.select_one(selector)
        if not container:
            continue
        paragraphs = _collect_paragraph_texts(container)
        if paragraphs:
            break
    if not paragraphs:
        paragraphs = _collect_paragraph_texts(soup)
    return paragraphs[0] if paragraphs else ""


def _collect_paragraph_texts(container: Tag) -> List[str]:
    texts: List[str] = []
    for p in container.find_all("p"):
        text = " ".join(p.get_text(separator=" ", strip=True).split())
        if not text:
            continue
        if text.lower().startswith("return to top"):
            continue
        texts.append(text)
    return texts


def extract_pdfs(soup: BeautifulSoup, page_url: str) -> List[PdfEntry]:
    entries: List[PdfEntry] = []
    seen = set()

    def record_entry(section_name: str, link: Tag) -> None:
        href = link.get("href", "").strip()
        if not href:
            return
        full_url = urljoin(page_url, href)
        if not full_url.lower().endswith(".pdf"):
            return
        name = normalize_whitespace(link.get_text())
        if not name:
            name = Path(urlparse(full_url).path).name
        key = (section_name, full_url)
        if key in seen:
            return
        seen.add(key)
        entries.append(PdfEntry(section=section_name, name=name, url=full_url))

    # 先掃描表格結構
    for table in soup.find_all("table"):
        header_candidates = []
        header_candidates.extend(table.find_all("caption"))
        header_candidates.extend(table.find_all("th"))
        found_section: Optional[str] = None
        for header in header_candidates:
            header_text = normalize_whitespace(header.get_text())
            key = normalize_section_label(header_text)
            section_name = SECTION_NAME_MAP.get(key)
            if section_name:
                found_section = section_name
                break
        if found_section:
            for link in table.find_all("a", href=True):
                record_entry(found_section, link)

    # 再補抓標題區塊
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        heading_text = normalize_whitespace(heading.get_text())
        key = normalize_section_label(heading_text)
        section_name = SECTION_NAME_MAP.get(key)
        if not section_name:
            continue
        for sibling in iterate_section_siblings(heading):
            for link in sibling.select("a[href]"):
                record_entry(section_name, link)

    # 針對 cpg-row / three-column 結構
    for row in soup.select("div.cpg-row"):
        header_div = row.select_one("div.cell.header")
        data_div = row.select_one("div.cell.data")
        if not header_div or not data_div:
            continue
        header_text = normalize_whitespace(header_div.get_text())
        key = normalize_section_label(header_text)
        section_name = SECTION_NAME_MAP.get(key)
        if not section_name:
            continue
        for link in data_div.select("a[href]"):
            record_entry(section_name, link)

    # 針對兩欄或三欄布局 (containerCell > cpg-row > cell header/data)
    for container in soup.select("div.containerCell"):
        header_div = container.find("div", class_="cell header")
        data_div = container.find("div", class_="cell data")
        if not header_div or not data_div:
            continue
        header_text = normalize_whitespace(header_div.get_text())
        key = normalize_section_label(header_text)
        section_name = SECTION_NAME_MAP.get(key)
        if not section_name:
            continue
        for link in data_div.find_all("a", href=True):
            record_entry(section_name, link)

    return entries


def iterate_section_siblings(heading: Tag) -> Iterable[Tag]:
    for sibling in heading.next_siblings:
        if isinstance(sibling, str):
            continue
        if sibling.name and re.fullmatch(r"h[1-6]", sibling.name):
            break
        yield sibling


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def slugify(text: str, fallback: str = "category") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return cleaned or fallback


def download_pdf(session: requests.Session, url: str, dest_dir: Path) -> Optional[Path]:
    parsed = urlparse(url)
    cleaned_path = parsed.path.lstrip("/")
    safe_path = cleaned_path or Path(parsed.path).name or "download.pdf"
    relative_parts = Path(parsed.netloc) / Path(safe_path)
    target = dest_dir / relative_parts
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        logging.debug("檔案已存在，略過下載: %s", target)
        return target

    logging.info("下載 PDF: %s", url)
    try:
        with session.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(target, "wb") as fout:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        fout.write(chunk)
        return target
    except RequestException as exc:
        logging.error("下載失敗 %s: %s", url, exc)
        return None


def scrape_category(
    session: requests.Session,
    url: str,
) -> Optional[CategoryMetadata]:
    logging.info("處理分類頁面: %s", url)
    try:
        soup = fetch_html(session, url)
    except RequestException as exc:
        logging.error("無法取得分類頁面 %s: %s", url, exc)
        return None

    title = extract_title(soup)
    intro = extract_intro_paragraph(soup)
    pdfs = extract_pdfs(soup, url)
    return CategoryMetadata(url=url, title=title, intro=intro, pdfs=pdfs)


def write_to_excel(records: List[dict], output_path: Path) -> None:
    df = pd.DataFrame(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
    logging.info("已產出 Excel: %s", output_path)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="抓取 VA/DoD 臨床指引網站資訊")
    parser.add_argument(
        "--output-xlsx",
        default="va_guidelines_metadata.xlsx",
        help="輸出的 Excel 路徑 (預設: va_guidelines_metadata.xlsx)",
    )
    parser.add_argument(
        "--download-dir",
        default="va_guidelines_pdfs",
        help="PDF 下載儲存目錄 (預設: va_guidelines_pdfs)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="測試用：僅處理前 N 個分類",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="顯示更詳細的偵錯訊息",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    configure_logging(args.verbose)

    output_path = Path(args.output_xlsx).expanduser().resolve()
    download_root = Path(args.download_dir).expanduser().resolve()

    session = create_session()

    try:
        index_soup = fetch_html(session, BASE_URL)
    except RequestException as exc:
        logging.error("無法存取主頁 %s: %s", BASE_URL, exc)
        return 1

    category_urls = extract_category_links(index_soup)
    if args.limit is not None:
        category_urls = category_urls[: args.limit]

    all_records: List[dict] = []

    for url in category_urls:
        metadata = scrape_category(session, url)
        if not metadata:
            continue
        if metadata.pdfs:
            for pdf in metadata.pdfs:
                file_path = download_pdf(session, pdf.url, download_root)
                all_records.append(
                    {
                        "category_url": metadata.url,
                        "category_title": metadata.title,
                        "intro_paragraph": metadata.intro,
                        "pdf_section": pdf.section,
                        "pdf_name": pdf.name,
                        "pdf_url": pdf.url,
                        "pdf_local_path": str(file_path) if file_path else "",
                    }
                )
        else:
            all_records.append(
                {
                    "category_url": metadata.url,
                    "category_title": metadata.title,
                    "intro_paragraph": metadata.intro,
                    "pdf_section": "",
                    "pdf_name": "",
                    "pdf_url": "",
                    "pdf_local_path": "",
                }
            )

    if not all_records:
        logging.warning("未取得任何資料，Excel 不會產生。")
        return 0

    write_to_excel(all_records, output_path)
    logging.info("完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())

