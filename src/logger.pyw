#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志系统
提供项目级别的日志记录功能，支持不同级别的日志输出和文件记录
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    """统一日志管理器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logger()
            Logger._initialized = True
    
    def _setup_logger(self):
        """设置日志配置"""
        # 创建日志目录
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 设置日志文件路径
        log_file = log_dir / f"ocr_app_{datetime.now().strftime('%Y%m%d')}.log"
        
        # 创建logger
        self.logger = logging.getLogger('OCR_APP')
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 文件处理器
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # 控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # 设置格式
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # 添加处理器
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str, **kwargs):
        """调试级别日志"""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """信息级别日志"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告级别日志"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """错误级别日志"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """严重错误级别日志"""
        self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """异常日志（包含堆栈信息）"""
        self.logger.exception(message, **kwargs)


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        self.logger = Logger()
    
    def handle_exception(self, func_name: str, exception: Exception, 
                        context: Optional[dict] = None) -> dict:
        """
        统一异常处理
        
        Args:
            func_name: 发生异常的函数名
            exception: 异常对象
            context: 上下文信息
            
        Returns:
            标准化的错误响应
        """
        error_info = {
            'success': False,
            'error_type': type(exception).__name__,
            'error_message': str(exception),
            'function': func_name,
            'timestamp': datetime.now().isoformat()
        }
        
        if context:
            error_info['context'] = context
        
        # 记录异常日志
        self.logger.exception(
            f"异常发生在 {func_name}: {exception}",
            extra={'context': context}
        )
        
        return error_info
    
    def handle_validation_error(self, field: str, value: any, 
                              expected: str) -> dict:
        """
        处理验证错误
        
        Args:
            field: 字段名
            value: 实际值
            expected: 期望值描述
            
        Returns:
            标准化的验证错误响应
        """
        error_info = {
            'success': False,
            'error_type': 'ValidationError',
            'error_message': f'字段 {field} 验证失败',
            'field': field,
            'value': str(value),
            'expected': expected,
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.warning(
            f"验证错误: 字段 {field} = {value}, 期望: {expected}"
        )
        
        return error_info
    
    def create_success_response(self, data: any = None, 
                              message: str = "操作成功") -> dict:
        """
        创建成功响应
        
        Args:
            data: 响应数据
            message: 成功消息
            
        Returns:
            标准化的成功响应
        """
        response = {
            'success': True,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        if data is not None:
            response['data'] = data
        
        return response


def get_logger() -> Logger:
    """获取日志实例"""
    return Logger()


def get_error_handler() -> ErrorHandler:
    """获取错误处理器实例"""
    return ErrorHandler()


# 装饰器：自动异常处理
def handle_exceptions(func_name: str = None):
    """
    异常处理装饰器
    
    Args:
        func_name: 自定义函数名，默认使用实际函数名
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()
            name = func_name or func.__name__
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                return error_handler.handle_exception(name, e, {
                    'args': str(args)[:200],  # 限制长度避免日志过大
                    'kwargs': str(kwargs)[:200]
                })
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # 测试日志系统
    logger = get_logger()
    error_handler = get_error_handler()
    
    logger.info("日志系统测试开始")
    logger.debug("这是调试信息")
    logger.warning("这是警告信息")
    
    # 测试异常处理
    try:
        raise ValueError("测试异常")
    except Exception as e:
        error_response = error_handler.handle_exception("test_function", e)
        print("错误响应:", error_response)
    
    # 测试成功响应
    success_response = error_handler.create_success_response(
        data={"tests": "data"},
        message="测试成功"
    )
    print("成功响应:", success_response)
    
    logger.info("日志系统测试完成")