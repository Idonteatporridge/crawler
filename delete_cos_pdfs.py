#!/usr/bin/env python3
# -*- coding=utf-8 -*-
"""
删除上传到腾讯云COS的PDF文件
"""
import os
import sys
import logging
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

def delete_cos_pdfs(confirm=False, website_names=None):
    """删除COS上的PDF文件"""
    try:
        # 初始化COS客户端
        config = CosConfig(
            Region=region_name,
            SecretId=access_key,
            SecretKey=secret_key,
            # Token 为 None，因为使用的是永久密钥
            # Scheme 默认为 https，可不填
        )
        
        # 创建COS客户端
        cos_client = CosS3Client(config)
        
        # 构建前缀列表
        prefixes = []
        if website_names:
            for website_name in website_names:
                prefix = f"{COS_PREFIX}/{website_name}"
                prefixes.append(prefix)
            print(f"准备删除COS上的PDF文件...")
            print(f"Bucket: {bucket_name}")
            print(f"Region: {region_name}")
            print(f"Websites: {', '.join(website_names)}")
        else:
            prefixes.append(COS_PREFIX)
            print(f"准备删除COS上的PDF文件...")
            print(f"Bucket: {bucket_name}")
            print(f"Region: {region_name}")
            print(f"Prefix: {COS_PREFIX}")
        print("-" * 60)
        
        # 列出所有要删除的PDF文件
        all_objects = []
        
        for prefix in prefixes:
            marker = ""
            print(f"正在列出前缀 '{prefix}' 下的PDF文件...")
            while True:
                response = cos_client.list_objects(
                    Bucket=bucket_name,
                    Prefix=prefix,
                    Marker=marker,
                    MaxKeys=1000  # 每次最多获取1000个对象
                )
                
                # 处理对象列表
                if 'Contents' in response:
                    all_objects.extend(response['Contents'])
                
                # 检查是否有更多对象
                if 'IsTruncated' in response and response['IsTruncated'] == 'true':
                    marker = response['NextMarker']
                    print(f"已找到 {len(all_objects)} 个文件，继续搜索...")
                else:
                    break
        
        total_files = len(all_objects)
        print(f"总共找到 {total_files} 个PDF文件")
        print("-" * 60)
        
        # 安全确认
        if not confirm:
            if website_names:
                print(f"警告: 此操作将删除以下网站的所有PDF文件，不可恢复！")
                for website_name in website_names:
                    print(f"  - {website_name}")
            else:
                print("警告: 此操作将删除所有PDF文件，不可恢复！")
            print("请确认是否要继续删除操作。")
            print("如果要确认删除，请使用 --confirm 参数运行此脚本。")
            print()
            if website_names:
                print(f"示例: python delete_cos_pdfs.py --website {' '.join(website_names)} --confirm")
            else:
                print("示例: python delete_cos_pdfs.py --confirm")
            return False
        
        # 开始删除
        print("开始删除文件...")
        deleted_count = 0
        error_count = 0
        
        for obj in all_objects:
            key = obj['Key']
            try:
                # 删除单个文件
                cos_client.delete_object(
                    Bucket=bucket_name,
                    Key=key
                )
                deleted_count += 1
                print(f"已删除: {key}")
            except CosServiceError as e:
                error_count += 1
                print(f"删除失败: {key} - {e}")
        
        print("-" * 60)
        print(f"删除完成！")
        print(f"成功删除: {deleted_count} 个文件")
        print(f"删除失败: {error_count} 个文件")
        print(f"总计: {total_files} 个文件")
        
        # 验证删除结果
        print("-" * 60)
        print("验证删除结果...")
        
        # 再次列出文件
        remaining_objects = []
        
        for prefix in prefixes:
            marker = ""
            while True:
                response = cos_client.list_objects(
                    Bucket=bucket_name,
                    Prefix=prefix,
                    Marker=marker,
                    MaxKeys=1000
                )
                
                if 'Contents' in response:
                    remaining_objects.extend(response['Contents'])
                
                if 'IsTruncated' in response and response['IsTruncated'] == 'true':
                    marker = response['NextMarker']
                else:
                    break
        
        remaining_count = len(remaining_objects)
        print(f"剩余文件数量: {remaining_count}")
        
        if remaining_count == 0:
            if website_names:
                print(f"✓ 以下网站的所有PDF文件已成功删除！")
                for website_name in website_names:
                    print(f"  - {website_name}")
            else:
                print("✓ 所有PDF文件已成功删除！")
        else:
            print("✗ 仍有文件未删除，请检查上面的错误信息。")
        
        return True
        
    except ImportError:
        print("错误: 未安装qcloud-cos-python-sdk-v5库，请运行 'pip install -U cos-python-sdk-v5'")
        return False
    except CosServiceError as e:
        print(f"COS服务错误: {e}")
        return False
    except Exception as e:
        print(f"删除过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    # 检查命令行参数
    confirm = False
    website_names = None
    
    import argparse
    parser = argparse.ArgumentParser(description='删除COS上的PDF文件')
    parser.add_argument('--confirm', action='store_true', help='确认删除操作')
    parser.add_argument('--website', '-w', type=str, nargs='+', help='指定要删除的网站名称（可指定多个）')
    args = parser.parse_args()
    
    confirm = args.confirm
    website_names = args.website
    
    delete_cos_pdfs(confirm, website_names)