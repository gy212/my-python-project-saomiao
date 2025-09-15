# -*- coding: utf-8 -*-
"""
batch_optimizer.pyw

功能: 批量处理优化模块
职责:
1. 优化批量图片处理的内存使用
2. 实现智能并发控制
3. 提供图片预处理和压缩功能
4. 优化文件I/O操作
5. 实现处理结果缓存和清理
"""

import os
import gc
import time
import threading
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from PIL import Image, ImageEnhance, ImageFilter
import psutil

from .logger import get_logger, get_error_handler, handle_exceptions
from .cache_manager import get_cache_manager, CacheConfig
from .error_manager import get_error_manager, enhanced_handle_exceptions
from .performance_monitor import get_performance_monitor, performance_monitor


@dataclass
class ProcessingConfig:
    """批量处理配置"""
    max_workers: int = 3
    max_memory_usage: float = 0.8  # 最大内存使用率
    image_max_size: Tuple[int, int] = (2048, 2048)  # 图片最大尺寸
    enable_compression: bool = True
    compression_quality: int = 85
    enable_preprocessing: bool = True
    cache_results: bool = True
    max_cache_size: int = 100  # 最大缓存结果数


class BatchOptimizer:
    """批量处理优化器"""
    
    def __init__(self, config: ProcessingConfig = None):
        self.config = config or ProcessingConfig()
        self.logger = get_logger()
        self.error_handler = get_error_handler()
        
        # 集成错误管理器和性能监控器
        self.error_manager = get_error_manager()
        self.performance_monitor = get_performance_monitor()
        
        # 内存监控
        self.memory_monitor = MemoryMonitor()
        
        # 使用新的缓存管理器
        cache_config = CacheConfig()
        cache_config.max_memory_cache_size = self.config.max_cache_size
        cache_config.memory_cache_ttl = 1800  # 30分钟TTL
        cache_config.disk_cache_ttl = 3600  # 1小时磁盘缓存
        self.cache_manager = get_cache_manager(cache_config)
        
        # 保留旧缓存接口以兼容现有代码
        self.result_cache: Dict[str, Any] = {}
        self.cache_lock = threading.Lock()
        
        # 性能统计
        self.stats = {
            'processed_images': 0,
            'total_processing_time': 0.0,
            'memory_peak': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        self.logger.info(f"批量处理优化器初始化完成: 最大工作线程={self.config.max_workers}, 内存限制={self.config.max_memory_usage*100}%, 已集成错误管理和性能监控")

    @enhanced_handle_exceptions("optimize_image_batch")
    @performance_monitor("optimize_image_batch")
    def optimize_image_batch(self, image_paths: List[str]) -> List[Dict]:
        """优化批量图片处理
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            List[Dict]: 优化后的图片信息列表
        """
        if not image_paths:
            return []
        
        self.logger.info(f"开始优化批量图片处理: {len(image_paths)} 张图片")
        start_time = time.time()
        
        optimized_images = []
        
        # 按文件大小排序，优先处理小文件
        sorted_paths = self._sort_images_by_size(image_paths)
        
        # 分批处理，避免内存溢出
        batch_size = self._calculate_optimal_batch_size(sorted_paths)
        
        for i in range(0, len(sorted_paths), batch_size):
            batch = sorted_paths[i:i + batch_size]
            self.logger.debug(f"处理批次 {i//batch_size + 1}: {len(batch)} 张图片")
            
            # 检查内存使用情况
            if self.memory_monitor.get_memory_usage() > self.config.max_memory_usage:
                self.logger.warning("内存使用率过高，执行垃圾回收")
                self._cleanup_memory()
            
            batch_results = self._process_image_batch(batch)
            optimized_images.extend(batch_results)
            
            # 更新统计信息
            self.stats['processed_images'] += len(batch)
        
        processing_time = time.time() - start_time
        self.stats['total_processing_time'] += processing_time
        
        self.logger.info(f"批量图片优化完成: {len(optimized_images)} 张图片, 耗时: {processing_time:.2f}秒")
        return optimized_images

    def _sort_images_by_size(self, image_paths: List[str]) -> List[str]:
        """按文件大小排序图片"""
        try:
            path_sizes = []
            for path in image_paths:
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    path_sizes.append((path, size))
                else:
                    self.logger.warning(f"图片文件不存在: {path}")
            
            # 按大小排序（小文件优先）
            path_sizes.sort(key=lambda x: x[1])
            return [path for path, _ in path_sizes]
        except Exception as e:
            self.logger.error(f"排序图片失败: {e}")
            return image_paths

    def _calculate_optimal_batch_size(self, image_paths: List[str]) -> int:
        """计算最优批次大小"""
        if not image_paths:
            return 1
        
        # 基于可用内存和图片大小估算
        available_memory = psutil.virtual_memory().available
        avg_file_size = sum(os.path.getsize(path) for path in image_paths[:min(5, len(image_paths))]) / min(5, len(image_paths))
        
        # 估算每张图片处理需要的内存（解压后约为文件大小的3-5倍）
        estimated_memory_per_image = avg_file_size * 4
        
        # 计算批次大小（保留50%内存余量）
        batch_size = max(1, int(available_memory * 0.5 / estimated_memory_per_image))
        batch_size = min(batch_size, self.config.max_workers * 2)  # 不超过工作线程数的2倍
        
        self.logger.debug(f"计算最优批次大小: {batch_size}, 平均文件大小: {avg_file_size/1024/1024:.1f}MB")
        return batch_size

    def _process_image_batch(self, image_paths: List[str]) -> List[Dict]:
        """处理一批图片"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # 提交任务
            future_to_path = {
                executor.submit(self._optimize_single_image, path): path 
                for path in image_paths
            }
            
            # 收集结果
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    self.logger.error(f"处理图片失败 {path}: {e}")
                    results.append({
                        'original_path': path,
                        'status': 'failed',
                        'error': str(e)
                    })
        
        return results

    @handle_exceptions("optimize_single_image")
    def _optimize_single_image(self, image_path: str) -> Optional[Dict]:
        """优化单张图片"""
        if not os.path.exists(image_path):
            return None
        
        # 检查缓存
        cached_result = self._get_cached_result(image_path)
        if cached_result:
            return cached_result
        
        try:
            result = {
                'original_path': image_path,
                'file_name': os.path.basename(image_path),
                'original_size': os.path.getsize(image_path),
                'status': 'success'
            }
            
            # 图片预处理
            if self.config.enable_preprocessing:
                processed_info = self._preprocess_image(image_path)
                result.update(processed_info)
            
            # 缓存结果
            if self.config.cache_results:
                self._cache_result(image_path, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"优化图片失败 {image_path}: {e}")
            return {
                'original_path': image_path,
                'status': 'failed',
                'error': str(e)
            }

    def _preprocess_image(self, image_path: str) -> Dict:
        """预处理图片"""
        try:
            with Image.open(image_path) as img:
                original_size = img.size
                original_mode = img.mode
                
                # 转换为RGB模式（如果需要）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 调整图片大小
                if img.size[0] > self.config.image_max_size[0] or img.size[1] > self.config.image_max_size[1]:
                    img.thumbnail(self.config.image_max_size, Image.Resampling.LANCZOS)
                    self.logger.debug(f"图片尺寸调整: {original_size} -> {img.size}")
                
                # 图片增强（提高OCR识别率）
                enhanced_img = self._enhance_image_for_ocr(img)
                
                # 如果启用压缩，保存临时文件
                temp_path = None
                if self.config.enable_compression:
                    temp_path = self._save_compressed_image(enhanced_img, image_path)
                
                return {
                    'preprocessed': True,
                    'original_size': original_size,
                    'processed_size': enhanced_img.size,
                    'original_mode': original_mode,
                    'processed_mode': enhanced_img.mode,
                    'temp_path': temp_path,
                    'size_reduction': original_size[0] * original_size[1] - enhanced_img.size[0] * enhanced_img.size[1]
                }
                
        except Exception as e:
            self.logger.error(f"预处理图片失败 {image_path}: {e}")
            return {'preprocessed': False, 'error': str(e)}

    def _enhance_image_for_ocr(self, img: Image.Image) -> Image.Image:
        """增强图片以提高OCR识别率"""
        try:
            # 增强对比度
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            
            # 增强锐度
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.1)
            
            # 轻微降噪
            img = img.filter(ImageFilter.MedianFilter(size=3))
            
            return img
        except Exception as e:
            self.logger.warning(f"图片增强失败: {e}")
            return img

    def _save_compressed_image(self, img: Image.Image, original_path: str) -> Optional[str]:
        """保存压缩后的图片"""
        try:
            # 生成临时文件路径
            base_name = os.path.splitext(os.path.basename(original_path))[0]
            temp_dir = os.path.join(os.path.dirname(original_path), '.temp_processed')
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_path = os.path.join(temp_dir, f"{base_name}_processed.jpg")
            
            # 保存压缩图片
            img.save(temp_path, 'JPEG', quality=self.config.compression_quality, optimize=True)
            
            self.logger.debug(f"保存压缩图片: {temp_path}")
            return temp_path
            
        except Exception as e:
            self.logger.error(f"保存压缩图片失败: {e}")
            return None

    def _get_cache_key(self, image_path: str) -> Dict[str, Any]:
        """生成缓存键数据"""
        # 基于文件路径和修改时间生成唯一键
        try:
            mtime = os.path.getmtime(image_path)
            file_size = os.path.getsize(image_path)
            return {
                'image_path': image_path,
                'file_mtime': mtime,
                'file_size': file_size,
                'config': {
                    'max_size': self.config.image_max_size,
                    'compression_quality': self.config.compression_quality,
                    'enable_preprocessing': self.config.enable_preprocessing
                }
            }
        except OSError:
            return {
                'image_path': image_path,
                'config': {
                    'max_size': self.config.image_max_size,
                    'compression_quality': self.config.compression_quality,
                    'enable_preprocessing': self.config.enable_preprocessing
                }
            }

    def _get_cached_result(self, image_path: str) -> Optional[Dict]:
        """获取缓存结果"""
        cache_key_data = self._get_cache_key(image_path)
        
        # 尝试从新缓存管理器获取
        cached_result = self.cache_manager.get(cache_key_data)
        if cached_result is not None:
            self.stats['cache_hits'] += 1
            return cached_result
        
        # 兼容旧缓存系统
        old_cache_key = f"{image_path}_{cache_key_data.get('file_mtime', '')}"
        with self.cache_lock:
            if old_cache_key in self.result_cache:
                result = self.result_cache[old_cache_key]
                # 将结果迁移到新缓存系统
                self.cache_manager.put(cache_key_data, result)
                self.stats['cache_hits'] += 1
                return result
        
        self.stats['cache_misses'] += 1
        return None

    def _cache_result(self, image_path: str, result: Dict):
        """缓存结果"""
        cache_key_data = self._get_cache_key(image_path)
        
        # 存储到新缓存管理器
        self.cache_manager.put(cache_key_data, result)
        
        # 兼容旧缓存系统
        old_cache_key = f"{image_path}_{cache_key_data.get('file_mtime', '')}"
        with self.cache_lock:
            # 检查缓存大小限制
            if len(self.result_cache) >= self.config.max_cache_size:
                # 删除最旧的缓存项
                oldest_key = next(iter(self.result_cache))
                del self.result_cache[oldest_key]
            
            self.result_cache[old_cache_key] = result

    def _cleanup_memory(self):
        """清理内存"""
        # 清理新缓存管理器
        self.cache_manager.clear("memory")
        
        # 清理旧缓存
        with self.cache_lock:
            cache_size = len(self.result_cache)
            self.result_cache.clear()
            
        # 强制垃圾回收
        gc.collect()
        
        current_memory = self.memory_monitor.get_memory_usage()
        self.logger.info(f"内存清理完成: 清理缓存 {cache_size} 项, 当前内存使用率: {current_memory*100:.1f}%")

    def cleanup_temp_files(self, base_dir: str):
        """清理临时文件"""
        temp_dir = os.path.join(base_dir, '.temp_processed')
        if os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                self.logger.info(f"清理临时文件目录: {temp_dir}")
            except Exception as e:
                self.logger.error(f"清理临时文件失败: {e}")

    def get_performance_stats(self) -> Dict:
        """获取性能统计信息"""
        stats = self.stats.copy()
        stats['current_memory_usage'] = self.memory_monitor.get_memory_usage()
        stats['cache_size'] = len(self.result_cache)
        
        if stats['processed_images'] > 0:
            stats['avg_processing_time'] = stats['total_processing_time'] / stats['processed_images']
            stats['cache_hit_rate'] = stats['cache_hits'] / (stats['cache_hits'] + stats['cache_misses'])
        
        return stats


class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用率"""
        try:
            memory = psutil.virtual_memory()
            return memory.percent / 100.0
        except Exception as e:
            self.logger.error(f"获取内存使用率失败: {e}")
            return 0.0
    
    def get_available_memory(self) -> int:
        """获取可用内存（字节）"""
        try:
            memory = psutil.virtual_memory()
            return memory.available
        except Exception as e:
            self.logger.error(f"获取可用内存失败: {e}")
            return 0
    
    def is_memory_critical(self, threshold: float = 0.9) -> bool:
        """检查内存是否达到临界状态"""
        return self.get_memory_usage() > threshold