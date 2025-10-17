"""
增强错误管理模块
提供统一的错误处理、用户友好的错误提示和错误恢复机制
"""

import traceback
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

try:
    from .logger import get_logger, handle_exceptions
except ImportError:
    from logger import get_logger, handle_exceptions

logger = get_logger()

class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 轻微错误，不影响主要功能
    MEDIUM = "medium"     # 中等错误，影响部分功能
    HIGH = "high"         # 严重错误，影响主要功能
    CRITICAL = "critical" # 致命错误，应用无法继续运行

class ErrorCategory(Enum):
    """错误类别"""
    NETWORK = "network"           # 网络相关错误
    FILE_IO = "file_io"          # 文件操作错误
    API = "api"                  # API调用错误
    VALIDATION = "validation"     # 数据验证错误
    PROCESSING = "processing"     # 处理逻辑错误
    SYSTEM = "system"            # 系统级错误
    USER_INPUT = "user_input"    # 用户输入错误

@dataclass
class ErrorInfo:
    """错误信息"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    user_message: str
    technical_details: str
    timestamp: datetime
    function_name: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    context: Optional[Dict[str, Any]] = None
    suggested_actions: List[str] = None
    recovery_actions: List[Callable] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为JSON安全的字典格式"""
        return {
            "error_id": self.error_id,
            "category": self.category.value if self.category else None,
            "severity": self.severity.value if self.severity else None,
            "message": self.message,
            "user_message": self.user_message,
            "technical_details": self.technical_details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "function_name": self.function_name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
            "suggested_actions": self.suggested_actions,
            # 不包含 recovery_actions，因为它包含不可序列化的函数对象
        }

class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self):
        self.recovery_strategies: Dict[ErrorCategory, List[Callable]] = {
            ErrorCategory.NETWORK: [
                self._retry_with_backoff,
                self._check_network_connection,
                self._switch_to_offline_mode
            ],
            ErrorCategory.FILE_IO: [
                self._check_file_permissions,
                self._create_missing_directories,
                self._cleanup_temp_files
            ],
            ErrorCategory.API: [
                self._validate_api_key,
                self._retry_api_call,
                self._fallback_to_local_processing
            ],
            ErrorCategory.PROCESSING: [
                self._clear_cache,
                self._restart_processing_service,
                self._reduce_processing_complexity
            ]
        }
    
    def attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """尝试错误恢复"""
        strategies = self.recovery_strategies.get(error_info.category, [])
        
        for strategy in strategies:
            try:
                if strategy(error_info):
                    logger.info(f"错误恢复成功: {error_info.error_id} 使用策略 {strategy.__name__}")
                    return True
            except Exception as e:
                logger.warning(f"恢复策略失败 {strategy.__name__}: {e}")
        
        return False
    
    def _retry_with_backoff(self, error_info: ErrorInfo) -> bool:
        """带退避的重试策略"""
        # 实现指数退避重试
        return False
    
    def _check_network_connection(self, error_info: ErrorInfo) -> bool:
        """检查网络连接"""
        # 实现网络连接检查
        return False
    
    def _switch_to_offline_mode(self, error_info: ErrorInfo) -> bool:
        """切换到离线模式"""
        # 实现离线模式切换
        return False
    
    def _check_file_permissions(self, error_info: ErrorInfo) -> bool:
        """检查文件权限"""
        # 实现文件权限检查和修复
        return False
    
    def _create_missing_directories(self, error_info: ErrorInfo) -> bool:
        """创建缺失的目录"""
        # 实现目录创建
        return False
    
    def _cleanup_temp_files(self, error_info: ErrorInfo) -> bool:
        """清理临时文件"""
        # 实现临时文件清理
        return False
    
    def _validate_api_key(self, error_info: ErrorInfo) -> bool:
        """验证API密钥"""
        # 实现API密钥验证
        return False
    
    def _retry_api_call(self, error_info: ErrorInfo) -> bool:
        """重试API调用"""
        # 实现API重试
        return False
    
    def _fallback_to_local_processing(self, error_info: ErrorInfo) -> bool:
        """回退到本地处理"""
        # 实现本地处理回退
        return False
    
    def _clear_cache(self, error_info: ErrorInfo) -> bool:
        """清理缓存"""
        # 实现缓存清理
        return False
    
    def _restart_processing_service(self, error_info: ErrorInfo) -> bool:
        """重启处理服务"""
        # 实现服务重启
        return False
    
    def _reduce_processing_complexity(self, error_info: ErrorInfo) -> bool:
        """降低处理复杂度"""
        # 实现复杂度降低
        return False

