# 腾讯云COS配置:修改成自己的COS配置信息
storage_type = "cos"
endpoint_url = "https://cos.ap-beijing.myqcloud.com"
access_key = ""
secret_key = ""
bucket_name = ""
region_name = "ap-beijing"

# 下载配置
DOWNLOAD_DIR = "downloaded_pdfs"
COS_PREFIX = "pdfs"  # COS存储前缀

# 测试模式配置
TEST_MODE = False  # 设置为True进行测试，每个CSV只下载2个PDF
TEST_LIMIT_PER_CSV = 2  # 每个CSV文件测试的PDF数量

# 超时设置
PDF_DOWNLOAD_TIMEOUT = 20  # 20秒超时

# 下载配置
DOWNLOAD_DIR = "downloaded_pdfs"

# 请求配置
REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
MIN_DELAY = 1  # 最小延迟时间（秒）
MAX_DELAY = 3  # 最大延迟时间（秒）

# 文件命名配置
MAX_TITLE_LENGTH = 50  # 文件名中标题的最大长度

# 日志配置
LOG_LEVEL = "INFO"  # 日志级别：DEBUG, INFO, WARNING, ERROR

# 代理配置
PROXY_ENABLED = True  # 是否启用代理功能
PROXY_UPDATE_INTERVAL = 360  # 代理池更新间隔（秒）