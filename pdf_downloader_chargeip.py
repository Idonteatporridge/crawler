import os
import csv
import requests
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import config
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# 腾讯云COS配置
storage_type = config.storage_type
endpoint_url = config.endpoint_url
access_key = config.access_key
secret_key = config.secret_key
bucket_name = config.bucket_name
region_name = config.region_name

class Logger:
    """日志类，同时输出到终端和文件"""
    def __init__(self, log_file):
        self.terminal = sys.stdout
        self.log_file = open(log_file, "a", encoding="utf-8")
    
    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()  # 立即写入文件
    
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
    
    def close(self):
        if not self.log_file.closed:
            self.log_file.close()

DOWNLOAD_DIR = config.DOWNLOAD_DIR
COS_PREFIX = config.COS_PREFIX

# 测试模式配置
TEST_MODE = config.TEST_MODE
TEST_LIMIT_PER_CSV = config.TEST_LIMIT_PER_CSV

# 超时设置
PDF_DOWNLOAD_TIMEOUT = config.PDF_DOWNLOAD_TIMEOUT

# 代理配置
PROXY_ENABLED = getattr(config, 'PROXY_ENABLED', True)
PROXY_UPDATE_INTERVAL = getattr(config, 'PROXY_UPDATE_INTERVAL', 360)  

# 统计信息
total_links = 0
successful_downloads = 0
failed_downloads = 0

# 线程锁，用于保护全局变量
lock = threading.Lock()

import subprocess
import re

class ProxyManager:
    """代理IP管理器，通过API获取代理IP，每5分钟更换一次"""
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.current_proxy = None  # 当前使用的代理
        self.proxy_expire_time = 0  # 代理过期时间
        self.lock = threading.Lock()
        self.initialization_failed = False  # 标记初始化是否失败
        
        # API配置
        self.api_url = "https://dps.kdlapi.com/api/getdps/?secret_id=o2ccff10ufshqpdl5fbu&signature=6v2g4lu3kts87k874xi93qafvooe9vs1&num=1&sep=1"
        self.username = ""
        self.password = ""
        self.proxy_lifetime = 5 * 60  # 代理IP寿命为5分钟
        
        # 如果启用代理，立即获取第一个代理IP
        if self.enabled:
            self.get_new_proxy()
    
    def get_new_proxy(self):
        """从API获取新的代理IP"""
        print("获取新的代理IP...")
        try:
            # 调用API获取代理IP
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            proxy_ip = response.text.strip()
            
            if not proxy_ip:
                print("警告: API返回空代理IP")
                return False
            
            # 构建代理字符串
            self.current_proxy = f"http://{self.username}:{self.password}@{proxy_ip}"
            
            # 设置过期时间
            self.proxy_expire_time = time.time() + self.proxy_lifetime
            
            # 验证代理是否可用
            if self.verify_proxy():
                print(f"获取代理成功: {proxy_ip}")
                print(f"代理将在 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.proxy_expire_time))} 过期")
                return True
            else:
                print("警告: 代理验证失败，将重新获取")
                return False
        except Exception as e:
            print(f"获取代理失败: {e}")
            return False
    
    def verify_proxy(self):
        """验证代理是否有效"""
        if not self.current_proxy:
            return False
        
        proxies = {
            "http": self.current_proxy,
            "https": self.current_proxy
        }
        
        try:
            # 测试HTTP连接
            response = requests.get("http://httpbin.org/ip", 
                                  proxies=proxies, 
                                  timeout=10, 
                                  headers={'Connection': 'close'})
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
    
    def get_proxy(self):
        """获取可用代理"""
        with self.lock:
            # 如果代理未启用或初始化失败，返回None
            if not self.enabled:
                return None
            
            # 检查代理是否过期或未设置
            if not self.current_proxy or time.time() >= self.proxy_expire_time:
                # 尝试获取新代理
                if not self.get_new_proxy():
                    print("警告: 无法获取有效代理，将不使用代理")
                    return None
            
            return self.current_proxy
    
    def change_proxy(self):
        """强制更换代理IP"""
        with self.lock:
            # 如果代理未启用，返回False
            if not self.enabled:
                return False
            
            # 立即获取新代理
            return self.get_new_proxy()


