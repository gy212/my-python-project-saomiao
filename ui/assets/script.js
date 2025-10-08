/*
 * JavaScript功能已迁移到内联脚本
 * 此文件保留用于向后兼容性和扩展功能
 * 主要功能现在都在ui.html的<script>标签中定义
 */

// 备用功能 - 如果内联脚本加载失败
window.fallbackScripts = {
    // 简单的主题切换备用功能
    toggleTheme: function() {
        const html = document.documentElement;
        const isDark = html.classList.contains('dark');
        if (isDark) {
            html.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        } else {
            html.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
    },

    // 简单的状态更新功能
    updateStatus: function(message) {
        const statusBar = document.getElementById('status-bar');
        if (statusBar) {
            statusBar.textContent = message;
        }
    },

    // 初始化备用功能
    init: function() {
        // 检查是否需要启用备用功能
        if (!window.mainScriptLoaded) {
            console.warn('主脚本未加载，启用备用功能');
            this.bindFallbackEvents();
        }
    },

    // 绑定备用事件
    bindFallbackEvents: function() {
        const themeBtn = document.getElementById('theme-toggle-btn');
        if (themeBtn) {
            themeBtn.addEventListener('click', this.toggleTheme);
        }
    }
};

// 扩展功能 - 可以在这里添加额外的功能
window.extendedFeatures = {
    // 键盘快捷键支持
    initKeyboardShortcuts: function() {
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + D 切换主题
            if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
                e.preventDefault();
                const themeBtn = document.getElementById('theme-toggle-btn');
                if (themeBtn) themeBtn.click();
            }
            
            // Ctrl/Cmd + U 打开文件选择
            if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
                e.preventDefault();
                const fileInput = document.getElementById('file-upload-trigger');
                if (fileInput) fileInput.click();
            }
            
            // Enter 开始处理（当焦点不在输入框时）
            if (e.key === 'Enter' && !['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                e.preventDefault();
                const processBtn = document.getElementById('process-btn');
                if (processBtn && !processBtn.disabled) processBtn.click();
            }
        });
    },

    // 性能监控
    initPerformanceMonitoring: function() {
        if ('performance' in window) {
            window.addEventListener('load', function() {
                setTimeout(function() {
                    const perfData = performance.getEntriesByType('navigation')[0];
                    if (perfData) {
                        console.log('页面加载性能:', {
                            domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                            loadComplete: perfData.loadEventEnd - perfData.loadEventStart,
                            totalTime: perfData.loadEventEnd - perfData.fetchStart
                        });
                    }
                }, 0);
            });
        }
    },

    // 错误处理
    initErrorHandling: function() {
        window.addEventListener('error', function(e) {
            console.error('JavaScript错误:', e.error);
            const statusBar = document.getElementById('status-bar');
            if (statusBar) {
                statusBar.textContent = '发生错误，请刷新页面重试';
                statusBar.style.color = '#dc2626';
            }
        });

        window.addEventListener('unhandledrejection', function(e) {
            console.error('未处理的Promise拒绝:', e.reason);
        });
    }
};

// 初始化扩展功能
document.addEventListener('DOMContentLoaded', function() {
    // 延迟初始化，确保主脚本有机会加载
    setTimeout(function() {
        window.fallbackScripts.init();
        window.extendedFeatures.initKeyboardShortcuts();
        window.extendedFeatures.initPerformanceMonitoring();
        window.extendedFeatures.initErrorHandling();
    }, 100);
});

// 导出功能供其他脚本使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        fallbackScripts: window.fallbackScripts,
        extendedFeatures: window.extendedFeatures
    };
}
