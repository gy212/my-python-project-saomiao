# -*- coding: utf-8 -*-
"""
cache_manager.pyw

功能: 缓存管理模块
职责:
1. 提供统一的缓存策略和管理
2. 支持多种缓存类型（内存、磁盘、LRU等）
3. 实现缓存过期和清理机制
4. 提供缓存统计和监控功能
5. 优化图片和文本缓存性能
"""

import os
import json
import time
import hashlib
import threading
import tempfile
import shutil
from contextlib import suppress
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass
from collections import OrderedDict
import pickle
import gzip

from .logger import get_logger, handle_exceptions


@dataclass
class CacheConfig:
    """缓存配置"""
    # 内存缓存配置
    max_memory_cache_size: int = 100  # 最大内存缓存项数
    memory_cache_ttl: int = 3600  # 内存缓存TTL（秒）
    
    # 磁盘缓存配置
    enable_disk_cache: bool = True
    disk_cache_dir: str = None  # 磁盘缓存目录
    max_disk_cache_size: int = 1000  # 最大磁盘缓存项数
    disk_cache_ttl: int = 86400  # 磁盘缓存TTL（秒）
    
    # 压缩配置
    enable_compression: bool = True
    compression_level: int = 6
    
    # 清理配置
    cleanup_interval: int = 300  # 清理间隔（秒）
    max_cache_age: int = 604800  # 最大缓存年龄（秒，7天）


@dataclass
class CacheItem:
    """缓存项"""
    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    size_bytes: int = 0
    compressed: bool = False


