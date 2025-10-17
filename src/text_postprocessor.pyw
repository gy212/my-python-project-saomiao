"""
文本后处理模块
提供OCR结果质量提升功能，包括文本清理、置信度评估、人工校对支持
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import difflib


@dataclass
class TextQualityMetrics:
    """文本质量指标"""
    confidence_score: float  # 置信度分数 (0-1)
    character_count: int     # 字符数
    word_count: int         # 词数
    line_count: int         # 行数
    error_indicators: List[str]  # 错误指标
    readability_score: float     # 可读性分数 (0-1)
    completeness_score: float    # 完整性分数 (0-1)


@dataclass
class CorrectionSuggestion:
    """校正建议"""
    original_text: str      # 原始文本
    suggested_text: str     # 建议文本
    confidence: float       # 建议置信度
    reason: str            # 建议原因
    position: Tuple[int, int]  # 位置 (start, end)


class TextPostProcessor:
    """文本后处理器"""
    
    def __init__(self):
        """初始化文本后处理器"""
        self.logger = logging.getLogger(__name__)
        
        # 常见OCR错误模式
        self.common_errors = {
            # 数字和字母混淆
            'O': '0', '0': 'O', 'I': '1', '1': 'I', 'l': '1',
            'S': '5', '5': 'S', 'Z': '2', '2': 'Z',
            # 中文字符常见错误
            '门': '们', '们': '门', '未': '末', '末': '未',
            '己': '已', '已': '己', '白': '百', '百': '白',
        }
        
        # 常见词汇字典（用于拼写检查）
        self.common_words = set()
        self._load_common_words()
        
        # Cleanup rules (Markdown/LaTeX safe)
        self.cleanup_patterns = [
            (r'\r\n?', '\n'),  # normalize newlines
            (r'\u00a0', ' '),  # replace non-breaking space
            (r'\u200b', ''),  # drop zero-width space
            (r'\u200c', ''),  # drop zero-width non-joiner
            (r'\u200d', ''),  # drop zero-width joiner
            (r'\ufeff', ''),  # remove BOM
            (r'\n{3,}', '\n\n'),  # limit consecutive blank lines
        ]
        self._control_char_pattern = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]')

    def _load_common_words(self):
        """加载常见词汇"""
        # 这里可以从文件加载，现在使用一些基本词汇
        basic_words = [
            '公司', '有限', '责任', '股份', '集团', '企业', '商贸', '科技',
            '发展', '投资', '管理', '服务', '贸易', '实业', '控股', '国际',
            '中国', '北京', '上海', '广州', '深圳', '杭州', '南京', '成都',
            '地址', '电话', '传真', '邮编', '网址', '邮箱', '联系人',
            '年', '月', '日', '时', '分', '秒', '元', '万', '亿',
        ]
        self.common_words.update(basic_words)
    
    def process_text(self, text: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理文本，提升OCR结果质量
        
        Args:
            text: 原始OCR文本
            options: 处理选项
            
        Returns:
            处理结果字典
        """
        try:
            if not text or not text.strip():
                return {
                    'status': 'error',
                    'message': '输入文本为空',
                    'original_text': text
                }
            
            # 默认选项
            default_options = {
                'enable_cleanup': True,
                'enable_error_correction': True,
                'enable_quality_assessment': True,
                'enable_suggestions': True,
                'confidence_threshold': 0.7
            }
            
            if options:
                default_options.update(options)
            
            result = {
                'status': 'success',
                'original_text': text,
                'processed_text': text,
                'processing_steps': [],
                'quality_metrics': None,
                'suggestions': [],
                'confidence_score': 0.0
            }
            
            # 1. 文本清理
            if default_options['enable_cleanup']:
                cleaned_text = self._clean_text(text)
                result['processed_text'] = cleaned_text
                result['processing_steps'].append('text_cleanup')
                self.logger.debug(f"文本清理完成，长度从 {len(text)} 变为 {len(cleaned_text)}")
            
            # 2. 错误校正
            if default_options['enable_error_correction']:
                corrected_text = self._correct_common_errors(result['processed_text'])
                result['processed_text'] = corrected_text
                result['processing_steps'].append('error_correction')
            
            # 3. 质量评估
            if default_options['enable_quality_assessment']:
                quality_metrics = self._assess_text_quality(result['processed_text'])
                result['quality_metrics'] = quality_metrics
                result['confidence_score'] = quality_metrics.confidence_score
                result['processing_steps'].append('quality_assessment')
            
            # 4. 生成改进建议
            if default_options['enable_suggestions']:
                suggestions = self._generate_suggestions(
                    result['original_text'], 
                    result['processed_text'],
                    default_options['confidence_threshold']
                )
                result['suggestions'] = suggestions
                result['processing_steps'].append('suggestion_generation')
            
            return result
            
        except Exception as e:
            self.logger.error(f"文本后处理失败: {str(e)}")
            return {
                'status': 'error',
                'message': f'处理失败: {str(e)}',
                'original_text': text
            }
    
    def _clean_text(self, text: str) -> str:
        """Clean text while preserving Markdown/LaTeX syntax"""
        if not text:
            return ''

        cleaned = text

        # Apply cleanup patterns
        for pattern, replacement in self.cleanup_patterns:
            cleaned = re.sub(pattern, replacement, cleaned)

        # Remove invisible control characters
        cleaned = self._remove_control_chars(cleaned)

        # Fix common OCR spacing issues
        cleaned = self._fix_spacing_issues(cleaned)

        return cleaned.strip()

    def _remove_control_chars(self, text: str) -> str:
        """Remove control chars without touching Markdown-friendly tokens"""
        return self._control_char_pattern.sub('', text)

    def _fix_spacing_issues(self, text: str) -> str:
        """修复空格问题"""
        # 中文字符间不应有空格
        text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', text)
        
        # 数字和单位间应有空格
        text = re.sub(r'(\d+)([a-zA-Z\u4e00-\u9fff])', r'\1 \2', text)
        
        # 标点符号前不应有空格
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        
        return text
    
    def _correct_common_errors(self, text: str) -> str:
        """校正常见错误"""
        corrected = text
        
        # 应用常见错误替换
        for wrong, correct in self.common_errors.items():
            # 只在特定上下文中替换，避免误替换
            if self._should_replace_character(corrected, wrong, correct):
                corrected = corrected.replace(wrong, correct)
        
        # 修复数字格式
        corrected = self._fix_number_formats(corrected)
        
        # 修复日期格式
        corrected = self._fix_date_formats(corrected)
        
        return corrected
    
    def _should_replace_character(self, text: str, wrong: str, correct: str) -> bool:
        """判断是否应该替换字符"""
        # 简单的上下文检查
        if wrong.isdigit() and correct.isalpha():
            # 如果在数字上下文中，不替换数字为字母
            pattern = rf'\d*{re.escape(wrong)}\d*'
            if re.search(pattern, text):
                return False
        
        return True
    
    def _fix_number_formats(self, text: str) -> str:
        """修复数字格式"""
        # 修复电话号码格式
        text = re.sub(r'(\d{3})\s*-?\s*(\d{4})\s*-?\s*(\d{4})', r'\1-\2-\3', text)
        
        # 修复邮编格式
        text = re.sub(r'(\d{6})', lambda m: m.group(1) if len(m.group(1)) == 6 else m.group(0), text)
        
        return text
    
    def _fix_date_formats(self, text: str) -> str:
        """修复日期格式"""
        # 修复年月日格式
        text = re.sub(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', r'\1年\2月\3日', text)
        
        # 修复数字日期格式
        text = re.sub(r'(\d{4})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})', r'\1/\2/\3', text)
        
        return text
    
    def _assess_text_quality(self, text: str) -> TextQualityMetrics:
        """评估文本质量"""
        # 基本统计
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.split('\n'))
        
        # 计算置信度分数
        confidence_score = self._calculate_confidence_score(text)
        
        # 检测错误指标
        error_indicators = self._detect_error_indicators(text)
        
        # 计算可读性分数
        readability_score = self._calculate_readability_score(text)
        
        # 计算完整性分数
        completeness_score = self._calculate_completeness_score(text)
        
        return TextQualityMetrics(
            confidence_score=confidence_score,
            character_count=char_count,
            word_count=word_count,
            line_count=line_count,
            error_indicators=error_indicators,
            readability_score=readability_score,
            completeness_score=completeness_score
        )
    
    def _calculate_confidence_score(self, text: str) -> float:
        """计算置信度分数"""
        score = 1.0
        
        # 检查异常字符比例
        total_chars = len(text)
        if total_chars == 0:
            return 0.0
        
        # 计算可识别字符比例
        recognizable_chars = len(re.findall(r'[\w\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef.,!?;:()[\]{}""''—-]', text))
        recognizable_ratio = recognizable_chars / total_chars
        
        # 检查连续特殊字符
        special_sequences = len(re.findall(r'[^\w\s\u4e00-\u9fff]{3,}', text))
        if special_sequences > 0:
            score -= 0.2 * special_sequences / total_chars * 100
        
        # 检查字符分布合理性
        char_distribution_score = self._assess_character_distribution(text)
        
        final_score = score * recognizable_ratio * char_distribution_score
        return max(0.0, min(1.0, final_score))
    
    def _assess_character_distribution(self, text: str) -> float:
        """评估字符分布合理性"""
        if not text:
            return 0.0
        
        # 统计不同类型字符的比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        digits = len(re.findall(r'\d', text))
        spaces = len(re.findall(r'\s', text))
        punctuation = len(re.findall(r'[.,!?;:()[\]{}""''—-]', text))
        
        total = len(text)
        
        # 计算分布合理性
        ratios = {
            'chinese': chinese_chars / total,
            'english': english_chars / total,
            'digits': digits / total,
            'spaces': spaces / total,
            'punctuation': punctuation / total
        }
        
        # 合理的分布应该不会有某一类字符占比过高
        max_ratio = max(ratios.values())
        if max_ratio > 0.8:  # 某类字符占比超过80%可能有问题
            return 0.5
        
        return 1.0
    
    def _detect_error_indicators(self, text: str) -> List[str]:
        """检测错误指标"""
        indicators = []
        
        # 检查连续重复字符
        if re.search(r'(.)\1{4,}', text):
            indicators.append('连续重复字符')
        
        # 检查异常空格
        if re.search(r'\s{5,}', text):
            indicators.append('异常空格')
        
        # 检查乱码字符
        if re.search(r'[^\w\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef.,!?;:()[\]{}""''—-]{3,}', text):
            indicators.append('疑似乱码')
        
        # 检查不完整的词汇
        incomplete_words = re.findall(r'\b\w{1,2}\b', text)
        if len(incomplete_words) > len(text.split()) * 0.3:
            indicators.append('过多短词')
        
        return indicators
    
    def _calculate_readability_score(self, text: str) -> float:
        """计算可读性分数"""
        if not text.strip():
            return 0.0
        
        # 基于句子长度和词汇复杂度的简单可读性评估
        sentences = re.split(r'[.!?。！？]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.5
        
        # 平均句子长度
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        
        # 理想句子长度为10-20个词
        if 10 <= avg_sentence_length <= 20:
            length_score = 1.0
        elif avg_sentence_length < 5 or avg_sentence_length > 30:
            length_score = 0.3
        else:
            length_score = 0.7
        
        return length_score
    
    def _calculate_completeness_score(self, text: str) -> float:
        """计算完整性分数"""
        if not text.strip():
            return 0.0
        
        score = 1.0
        
        # 检查是否有明显的截断
        if text.endswith('...') or text.endswith('…'):
            score -= 0.2
        
        # 检查是否有不完整的句子
        if not re.search(r'[.!?。！？]$', text.strip()):
            score -= 0.1
        
        # 检查是否有孤立的标点符号
        isolated_punct = len(re.findall(r'\s[.,!?;:]\s', text))
        if isolated_punct > 0:
            score -= 0.1 * isolated_punct
        
        return max(0.0, score)
    
    def _generate_suggestions(self, original: str, processed: str, threshold: float) -> List[CorrectionSuggestion]:
        """生成改进建议"""
        suggestions = []
        
        # 比较原文和处理后的文本
        if original != processed:
            # 使用difflib找出差异
            differ = difflib.SequenceMatcher(None, original, processed)
            
            for tag, i1, i2, j1, j2 in differ.get_opcodes():
                if tag == 'replace':
                    suggestion = CorrectionSuggestion(
                        original_text=original[i1:i2],
                        suggested_text=processed[j1:j2],
                        confidence=0.8,
                        reason='自动校正',
                        position=(i1, i2)
                    )
                    suggestions.append(suggestion)
        
        # 添加其他类型的建议
        suggestions.extend(self._suggest_formatting_improvements(processed))
        suggestions.extend(self._suggest_content_improvements(processed))
        
        # 过滤低置信度建议
        return [s for s in suggestions if s.confidence >= threshold]
    
    def _suggest_formatting_improvements(self, text: str) -> List[CorrectionSuggestion]:
        """建议格式改进"""
        suggestions = []
        
        # 检查标点符号使用
        if re.search(r'[a-zA-Z\u4e00-\u9fff][.!?]', text):
            # 建议在句号后添加空格
            for match in re.finditer(r'([a-zA-Z\u4e00-\u9fff])([.!?])([a-zA-Z\u4e00-\u9fff])', text):
                suggestions.append(CorrectionSuggestion(
                    original_text=match.group(0),
                    suggested_text=f"{match.group(1)}{match.group(2)} {match.group(3)}",
                    confidence=0.7,
                    reason='标点符号后建议添加空格',
                    position=(match.start(), match.end())
                ))
        
        return suggestions
    
    def _suggest_content_improvements(self, text: str) -> List[CorrectionSuggestion]:
        """建议内容改进"""
        suggestions = []
        
        # 检查可能的拼写错误（基于常见词汇）
        words = re.findall(r'\b[\u4e00-\u9fff]+\b', text)
        for word in words:
            if len(word) > 1 and word not in self.common_words:
                # 寻找相似的常见词汇
                similar_words = difflib.get_close_matches(word, self.common_words, n=1, cutoff=0.8)
                if similar_words:
                    suggestions.append(CorrectionSuggestion(
                        original_text=word,
                        suggested_text=similar_words[0],
                        confidence=0.6,
                        reason='可能的拼写错误',
                        position=(text.find(word), text.find(word) + len(word))
                    ))
        
        return suggestions
    
    def batch_process_texts(self, texts: List[str], options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """批量处理文本"""
        results = []
        
        for i, text in enumerate(texts):
            result = self.process_text(text, options)
            results.append(result)
            
            if (i + 1) % 10 == 0:
                self.logger.info(f"已处理 {i + 1}/{len(texts)} 个文本")
        
        return results
    
    def get_processing_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取处理统计信息"""
        if not results:
            return {}
        
        successful_results = [r for r in results if r.get('status') == 'success']
        
        if not successful_results:
            return {'success_rate': 0.0}
        
        # 计算平均质量指标
        avg_confidence = sum(r.get('confidence_score', 0) for r in successful_results) / len(successful_results)
        
        # 统计建议数量
        total_suggestions = sum(len(r.get('suggestions', [])) for r in successful_results)
        
        # 统计错误指标
        all_error_indicators = []
        for r in successful_results:
            if r.get('quality_metrics') and r['quality_metrics'].error_indicators:
                all_error_indicators.extend(r['quality_metrics'].error_indicators)
        
        error_counter = Counter(all_error_indicators)
        
        return {
            'success_rate': len(successful_results) / len(results),
            'average_confidence': avg_confidence,
            'total_suggestions': total_suggestions,
            'average_suggestions_per_text': total_suggestions / len(successful_results) if successful_results else 0,
            'common_errors': dict(error_counter.most_common(5)),
            'processed_count': len(results),
            'successful_count': len(successful_results)
        }