class UserFriendlyErrorManager:
    """用户友好的错误管理器"""
    
    def __init__(self):
        self.error_history: List[ErrorInfo] = []
        self.recovery_manager = ErrorRecoveryManager()
        self.error_templates = self._load_error_templates()
        self.max_history_size = 100
    
    def _load_error_templates(self) -> Dict[str, Dict[str, str]]:
        """加载错误模板"""
        return {
            "network_timeout": {
                "user_message": "网络连接超时，请检查您的网络连接后重试。",
                "suggested_actions": [
                    "检查网络连接是否正常",
                    "尝试刷新页面",
                    "稍后再试"
                ]
            },
            "file_not_found": {
                "user_message": "找不到指定的文件，请确认文件路径是否正确。",
                "suggested_actions": [
                    "检查文件是否存在",
                    "确认文件路径正确",
                    "重新选择文件"
                ]
            },
            "api_key_invalid": {
                "user_message": "API密钥无效，请检查配置设置。",
                "suggested_actions": [
                    "检查API密钥是否正确",
                    "重新配置API设置",
                    "联系管理员获取有效密钥"
                ]
            },
            "processing_failed": {
                "user_message": "处理失败，请尝试重新处理或联系技术支持。",
                "suggested_actions": [
                    "重新尝试处理",
                    "检查输入文件格式",
                    "清理缓存后重试"
                ]
            },
            "memory_insufficient": {
                "user_message": "内存不足，请关闭其他应用程序或处理较小的文件。",
                "suggested_actions": [
                    "关闭其他应用程序",
                    "处理较小的文件",
                    "重启应用程序"
                ]
            }
        }
    
    def handle_error(self, exception: Exception, function_name: str, 
                    context: Optional[Dict[str, Any]] = None) -> ErrorInfo:
        """处理错误并生成用户友好的错误信息"""
        
        # 分析错误类型和严重程度
        category, severity = self._analyze_error(exception)
        
        # 生成错误ID
        error_id = f"{category.value}_{int(time.time())}"
        
        # 获取错误位置信息
        tb = traceback.extract_tb(exception.__traceback__)
        file_path = tb[-1].filename if tb else None
        line_number = tb[-1].lineno if tb else None
        
        # 生成用户友好的错误消息
        user_message, suggested_actions = self._generate_user_message(exception, category)
        
        # 创建错误信息
        error_info = ErrorInfo(
            error_id=error_id,
            category=category,
            severity=severity,
            message=str(exception),
            user_message=user_message,
            technical_details=traceback.format_exc(),
            timestamp=datetime.now(),
            function_name=function_name,
            file_path=file_path,
            line_number=line_number,
            context=context,
            suggested_actions=suggested_actions
        )
        
        # 记录错误
        self._record_error(error_info)
        
        # 尝试自动恢复
        if severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]:
            recovery_success = self.recovery_manager.attempt_recovery(error_info)
            if recovery_success:
                logger.info(f"错误自动恢复成功: {error_id}")
        
        return error_info
    
    def _analyze_error(self, exception: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """分析错误类型和严重程度"""
        error_type = type(exception).__name__
        error_message = str(exception).lower()
        
        # 根据异常类型和消息内容判断类别和严重程度
        if isinstance(exception, (ConnectionError, TimeoutError)) or "network" in error_message:
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        
        elif isinstance(exception, (FileNotFoundError, PermissionError, OSError)):
            return ErrorCategory.FILE_IO, ErrorSeverity.MEDIUM
        
        elif "api" in error_message or "401" in error_message or "403" in error_message:
            return ErrorCategory.API, ErrorSeverity.HIGH
        
        elif isinstance(exception, ValueError) or "validation" in error_message:
            return ErrorCategory.VALIDATION, ErrorSeverity.LOW
        
        elif "memory" in error_message or isinstance(exception, MemoryError):
            return ErrorCategory.SYSTEM, ErrorSeverity.HIGH
        
        else:
            return ErrorCategory.PROCESSING, ErrorSeverity.MEDIUM
    
    def _generate_user_message(self, exception: Exception, 
                             category: ErrorCategory) -> tuple[str, List[str]]:
        """生成用户友好的错误消息"""
        error_message = str(exception).lower()
        
        # 根据错误类型匹配模板
        for template_key, template in self.error_templates.items():
            if any(keyword in error_message for keyword in template_key.split("_")):
                return template["user_message"], template["suggested_actions"]
        
        # 默认消息
        default_messages = {
            ErrorCategory.NETWORK: ("网络连接出现问题，请检查网络设置。", ["检查网络连接", "重试操作"]),
            ErrorCategory.FILE_IO: ("文件操作失败，请检查文件权限。", ["检查文件权限", "重新选择文件"]),
            ErrorCategory.API: ("服务调用失败，请检查配置。", ["检查API配置", "联系技术支持"]),
            ErrorCategory.VALIDATION: ("输入数据有误，请检查输入。", ["检查输入格式", "重新输入"]),
            ErrorCategory.PROCESSING: ("处理过程中出现错误。", ["重试操作", "清理缓存"]),
            ErrorCategory.SYSTEM: ("系统资源不足。", ["释放系统资源", "重启应用"])
        }
        
        return default_messages.get(category, ("发生未知错误。", ["重试操作", "联系技术支持"]))
    
    def _record_error(self, error_info: ErrorInfo):
        """记录错误信息"""
        self.error_history.append(error_info)
        
        # 限制历史记录大小
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
        
        # 记录到日志
        logger.error(f"错误记录: {error_info.error_id} - {error_info.message}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        if not self.error_history:
            return {"total_errors": 0}
        
        # 按类别统计
        category_stats = {}
        severity_stats = {}
        
        for error in self.error_history:
            category_stats[error.category.value] = category_stats.get(error.category.value, 0) + 1
            severity_stats[error.severity.value] = severity_stats.get(error.severity.value, 0) + 1
        
        # 最近24小时的错误
        recent_errors = [
            error for error in self.error_history 
            if error.timestamp > datetime.now() - timedelta(hours=24)
        ]
        
        return {
            "total_errors": len(self.error_history),
            "recent_errors_24h": len(recent_errors),
            "category_distribution": category_stats,
            "severity_distribution": severity_stats,
            "most_common_category": max(category_stats.items(), key=lambda x: x[1])[0] if category_stats else None
        }
    
    def clear_error_history(self):
        """清理错误历史"""
        self.error_history.clear()
        logger.info("错误历史已清理")

# 全局错误管理器实例
_error_manager = None

def get_error_manager() -> UserFriendlyErrorManager:
    """获取错误管理器实例"""
    global _error_manager
    if _error_manager is None:
        _error_manager = UserFriendlyErrorManager()
    return _error_manager


def enhanced_handle_exceptions(func_name: str = None):
    """??????????"""

    def _on_exception(exception: Exception, name: str, context: Dict[str, str], default_response: Dict[str, Any]) -> Dict[str, Any]:
        error_manager = get_error_manager()
        try:
            error_info = error_manager.handle_error(exception, name, context)
        except Exception:
            return default_response

        return {
            'success': False,
            'error_id': error_info.error_id,
            'message': error_info.user_message,
            'suggested_actions': error_info.suggested_actions,
            'severity': error_info.severity.value,
            'timestamp': error_info.timestamp.isoformat()
        }

    return handle_exceptions(func_name, on_exception=_on_exception)