class LRUCache:
    """LRU缓存实现"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self.lock:
            if key in self.cache:
                # 移动到末尾（最近使用）
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
            return None
    
    def put(self, key: str, value: Any) -> None:
        """添加缓存项"""
        with self.lock:
            if key in self.cache:
                # 更新现有项
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # 删除最久未使用的项
                self.cache.popitem(last=False)
            
            self.cache[key] = value
    
    def remove(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        with self.lock:
            return len(self.cache)
    
    def keys(self) -> List[str]:
        """获取所有键"""
        with self.lock:
            return list(self.cache.keys())


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.logger = get_logger()
        
        # 初始化缓存目录
        if self.config.disk_cache_dir is None:
            self.config.disk_cache_dir = os.path.join(tempfile.gettempdir(), "ocr_cache")
        
        os.makedirs(self.config.disk_cache_dir, exist_ok=True)
        
        # 初始化缓存存储
        self.memory_cache = LRUCache(self.config.max_memory_cache_size)
        self.cache_metadata = {}  # 缓存元数据
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'memory_hits': 0,
            'memory_misses': 0,
            'disk_hits': 0,
            'disk_misses': 0,
            'total_requests': 0,
            'cache_size_bytes': 0
        }
        
        # 启动清理线程
        self._stop_cleanup = threading.Event()
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
        self.logger.info(f"缓存管理器初始化完成: 内存缓存={self.config.max_memory_cache_size}, "
                        f"磁盘缓存={self.config.max_disk_cache_size}, "
                        f"缓存目录={self.config.disk_cache_dir}")
    
    def _generate_cache_key(self, key_data: Union[str, Dict, Tuple]) -> str:
        """生成缓存键"""
        if isinstance(key_data, str):
            content = key_data
        elif isinstance(key_data, dict):
            content = json.dumps(key_data, sort_keys=True)
        elif isinstance(key_data, (tuple, list)):
            content = str(key_data)
        else:
            content = str(key_data)
        
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_disk_cache_path(self, cache_key: str) -> str:
        """获取磁盘缓存文件路径"""
        return os.path.join(self.config.disk_cache_dir, f"{cache_key}.cache")
    
    def _compress_data(self, data: bytes) -> bytes:
        """压缩数据"""
        if self.config.enable_compression:
            return gzip.compress(data, compresslevel=self.config.compression_level)
        return data
    
    def _decompress_data(self, data: bytes) -> bytes:
        """解压数据"""
        if self.config.enable_compression:
            try:
                return gzip.decompress(data)
            except:
                return data  # 如果解压失败，返回原数据
        return data
    
    def _serialize_value(self, value: Any) -> bytes:
        """序列化值"""
        try:
            return pickle.dumps(value)
        except Exception as e:
            self.logger.warning(f"序列化失败: {e}")
            return str(value).encode('utf-8')
    
    def _deserialize_value(self, data: bytes) -> Any:
        """反序列化值"""
        try:
            return pickle.loads(data)
        except:
            try:
                return data.decode('utf-8')
            except:
                return data
    
    @handle_exceptions("cache_get")
    def get(self, key_data: Union[str, Dict, Tuple], cache_type: str = "auto") -> Optional[Any]:
        """获取缓存项
        
        Args:
            key_data: 缓存键数据
            cache_type: 缓存类型 ("memory", "disk", "auto")
        
        Returns:
            缓存的值，如果不存在返回None
        """
        cache_key = self._generate_cache_key(key_data)
        current_time = time.time()
        
        with self.lock:
            self.stats['total_requests'] += 1
            
            # 1. 尝试从内存缓存获取
            if cache_type in ("memory", "auto"):
                memory_value = self.memory_cache.get(cache_key)
                if memory_value is not None:
                    # 检查是否过期
                    if cache_key in self.cache_metadata:
                        metadata = self.cache_metadata[cache_key]
                        if current_time - metadata['created_at'] < self.config.memory_cache_ttl:
                            metadata['accessed_at'] = current_time
                            metadata['access_count'] += 1
                            self.stats['memory_hits'] += 1
                            return memory_value
                        else:
                            # 过期，删除
                            self.memory_cache.remove(cache_key)
                            del self.cache_metadata[cache_key]
                
                self.stats['memory_misses'] += 1
            
            # 2. 尝试从磁盘缓存获取
            if self.config.enable_disk_cache and cache_type in ("disk", "auto"):
                disk_path = self._get_disk_cache_path(cache_key)
                if os.path.exists(disk_path):
                    try:
                        # 检查文件是否过期
                        file_age = current_time - os.path.getmtime(disk_path)
                        if file_age < self.config.disk_cache_ttl:
                            with open(disk_path, 'rb') as f:
                                compressed_data = f.read()
                            
                            data = self._decompress_data(compressed_data)
                            value = self._deserialize_value(data)
                            
                            # 将结果放入内存缓存
                            self.memory_cache.put(cache_key, value)
                            self.cache_metadata[cache_key] = {
                                'created_at': current_time,
                                'accessed_at': current_time,
                                'access_count': 1,
                                'size_bytes': len(data)
                            }
                            
                            self.stats['disk_hits'] += 1
                            return value
                        else:
                            # 过期，删除文件
                            os.remove(disk_path)
                    except Exception as e:
                        self.logger.warning(f"读取磁盘缓存失败: {cache_key}, 错误: {e}")
                
                self.stats['disk_misses'] += 1
            
            return None
    
    @handle_exceptions("cache_put")
    def put(self, key_data: Union[str, Dict, Tuple], value: Any, cache_type: str = "auto") -> bool:
        """存储缓存项
        
        Args:
            key_data: 缓存键数据
            value: 要缓存的值
            cache_type: 缓存类型 ("memory", "disk", "auto")
        
        Returns:
            是否成功存储
        """
        cache_key = self._generate_cache_key(key_data)
        current_time = time.time()
        
        try:
            with self.lock:
                # 序列化数据
                serialized_data = self._serialize_value(value)
                data_size = len(serialized_data)
                
                # 1. 存储到内存缓存
                if cache_type in ("memory", "auto"):
                    self.memory_cache.put(cache_key, value)
                    self.cache_metadata[cache_key] = {
                        'created_at': current_time,
                        'accessed_at': current_time,
                        'access_count': 1,
                        'size_bytes': data_size
                    }
                
                # 2. 存储到磁盘缓存
                if self.config.enable_disk_cache and cache_type in ("disk", "auto"):
                    disk_path = self._get_disk_cache_path(cache_key)
                    compressed_data = self._compress_data(serialized_data)
                    
                    with open(disk_path, 'wb') as f:
                        f.write(compressed_data)
                
                self.stats['cache_size_bytes'] += data_size
                return True
                
        except Exception as e:
            self.logger.error(f"存储缓存失败: {cache_key}, 错误: {e}")
            return False
    
    def remove(self, key_data: Union[str, Dict, Tuple]) -> bool:
        """删除缓存项"""
        cache_key = self._generate_cache_key(key_data)
        
        with self.lock:
            removed = False
            
            # 从内存缓存删除
            if self.memory_cache.remove(cache_key):
                removed = True
                if cache_key in self.cache_metadata:
                    del self.cache_metadata[cache_key]
            
            # 从磁盘缓存删除
            if self.config.enable_disk_cache:
                disk_path = self._get_disk_cache_path(cache_key)
                if os.path.exists(disk_path):
                    try:
                        os.remove(disk_path)
                        removed = True
                    except Exception as e:
                        self.logger.warning(f"删除磁盘缓存失败: {cache_key}, 错误: {e}")
            
            return removed
    
    def clear(self, cache_type: str = "all") -> None:
        """清空缓存
        
        Args:
            cache_type: 要清空的缓存类型 ("memory", "disk", "all")
        """
        with self.lock:
            if cache_type in ("memory", "all"):
                self.memory_cache.clear()
                self.cache_metadata.clear()
                self.logger.info("内存缓存已清空")
            
            if cache_type in ("disk", "all") and self.config.enable_disk_cache:
                try:
                    if os.path.exists(self.config.disk_cache_dir):
                        shutil.rmtree(self.config.disk_cache_dir)
                        os.makedirs(self.config.disk_cache_dir, exist_ok=True)
                    self.logger.info("磁盘缓存已清空")
                except Exception as e:
                    self.logger.error(f"清空磁盘缓存失败: {e}")
            
            # 重置统计信息
            self.stats = {
                'memory_hits': 0,
                'memory_misses': 0,
                'disk_hits': 0,
                'disk_misses': 0,
                'total_requests': 0,
                'cache_size_bytes': 0
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.stats['total_requests']
            memory_hit_rate = (self.stats['memory_hits'] / total_requests * 100) if total_requests > 0 else 0
            disk_hit_rate = (self.stats['disk_hits'] / total_requests * 100) if total_requests > 0 else 0
            overall_hit_rate = ((self.stats['memory_hits'] + self.stats['disk_hits']) / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'memory_cache_size': self.memory_cache.size(),
                'memory_hit_rate': memory_hit_rate,
                'disk_hit_rate': disk_hit_rate,
                'overall_hit_rate': overall_hit_rate,
                'total_requests': total_requests,
                'cache_size_mb': self.stats['cache_size_bytes'] / (1024 * 1024),
                **self.stats
            }
    
    def _cleanup_worker(self):
        """清理工作线程"""
        while not self._stop_cleanup.wait(self.config.cleanup_interval):
            try:
                self._cleanup_expired_items()
            except Exception as e:
                self.logger.error(f"缓存清理失败: {e}")
    
    def _cleanup_expired_items(self):
        """清理过期项"""
        current_time = time.time()
        
        with self.lock:
            # 清理内存缓存中的过期项
            expired_keys = []
            for key, metadata in self.cache_metadata.items():
                if current_time - metadata['created_at'] > self.config.memory_cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self.memory_cache.remove(key)
                del self.cache_metadata[key]
            
            if expired_keys:
                self.logger.debug(f"清理过期内存缓存项: {len(expired_keys)} 个")
        
        # 清理磁盘缓存中的过期文件
        if self.config.enable_disk_cache and os.path.exists(self.config.disk_cache_dir):
            try:
                expired_files = []
                for filename in os.listdir(self.config.disk_cache_dir):
                    if filename.endswith('.cache'):
                        filepath = os.path.join(self.config.disk_cache_dir, filename)
                        file_age = current_time - os.path.getmtime(filepath)
                        if file_age > self.config.disk_cache_ttl:
                            expired_files.append(filepath)
                
                for filepath in expired_files:
                    os.remove(filepath)
                
                if expired_files:
                    self.logger.debug(f"清理过期磁盘缓存文件: {len(expired_files)} 个")
                    
            except Exception as e:
                self.logger.warning(f"清理磁盘缓存失败: {e}")
    
    def stop(self):
        """停止缓存管理器"""
        self._stop_cleanup.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        self.logger.info("缓存管理器已停止")
    
    def __del__(self):
        """析构函数"""
        with suppress(Exception):
            self.stop()


# 全局缓存管理器实例
_cache_manager = None
_cache_lock = threading.Lock()


def get_cache_manager(config: Optional[CacheConfig] = None) -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    
    with _cache_lock:
        if _cache_manager is None:
            _cache_manager = CacheManager(config)
        return _cache_manager


def clear_global_cache():
    """清空全局缓存"""
    global _cache_manager
    
    with _cache_lock:
        if _cache_manager is not None:
            _cache_manager.clear()
