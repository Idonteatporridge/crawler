#!/usr/bin/env python3
# -*- coding=utf-8 -*-
"""
验证PDF文件是否成功上传到腾讯云COS，并检查无效PDF（HTML页面）
"""
import os
import sys
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from qcloud_cos import CosServiceError

# 加载配置
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import access_key, secret_key, bucket_name, region_name, COS_PREFIX

# 配置日志
logging.basicConfig(level=logging.INFO, stream=sys.stdout, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_valid_pdf(content):
    """验证内容是否为有效的PDF文件"""
    if not content or len(content) < 10:
        return False
    
    # 检查PDF文件头（PDF文件以%PDF开头）
    if content[:4] != b'%PDF':
        return False
    
    return True

# 全局COS客户端实例
cos_client = None

# 初始化COS客户端的函数
def init_cos_client():
    """初始化并返回COS客户端实例"""
    global cos_client
    if cos_client is None:
        config = CosConfig(
            Region=region_name,
            SecretId=access_key,
            SecretKey=secret_key,
        )
        cos_client = CosS3Client(config)
    return cos_client

def check_invalid_pdfs():
    """检查COS中的无效PDF文件"""
    try:
        # 初始化COS客户端
        cos_client = init_cos_client()
        
        print(f"正在检查COS中的无效PDF文件...")
        print(f"Bucket: {bucket_name}")
        print(f"Region: {region_name}")
        print(f"Prefix: {COS_PREFIX}")
        print("-" * 60)
        
        # 列出所有上传的PDF文件
        all_objects = []
        marker = ""
        
        # 增加MaxKeys到最大值（2000）以减少API调用次数
        while True:
            response = cos_client.list_objects(
                Bucket=bucket_name,
                Prefix=COS_PREFIX,
                Marker=marker,
                MaxKeys=2000  # 每次最多获取2000个对象（COS API最大值）
            )
            
            # 处理对象列表
            if 'Contents' in response:
                all_objects.extend(response['Contents'])
            
            # 检查是否有更多对象
            if 'IsTruncated' in response and response['IsTruncated'] == 'true':
                marker = response['NextMarker']
            else:
                break
        
        # 统计结果
        total_files = len(all_objects)
        print(f"总共在COS中发现 {total_files} 个PDF文件")
        print("-" * 60)
        
        # 检查无效PDF的函数（用于多线程）
        def check_single_pdf(obj):
            """检查单个PDF文件是否有效"""
            key = obj['Key']
            size = int(obj['Size'])
            
            try:
                # 只下载文件的前10个字节来检查PDF文件头，而不是整个文件
                response = cos_client.get_object(
                    Bucket=bucket_name,
                    Key=key,
                    Range='bytes=0-9'  # 只下载前10个字节
                )
                content = response['Body'].read()
                
                # 验证是否为有效的PDF文件
                if not is_valid_pdf(content):
                    # 提取期刊名称
                    parts = key.split('/')
                    journal_name = parts[1] if len(parts) >= 3 else "未知"
                    
                    return {
                        'key': key,
                        'size': size,
                        'journal': journal_name
                    }
                
            except Exception as e:
                print(f"\n获取文件 {key} 时出错: {e}")
            return None
        
        # 检查无效PDF（使用多线程）
        invalid_pdfs = []
        invalid_by_journal = {}
        
        print(f"开始检查无效PDF文件 (使用多线程，可能需要较长时间)...")
        print("进度: 0 / {total_files}".format(total_files=total_files), end="")
        
        # 使用线程池并行检查PDF文件
        with ThreadPoolExecutor(max_workers=20) as executor:  # 20个线程
            # 提交所有任务
            futures = {executor.submit(check_single_pdf, obj): obj for obj in all_objects}
            
            # 处理结果
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                
                # 更新进度（减少更新频率）
                if (i + 1) % 100 == 0 or (i + 1) == total_files:
                    print(f"\r进度: {i + 1} / {total_files}", end="")
                    sys.stdout.flush()
                
                if result:
                    invalid_pdfs.append(result)
                    journal_name = result['journal']
                    
                    # 更新期刊统计
                    if journal_name not in invalid_by_journal:
                        invalid_by_journal[journal_name] = 0
                    invalid_by_journal[journal_name] += 1
        
        print()  # 换行
        print("-" * 60)
        
        # 打印无效PDF统计
        print("无效PDF文件统计:")
        print(f"总共发现 {len(invalid_pdfs)} 个无效PDF文件")
        print(f"无效率: {len(invalid_pdfs)/total_files*100:.2f}%")
        print()
        
        # 按期刊统计无效PDF
        print("各期刊无效PDF统计:")
        for journal, count in sorted(invalid_by_journal.items(), key=lambda x: x[1], reverse=True):
            print(f"{journal}: {count} 个无效文件")
        print("-" * 60)
        
        # 询问是否删除无效PDF
        if invalid_pdfs:
            delete_choice = input("是否删除所有无效PDF文件？(y/n): ").strip().lower()
            
            if delete_choice == 'y':
                print("\n开始删除无效PDF文件...")
                deleted_count = 0
                
                for pdf in invalid_pdfs:
                    try:
                        cos_client.delete_object(
                            Bucket=bucket_name,
                            Key=pdf['key']
                        )
                        deleted_count += 1
                        print(f"已删除: {pdf['key']} ({pdf['size']:,} bytes)")
                    except Exception as e:
                        print(f"删除 {pdf['key']} 时出错: {e}")
                
                print(f"\n删除完成！共删除 {deleted_count} 个无效PDF文件")
            else:
                print("未删除任何无效PDF文件")
        
        print("-" * 60)
        print("检查完成！")
        
        return True
        
    except ImportError:
        print("错误: 未安装qcloud-cos-python-sdk-v5库，请运行 'pip install -U cos-python-sdk-v5'")
        return False
    except CosServiceError as e:
        print(f"COS服务错误: {e}")
        return False
    except Exception as e:
        print(f"检查过程中发生错误: {e}")
        return False

def verify_cos_uploads():
    """验证COS上传结果"""
    try:
        # 初始化COS客户端
        cos_client = init_cos_client()
        
        print(f"正在验证COS上传结果...")
        print(f"Bucket: {bucket_name}")
        print(f"Region: {region_name}")
        print(f"Prefix: {COS_PREFIX}")
        print("-" * 60)
        
        # 列出所有上传的PDF文件
        all_objects = []
        marker = ""
        
        # 增加MaxKeys到最大值（2000）以减少API调用次数
        while True:
            response = cos_client.list_objects(
                Bucket=bucket_name,
                Prefix=COS_PREFIX,
                Marker=marker,
                MaxKeys=2000  # 每次最多获取2000个对象（COS API最大值）
            )
            
            # 处理对象列表
            if 'Contents' in response:
                all_objects.extend(response['Contents'])
            
            # 检查是否有更多对象
            if 'IsTruncated' in response and response['IsTruncated'] == 'true':
                marker = response['NextMarker']
            else:
                break
        
        # 统计结果
        total_files = len(all_objects)
        print(f"总共上传了 {total_files} 个PDF文件到COS")
        print("-" * 60)
        
        # 按期刊分类统计
        journal_stats = {}
        for obj in all_objects:
            key = obj['Key']
            # 从路径中提取期刊名称
            parts = key.split('/')
            if len(parts) >= 3:
                journal_name = parts[1]
                if journal_name not in journal_stats:
                    journal_stats[journal_name] = 0
                journal_stats[journal_name] += 1
        
        # 打印各期刊上传统计
        print("各期刊上传统计:")
        for journal, count in sorted(journal_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"{journal}: {count} 个文件")
        print("-" * 60)
        
        # 验证文件大小
        print("验证文件大小 (随机抽查5个文件):")
        sample_size = min(5, total_files)
        import random
        sampled_objects = random.sample(all_objects, sample_size)
        
        for obj in sampled_objects:
            key = obj['Key']
            size = obj['Size']
            last_modified = obj['LastModified']
            
            print(f"文件: {key}")
            print(f"  大小: {int(size):,} bytes")
            print(f"  最后修改时间: {last_modified}")
            
            # 尝试获取文件元数据，验证文件是否可访问
            try:
                head_response = cos_client.head_object(
                    Bucket=bucket_name,
                    Key=key
                )
                print(f"  状态: 可访问 ✓")
            except CosServiceError as e:
                print(f"  状态: 访问失败 ✗ - {e}")
            print()
        
        # 生成访问URL
        print("访问URL示例:")
        if all_objects:
            example_obj = all_objects[0]
            example_key = example_obj['Key']
            cos_url = f"https://{bucket_name}.cos.{region_name}.myqcloud.com/{example_key}"
            print(f"示例URL: {cos_url}")
            print("注意: 请确保文件权限设置为公开可读，否则需要签名访问")
        
        print("-" * 60)
        print("验证完成！")
        print(f"总结: 共上传 {total_files} 个PDF文件到COS，分布在 {len(journal_stats)} 个期刊目录中")
        
        return True
        
    except ImportError:
        print("错误: 未安装qcloud-cos-python-sdk-v5库，请运行 'pip install -U cos-python-sdk-v5'")
        return False
    except CosServiceError as e:
        print(f"COS服务错误: {e}")
        return False
    except Exception as e:
        print(f"验证过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    # 解析命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--check-invalid":
        check_invalid_pdfs()
    else:
        verify_cos_uploads()
        print()
        print("提示: 运行 'python verify_cos_uploads.py --check-invalid' 可以检查并删除无效PDF文件")