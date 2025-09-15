"""
内存管理模块
提供图像压缩、结果清理和内存监控功能
"""

import os
import gc
import psutil
import threading
import time
from typing import Dict, List, Optional, Tuple
from PIL import Image
import tempfile
import shutil
from datetime import datetime, timedelta
from src.logger import get_logger, get_error_handler
from src.cache_manager import get_cache_manager, CacheConfig
from src.error_manager import get_error_manager, enhanced_handle_exceptions
from src.performance_monitor import get_performance_monitor, performance_monitor

logger = get_logger()

class MemoryConfig:
    """内存管理配置"""
    def __init__(self):
        self.max_memory_usage = 0.8  # 最大内存使用率 (80%)
        self.cleanup_threshold = 0.7  # 清理阈值 (70%)
        self.image_compression_quality = 85  # 图像压缩质量
        self.max_image_size = (2048, 2048)  # 最大图像尺寸
        self.temp_file_lifetime = 3600  # 临时文件生存时间（秒）
        self.monitoring_interval = 30  # 内存监控间隔（秒）

class MemoryManager:
    """内存管理器"""
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        
        # 集成错误管理器和性能监控器
        self.error_manager = get_error_manager()
        self.performance_monitor = get_performance_monitor()
        
        # 临时文件管理
        self._temp_files: Dict[str, datetime] = {}
        
        # 保留旧的压缩缓存以兼容现有代码
        self._compressed_cache: Dict[str, str] = {}
        
        # 监控线程
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._lock = threading.Lock()
        
        # 初始化新的缓存管理器
        cache_config = CacheConfig(
            max_memory_cache_size=100,  # 最大内存缓存项数
            memory_cache_ttl=1800,     # 30分钟内存缓存TTL
            disk_cache_ttl=7200,       # 2小时磁盘缓存TTL
            enable_disk_cache=True,
            enable_compression=True
        )
        self.cache_manager = get_cache_manager(cache_config)
        
        # 启动内存监控
        self._start_monitoring()
        
        logger.info(f"内存管理器初始化完成: 最大内存使用率={self.config.max_memory_usage*100}%, "
                   f"清理阈值={self.config.cleanup_threshold*100}%, 已集成错误管理和性能监控")
    
    def _start_monitoring(self):
        """启动内存监控线程"""
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            self._monitoring_thread = threading.Thread(
                target=self._monitor_memory,
                daemon=True
            )
            self._monitoring_thread.start()
    
    def _monitor_memory(self):
        """内存监控循环"""
        while not self._stop_monitoring.wait(self.config.monitoring_interval):
            try:
                memory_usage = self.get_memory_usage()
                
                if memory_usage > self.config.cleanup_threshold:
                    logger.warning(f"内存使用率过高: {memory_usage:.1%}, 开始清理")
                    self.cleanup_memory()
                
                # 清理过期的临时文件
                self._cleanup_expired_temp_files()
                
            except Exception as e:
                logger.error(f"内存监控出错: {e}")
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用率"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            
            # 计算进程内存使用率
            usage_ratio = memory_info.rss / system_memory.total
            return usage_ratio
            
        except Exception as e:
            logger.error(f"获取内存使用率失败: {e}")
            return 0.0
    
    @performance_monitor("compress_image")
    def compress_image(self, image_path: str, output_path: Optional[str] = None) -> str:
        """
        压缩图像
        
        Args:
            image_path: 原始图像路径
            output_path: 输出路径，如果为None则创建临时文件
            
        Returns:
            压缩后的图像路径
        """
        try:
            # 生成缓存键
            cache_key_data = {
                'image_path': image_path,
                'config': {
                    'quality': self.config.image_compression_quality,
                    'max_size': self.config.max_image_size
                }
            }
            
            # 添加文件修改时间到缓存键
            try:
                mtime = os.path.getmtime(image_path)
                cache_key_data['file_mtime'] = mtime
            except OSError:
                pass
            
            # 检查新缓存管理器
            cached_result = self.cache_manager.get(cache_key_data)
            if cached_result and os.path.exists(cached_result):
                return cached_result
            
            # 检查旧缓存（兼容性）
            if image_path in self._compressed_cache:
                cached_path = self._compressed_cache[image_path]
                if os.path.exists(cached_path):
                    # 迁移到新缓存系统
                    self.cache_manager.put(cache_key_data, cached_path)
                    return cached_path
            
            with Image.open(image_path) as img:
                # 转换为RGB模式（如果需要）
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # 调整图像尺寸
                if img.size[0] > self.config.max_image_size[0] or img.size[1] > self.config.max_image_size[1]:
                    img.thumbnail(self.config.max_image_size, Image.Resampling.LANCZOS)
                    logger.info(f"图像尺寸调整: {image_path} -> {img.size}")
                
                # 创建输出路径
                if output_path is None:
                    temp_fd, output_path = tempfile.mkstemp(suffix='.jpg', prefix='compressed_')
                    os.close(temp_fd)
                    self._register_temp_file(output_path)
                
                # 保存压缩图像
                img.save(
                    output_path,
                    'JPEG',
                    quality=self.config.image_compression_quality,
                    optimize=True
                )
                
                # 更新新缓存管理器
                self.cache_manager.put(cache_key_data, output_path)
                
                # 更新旧缓存（兼容性）
                with self._lock:
                    self._compressed_cache[image_path] = output_path
                
                # 计算压缩比
                original_size = os.path.getsize(image_path)
                compressed_size = os.path.getsize(output_path)
                compression_ratio = compressed_size / original_size
                
                logger.info(f"图像压缩完成: {image_path} -> {output_path}, "
                           f"压缩比: {compression_ratio:.2%}")
                
                return output_path
                
        except Exception as e:
            logger.error(f"图像压缩失败: {image_path}, 错误: {e}")
            return image_path  # 返回原始路径
    
    def compress_images_batch(self, image_paths: List[str]) -> List[str]:
        """
        批量压缩图像
        
        Args:
            image_paths: 图像路径列表
            
        Returns:
            压缩后的图像路径列表
        """
        compressed_paths = []
        
        for image_path in image_paths:
            compressed_path = self.compress_image(image_path)
            compressed_paths.append(compressed_path)
        
        return compressed_paths
    
    def _register_temp_file(self, file_path: str):
        """注册临时文件"""
        with self._lock:
            self._temp_files[file_path] = datetime.now()
    
    def _cleanup_expired_temp_files(self):
        """清理过期的临时文件"""
        current_time = datetime.now()
        expired_files = []
        
        with self._lock:
            for file_path, created_time in self._temp_files.items():
                if (current_time - created_time).total_seconds() > self.config.temp_file_lifetime:
                    expired_files.append(file_path)
        
        for file_path in expired_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"清理过期临时文件: {file_path}")
                
                with self._lock:
                    self._temp_files.pop(file_path, None)
                    # 同时清理压缩缓存
                    for key, value in list(self._compressed_cache.items()):
                        if value == file_path:
                            self._compressed_cache.pop(key, None)
                            break
                            
            except Exception as e:
                logger.error(f"清理临时文件失败: {file_path}, 错误: {e}")
    
    def cleanup_memory(self):
        """清理内存"""
        try:
            # 强制垃圾回收
            collected = gc.collect()
            logger.info(f"垃圾回收完成，清理对象数: {collected}")
            
            # 清理新缓存管理器
            self.cache_manager.clear("memory")
            
            # 清理旧压缩缓存（兼容性）
            with self._lock:
                cache_size = len(self._compressed_cache)
                self._compressed_cache.clear()
                logger.info(f"清理压缩缓存，清理项目数: {cache_size}")
            
            # 清理过期临时文件
            self._cleanup_expired_temp_files()
            
            # 获取清理后的内存使用率
            new_usage = self.get_memory_usage()
            logger.info(f"内存清理完成，当前使用率: {new_usage:.1%}")
            
        except Exception as e:
            logger.error(f"内存清理失败: {e}")
    
    def get_memory_stats(self) -> Dict:
        """获取内存统计信息"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            
            stats = {
                'process_memory_mb': memory_info.rss / 1024 / 1024,
                'system_memory_total_gb': system_memory.total / 1024 / 1024 / 1024,
                'system_memory_available_gb': system_memory.available / 1024 / 1024 / 1024,
                'system_memory_usage_percent': system_memory.percent,
                'process_memory_usage_percent': (memory_info.rss / system_memory.total) * 100,
                'temp_files_count': len(self._temp_files),
                'compressed_cache_count': len(self._compressed_cache)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取内存统计信息失败: {e}")
            return {}
    
    def should_compress_image(self, image_path: str) -> bool:
        """判断是否需要压缩图像"""
        try:
            # 检查文件大小
            file_size = os.path.getsize(image_path)
            if file_size < 1024 * 1024:  # 小于1MB不压缩
                return False
            
            # 检查内存使用率
            memory_usage = self.get_memory_usage()
            if memory_usage > self.config.cleanup_threshold:
                return True
            
            # 检查图像尺寸
            try:
                with Image.open(image_path) as img:
                    if (img.size[0] > self.config.max_image_size[0] or 
                        img.size[1] > self.config.max_image_size[1]):
                        return True
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"判断是否压缩图像失败: {image_path}, 错误: {e}")
            return False
    
    def cleanup_temp_directory(self, temp_dir: str):
        """清理临时目录"""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"清理临时目录: {temp_dir}")
        except Exception as e:
            logger.error(f"清理临时目录失败: {temp_dir}, 错误: {e}")
    
    def stop(self):
        """停止内存管理器"""
        self._stop_monitoring.set()
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)
        
        # 清理所有临时文件
        self._cleanup_expired_temp_files()
        
        logger.info("内存管理器已停止")
    
    def __del__(self):
        """析构函数"""
        try:
            self.stop()
        except Exception:
            pass