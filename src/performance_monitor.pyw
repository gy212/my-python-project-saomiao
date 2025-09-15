"""
性能监控模块
提供实时性能监控、资源使用统计和性能优化建议
"""

import os
import time
import psutil
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json

from .logger import get_logger

logger = get_logger()

@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    active_threads: int
    processing_queue_size: int = 0
    cache_hit_rate: float = 0.0
    average_response_time: float = 0.0

@dataclass
class FunctionPerformance:
    """函数性能统计"""
    function_name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    error_count: int = 0
    last_called: Optional[datetime] = None

class PerformanceCollector:
    """性能数据收集器"""
    
    def __init__(self, max_history_size: int = 1000):
        self.max_history_size = max_history_size
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.function_stats: Dict[str, FunctionPerformance] = {}
        self.process = psutil.Process()
        self.start_time = time.time()
        
        # 初始化网络和磁盘IO基准值
        self._init_baseline_metrics()
    
    def _init_baseline_metrics(self):
        """初始化基准指标"""
        try:
            self.baseline_net_io = psutil.net_io_counters()
            self.baseline_disk_io = psutil.disk_io_counters()
        except Exception as e:
            logger.warning(f"无法获取基准IO指标: {e}")
            self.baseline_net_io = None
            self.baseline_disk_io = None
    
    def collect_system_metrics(self) -> PerformanceMetrics:
        """收集系统性能指标"""
        try:
            # CPU和内存使用率
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            memory_used_mb = memory_info.rss / 1024 / 1024
            
            # 磁盘IO
            disk_io_read_mb = 0
            disk_io_write_mb = 0
            if self.baseline_disk_io:
                try:
                    current_disk_io = psutil.disk_io_counters()
                    if current_disk_io:
                        disk_io_read_mb = (current_disk_io.read_bytes - self.baseline_disk_io.read_bytes) / 1024 / 1024
                        disk_io_write_mb = (current_disk_io.write_bytes - self.baseline_disk_io.write_bytes) / 1024 / 1024
                except Exception:
                    pass
            
            # 网络IO
            network_sent_mb = 0
            network_recv_mb = 0
            if self.baseline_net_io:
                try:
                    current_net_io = psutil.net_io_counters()
                    if current_net_io:
                        network_sent_mb = (current_net_io.bytes_sent - self.baseline_net_io.bytes_sent) / 1024 / 1024
                        network_recv_mb = (current_net_io.bytes_recv - self.baseline_net_io.bytes_recv) / 1024 / 1024
                except Exception:
                    pass
            
            # 活动线程数
            active_threads = threading.active_count()
            
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                disk_io_read_mb=disk_io_read_mb,
                disk_io_write_mb=disk_io_write_mb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                active_threads=active_threads
            )
            
            self.metrics_history.append(metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=0, memory_percent=0, memory_used_mb=0,
                disk_io_read_mb=0, disk_io_write_mb=0,
                network_sent_mb=0, network_recv_mb=0,
                active_threads=0
            )
    
    def record_function_call(self, function_name: str, execution_time: float, success: bool = True):
        """记录函数调用性能"""
        if function_name not in self.function_stats:
            self.function_stats[function_name] = FunctionPerformance(function_name=function_name)
        
        stats = self.function_stats[function_name]
        stats.call_count += 1
        stats.total_time += execution_time
        stats.min_time = min(stats.min_time, execution_time)
        stats.max_time = max(stats.max_time, execution_time)
        stats.avg_time = stats.total_time / stats.call_count
        stats.last_called = datetime.now()
        
        if not success:
            stats.error_count += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        recent_metrics = list(self.metrics_history)[-10:]  # 最近10个数据点
        
        # 计算平均值
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory_mb = sum(m.memory_used_mb for m in recent_metrics) / len(recent_metrics)
        
        # 运行时间
        uptime_seconds = time.time() - self.start_time
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))
        
        # 函数性能统计
        top_functions = sorted(
            self.function_stats.values(),
            key=lambda x: x.total_time,
            reverse=True
        )[:5]
        
        return {
            "uptime": uptime_str,
            "system_metrics": {
                "avg_cpu_percent": round(avg_cpu, 2),
                "avg_memory_percent": round(avg_memory, 2),
                "avg_memory_mb": round(avg_memory_mb, 2),
                "active_threads": recent_metrics[-1].active_threads if recent_metrics else 0
            },
            "function_performance": [
                {
                    "name": f.function_name,
                    "call_count": f.call_count,
                    "avg_time": round(f.avg_time, 4),
                    "total_time": round(f.total_time, 2),
                    "error_rate": round(f.error_count / f.call_count * 100, 2) if f.call_count > 0 else 0
                }
                for f in top_functions
            ],
            "total_function_calls": sum(f.call_count for f in self.function_stats.values()),
            "total_errors": sum(f.error_count for f in self.function_stats.values())
        }

