#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能测试脚本
用于测试应用启动时间和模块加载性能
"""

import time
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_module_import_performance():
    """测试模块导入性能"""
    print("=== 模块导入性能测试 ===")
    
    # 测试配置管理器导入
    start_time = time.time()
    import config_manager as cfg
    config_time = time.time() - start_time
    print(f"config_manager 导入耗时: {config_time:.4f}秒")
    
    # 测试主API导入
    start_time = time.time()
    from main_api import Api
    api_time = time.time() - start_time
    print(f"main_api 导入耗时: {api_time:.4f}秒")
    
    # 测试API实例化
    start_time = time.time()
    api_instance = Api()
    instance_time = time.time() - start_time
    print(f"API实例化耗时: {instance_time:.4f}秒")
    
    return config_time + api_time + instance_time

def test_lazy_loading():
    """测试延迟加载性能"""
    print("\n=== 延迟加载性能测试 ===")
    
    from main_api import Api
    api_instance = Api()
    
    # 测试配置延迟加载
    start_time = time.time()
    config = api_instance.config
    config_lazy_time = time.time() - start_time
    print(f"配置延迟加载耗时: {config_lazy_time:.4f}秒")
    
    # 测试OCR服务延迟加载
    start_time = time.time()
    ocr_service = api_instance.ocr_service
    ocr_lazy_time = time.time() - start_time
    print(f"OCR服务延迟加载耗时: {ocr_lazy_time:.4f}秒")
    
    # 测试表格提取器延迟加载
    start_time = time.time()
    table_extractor = api_instance._get_table_extractor()
    table_lazy_time = time.time() - start_time
    print(f"表格提取器延迟加载耗时: {table_lazy_time:.4f}秒")
    
    # 测试文件导出器延迟加载
    start_time = time.time()
    file_exporter = api_instance._get_file_exporter()
    file_lazy_time = time.time() - start_time
    print(f"文件导出器延迟加载耗时: {file_lazy_time:.4f}秒")
    
    return config_lazy_time + ocr_lazy_time + table_lazy_time + file_lazy_time

def main():
    """主测试函数"""
    print("开始性能测试...")
    
    total_start = time.time()
    
    # 测试模块导入
    import_time = test_module_import_performance()
    
    # 测试延迟加载
    lazy_time = test_lazy_loading()
    
    total_time = time.time() - total_start
    
    print(f"\n=== 性能测试总结 ===")
    print(f"模块导入总耗时: {import_time:.4f}秒")
    print(f"延迟加载总耗时: {lazy_time:.4f}秒")
    print(f"测试总耗时: {total_time:.4f}秒")
    
    # 性能评估
    if total_time < 1.0:
        print("✅ 性能优秀: 启动时间小于1秒")
    elif total_time < 2.0:
        print("✅ 性能良好: 启动时间小于2秒")
    elif total_time < 3.0:
        print("⚠️ 性能一般: 启动时间2-3秒")
    else:
        print("❌ 性能较差: 启动时间超过3秒，需要进一步优化")

if __name__ == "__main__":
    main()