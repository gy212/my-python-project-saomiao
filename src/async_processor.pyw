# -*- coding: utf-8 -*-
"""
async_processor.pyw

功能: 异步OCR处理模块
职责:
1. 提供异步OCR处理功能，避免阻塞UI
2. 实现进度跟踪和状态更新
3. 支持任务取消功能
4. 管理并发处理和资源控制
5. 统一的错误处理与日志记录
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .logger import get_logger, get_error_handler, handle_exceptions


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ProcessingTask:
    """处理任务数据类"""
    task_id: str
    image_path: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Optional[Dict] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class AsyncOCRProcessor:
    """异步OCR处理器"""
    
    def __init__(self, ocr_service, max_workers: int = 3):
        self.ocr_service = ocr_service
        self.max_workers = max_workers
        self.logger = get_logger()
        self.error_handler = get_error_handler()
        
        # 任务管理
        self.tasks: Dict[str, ProcessingTask] = {}
        self.active_futures: Dict[str, Any] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cancelled_tasks = set()
        
        # 进度回调（使用私有属性避免JSON序列化）
        self._progress_callback: Optional[Callable] = None
        self._completion_callback: Optional[Callable] = None
        
        self.logger.info(f"异步OCR处理器初始化完成，最大工作线程数: {max_workers}")
    
    def set_progress_callback(self, callback: Callable[[str, float, str], None]):
        """设置进度更新回调函数
        
        Args:
            callback: 回调函数，参数为 (task_id, progress, status)
        """
        self._progress_callback = callback
        self.logger.debug("进度回调函数已设置")
    
    def set_completion_callback(self, callback: Callable[[str, Dict], None]):
        """设置任务完成回调函数
        
        Args:
            callback: 回调函数，参数为 (task_id, result)
        """
        self._completion_callback = callback
        self.logger.debug("完成回调函数已设置")
    
    def _update_progress(self, task_id: str, progress: float, status: str = None):
        """更新任务进度"""
        if task_id in self.tasks:
            self.tasks[task_id].progress = progress
            if status:
                try:
                    self.tasks[task_id].status = TaskStatus(status)
                except ValueError:
                    pass
            
            if self._progress_callback:
                try:
                    self._progress_callback(task_id, progress, status or self.tasks[task_id].status.value)
                except Exception as e:
                    self.logger.error(f"进度回调执行失败: {e}")
    
    def _notify_completion(self, task_id: str):
        """通知任务完成"""
        if task_id in self.tasks and self._completion_callback:
            try:
                task = self.tasks[task_id]
                result = {
                    "task_id": task_id,
                    "status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                    "duration": (task.end_time - task.start_time) if task.start_time and task.end_time else None
                }
                self._completion_callback(task_id, result)
            except Exception as e:
                self.logger.error(f"完成回调执行失败: {e}")
    
    def _process_single_image(self, task: ProcessingTask, markdown_tables: List[str] = None) -> Dict:
        """处理单张图片的OCR任务"""
        task_id = task.task_id
        
        try:
            # 检查是否已取消
            if task_id in self.cancelled_tasks:
                self.logger.info(f"任务已取消: {task_id}")
                return {"status": "cancelled", "error": "任务已取消"}
            
            # 更新状态为运行中
            task.status = TaskStatus.RUNNING
            task.start_time = time.time()
            self._update_progress(task_id, 10.0, "running")
            
            self.logger.info(f"开始处理OCR任务: {task_id} - {task.image_path}")
            
            # 模拟进度更新
            self._update_progress(task_id, 30.0)
            
            # 执行OCR处理
            result = self.ocr_service.extract_text_from_image(task.image_path, markdown_tables)
            
            # 再次检查是否已取消
            if task_id in self.cancelled_tasks:
                self.logger.info(f"任务在处理过程中被取消: {task_id}")
                return {"status": "cancelled", "error": "任务已取消"}
            
            # 更新进度
            self._update_progress(task_id, 90.0)
            
            # 处理结果
            if result.get("status") == "成功":
                task.status = TaskStatus.COMPLETED
                task.result = result
                self._update_progress(task_id, 100.0, "completed")
                self.logger.info(f"OCR任务完成: {task_id}")
                return {"status": "success", "result": result}
            else:
                task.status = TaskStatus.FAILED
                task.error = result.get("error", "未知错误")
                self._update_progress(task_id, 100.0, "failed")
                self.logger.error(f"OCR任务失败: {task_id} - {task.error}")
                return {"status": "failed", "error": task.error}
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self._update_progress(task_id, 100.0, "failed")
            self.logger.error(f"OCR任务异常: {task_id} - {e}")
            return {"status": "failed", "error": str(e)}
        
        finally:
            task.end_time = time.time()
            # 清理活动任务
            if task_id in self.active_futures:
                del self.active_futures[task_id]
            # 通知完成
            self._notify_completion(task_id)
    
    @handle_exceptions("submit_ocr_task")
    def submit_ocr_task(self, task_id: str, image_path: str, markdown_tables: List[str] = None) -> bool:
        """提交OCR任务
        
        Args:
            task_id: 任务ID
            image_path: 图片路径
            markdown_tables: 预提取的表格数据
            
        Returns:
            bool: 是否成功提交任务
        """
        if task_id in self.tasks:
            self.logger.warning(f"任务ID已存在: {task_id}")
            return False
        
        # 创建任务
        task = ProcessingTask(task_id=task_id, image_path=image_path)
        self.tasks[task_id] = task
        
        # 提交到线程池
        future = self.executor.submit(self._process_single_image, task, markdown_tables)
        self.active_futures[task_id] = future
        
        self.logger.info(f"OCR任务已提交: {task_id} - {image_path}")
        return True
    
    @handle_exceptions("submit_batch_ocr_tasks")
    def submit_batch_ocr_tasks(self, image_paths: List[str], markdown_tables_list: List[List[str]] = None) -> List[str]:
        """批量提交OCR任务
        
        Args:
            image_paths: 图片路径列表
            markdown_tables_list: 每张图片对应的表格数据列表
            
        Returns:
            List[str]: 任务ID列表
        """
        task_ids = []
        
        for i, image_path in enumerate(image_paths):
            task_id = f"ocr_task_{int(time.time() * 1000)}_{i}"
            markdown_tables = markdown_tables_list[i] if markdown_tables_list and i < len(markdown_tables_list) else None
            
            if self.submit_ocr_task(task_id, image_path, markdown_tables):
                task_ids.append(task_id)
        
        self.logger.info(f"批量提交OCR任务完成: {len(task_ids)} 个任务")
        return task_ids
    
    def cancel_task(self, task_id: str) -> bool:
        """取消指定任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        if task_id not in self.tasks:
            self.logger.warning(f"任务不存在: {task_id}")
            return False
        
        # 标记为已取消
        self.cancelled_tasks.add(task_id)
        
        # 尝试取消future
        if task_id in self.active_futures:
            future = self.active_futures[task_id]
            cancelled = future.cancel()
            if cancelled:
                self.logger.info(f"任务已取消: {task_id}")
            else:
                self.logger.info(f"任务正在运行中，已标记取消: {task_id}")
        
        # 更新任务状态
        task = self.tasks[task_id]
        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            task.end_time = time.time()
            self._update_progress(task_id, 100.0, "cancelled")
            self._notify_completion(task_id)
        
        return True
    
    def cancel_all_tasks(self) -> int:
        """取消所有任务
        
        Returns:
            int: 取消的任务数量
        """
        cancelled_count = 0
        
        for task_id in list(self.tasks.keys()):
            if self.tasks[task_id].status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                if self.cancel_task(task_id):
                    cancelled_count += 1
        
        self.logger.info(f"已取消 {cancelled_count} 个任务")
        return cancelled_count
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 任务状态信息（JSON安全）
        """
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        # 返回JSON安全的数据，不包含任何函数对象
        return {
            "task_id": task_id,
            "image_path": task.image_path,
            "status": task.status.value,
            "progress": task.progress,
            "result": task.result,
            "error": task.error,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "duration": (task.end_time - task.start_time) if task.start_time and task.end_time else None
        }
    
    def get_all_tasks_status(self) -> Dict[str, Dict]:
        """获取所有任务状态"""
        return {task_id: self.get_task_status(task_id) for task_id in self.tasks}
    
    def cleanup_completed_tasks(self, keep_recent: int = 10) -> int:
        """清理已完成的任务
        
        Args:
            keep_recent: 保留最近的任务数量
            
        Returns:
            int: 清理的任务数量
        """
        completed_tasks = [
            (task_id, task) for task_id, task in self.tasks.items()
            if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]
        ]
        
        # 按结束时间排序，保留最近的任务
        completed_tasks.sort(key=lambda x: x[1].end_time or 0, reverse=True)
        
        tasks_to_remove = completed_tasks[keep_recent:]
        removed_count = 0
        
        for task_id, _ in tasks_to_remove:
            if task_id in self.tasks:
                del self.tasks[task_id]
                removed_count += 1
            if task_id in self.cancelled_tasks:
                self.cancelled_tasks.remove(task_id)
        
        if removed_count > 0:
            self.logger.info(f"清理了 {removed_count} 个已完成的任务")
        
        return removed_count
    
    def shutdown(self):
        """关闭处理器"""
        self.logger.info("正在关闭异步OCR处理器...")
        
        # 取消所有任务
        self.cancel_all_tasks()
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        self.logger.info("异步OCR处理器已关闭")
    
    def __del__(self):
        """析构函数"""
        try:
            self.shutdown()
        except:
            pass