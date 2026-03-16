# 豌豆数据源PDF爬虫项目

本项目是一个用于爬取医学期刊PDF文献的爬虫系统，支持从多个医学期刊网站下载PDF文件并上传到云存储。

## 项目结构

- `pdf_downloader_freeip.py` - 使用免费代理的PDF下载器
- `pdf_downloader_chargeip.py` - 使用付费代理的PDF下载器
- `pdf_downloader_noipchange.py` - 不使用代理的PDF下载器
- `config.py` - 配置文件
- `verify_cos_uploads.py` - 验证COS上传
- `sync_cos_to_psql.py` - 同步COS到PostgreSQL
- `ip_verify.py` 和 `ip_verify_free.py` - IP验证工具
- `check_csv_headers.py` - CSV文件头检查工具
- `delete_cos_pdfs.py` - 删除COS上的PDF文件
- 各个期刊目录 - 包含对应期刊的爬虫脚本和PDF链接CSV文件
- `other/` - 其他相关工具和脚本

## 功能特点

- **多期刊支持**：包含多个医学期刊的爬虫脚本
- **代理支持**：支持免费代理和付费代理
- **云存储集成**：支持将PDF上传到对象存储
- **日志记录**：详细的日志记录功能
- **错误处理**：完善的错误处理机制
- **测试模式**：支持测试模式，限制下载数量

## 环境要求

- Python 3.7+
- 依赖包：
  - requests
  - beautifulsoup4
  - lxml
  - tqdm
  - cos-python-sdk-v5 (腾讯云COS SDK)

## 使用方法

### 1. 配置环境

```bash
# 安装依赖
pip install -r requirements.txt

# 配置config.py文件
# 设置COS存储桶信息、代理设置等
```

### 2. 运行PDF下载器

```bash
# 使用免费代理下载
python pdf_downloader_freeip.py

# 使用付费代理下载
python pdf_downloader_chargeip.py

# 不使用代理下载
python pdf_downloader_noipchange.py
```

### 3. 运行单个期刊爬虫

进入对应期刊目录，运行爬虫脚本：

```bash
cd 中华医学杂志（英文版）
python crawler.py
```

## 配置说明

在 `config.py` 文件中，可以配置以下参数：

- `storage_type` - 存储类型（"cos" 或 "local"）
- `bucket_name` - COS存储桶名称
- `cos_secret_id` - COS Secret ID
- `cos_secret_key` - COS Secret Key
- `cos_region` - COS区域
- `PROXY_ENABLED` - 是否启用代理
- `PROXY_UPDATE_INTERVAL` - 代理更新间隔
- `TEST_MODE` - 是否启用测试模式
- `TEST_LIMIT_PER_CSV` - 测试模式下每个CSV文件的下载限制

## 日志记录

日志文件存储在 `log/` 目录下，命名格式为 `pdf_downloader_log_YYYYMMDD_HHMMSS.txt`。

## 注意事项

- 请遵守各期刊网站的robots.txt规则
- 合理设置下载间隔，避免对目标网站造成过大压力
- 本项目仅用于学术研究目的，请勿用于商业用途

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License