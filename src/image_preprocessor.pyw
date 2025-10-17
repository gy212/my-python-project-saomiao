"""
图像预处理模块
提供图像质量增强、噪声去除、文本区域检测等功能
"""

import cv2
import numpy as np
import os
import logging
from typing import List, Tuple, Optional, Dict, Any
from PIL import Image, ImageEnhance
import tempfile


class ImagePreprocessor:
    """图像预处理器"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        初始化图像预处理器
        
        Args:
            temp_dir: 临时文件目录，如果为None则使用系统默认
        """
        self.logger = logging.getLogger(__name__)
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        # 预处理配置
        self.config = {
            'denoise_strength': 3,  # 降噪强度
            'contrast_factor': 1.2,  # 对比度增强因子
            'brightness_factor': 1.1,  # 亮度增强因子
            'sharpness_factor': 1.3,  # 锐化因子
            'dpi_target': 300,  # 目标DPI
            'min_text_area': 100,  # 最小文本区域面积
        }
    
    def preprocess_image(self, image_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        预处理单张图像
        
        Args:
            image_path: 图像文件路径
            options: 预处理选项
            
        Returns:
            包含处理结果的字典
        """
        try:
            if not os.path.exists(image_path):
                return {
                    'status': 'error',
                    'message': f'图像文件不存在: {image_path}',
                    'original_path': image_path
                }
            
            # 合并配置选项
            config = self.config.copy()
            if options:
                config.update(options)
            
            # 读取图像
            image = cv2.imread(image_path)
            if image is None:
                return {
                    'status': 'error',
                    'message': f'无法读取图像文件: {image_path}',
                    'original_path': image_path
                }
            
            # 执行预处理步骤
            processed_image = self._apply_preprocessing_pipeline(image, config)
            
            # 保存处理后的图像
            temp_path = self._save_processed_image(processed_image, image_path)
            
            # 计算图像质量指标
            quality_metrics = self._calculate_quality_metrics(image, processed_image)
            
            return {
                'status': 'success',
                'original_path': image_path,
                'processed_path': temp_path,
                'quality_metrics': quality_metrics,
                'config_used': config
            }
            
        except Exception as e:
            self.logger.error(f"图像预处理失败 {image_path}: {str(e)}")
            return {
                'status': 'error',
                'message': f'预处理失败: {str(e)}',
                'original_path': image_path
            }
    
    def _apply_preprocessing_pipeline(self, image: np.ndarray, config: Dict[str, Any]) -> np.ndarray:
        """应用预处理管道"""
        processed = image.copy()
        
        # 1. 降噪处理
        processed = self._denoise_image(processed, config['denoise_strength'])
        
        # 2. 对比度和亮度增强
        processed = self._enhance_contrast_brightness(processed, 
                                                    config['contrast_factor'], 
                                                    config['brightness_factor'])
        
        # 3. 锐化处理
        processed = self._sharpen_image(processed, config['sharpness_factor'])
        
        # 4. 文本区域优化
        processed = self._optimize_text_regions(processed, config['min_text_area'])
        
        # 5. 二值化处理（可选）
        if config.get('enable_binarization', False):
            processed = self._adaptive_binarization(processed)
        
        return processed
    
    def _denoise_image(self, image: np.ndarray, strength: int) -> np.ndarray:
        """图像降噪"""
        # 使用非局部均值降噪
        denoised = cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
        return denoised
    
    def _enhance_contrast_brightness(self, image: np.ndarray, contrast: float, brightness: float) -> np.ndarray:
        """增强对比度和亮度"""
        # 转换为PIL图像进行增强
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        # 对比度增强
        enhancer = ImageEnhance.Contrast(pil_image)
        enhanced = enhancer.enhance(contrast)
        
        # 亮度增强
        enhancer = ImageEnhance.Brightness(enhanced)
        enhanced = enhancer.enhance(brightness)
        
        # 转换回OpenCV格式
        return cv2.cvtColor(np.array(enhanced), cv2.COLOR_RGB2BGR)
    
    def _sharpen_image(self, image: np.ndarray, factor: float) -> np.ndarray:
        """图像锐化"""
        # 转换为PIL图像
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        # 锐化增强
        enhancer = ImageEnhance.Sharpness(pil_image)
        sharpened = enhancer.enhance(factor)
        
        # 转换回OpenCV格式
        return cv2.cvtColor(np.array(sharpened), cv2.COLOR_RGB2BGR)
    
    def _optimize_text_regions(self, image: np.ndarray, min_area: int) -> np.ndarray:
        """优化文本区域"""
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 使用MSER检测文本区域
        mser = cv2.MSER_create()
        regions, _ = mser.detectRegions(gray)
        
        # 创建文本区域掩码
        mask = np.zeros_like(gray)
        for region in regions:
            if len(region) > min_area:
                hull = cv2.convexHull(region.reshape(-1, 1, 2))
                cv2.fillPoly(mask, [hull], 255)
        
        # 在文本区域应用额外的增强
        enhanced = image.copy()
        text_regions = cv2.bitwise_and(enhanced, enhanced, mask=mask)
        
        # 对文本区域进行额外的对比度增强
        lab = cv2.cvtColor(text_regions, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
        enhanced_text = cv2.merge([l, a, b])
        enhanced_text = cv2.cvtColor(enhanced_text, cv2.COLOR_LAB2BGR)
        
        # 合并增强的文本区域和原图像
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) / 255.0
        result = enhanced * (1 - mask_3ch) + enhanced_text * mask_3ch
        
        return result.astype(np.uint8)
    
    def _adaptive_binarization(self, image: np.ndarray) -> np.ndarray:
        """自适应二值化"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 使用自适应阈值
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
        
        # 转换回3通道
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    
    def _save_processed_image(self, image: np.ndarray, original_path: str) -> str:
        """保存处理后的图像"""
        # 生成临时文件名
        base_name = os.path.splitext(os.path.basename(original_path))[0]
        temp_filename = f"{base_name}_processed.jpg"
        temp_path = os.path.join(self.temp_dir, temp_filename)
        
        # 保存图像
        cv2.imwrite(temp_path, image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        return temp_path
    
    def _calculate_quality_metrics(self, original: np.ndarray, processed: np.ndarray) -> Dict[str, float]:
        """计算图像质量指标"""
        try:
            # 转换为灰度图进行计算
            orig_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            proc_gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            
            # 计算PSNR (峰值信噪比)
            mse = np.mean((orig_gray - proc_gray) ** 2)
            if mse == 0:
                psnr = float('inf')
            else:
                psnr = 20 * np.log10(255.0 / np.sqrt(mse))
            
            # 计算对比度
            orig_contrast = np.std(orig_gray)
            proc_contrast = np.std(proc_gray)
            contrast_improvement = proc_contrast / orig_contrast if orig_contrast > 0 else 1.0
            
            # 计算清晰度 (使用Laplacian方差)
            orig_sharpness = cv2.Laplacian(orig_gray, cv2.CV_64F).var()
            proc_sharpness = cv2.Laplacian(proc_gray, cv2.CV_64F).var()
            sharpness_improvement = proc_sharpness / orig_sharpness if orig_sharpness > 0 else 1.0
            
            return {
                'psnr': float(psnr),
                'contrast_improvement': float(contrast_improvement),
                'sharpness_improvement': float(sharpness_improvement),
                'original_contrast': float(orig_contrast),
                'processed_contrast': float(proc_contrast),
                'original_sharpness': float(orig_sharpness),
                'processed_sharpness': float(proc_sharpness)
            }
            
        except Exception as e:
            self.logger.warning(f"质量指标计算失败: {str(e)}")
            return {}
    
    def batch_preprocess(self, image_paths: List[str], options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """批量预处理图像"""
        results = []
        
        for image_path in image_paths:
            result = self.preprocess_image(image_path, options)
            results.append(result)
            
            # 记录处理进度
            if len(results) % 10 == 0:
                self.logger.info(f"已预处理 {len(results)}/{len(image_paths)} 张图像")
        
        return results
    
    def cleanup_temp_files(self, results: List[Dict[str, Any]]):
        """清理临时文件"""
        cleaned_count = 0
        
        for result in results:
            if result.get('status') == 'success' and 'processed_path' in result:
                temp_path = result['processed_path']
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        cleaned_count += 1
                except Exception as e:
                    self.logger.warning(f"清理临时文件失败 {temp_path}: {str(e)}")
        
        self.logger.info(f"已清理 {cleaned_count} 个临时文件")
    
    def get_preprocessing_config(self) -> Dict[str, Any]:
        """获取当前预处理配置"""
        return self.config.copy()
    
    def update_preprocessing_config(self, new_config: Dict[str, Any]):
        """更新预处理配置"""
        self.config.update(new_config)
        self.logger.info(f"预处理配置已更新: {new_config}")


class TextRegionDetector:
    """文本区域检测器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_text_regions(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        检测图像中的文本区域
        
        Args:
            image: 输入图像
            
        Returns:
            文本区域边界框列表 [(x, y, w, h), ...]
        """
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 使用EAST文本检测器（如果可用）或回退到传统方法
            return self._detect_with_traditional_method(gray)
            
        except Exception as e:
            self.logger.error(f"文本区域检测失败: {str(e)}")
            return []
    
    def _detect_with_traditional_method(self, gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """使用传统方法检测文本区域"""
        # 形态学操作检测文本区域
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        
        # 梯度操作
        grad_x = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_8U, 0, 1, ksize=3)
        gradient = cv2.addWeighted(grad_x, 0.5, grad_y, 0.5, 0)
        
        # 二值化
        _, binary = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 形态学闭运算
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 过滤和返回边界框
        text_regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # 过滤太小的区域
            if w > 20 and h > 10 and w * h > 200:
                text_regions.append((x, y, w, h))
        
        return text_regions
