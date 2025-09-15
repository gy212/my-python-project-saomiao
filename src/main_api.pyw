# -----------------------------------------------------------------------------
# 功能: 主API接口模块
# 职责:
# 1. 整合所有后端模块 (OCR, 表格提取, 文件导出) 的功能。
# 2. 作为pywebview的js_api，直接暴露给前端JavaScript调用。
# 3. 管理应用状态，如窗口实例、选定的文件路径等。
# 4. (修正) 补全前端需要的 clear_text_cache 方法。
# 5. 集成统一的日志系统和错误处理
# 6. (新) 异步OCR处理支持
# -----------------------------------------------------------------------------
import os
import platform
import subprocess
import webview
import re

# 导入自定义模块 - 延迟导入优化
from . import config_manager as cfg
from .logger import get_logger, get_error_handler, handle_exceptions
from .error_manager import get_error_manager, enhanced_handle_exceptions
from .performance_monitor import get_performance_monitor, performance_monitor
from .batch_optimizer import BatchOptimizer, ProcessingConfig
from .image_preprocessor import ImagePreprocessor
from .text_postprocessor import TextPostProcessor
from .memory_manager import MemoryManager, MemoryConfig

class Api:
    def __init__(self):
        self._window = None
        # 延迟加载配置和服务
        self._config = None
        self._api_key = None
        self._ocr_service = None
        self._recent_scans_history = None
        
        # 延迟导入的模块
        self._ocr_service_module = None
        self._file_exporter_module = None
        self._table_extractor_module = None
        
        # 异步处理器
        self._async_processor = None
        
        # 批量处理优化器（延迟初始化）
        self._batch_optimizer = None
        self._image_preprocessor = None
        self._text_postprocessor = None
        self._memory_manager = None
        
        # 启动性能监控
        get_performance_monitor().start_monitoring()
        
        get_logger().info("API实例初始化完成，已集成错误管理和性能监控")

    def _get_config(self):
        """延迟加载配置（内部使用）"""
        if self._config is None:
            self._config = cfg.load_config_data(cfg.CONFIG_FILE, {"api_key": ""})
        return self._config
    
    def _get_api_key(self):
        """延迟获取API密钥（内部使用）"""
        if self._api_key is None:
            config = self._get_config()
            self._api_key = config.get("api_key", "")
            get_logger().info(f"[DEBUG] API密钥加载完成，长度: {len(self._api_key)}")
        return self._api_key
    
    def _apply_api_key(self, value):
        """Apply API key internally."""
        self._api_key = value
        if self._ocr_service is not None:
            self._ocr_service.set_api_key(value)
    
    def _get_ocr_service(self):
        """获取OCR服务实例（内部使用）"""
        if self._ocr_service is None:
            if self._ocr_service_module is None:
                from . import ocr_service
                self._ocr_service_module = ocr_service
            api_key = self._get_api_key()
            get_logger().info(f"[DEBUG] 创建OCR服务，传入API密钥长度: {len(api_key)}")
            self._ocr_service = self._ocr_service_module.OcrService(api_key)
        return self._ocr_service

    def _get_batch_optimizer(self):
        """获取批量处理优化器实例（内部使用）"""
        if self._batch_optimizer is None:
            # 根据系统配置创建优化配置
            config = ProcessingConfig(
                max_workers=min(4, os.cpu_count() or 2),
                max_memory_usage=0.75,  # 75%内存限制
                enable_compression=True,
                enable_preprocessing=True
            )
            self._batch_optimizer = BatchOptimizer(config)
            get_logger().info("批量处理优化器已初始化")
        return self._batch_optimizer

    def _get_image_preprocessor(self):
        """获取图像预处理器实例（内部使用）"""
        if self._image_preprocessor is None:
            self._image_preprocessor = ImagePreprocessor()
            get_logger().info("图像预处理器已初始化")
        return self._image_preprocessor

    def _get_text_postprocessor(self):
        """获取文本后处理器实例（内部使用）"""
        if self._text_postprocessor is None:
            self._text_postprocessor = TextPostProcessor()
            get_logger().info("文本后处理器已初始化")
        return self._text_postprocessor

    def _get_memory_manager(self):
        """获取内存管理器实例（内部使用）"""
        if self._memory_manager is None:
            memory_config = MemoryConfig()
            self._memory_manager = MemoryManager(memory_config)
            get_logger().info("内存管理器已初始化")
        return self._memory_manager

    def _get_async_processor(self):
        """获取异步处理器实例（内部使用）"""
        if self._async_processor is None:
            from .async_processor import AsyncOCRProcessor
            self._async_processor = AsyncOCRProcessor(self._get_ocr_service(), max_workers=3)
            # 注意：不在这里设置回调函数，避免JSON序列化问题
            # 回调函数将在需要时单独设置
            get_logger().info("异步处理器已初始化")
        return self._async_processor

    def get_async_processor_status(self):
        """获取异步处理器状态信息（JSON安全）"""
        try:
            processor = self._get_async_processor()
            # 安全地获取任务状态，避免返回包含回调函数的对象
            active_count = 0
            total_count = 0
            
            if hasattr(processor, 'tasks') and processor.tasks:
                total_count = len(processor.tasks)
                for task in processor.tasks.values():
                    if hasattr(task, 'status') and hasattr(task.status, 'value'):
                        if task.status.value in ['pending', 'running']:
                            active_count += 1
            
            return {
                "initialized": True,
                "max_workers": 3,
                "active_tasks": active_count,
                "total_tasks": total_count,
                "status": "ready"
            }
        except Exception as e:
            get_logger().error(f"获取异步处理器状态失败: {e}")
            return {
                "initialized": False,
                "max_workers": 3,
                "active_tasks": 0,
                "total_tasks": 0,
                "status": "error",
                "error": str(e)
            }

    def _on_async_progress(self, task_id: str, progress: float, status: str):
        """异步任务进度回调"""
        get_logger().debug(f"异步任务进度更新: {task_id} - {progress:.1f}% - {status}")
        # 通过webview向前端发送进度更新
        if self._window:
            try:
                self._window.evaluate_js(f"""
                    if (window.onAsyncProgress) {{
                        window.onAsyncProgress('{task_id}', {progress}, '{status}');
                    }}
                """)
            except Exception as e:
                get_logger().error(f"发送进度更新到前端失败: {e}")

    def _on_async_completion(self, task_id: str, result: dict):
        """异步任务完成回调"""
        get_logger().info(f"异步任务完成: {task_id}")
        # 通过webview向前端发送完成通知
        if self._window:
            try:
                import json
                result_json = json.dumps(result, ensure_ascii=False)
                self._window.evaluate_js(f"""
                    if (window.onAsyncCompletion) {{
                        window.onAsyncCompletion('{task_id}', {result_json});
                    }}
                """)
            except Exception as e:
                get_logger().error(f"发送完成通知到前端失败: {e}")
    
    def _get_recent_scans_history(self):
        """延迟加载扫描历史（内部使用）"""
        if self._recent_scans_history is None:
            self._recent_scans_history = cfg.load_scan_history()
        return self._recent_scans_history
    
    def set_recent_scans_history(self, value):
        """设置扫描历史"""
        self._recent_scans_history = value
    
    def _get_file_exporter(self):
        """延迟导入文件导出模块"""
        if self._file_exporter_module is None:
            from . import file_exporter
            self._file_exporter_module = file_exporter
        return self._file_exporter_module
    
    def _get_table_extractor(self):
        """延迟导入表格提取模块"""
        if self._table_extractor_module is None:
            from . import table_extractor
            self._table_extractor_module = table_extractor
        return self._table_extractor_module

    def _sanitize_filename(self, filename):
        """清理文件名，保留中文字符和常用符号，只移除Windows文件名不允许的字符。"""
        # Windows文件名不允许的字符: < > : " | ? * \ /
        # 以及控制字符 (ASCII 0-31)
        import string
        forbidden_chars = '<>:"|?*\\/'
        control_chars = ''.join(chr(i) for i in range(32))
        
        # 移除禁用字符
        sane_name = filename
        for char in forbidden_chars + control_chars:
            sane_name = sane_name.replace(char, '')
        
        # 移除首尾空格和点号（Windows不允许）
        sane_name = sane_name.strip(' .')
        
        # 如果清理后为空，使用默认名称
        if not sane_name:
            return "scanned_document"
        
        # 限制长度（Windows路径限制）
        if len(sane_name) > 200:
            sane_name = sane_name[:200]
            
        return sane_name

    # --- API方法 (暴露给JavaScript) ---
    def set_window(self, window):
        """由主程序调用，注入窗口实例。"""
        self._window = window

    def clear_text_cache(self):
        """清除所有缓存。"""
        try:
            # 清除OCR服务的文本缓存
            self._get_ocr_service().clear_text_cache()
            
            # 清除批量优化器缓存
            if self._batch_optimizer:
                self._batch_optimizer._cleanup_memory()
            
            # 清除内存管理器缓存
            if self._memory_manager:
                self._memory_manager.cleanup_memory()
            
            # 清除错误历史
            get_error_manager().clear_error_history()
            
            get_logger().info("所有缓存和错误历史已清除")
            return {"success": True, "message": "缓存清除成功"}
        except Exception as e:
            error_info = get_error_manager().handle_error(e, "clear_text_cache")
            return {
                "success": False, 
                "error_id": error_info.error_id,
                "message": error_info.user_message
            }

    @handle_exceptions("select_files")
    def select_files(self):
        """选择文件对话框"""
        get_logger().info("用户触发文件选择对话框")
        
        if not self._window:
            error_msg = "窗口实例未初始化，无法打开文件选择对话框"
            get_logger().error(error_msg)
            return get_error_handler().handle_validation_error(
                "window", None, "已初始化的窗口实例"
            )

        try:
            file_types = ('图片文件 (*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.tiff)', 'All files (*.*)')
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG, 
                allow_multiple=True, 
                file_types=file_types
            )
            
            if result:
                get_logger().info(f"用户选择了 {len(result)} 个文件: {[os.path.basename(f) for f in result]}")
                return get_error_handler().create_success_response(
                    data=result, 
                    message=f"成功选择 {len(result)} 个文件"
                )
            else:
                get_logger().info("用户取消了文件选择")
                return get_error_handler().create_success_response(
                    data=[], 
                    message="用户取消选择"
                )
        except Exception as e:
            return get_error_handler().handle_exception("select_files", e)

    @handle_exceptions("upload_files")
    def upload_files(self, file_data_list):
        """处理拖拽上传的文件"""
        get_logger().info(f"开始处理拖拽上传的 {len(file_data_list)} 个文件")
        
        try:
            import tempfile
            import base64
            
            uploaded_paths = []
            temp_dir = tempfile.mkdtemp(prefix="ocr_upload_")
            
            for i, file_data in enumerate(file_data_list):
                if not isinstance(file_data, dict) or 'name' not in file_data or 'data' not in file_data:
                    get_logger().warning(f"文件数据格式无效: {file_data}")
                    continue
                
                file_name = file_data['name']
                file_content = file_data['data']
                
                # 验证文件扩展名
                valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']
                if not any(file_name.lower().endswith(ext) for ext in valid_extensions):
                    get_logger().warning(f"跳过不支持的文件类型: {file_name}")
                    continue
                
                try:
                    # 解码base64数据
                    if file_content.startswith('data:'):
                        # 移除data URL前缀
                        file_content = file_content.split(',', 1)[1]
                    
                    file_bytes = base64.b64decode(file_content)
                    
                    # 保存到临时文件
                    temp_file_path = os.path.join(temp_dir, file_name)
                    with open(temp_file_path, 'wb') as f:
                        f.write(file_bytes)
                    
                    uploaded_paths.append(temp_file_path)
                    get_logger().info(f"成功保存上传文件: {file_name} -> {temp_file_path}")
                    
                except Exception as e:
                    get_logger().error(f"处理文件 {file_name} 时出错: {e}")
                    continue
            
            if uploaded_paths:
                get_logger().info(f"成功处理 {len(uploaded_paths)} 个上传文件")
                return get_error_handler().create_success_response(
                    data=uploaded_paths,
                    message=f"成功上传 {len(uploaded_paths)} 个文件"
                )
            else:
                return get_error_handler().handle_validation_error(
                    "files", file_data_list, "有效的图片文件"
                )
                
        except Exception as e:
            return get_error_handler().handle_exception("upload_files", e)

    @handle_exceptions("set_api_key")
    def set_api_key(self, api_key_value):
        """设置并保存API密钥。"""
        get_logger().info("用户设置API密钥")
        
        try:
            self._apply_api_key(api_key_value)
            self._get_ocr_service().set_api_key(api_key_value)
            self._get_config()["api_key"] = self._get_api_key()
            cfg.save_config_data(cfg.CONFIG_FILE, self._get_config())
            
            get_logger().info("API密钥设置成功")
            return get_error_handler().create_success_response(message="API密钥设置成功")
        except Exception as e:
            return get_error_handler().handle_exception("set_api_key", e)

    def get_recent_scans(self):
        """获取最近的扫描历史记录。"""
        return self._get_recent_scans_history()

    def clear_recent_scans_history(self):
        """清除扫描历史。"""
        self._get_recent_scans_history().clear()
        cfg.save_scan_history(self._get_recent_scans_history())
        return {"status": "成功", "message": "最近扫描历史已清除。"}

    def open_file_in_system(self, file_path):
        """尝试用系统默认程序打开指定的文件。"""
        if not file_path or not os.path.exists(file_path):
            return {"status": "失败", "message": "文件路径无效或不存在。"}
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.call(('open', file_path))
            else:
                subprocess.call(('xdg-open', file_path))
            return {"status": "成功", "message": f"已尝试打开文件: {os.path.basename(file_path)}"}
        except Exception as e:
            return {"status": "失败", "message": f"打开文件失败: {e}"}

    def get_image_as_base64_data_uri(self, file_path):
        """将图片转换为可供前端显示的Base64 URI。"""
        if not file_path or not os.path.exists(file_path):
            return None
        return self._get_ocr_service().image_to_base64_data_uri(file_path)

    def process_images(self, image_paths, output_format, merge_mode: str = "separate"):
        """处理一张或多张图片的核心工作流（优化版）。
        merge_mode: "separate"（默认，逐张保存）或 "combined"（合并为单一文件）。
        """
        get_logger().info(f"开始处理图片: {len(image_paths)} 张, 输出格式: {output_format}, 合并模式: {merge_mode}")
        
        if not image_paths:
            error_msg = "没有提供图片路径"
            get_logger().warning(error_msg)
            return get_error_handler().handle_validation_error("image_paths", image_paths, "非空的图片路径列表")
            
        if not self._window:
            error_msg = "窗口实例未初始化"
            get_logger().error(error_msg)
            return get_error_handler().handle_validation_error("window", None, "已初始化的窗口实例")

        # 内存管理：检查是否需要压缩图像
        memory_stats = self._get_memory_manager().get_memory_stats()
        get_logger().info(f"处理前内存状态: 进程内存={memory_stats.get('process_memory_mb', 0):.1f}MB, "
                        f"系统内存使用率={memory_stats.get('system_memory_usage_percent', 0):.1f}%")
        
        # 根据内存使用情况决定是否压缩图像
        compressed_paths = []
        for image_path in image_paths:
            if self._get_memory_manager().should_compress_image(image_path):
                compressed_path = self._get_memory_manager().compress_image(image_path)
                compressed_paths.append(compressed_path)
            else:
                compressed_paths.append(image_path)

        # 批量处理优化
        if len(compressed_paths) > 3:  # 超过3张图片时启用优化
            get_logger().info("启用批量处理优化")
            optimized_images = self._get_batch_optimizer().optimize_image_batch(compressed_paths)
            
            # 使用优化后的图片路径
            processed_paths = []
            for opt_img in optimized_images:
                if opt_img.get('status') == 'success':
                    # 如果有临时处理文件，使用临时文件；否则使用原文件
                    path = opt_img.get('temp_path') or opt_img['original_path']
                    processed_paths.append(path)
                else:
                    # 处理失败的图片仍使用原路径
                    processed_paths.append(opt_img['original_path'])
            
            # 记录优化统计
            stats = self._get_batch_optimizer().get_performance_stats()
            get_logger().info(f"批量优化统计: 处理图片={stats.get('processed_images', 0)}, "
                           f"缓存命中率={stats.get('cache_hit_rate', 0)*100:.1f}%, "
                           f"内存使用率={stats.get('current_memory_usage', 0)*100:.1f}%")
        else:
            processed_paths = compressed_paths

        # 图像预处理（可选）
        enable_preprocessing = merge_mode == "separate" or len(image_paths) <= 5  # 限制预处理条件
        if enable_preprocessing:
            get_logger().info("启用图像预处理")
            preprocessing_results = self._get_image_preprocessor().batch_preprocess(processed_paths)
            
            # 使用预处理后的图片路径
            final_paths = []
            for i, result in enumerate(preprocessing_results):
                if result.get('status') == 'success' and 'processed_path' in result:
                    final_paths.append(result['processed_path'])
                    # 记录质量改进指标
                    metrics = result.get('quality_metrics', {})
                    if metrics:
                        get_logger().info(f"图像 {os.path.basename(processed_paths[i])} 预处理完成: "
                                       f"对比度提升={metrics.get('contrast_improvement', 1.0):.2f}x, "
                                       f"清晰度提升={metrics.get('sharpness_improvement', 1.0):.2f}x")
                else:
                    final_paths.append(processed_paths[i])
        else:
            final_paths = processed_paths

        # 延迟导入模块
        table_extractor = self._get_table_extractor()
        file_exporter = self._get_file_exporter()

        results = []
        saved_count = 0
        processed_count = 0

        # 输出扩展名映射
        file_ext_map = {"word": "docx", "pdf": "pdf"}
        sel_ext = file_ext_map.get(output_format, 'txt')

        # 若为合并模式，先处理提取，稍后统一保存
        combined_text_parts = []

        for i, image_path in enumerate(final_paths):
            original_path = image_paths[i]  # 保持原始路径用于显示
            image_name = os.path.basename(original_path)
            current_file_result = {"file_name": image_name}
            
            get_logger().info(f"开始处理图片: {image_name}")

            try:
                # --- 新的三步工作流 ---
                get_logger().debug(f"步骤 1: 正在从 '{image_name}' 提取表格...")
                markdown_tables = table_extractor.extract_tables_as_markdown(image_path)

                get_logger().debug("步骤 2: 正在提取文本内容...")
                extraction_result = self._get_ocr_service().extract_text_from_image(image_path, markdown_tables)

                if extraction_result["status"] != "成功":
                    get_logger().warning(f"图片 {image_name} 文本提取失败: {extraction_result}")
                    current_file_result.update(extraction_result)
                    results.append(current_file_result)
                    continue

                processed_count += 1
                full_markdown_text = extraction_result["text"]
                
                # 文本后处理 - 提升OCR结果质量
                get_logger().debug("步骤 3: 正在进行文本后处理...")
                postprocess_result = self._get_text_postprocessor().process_text(
                    full_markdown_text, 
                    {
                        'enable_cleanup': True,
                        'enable_error_correction': True,
                        'enable_quality_assessment': True,
                        'enable_suggestions': False,  # 批量处理时不生成建议
                        'confidence_threshold': 0.7
                    }
                )
                
                if postprocess_result.get('status') == 'success':
                    processed_text = postprocess_result['processed_text']
                    quality_metrics = postprocess_result.get('quality_metrics')
                    
                    # 记录质量改进信息
                    if quality_metrics:
                        get_logger().info(f"图片 {image_name} 文本后处理完成: "
                                       f"置信度={quality_metrics.confidence_score:.2f}, "
                                       f"可读性={quality_metrics.readability_score:.2f}")
                        
                        # 如果质量指标显示有问题，记录警告
                        if quality_metrics.error_indicators:
                            get_logger().warning(f"图片 {image_name} 检测到质量问题: {', '.join(quality_metrics.error_indicators)}")
                    
                    current_file_result["extracted_text"] = processed_text
                    current_file_result["text_quality"] = {
                        'confidence_score': quality_metrics.confidence_score if quality_metrics else 0.0,
                        'original_length': len(full_markdown_text),
                        'processed_length': len(processed_text),
                        'processing_steps': postprocess_result.get('processing_steps', [])
                    }
                else:
                    # 后处理失败，使用原始文本
                    get_logger().warning(f"图片 {image_name} 文本后处理失败，使用原始文本")
                    current_file_result["extracted_text"] = full_markdown_text
                    current_file_result["text_quality"] = {'confidence_score': 0.5}
                
                get_logger().info(f"图片 {image_name} 处理完成，最终文本长度: {len(current_file_result['extracted_text'])} 字符")

                # 合并模式：先记录文本，稍后统一保存
                if merge_mode == "combined":
                    # 为每张图片添加标题分隔，便于阅读
                    base_title = os.path.splitext(image_name)[0]
                    combined_text_parts.append(f"\n\n# {base_title}\n\n" + full_markdown_text + "\n\n---\n")
                    current_file_result.update({"status": "提取成功但未保存", "error": "合并导出模式，稍后统一保存。"})
                    results.append(current_file_result)
                    continue

                # 分别导出模式：逐张保存
                get_logger().debug(f"步骤 3: 准备保存为 {output_format.upper()}...")
                base_name = os.path.splitext(image_name)[0]
                sanitized_base_name = self._sanitize_filename(base_name)
                default_filename = f"{sanitized_base_name}.{sel_ext}"

                save_path = self._window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    directory=os.path.dirname(image_path),
                    save_filename=default_filename
                )

                if not save_path:
                    get_logger().info("用户取消了合并文件的保存")
                    # 更新所有结果为"用户取消"
                    for result in results:
                        if result.get("status") == "提取成功但未保存":
                            result.update({"status": "提取成功但用户取消保存", "error": "用户取消了合并文件的保存。"})
                    final_status = "部分成功"
                    msg = f"提取成功但用户取消保存: {processed_count} 张图片"
                else:
                    save_path_str = save_path[0] if isinstance(save_path, tuple) else save_path

                    save_success = False
                    save_error = None

                    if output_format == "word":
                        save_success, save_error = file_exporter.save_to_word(current_file_result["extracted_text"], save_path_str)
                    elif output_format == "pdf":
                        save_success, save_error = file_exporter.save_to_pdf(current_file_result["extracted_text"], save_path_str)

                    if save_success:
                        saved_count = processed_count  # 合并模式下，成功保存意味着所有图片都成功
                        get_logger().info(f"合并文件保存成功: {save_path_str}")
                        # 更新所有结果为"成功"
                        for result in results:
                            if result.get("status") == "提取成功但未保存":
                                result.update({"status": "成功并已保存", "saved_path": save_path_str})
                        
                        # 添加到历史记录
                        cfg.add_scan_to_history(
                            self._get_recent_scans_history(), f"{processed_count}张图片合并",
                            os.path.basename(save_path_str), sel_ext, save_path_str
                        )
                    else:
                        get_logger().error(f"合并文件保存失败: {save_error}")
                        # 更新所有结果为"保存失败"
                        for result in results:
                            if result.get("status") == "提取成功但未保存":
                                result.update({"status": "提取成功但保存失败", "error": f"合并文件保存时出错: {save_error}"})

            except Exception as e:
                get_logger().exception(f"处理图片 '{image_name}' 时发生意外错误: {e}")
                current_file_result.update({"status": "处理时发生意外错误", "error": str(e)})

            results.append(current_file_result)

        # 合并模式：统一保存一次
        if merge_mode == "combined" and processed_count > 0:
            get_logger().info(f"开始合并保存 {processed_count} 张图片的内容为 {output_format.upper()}")
            # 默认文件名：以第一张图片名为基底，加后缀"_合并"
            first_image_name = os.path.basename(image_paths[0])
            base_name = os.path.splitext(first_image_name)[0]
            sanitized_base_name = self._sanitize_filename(base_name)
            default_filename = f"{sanitized_base_name}_合并.{sel_ext}"

            save_path = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=os.path.dirname(image_paths[0]),
                save_filename=default_filename
            )

            if not save_path:
                get_logger().info("用户取消了合并文件的保存")
                # 更新所有结果为"用户取消"
                for result in results:
                    if result.get("status") == "提取成功但未保存":
                        result.update({"status": "提取成功但用户取消保存", "error": "用户取消了合并文件的保存。"})
                final_status = "部分成功"
                msg = f"提取成功但用户取消保存: {processed_count} 张图片"
            else:
                save_path_str = save_path[0] if isinstance(save_path, tuple) else save_path
                combined_markdown = "\n".join(combined_text_parts)

                save_success = False
                save_error = None
                if output_format == "word":
                    save_success, save_error = file_exporter.save_to_word(combined_markdown, save_path_str)
                elif output_format == "pdf":
                    save_success, save_error = file_exporter.save_to_pdf(combined_markdown, save_path_str)

                if save_success:
                    saved_count = processed_count  # 合并模式下，成功保存意味着所有图片都成功
                    get_logger().info(f"合并文件保存成功: {save_path_str}")
                    # 更新所有结果为"成功"
                    for result in results:
                        if result.get("status") == "提取成功但未保存":
                            result.update({"status": "成功并已保存", "saved_path": save_path_str})
                    
                    # 添加到历史记录
                    cfg.add_scan_to_history(
                        self._get_recent_scans_history(), f"{processed_count}张图片合并",
                        os.path.basename(save_path_str), sel_ext, save_path_str
                    )
                else:
                    get_logger().error(f"合并文件保存失败: {save_error}")
                    # 更新所有结果为"保存失败"
                    for result in results:
                        if result.get("status") == "提取成功但未保存":
                            result.update({"status": "提取成功但保存失败", "error": f"合并文件保存时出错: {save_error}"})

        # 最终状态判断
        if saved_count == len(image_paths):
            final_status = "成功"
            msg = f"所有图片处理成功: {saved_count}/{len(image_paths)}"
            get_logger().info(f"所有图片处理成功: {saved_count}/{len(image_paths)}")
        elif merge_mode == "combined" and processed_count > 0:
            final_status = "成功"
            msg = f"合并处理成功: {processed_count} 张图片"
            get_logger().info(f"合并处理成功: {processed_count} 张图片")
        elif saved_count > 0:
            final_status = "部分成功"
            msg = f"部分处理成功: 保存 {saved_count}/{processed_count}, 总共 {len(image_paths)}"
            get_logger().warning(f"部分处理成功: 保存 {saved_count}/{processed_count}, 总共 {len(image_paths)}")
        else:
            final_status = "失败"
            msg = f"所有图片处理失败: 总共 {len(image_paths)} 张"
            get_logger().error(f"所有图片处理失败: 总共 {len(image_paths)} 张")
        
        get_logger().info(f"图片处理完成: 状态={final_status}, 消息={msg}")
        
        # 处理后内存状态
        final_memory_stats = self._get_memory_manager().get_memory_stats()
        get_logger().info(f"处理后内存状态: 进程内存={final_memory_stats.get('process_memory_mb', 0):.1f}MB, "
                        f"系统内存使用率={final_memory_stats.get('system_memory_usage_percent', 0):.1f}%")
        
        # 如果内存使用率过高，执行清理
        if final_memory_stats.get('system_memory_usage_percent', 0) > 80:
            get_logger().info("内存使用率较高，执行清理")
            self._get_memory_manager().cleanup_memory()
        
        return {"status": final_status, "message": msg, "results": results}


    # ========== 异步OCR处理方法 ==========
    
    @handle_exceptions("start_async_ocr")
    def start_async_ocr(self, image_paths: list, output_format: str = "word", merge_mode: str = "separate") -> dict:
        """启动异步OCR处理
        
        Args:
            image_paths: 图片路径列表
            output_format: 输出格式 ("word" 或 "pdf")
            merge_mode: 合并模式 ("separate" 或 "combined")
            
        Returns:
            dict: 包含任务ID列表和状态的响应
        """
        try:
            if not image_paths:
                # 修复: 使用前端期望的状态字段
                return {"status": "失败", "message": "未选择任何图片"}
        
            get_logger().info(f"启动异步OCR处理: {len(image_paths)} 张图片")
            
            # 获取异步处理器
            async_processor = self._get_async_processor()
        
            # 预处理：检查文件存在性并提取表格
            valid_tasks = []
            for image_path in image_paths:
                if not os.path.exists(image_path):
                    get_logger().warning(f"图片文件不存在: {image_path}")
                    continue
                    
                # 预提取表格
                try:
                    table_extractor = self._get_table_extractor()
                    markdown_tables = table_extractor.extract_tables_as_markdown(image_path)
                    get_logger().debug(f"预提取表格: {image_path} - {len(markdown_tables)} 个表格")
                except Exception:
                    markdown_tables = []
                    get_logger().debug(f"表格提取失败或无表格: {image_path}")
                
                valid_tasks.append({
                    'image_path': image_path,
                    'markdown_tables': markdown_tables,
                    'output_format': output_format
                })
            
            # 提交异步任务（修复: 使用现有的批量提交方法）
            image_paths_list = [t['image_path'] for t in valid_tasks]
            markdown_tables_list = [t['markdown_tables'] for t in valid_tasks]
            task_ids = async_processor.submit_batch_ocr_tasks(image_paths_list, markdown_tables_list)
        
            get_logger().info(f"异步OCR任务已提交: {len(task_ids)} 个任务")
            
            return {
                "status": "成功",
                "message": f"已启动 {len(task_ids)} 个异步OCR任务",
                "task_id": (task_ids[0] if task_ids else None),
                "task_ids": task_ids,
                "total_tasks": len(task_ids)
            }
            
        except Exception as e:
            get_logger().error(f"启动异步OCR处理失败: {e}")
            # 修复: 返回前端可识别的错误结构
            return {"status": "失败", "message": str(e)}

    @handle_exceptions("get_async_task_status")
    def get_async_task_status(self, task_id: str = None) -> dict:
        """获取异步任务状态
        
        Args:
            task_id: 任务ID，如果为None则返回所有任务状态
            
        Returns:
            dict: 任务状态信息（与前端监控逻辑兼容的结构）
        """
        try:
            processor = self._get_async_processor()
            if task_id:
                status = processor.get_task_status(task_id)
                if status:
                    # 兼容前端: 顶层包含 status/completed/total/current_task/results
                    current_task = os.path.basename(status.get("image_path")) if status.get("image_path") else ""
                    results = []
                    if status.get("result"):
                        # 提取文本以便前端展示
                        extracted_text = status["result"].get("extracted_text") or status["result"].get("text")
                        results.append({"extracted_text": extracted_text})
                    return {
                        "status": status.get("status"),
                        "progress": status.get("progress", 0.0),
                        "completed": 1 if status.get("status") == "completed" else (0 if status.get("status") in ["pending", "running"] else 0),
                        "total": 1,
                        "current_task": current_task,
                        "results": results,
                        "error": status.get("error")
                    }
                else:
                    return {"status": "失败", "message": f"任务不存在: {task_id}"}
            else:
                all_status = processor.get_all_tasks_status()
                total = len(all_status)
                completed = sum(1 for s in all_status.values() if s.get("status") == "completed")
                # 取一个正在进行或待处理的任务名称
                running_task = next((s for s in all_status.values() if s.get("status") in ["running", "pending"]), None)
                current_task = os.path.basename(running_task.get("image_path")) if running_task and running_task.get("image_path") else ""
                results = []
                for s in all_status.values():
                    if s.get("result"):
                        extracted_text = s["result"].get("extracted_text") or s["result"].get("text")
                        results.append({"extracted_text": extracted_text})
                return {
                    "status": "running" if completed < total else "completed",
                    "completed": completed,
                    "total": total,
                    "current_task": current_task,
                    "results": results
                }
        except Exception as e:
            return {"status": "失败", "message": str(e)}

    @handle_exceptions("cancel_async_task")
    def cancel_async_task(self, task_id: str = None) -> dict:
        """取消异步任务
        
        Args:
            task_id: 任务ID，如果为None则取消所有任务
            
        Returns:
            dict: 取消结果
        """
        try:
            if task_id:
                success = self._get_async_processor().cancel_task(task_id)
                if success:
                    get_logger().info(f"异步任务已取消: {task_id}")
                    return get_error_handler().create_success_response({"message": f"任务 {task_id} 已取消"})
                else:
                    return get_error_handler().handle_validation_error("task_id", task_id, "cancellable task id")
            else:
                cancelled_count = self._get_async_processor().cancel_all_tasks()
                get_logger().info(f"已取消 {cancelled_count} 个异步任务")
                return get_error_handler().create_success_response({
                    "cancelled_count": cancelled_count,
                    "message": f"已取消 {cancelled_count} 个任务"
                })
        except Exception as e:
            return get_error_handler().handle_exception(e)
    
    @handle_exceptions("cleanup_async_tasks")
    def cleanup_async_tasks(self, keep_recent: int = 10) -> dict:
        """清理已完成的异步任务
        
        Args:
            keep_recent: 保留最近的任务数量
            
        Returns:
            dict: 清理结果
        """
        try:
            removed_count = self._get_async_processor().cleanup_completed_tasks(keep_recent)
            get_logger().info(f"清理了 {removed_count} 个已完成的异步任务")
            return get_error_handler().create_success_response({
                "removed_count": removed_count,
                "message": f"清理了 {removed_count} 个已完成的任务"
            })
        except Exception as e:
            return get_error_handler().handle_exception(e)
    
    def get_performance_stats(self):
        """获取性能统计信息（JSON安全）"""
        try:
            status = get_performance_monitor().get_current_status()
            # 确保返回的数据是JSON安全的
            return {
                "success": True,
                "data": {
                    "monitoring_active": status.get("monitoring_active", False),
                    "timestamp": status.get("timestamp", ""),
                    "summary": status.get("summary", {}),
                    "analysis": status.get("analysis", {})
                }
            }
        except Exception as e:
            return get_error_handler().handle_exception("get_performance_stats", e)

    def get_error_stats(self):
        """获取错误统计信息（JSON安全）"""
        try:
            stats = get_error_manager().get_error_statistics()
            # 确保返回的数据是JSON安全的
            return {
                "success": True,
                "data": {
                    "total_errors": stats.get("total_errors", 0),
                    "recent_errors_24h": stats.get("recent_errors_24h", 0),
                    "category_distribution": stats.get("category_distribution", {}),
                    "severity_distribution": stats.get("severity_distribution", {}),
                    "most_common_category": stats.get("most_common_category", None)
                }
            }
        except Exception as e:
            return get_error_handler().handle_exception("get_error_stats", e)

    @enhanced_handle_exceptions("export_performance_data")
    def export_performance_data(self, file_path: str = None):
        """导出性能数据"""
        if not file_path:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"performance_data_{timestamp}.json"
        
        get_performance_monitor().export_performance_data(file_path)
        return {
            "success": True,
            "message": f"性能数据已导出到: {file_path}",
            "file_path": file_path
        }

    @enhanced_handle_exceptions("save_async_results")
    def save_async_results(self, results, output_format, merge_mode: str = "separate"):
        """保存异步处理结果"""
        get_logger().info(f"开始保存异步处理结果: {len(results)} 个结果, 格式: {output_format}, 模式: {merge_mode}")
        
        if not results:
            return get_error_handler().handle_validation_error("results", results, "非空的结果列表")
            
        if not self._window:
            return get_error_handler().handle_validation_error("window", None, "已初始化的窗口实例")

        # 过滤出成功提取的结果
        successful_results = [r for r in results if r.get('extracted_text') and r['extracted_text'].strip()]
        
        if not successful_results:
            return {
                "success": False,
                "message": "没有成功提取的文本内容可保存"
            }

        # 延迟导入文件导出模块
        file_exporter = self._get_file_exporter()
        
        # 输出扩展名映射
        file_ext_map = {"word": "docx", "pdf": "pdf", "txt": "txt"}
        sel_ext = file_ext_map.get(output_format, 'txt')

        try:
            if merge_mode == "combined":
                # 合并模式：将所有文本合并为一个文件
                combined_text_parts = []
                for result in successful_results:
                    file_name = result.get('file_name', '未知文件')
                    base_title = os.path.splitext(file_name)[0]
                    combined_text_parts.append(f"\n\n# {base_title}\n\n{result['extracted_text']}\n\n---\n")
                
                combined_text = "".join(combined_text_parts)
                
                # 生成默认文件名
                default_filename = f"异步处理结果_合并.{sel_ext}"
                
                # 弹出保存对话框
                save_path = self._window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    save_filename=default_filename
                )
                
                if not save_path:
                    return {
                        "success": False,
                        "message": "用户取消了文件保存"
                    }
                
                save_path_str = save_path[0] if isinstance(save_path, tuple) else save_path
                
                # 保存文件
                save_success = False
                save_error = None
                
                if output_format == "word":
                    save_success, save_error = file_exporter.save_to_word(combined_text, save_path_str)
                elif output_format == "pdf":
                    save_success, save_error = file_exporter.save_to_pdf(combined_text, save_path_str)
                else:  # txt
                    try:
                        with open(save_path_str, 'w', encoding='utf-8') as f:
                            f.write(combined_text)
                        save_success = True
                    except Exception as e:
                        save_error = str(e)
                
                if save_success:
                    get_logger().info(f"异步结果合并保存成功: {save_path_str}")
                    return {
                        "success": True,
                        "message": f"成功保存 {len(successful_results)} 个结果到合并文件",
                        "saved_path": save_path_str
                    }
                else:
                    get_logger().error(f"异步结果合并保存失败: {save_error}")
                    return {
                        "success": False,
                        "message": f"保存失败: {save_error}"
                    }
            
            else:
                # 分别保存模式：逐个保存每个文件
                saved_files = []
                failed_files = []
                
                for result in successful_results:
                    file_name = result.get('file_name', '未知文件')
                    base_name = os.path.splitext(file_name)[0]
                    sanitized_base_name = self._sanitize_filename(base_name)
                    default_filename = f"{sanitized_base_name}.{sel_ext}"
                    
                    # 为每个文件弹出保存对话框
                    save_path = self._window.create_file_dialog(
                        webview.SAVE_DIALOG,
                        save_filename=default_filename
                    )
                    
                    if not save_path:
                        failed_files.append(f"{file_name} (用户取消)")
                        continue
                    
                    save_path_str = save_path[0] if isinstance(save_path, tuple) else save_path
                    
                    # 保存单个文件
                    save_success = False
                    save_error = None
                    
                    if output_format == "word":
                        save_success, save_error = file_exporter.save_to_word(result['extracted_text'], save_path_str)
                    elif output_format == "pdf":
                        save_success, save_error = file_exporter.save_to_pdf(result['extracted_text'], save_path_str)
                    else:  # txt
                        try:
                            with open(save_path_str, 'w', encoding='utf-8') as f:
                                f.write(result['extracted_text'])
                            save_success = True
                        except Exception as e:
                            save_error = str(e)
                    
                    if save_success:
                        saved_files.append(save_path_str)
                        get_logger().info(f"异步结果单独保存成功: {save_path_str}")
                    else:
                        failed_files.append(f"{file_name} ({save_error})")
                        get_logger().error(f"异步结果单独保存失败: {file_name} - {save_error}")
                
                # 返回保存结果统计
                if saved_files:
                    message = f"成功保存 {len(saved_files)} 个文件"
                    if failed_files:
                        message += f"，失败 {len(failed_files)} 个"
                    
                    return {
                        "success": True,
                        "message": message,
                        "saved_files": saved_files,
                        "failed_files": failed_files
                    }
                else:
                    return {
                        "success": False,
                        "message": f"所有文件保存失败: {'; '.join(failed_files)}"
                    }
                    
        except Exception as e:
            error_msg = f"保存异步结果时发生错误: {str(e)}"
            get_logger().error(error_msg)
            return {
                "success": False,
                "message": error_msg
            }