# 初始化代理管理器
proxy_manager = ProxyManager(enabled=PROXY_ENABLED)





# 创建下载目录
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_pdf_filename(website_name, article_id):
    """生成PDF文件名，规则为：期刊名_article_id"""
    # 统一使用期刊名_article_id格式
    return f"{website_name}_{article_id}.pdf"


def download_pdf_with_browser(url):
    """使用浏览器下载PDF，处理需要人工验证的情况"""
    print(f"使用浏览器下载: {url}")
    
    try:
        # 获取用户的下载目录
        download_dir = os.path.expanduser("~/Downloads")
        print(f"监控下载目录: {download_dir}")
        
        # 获取下载目录中已有的PDF文件列表，用于排除已存在的文件
        existing_pdfs = [f for f in os.listdir(download_dir) if f.endswith('.pdf')]
        existing_pdf_paths = [os.path.join(download_dir, f) for f in existing_pdfs]
        
        # 创建浏览器实例，使用无头模式不显示窗口
        options = uc.ChromeOptions()
        # options.add_argument('--headless')
        
        # 如果启用了代理，设置浏览器代理
        proxy = proxy_manager.get_proxy()
        if proxy:
            print(f"为浏览器设置代理: {proxy}")
            # 解析代理地址
            import urllib.parse
            parsed = urllib.parse.urlparse(proxy)
            proxy_host = parsed.hostname
            proxy_port = parsed.port
            proxy_user = parsed.username
            proxy_pass = parsed.password
            
            # 设置代理认证
            options.add_argument(f'--proxy-server=http://{proxy_host}:{proxy_port}')
            options.add_extension('proxy_auth_plugin.zip')  # 注意：需要预先创建Chrome代理认证插件
        
        driver = uc.Chrome(options=options)

        # 访问PDF下载链接
        driver.get(url)
        
        # 等待页面加载，提示用户进行验证
        print("请完成页面上的验证（如需要）...")
        print("验证完成后，浏览器会自动下载PDF文件...")
        print("请等待文件下载完成，程序将自动处理...")
        
        # 等待用户处理验证和文件下载
        print("按Enter键表示下载完成，或等待30秒自动继续...")
        
        # 设置最大等待时间（秒）
        max_wait_time = 30
        start_time = time.time()
        
        # 监控下载目录，寻找新的PDF文件
        new_pdf_path = None
        while time.time() - start_time < max_wait_time:
            # 获取当前下载目录中的PDF文件列表
            current_pdfs = [f for f in os.listdir(download_dir) if f.endswith('.pdf')]
            current_pdf_paths = [os.path.join(download_dir, f) for f in current_pdfs]
            
            # 找到新出现的PDF文件
            for pdf_path in current_pdf_paths:
                if pdf_path not in existing_pdf_paths:
                    # 等待文件下载完成（文件大小不再变化）
                    time.sleep(1)
                    initial_size = os.path.getsize(pdf_path)
                    time.sleep(1)
                    final_size = os.path.getsize(pdf_path)
                    
                    if final_size == initial_size and final_size > 1000:  # 确保文件已下载完成且不是空文件
                        new_pdf_path = pdf_path
                        break
            
            if new_pdf_path:
                break
            
            time.sleep(2)  # 每3秒检查一次
        
        if not new_pdf_path:
            print("浏览器下载失败: 超时或未检测到新的PDF文件")
            driver.quit()
            return None
        
        print(f"检测到新的PDF文件: {new_pdf_path}")
        
        # 读取PDF文件内容
        with open(new_pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        # 检查文件大小
        if len(pdf_content) < 1000:
            print(f"警告: 下载的文件可能不完整，大小: {len(pdf_content)} bytes")
            # 删除不完整文件
            os.remove(new_pdf_path)
            driver.quit()
            return None
        
        # 删除本地PDF文件
        os.remove(new_pdf_path)
        print(f"已删除本地PDF文件: {new_pdf_path}")
        
        # 关闭浏览器
        driver.quit()
        
        print(f"浏览器下载成功 (本地文件处理): {len(pdf_content)} bytes")
        return pdf_content
        
    except KeyboardInterrupt:
        print("用户中断了下载操作")
        try:
            driver.quit()
        except:
            pass
        return None
    except Exception as e:
        print(f"浏览器下载出错: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

def is_valid_pdf(content):
    """验证内容是否为有效的PDF文件"""
    if not content or len(content) < 10:
        return False
    
    # 检查PDF文件头（PDF文件以%PDF开头）
    if content[:4] != b'%PDF':
        print(f"警告: 文件头不是PDF格式，实际前10字节: {content[:10]}")
        return False
    
    # 检查是否包含HTML标记（可能是错误页面）
    content_str = content[:1000].decode('utf-8', errors='ignore').lower()
    if '<html' in content_str or '<!doctype html' in content_str:
        print("警告: 下载的内容是HTML页面，可能是网站限制提示")
        return False  # 返回False，触发重试和换IP
    
    return True

def detect_download_limit(content):
    """检测是否触发了下载限制"""
    if not content:
        return False
    
    content_str = content.decode('utf-8', errors='ignore').lower()
    
    # 检测限制提示关键词
    limit_keywords = [
        '下载文章数进行适当限制',
        '日下载量',
        '不能再进行下载全文',
        '谢谢您的合作',
        '您本日在本站下载的全文数量',
        'access denied',
        'permission denied',
        'too many requests',
        'rate limit exceeded',
        'download limit exceeded'
    ]
    
    for keyword in limit_keywords:
        if keyword in content_str:
            return True
    
    # 检测是否返回了HTML页面而不是PDF（常见的限制情况）
    if content[:10] in [b'<!DOCTYPE ', b'\r\n<!DOCTYP']:
        return True
    
    return False


def download_pdf_to_memory(url, max_retries=2):
    """下载PDF文件，处理两种不同类型的链接，增加重试机制"""
    retries = 0
    while retries < max_retries:
        try:
            print(f"正在下载: {url} (尝试 {retries + 1}/{max_retries})")
            
            # 发送请求，设置合适的headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # 获取代理IP
            proxy = proxy_manager.get_proxy()
            proxies = {"http": proxy, "https": proxy} if proxy else None
            
            # 使用更精确的超时设置（连接超时15秒，读取超时15秒）
            try:
                # 拆分超时为连接超时和读取超时，避免卡住
                timeout_config = (20, 20)  # (connect_timeout, read_timeout)
                response = requests.get(url, headers=headers, stream=False, 
                                      timeout=timeout_config, 
                                      verify=False, proxies=proxies, 
                                      allow_redirects=True, 
                                     ) 
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"请求出错: {e}")
                # 不再主动更换代理IP，只在代理过期时自动更换
                retries += 1
                if retries < max_retries:
                    print(f"准备重试...")
                continue
            
            # 检查响应是否为PDF
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' not in content_type:
                print(f"警告: 响应Content-Type不是PDF: {content_type}")
            
            # 检查文件大小，确保下载成功
            content_length = len(response.content)
            if content_length < 1000:  # 小于1KB可能是错误页面
                print(f"警告: 下载的文件可能不完整，大小: {content_length} bytes")
                retries += 1
                if retries < max_retries:
                    print(f"准备重试...")
                continue
            
            # 验证是否为有效的PDF文件
            if not is_valid_pdf(response.content):
                print(f"警告: 下载的内容不是有效的PDF文件")
                # 不再主动更换代理IP，只在代理过期时自动更换
                retries += 1
                if retries < max_retries:
                    print(f"准备重试...")
                continue
            
            # 检测是否触发了下载限制
            if detect_download_limit(response.content):
                print(f"警告: 触发了网站下载限制")
                # 不再主动更换代理IP，只在代理过期时自动更换
                retries += 1
                if retries < max_retries:
                    print(f"准备重试... (已尝试 {retries}/{max_retries})")
                continue
            
            print(f"下载成功 (内存): {content_length} bytes")
            return response.content
            
        except requests.exceptions.Timeout as e:
            print(f"下载超时: {e} (超过{PDF_DOWNLOAD_TIMEOUT}秒)")
            retries += 1
            if retries < max_retries:
                print(f"准备重试...")
            continue
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {e}")
            # 对于5xx服务器错误，尝试重试
            if any(error_code in str(e) for error_code in ['500', '501', '502', '503', '504', '505']) and retries < max_retries:
                print(f"服务器错误，准备重试...")
                retries += 1
                continue
            # 对于403 Forbidden错误，使用浏览器下载
            elif '403' in str(e):
                print(f"遇到403 Forbidden错误，尝试使用浏览器下载...")
                # 使用浏览器下载PDF
                pdf_content = download_pdf_with_browser(url)
                if pdf_content:
                    print(f"浏览器下载成功: {len(pdf_content)} bytes")
                    return pdf_content
                else:
                        print("浏览器下载失败")
                        # 不再主动更换代理IP，只在代理过期时自动更换
                        break
            break
        except Exception as e:
            print(f"下载失败: {e}")
            # 不再主动更换代理IP，只在代理过期时自动更换
            break
    
    return None

def check_cos_object_exists(bucket, cos_key):
    """检查COS中是否存在指定的对象"""
    try:
        # 动态导入cos模块，避免未安装时出错
        from qcloud_cos import CosConfig
        from qcloud_cos import CosS3Client
        from qcloud_cos.cos_exception import CosServiceError
        
        # 配置COS客户端
        config = CosConfig(
            Region=region_name,  # 区域
            SecretId=access_key,  # SecretId
            SecretKey=secret_key,  # SecretKey
        )
        
        # 创建COS客户端
        cos_client = CosS3Client(config)
        
        # 使用head_object检查对象是否存在
        cos_client.head_object(
            Bucket=bucket,
            Key=cos_key
        )
        
        # 如果没有抛出异常，说明对象存在
        return True
        
    except CosServiceError as e:
        # 404错误表示对象不存在
        if e.get_status_code() == 404:
            return False
        # 其他错误则视为检查失败
        print(f"检查COS对象时出错: {e}")
        return False
    except Exception as e:
        print(f"检查COS对象时出错: {e}")
        return False

def upload_to_cos_from_memory(content, bucket, cos_key):
    """从内存直接上传到腾讯云COS"""
    # 先检查对象是否已经存在
    if check_cos_object_exists(bucket, cos_key):
        cos_url = f"https://{bucket}.cos.{region_name}.myqcloud.com/{cos_key}"
        print(f"COS中已存在该文件，跳过上传: {cos_url}")
        return cos_url
    
    try:
        # 动态导入cos模块，避免未安装时出错
        from qcloud_cos import CosConfig
        from qcloud_cos import CosS3Client
        
        # 配置COS客户端（根据腾讯云文档正确配置）
        config = CosConfig(
            Region=region_name,  # 区域
            SecretId=access_key,  # SecretId
            SecretKey=secret_key,  # SecretKey
            # Endpoint 不是必填参数，如果不传入，SDK 会自动根据 Region 生成对应的默认域名
        )
        
        # 创建COS客户端
        cos_client = CosS3Client(config)
        
        # 从内存直接上传
        cos_client.put_object(
            Bucket=bucket,
            Body=content,
            Key=cos_key,
            ContentType='application/pdf'  # 明确设置为PDF类型
        )
        
        # 生成正确的COS URL
        cos_url = f"https://{bucket}.cos.{region_name}.myqcloud.com/{cos_key}"
        print(f"上传成功到COS: {cos_url}")
        return cos_url
        
    except Exception as e:
        print(f"上传到COS失败: {e}")
        return None

def process_csv_file(csv_path):
    """处理单个CSV文件中的PDF链接"""
    global total_links, successful_downloads, failed_downloads
    
    print(f"\n处理CSV文件: {csv_path}")
    
    # 获取网站名称（从目录名获取）
    website_name = os.path.basename(os.path.dirname(csv_path))
    
    # CSV文件统计
    csv_total = 0
    csv_success = 0
    csv_failed = 0
    
    # 读取CSV文件
    try:
        # 尝试处理可能的BOM问题
        with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # 打印字段名用于调试
            print(f"CSV字段名: {reader.fieldnames}")
            
            # 检查是否有pdf_url列
            if 'pdf_url' not in reader.fieldnames:
                print(f"错误: CSV文件中没有pdf_url列")
                return
            
            # 检查是否有article_id列
            if 'article_id' not in reader.fieldnames:
                print(f"错误: CSV文件中没有article_id列")
                return
            
            # 测试模式计数器
            test_count = 0
            
            # 处理每一行
            for row in reader:
                # 打印第一行数据用于调试
                if test_count == 0:
                    print(f"第一行数据: {row}")
                
                pdf_url = row.get('pdf_url', '').strip()
                article_id = row.get('article_id', '').strip()
                title = row.get('title', '').strip()
                
                if not pdf_url:
                    print(f"跳过: 没有PDF链接")
                    continue
                    
                if not article_id:
                    print(f"跳过: article_id为空")
                    continue
                
                # 打印article_id值用于调试
                if test_count == 0:
                    print(f"获取到的article_id: '{article_id}'")
                
                # 不再需要哈希查重，因为会通过COS检查文件是否存在
                
                # 生成PDF文件名（期刊名+文章ID）
                pdf_filename = get_pdf_filename(website_name, article_id)
                
                # 生成COS对象键
                cos_key = f"{COS_PREFIX}/{website_name}/{pdf_filename}"
                cos_key = cos_key.replace('//', '/')  # 清理可能的双斜杠
                
                # 增加总链接计数（线程安全）
                with lock:
                    total_links += 1
                csv_total += 1
                
                # 先检查COS中是否已存在该文件
                if check_cos_object_exists(bucket_name, cos_key):
                    cos_url = f"https://{bucket_name}.cos.{region_name}.myqcloud.com/{cos_key}"
                    print(f"COS中已存在该文件，跳过下载和上传: {cos_url}")
                    # 增加成功下载计数（线程安全）
                    with lock:
                        successful_downloads += 1
                    csv_success += 1
                else:
                    # 下载PDF到内存
                    pdf_content = download_pdf_to_memory(pdf_url)
                    
                    if pdf_content:
                        # 直接从内存上传到COS
                        cos_url = upload_to_cos_from_memory(pdf_content, bucket_name, cos_key)
                        
                        if cos_url:
                            # 增加成功下载计数（线程安全）
                            with lock:
                                successful_downloads += 1
                            csv_success += 1
                            pass  # 消息已在upload_to_cos_from_memory函数中打印
                        else:
                            print(f"上传到COS失败")
                            # 上传失败不计入成功统计
                            with lock:
                                failed_downloads += 1
                            csv_failed += 1
                    else:
                        # 增加失败下载计数（线程安全）
                        with lock:
                            failed_downloads += 1
                        csv_failed += 1
                        print(f"下载失败: {pdf_url}")
                
                # 测试模式限制
                if TEST_MODE and test_count >= TEST_LIMIT_PER_CSV - 1:
                    print(f"测试模式: 已完成 {TEST_LIMIT_PER_CSV} 个PDF的测试")
                    break
                
                test_count += 1
                
                # 随机延迟，避免请求过于频繁
                # time.sleep(random.uniform(1, 2))
        
        # 打印CSV文件统计
        print(f"\nCSV文件统计:")
        print(f"总链接数: {csv_total}")
        print(f"成功数: {csv_success}")
        print(f"失败数: {csv_failed}")
        print(f"成功率: {csv_success/csv_total*100:.2f}%" if csv_total > 0 else "成功率: 0.00%")
                
    except Exception as e:
        print(f"处理CSV文件时出错: {e}")

def main():
    """主函数，遍历所有网站目录并处理其中的CSV文件，或处理指定的单个期刊目录"""
    global total_links, successful_downloads, failed_downloads
    
    # 初始化日志目录
    log_dir = "log"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 初始化日志
    log_filename = os.path.join(log_dir, f"pdf_downloader_log_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    sys.stdout = Logger(log_filename)
    
    try:
        # 重置统计信息
        total_links = 0
        successful_downloads = 0
        failed_downloads = 0
        
        print("开始处理PDF下载和上传任务...")
        print(f"日志文件: {log_filename}")
        print(f"存储类型: {storage_type}")
        print(f"存储桶: {bucket_name}")
        print(f"超时设置: {PDF_DOWNLOAD_TIMEOUT}秒")
        print(f"代理功能: {'开启' if PROXY_ENABLED else '关闭'}")
        if PROXY_ENABLED:
            print(f"代理更新间隔: {PROXY_UPDATE_INTERVAL}秒")
        print(f"测试模式: {'开启' if TEST_MODE else '关闭'}")
        if TEST_MODE:
            print(f"测试限制: 每个CSV文件{TEST_LIMIT_PER_CSV}个PDF")
        print("-" * 60)
        
        # 获取当前目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 收集所有CSV文件路径
        csv_files_to_process = []
        
        # 检查是否有命令行参数指定期刊目录
        if len(sys.argv) > 1:
            # 处理指定的多个期刊目录
            journal_dirs = sys.argv[1:]
            print(f"\n指定的期刊目录: {', '.join(journal_dirs)}")
            
            for journal_dir in journal_dirs:
                journal_path = os.path.join(current_dir, journal_dir)
                
                # 检查目录是否存在
                if not os.path.isdir(journal_path):
                    print(f"\n跳过不存在的目录: {journal_dir}")
                    continue
                
                # 检查目录中是否有CSV文件
                csv_files = [f for f in os.listdir(journal_path) if f.endswith('.csv')]
                
                if csv_files:
                    print(f"\n发现目录: {journal_dir}")
                    print(f"包含CSV文件: {len(csv_files)}个")
                    
                    for csv_file in csv_files:
                        csv_path = os.path.join(journal_path, csv_file)
                        csv_files_to_process.append(csv_path)
                else:
                    print(f"\n跳过目录: {journal_dir} (无CSV文件)")
        else:
            # 处理所有期刊目录
            for item in os.listdir(current_dir):
                item_path = os.path.join(current_dir, item)
                
                # 检查是否是目录且不是系统目录
                if os.path.isdir(item_path) and not item.startswith('.') and item not in ['downloaded_pdfs', 'log', 'other']:
                    # 检查目录中是否有CSV文件
                    csv_files = [f for f in os.listdir(item_path) if f.endswith('.csv')]
                    
                    if csv_files:
                        print(f"\n发现目录: {item}")
                        print(f"包含CSV文件: {len(csv_files)}个")
                        
                        for csv_file in csv_files:
                            csv_path = os.path.join(item_path, csv_file)
                            csv_files_to_process.append(csv_path)
                    else:
                        print(f"\n跳过目录: {item} (无CSV文件)")
        
        # 使用线程池处理CSV文件
        if csv_files_to_process:
            # 使用线程池处理CSV文件
            max_workers = min(10, os.cpu_count() * 2)  # 根据CPU核心数设置最大线程数，最多10个
            print(f"\n使用多线程处理，最大线程数: {max_workers}")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务到线程池
                future_to_csv = {executor.submit(process_csv_file, csv_path): csv_path for csv_path in csv_files_to_process}
                
                # 等待所有任务完成
                for future in as_completed(future_to_csv):
                    csv_path = future_to_csv[future]
                    try:
                        future.result()  # 获取结果，捕获异常
                    except Exception as e:
                        print(f"处理CSV文件时出错: {csv_path}, 错误: {e}")
        
        # 打印总体统计信息
        print("\n" + "=" * 60)
        print("总体统计信息:")
        print(f"总链接数: {total_links}")
        print(f"成功数: {successful_downloads}")
        print(f"失败数: {failed_downloads}")
        print(f"成功率: {successful_downloads/total_links*100:.2f}%" if total_links > 0 else "成功率: 0.00%")
        print(f"日志已保存到: {log_filename}")
        print("=" * 60)
    finally:
        # 恢复标准输出并关闭日志文件
        if hasattr(sys.stdout, 'close'):
            sys.stdout.close()
        sys.stdout = sys.__stdout__

if __name__ == "__main__":
    # 显示使用说明
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("使用方法:")
        print("  python pdf_downloader.py                  # 处理所有期刊目录")
        print("  python pdf_downloader.py <期刊目录名>     # 处理指定的单个期刊目录")
        print("  python pdf_downloader.py -h/--help        # 显示帮助信息")
        print("\n示例:")
        print("  python pdf_downloader.py 中华医学超声杂志（电子版）")
        sys.exit(0)
    
    main()