class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self, collector: PerformanceCollector):
        self.collector = collector
        self.thresholds = {
            "cpu_high": 80.0,
            "memory_high": 85.0,
            "response_time_slow": 5.0,
            "error_rate_high": 5.0
        }
    
    def analyze_performance(self) -> Dict[str, Any]:
        """分析性能并提供建议"""
        if not self.collector.metrics_history:
            return {"status": "insufficient_data"}
        
        recent_metrics = list(self.collector.metrics_history)[-20:]  # 最近20个数据点
        issues = []
        recommendations = []
        
        # CPU使用率分析
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        if avg_cpu > self.thresholds["cpu_high"]:
            issues.append(f"CPU使用率过高: {avg_cpu:.1f}%")
            recommendations.append("考虑优化计算密集型操作或增加并发处理")
        
        # 内存使用率分析
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        if avg_memory > self.thresholds["memory_high"]:
            issues.append(f"内存使用率过高: {avg_memory:.1f}%")
            recommendations.append("考虑清理缓存或优化内存使用")
        
        # 函数性能分析
        slow_functions = [
            f for f in self.collector.function_stats.values()
            if f.avg_time > self.thresholds["response_time_slow"]
        ]
        
        if slow_functions:
            issues.append(f"发现{len(slow_functions)}个响应缓慢的函数")
            recommendations.append("优化慢函数的执行逻辑")
        
        # 错误率分析
        high_error_functions = [
            f for f in self.collector.function_stats.values()
            if f.call_count > 0 and (f.error_count / f.call_count * 100) > self.thresholds["error_rate_high"]
        ]
        
        if high_error_functions:
            issues.append(f"发现{len(high_error_functions)}个高错误率函数")
            recommendations.append("检查和修复高错误率的函数")
        
        # 趋势分析
        if len(recent_metrics) >= 10:
            cpu_trend = self._calculate_trend([m.cpu_percent for m in recent_metrics])
            memory_trend = self._calculate_trend([m.memory_percent for m in recent_metrics])
            
            if cpu_trend > 0.1:
                issues.append("CPU使用率呈上升趋势")
            if memory_trend > 0.1:
                issues.append("内存使用率呈上升趋势")
        
        return {
            "status": "analyzed",
            "issues": issues,
            "recommendations": recommendations,
            "performance_score": self._calculate_performance_score(recent_metrics),
            "slow_functions": [
                {
                    "name": f.function_name,
                    "avg_time": f.avg_time,
                    "call_count": f.call_count
                }
                for f in slow_functions[:5]
            ]
        }
    
    def _calculate_trend(self, values: List[float]) -> float:
        """计算趋势（简单线性回归斜率）"""
        if len(values) < 2:
            return 0
        
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        return slope
    
    def _calculate_performance_score(self, metrics: List[PerformanceMetrics]) -> float:
        """计算性能评分（0-100）"""
        if not metrics:
            return 0
        
        avg_cpu = sum(m.cpu_percent for m in metrics) / len(metrics)
        avg_memory = sum(m.memory_percent for m in metrics) / len(metrics)
        
        # 基础分数
        cpu_score = max(0, 100 - avg_cpu)
        memory_score = max(0, 100 - avg_memory)
        
        # 错误率影响
        total_calls = sum(f.call_count for f in self.collector.function_stats.values())
        total_errors = sum(f.error_count for f in self.collector.function_stats.values())
        error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0
        error_score = max(0, 100 - error_rate * 10)
        
        # 综合评分
        overall_score = (cpu_score * 0.4 + memory_score * 0.4 + error_score * 0.2)
        return round(overall_score, 1)

class PerformanceMonitor:
    """性能监控主类"""
    
    def __init__(self, monitoring_interval: float = 5.0):
        self.monitoring_interval = monitoring_interval
        self.collector = PerformanceCollector()
        self.analyzer = PerformanceAnalyzer(self.collector)
        self.monitoring_thread = None
        self.is_monitoring = False
        self._lock = threading.Lock()
    
    def start_monitoring(self):
        """开始性能监控"""
        with self._lock:
            if self.is_monitoring:
                return
            
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        with self._lock:
            self.is_monitoring = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=1.0)
            logger.info("性能监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                self.collector.collect_system_metrics()
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"性能监控循环错误: {e}")
                time.sleep(self.monitoring_interval)
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前性能状态"""
        summary = self.collector.get_performance_summary()
        analysis = self.analyzer.analyze_performance()
        
        return {
            "monitoring_active": self.is_monitoring,
            "summary": summary,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
    
    def record_function_performance(self, function_name: str, execution_time: float, success: bool = True):
        """记录函数性能"""
        self.collector.record_function_call(function_name, execution_time, success)
    
    def export_performance_data(self, file_path: str):
        """导出性能数据"""
        try:
            data = {
                "export_time": datetime.now().isoformat(),
                "summary": self.collector.get_performance_summary(),
                "analysis": self.analyzer.analyze_performance(),
                "metrics_history": [
                    {
                        "timestamp": m.timestamp.isoformat(),
                        "cpu_percent": m.cpu_percent,
                        "memory_percent": m.memory_percent,
                        "memory_used_mb": m.memory_used_mb,
                        "active_threads": m.active_threads
                    }
                    for m in list(self.collector.metrics_history)
                ]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"性能数据已导出到: {file_path}")
        except Exception as e:
            logger.error(f"导出性能数据失败: {e}")

def performance_monitor(function_name: str = None):
    """性能监控装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = function_name or func.__name__
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                monitor = get_performance_monitor()
                monitor.record_function_performance(name, execution_time, success)
        
        return wrapper
    return decorator

# 全局性能监控器实例
_performance_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """获取性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor