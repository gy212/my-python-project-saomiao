document.addEventListener('DOMContentLoaded', function() {
    const showAppContent = () => {
        const loader = document.getElementById('loader');
        const appShell = document.querySelector('.app-shell');

        // 隐藏加载动画并显示应用内容
        if(loader) loader.style.display = 'none';
        if(appShell) appShell.style.display = 'block';
    };

    // 监听 pywebviewready 事件，这是显示主内容最可靠的时机
    window.addEventListener('pywebviewready', showAppContent, { once: true });
    // --- "液态玻璃"高光追踪脚本 (性能优化版) ---
    const glassPanes = document.querySelectorAll('.glass-pane');
    let mouseX = 0;
    let mouseY = 0;
    document.body.addEventListener('mousemove', e => {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });
    function animationLoop() {
        glassPanes.forEach(pane => {
            const rect = pane.getBoundingClientRect();
            const x = mouseX - rect.left;
            const y = mouseY - rect.top;
            pane.style.setProperty('--mouse-x', `${x}px`);
            pane.style.setProperty('--mouse-y', `${y}px`);
        });
        requestAnimationFrame(animationLoop);
    }
    animationLoop();

    // --- 全局元素获取 ---
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const themeIconLight = document.getElementById('theme-icon-light');
    const themeIconDark = document.getElementById('theme-icon-dark');
    const settingsBtn = document.getElementById('settings-btn');
    const apiKeyModalOverlay = document.getElementById('api-key-modal-overlay');
    const apiKeyInput = document.getElementById('api-key-input');
    const saveApiKeyBtn = document.getElementById('save-api-key-btn');
    const cancelApiKeyBtn = document.getElementById('cancel-api-key-btn');
    const statusBar = document.getElementById('status-bar');
    const fileUploadInput = document.getElementById('file-upload-trigger');
    const fileInputAreaLabel = document.querySelector('label[for="file-upload-trigger"]');
    const imagePreviewArea = document.getElementById('image-preview-area');
    const extractedTextArea = document.getElementById('extracted-text-area');
    const copyTextBtn = document.getElementById('copy-text-btn');
    const processBtn = document.getElementById('process-btn');
    const formatToggle = document.getElementById('format-toggle');
    const mergeToggle = document.getElementById('merge-toggle');

    // --- 应用状态 ---
    let selectedFiles = [];
    let selectedOutputFormat = 'word';
    let selectedMergeMode = 'separate';
    
    // --- 自动切换配置 ---
    const IMAGE_COUNT_THRESHOLD = 3; // 图像数量阈值，超过此数量自动使用异步处理
    let isAsyncProcessing = false;
    let currentTaskIds = [];

    // --- 功能函数 ---
    async function waitForPywebviewApi(maxAttempts = 15, delayMs = 200) {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            if (window.pywebview && window.pywebview.api) {
                return true;
            }
            await new Promise(resolve => setTimeout(resolve, delayMs));
        }
        return false;
    }

    function updateStatus(message, isError = false) {
        if (statusBar) {
            statusBar.textContent = message;
            statusBar.style.color = isError ? '#ef4444' : '';
        }
    }

    // API密钥状态检查函数
    async function checkApiKeyStatus() {
        console.log("开始检查API密钥状态...");
        try {
            // 首先检查localStorage中的API密钥
            const localApiKey = localStorage.getItem('llm_api_key');
            let isValidApiKey = localApiKey && localApiKey.trim().length > 0;
            console.log("localStorage中的API密钥:", localApiKey ? "存在" : "不存在");
            
            // 如果localStorage中没有API密钥，尝试从后端获取
            if (!isValidApiKey) {
                console.log("尝试从后端获取API密钥...");
                const apiReady = await waitForPywebviewApi();

                if (!apiReady) {
                    console.warn("pywebview API 暂未就绪，延迟同步API密钥");
                } else {
                    try {
                        const response = await window.pywebview.api.get_api_key();
                        console.log("后端API响应:", response);
                        if (response && response.success && response.data) {
                            const backendApiKey = response.data.api_key;
                            console.log("后端API密钥:", backendApiKey ? "存在" : "不存在");
                            if (backendApiKey && backendApiKey.trim().length > 0) {
                                // 将后端的API密钥同步到localStorage
                                localStorage.setItem('llm_api_key', backendApiKey);
                                apiKeyInput.value = backendApiKey;
                                isValidApiKey = true;
                                console.log("已从后端同步API密钥到前端");
                            }
                        }
                    } catch (error) {
                        console.warn("无法从后端获取API密钥:", error);
                    }
                }
            }
            
            // 移除所有API密钥状态类
            settingsBtn.classList.remove('api-key-valid', 'api-key-invalid');
            
            // 根据API密钥状态添加相应的类
            if (isValidApiKey) {
                settingsBtn.classList.add('api-key-valid');
                console.log("API密钥状态: 有效 (绿色)");
            } else {
                settingsBtn.classList.add('api-key-invalid');
                console.log("API密钥状态: 无效 (红色)");
            }
            
            return isValidApiKey;
        } catch (error) {
            console.error("检查API密钥状态时出错:", error);
            settingsBtn.classList.remove('api-key-valid', 'api-key-invalid');
            settingsBtn.classList.add('api-key-invalid');
            return false;
        }
    }

    function applyTheme(theme) {
        if (theme === 'dark') {
            document.body.classList.add('dark');
            themeIconLight.classList.add('hidden');
            themeIconDark.classList.remove('hidden');
        } else {
            document.body.classList.remove('dark');
            themeIconLight.classList.remove('hidden');
            themeIconDark.classList.add('hidden');
        }
    }

    async function handleFileSelection(fileList) {
        if (!fileList || fileList.length === 0) return;
        selectedFiles = Array.from(fileList);
        
        // 显示第一张图片预览
        const reader = new FileReader();
        reader.onload = (e) => { 
            imagePreviewArea.innerHTML = `<img src="${e.target.result}" class="max-w-full max-h-full object-contain rounded-lg">`;
        };
        reader.readAsDataURL(selectedFiles[0]);
        
        // 根据图像数量自动确定处理模式
        isAsyncProcessing = selectedFiles.length > IMAGE_COUNT_THRESHOLD;
        const processingMode = isAsyncProcessing ? '异步' : '同步';
        updateStatus(`已选择 ${selectedFiles.length} 个文件，将使用${processingMode}处理模式`);
    }

    // 异步处理进度监控函数
    async function monitorAsyncProgress(taskIds) {
        const checkInterval = 1000; // 每秒检查一次
        let allCompleted = false;
        
        while (!allCompleted) {
            try {
                const status = await window.pywebview.api.get_async_task_status(taskIds);
                
                if (status.status === 'completed') {
                    // 所有任务完成
                    allCompleted = true;
                    updateStatus('所有图像处理完成！');
                    
                    // 显示结果
                    if (status.results && status.results.length > 0) {
                        const combinedText = status.results.map(result => result.text || '').join('\n\n---\n\n');
                        extractedTextArea.value = combinedText;
                    }
                    
                    // 重置状态
                    isAsyncProcessing = false;
                    currentTaskIds = [];
                    
                } else if (status.status === 'failed') {
                    allCompleted = true;
                    updateStatus(`处理失败: ${status.error || '未知错误'}`, true);
                    isAsyncProcessing = false;
                    currentTaskIds = [];
                    
                } else {
                    // 更新进度
                    const progress = Math.round(status.progress || 0);
                    const currentTask = status.current_task || '';
                    updateStatus(`处理进度: ${progress}% (${status.completed}/${status.total}) - ${currentTask}`);
                }
                
            } catch (error) {
                console.error('监控异步进度时出错:', error);
                updateStatus('监控进度时出错', true);
                allCompleted = true;
                isAsyncProcessing = false;
                currentTaskIds = [];
            }
            
            if (!allCompleted) {
                await new Promise(resolve => setTimeout(resolve, checkInterval));
            }
        }
    }

    const closeModal = () => {
        apiKeyModalOverlay.classList.remove('active');
    };

    // --- 事件监听器绑定 ---
    themeToggleBtn.addEventListener('click', function() {
        const newTheme = document.body.classList.contains('dark') ? 'light' : 'dark';
        localStorage.setItem('theme', newTheme);
        applyTheme(newTheme);
    });

    settingsBtn.addEventListener('click', () => {
        apiKeyModalOverlay.classList.add('active');
    });

    cancelApiKeyBtn.addEventListener('click', closeModal);
    apiKeyModalOverlay.addEventListener('click', (e) => {
        if (e.target === apiKeyModalOverlay) {
            closeModal();
        }
    });

    saveApiKeyBtn.addEventListener('click', () => {
        const apiKey = apiKeyInput.value.trim();
        if (apiKey) {
            localStorage.setItem('llm_api_key', apiKey);
            updateStatus('API Key 已成功保存！');
            checkApiKeyStatus(); // 更新按钮状态
            closeModal();
        } else {
            updateStatus('API Key 不能为空。', true);
        }
    });

    fileUploadInput.addEventListener('change', (e) => handleFileSelection(e.target.files));
    fileInputAreaLabel.addEventListener('drop', (e) => { e.preventDefault(); handleFileSelection(e.dataTransfer.files); });
    fileInputAreaLabel.addEventListener('dragover', (e) => e.preventDefault());

    formatToggle.addEventListener('click', function() {
        this.classList.toggle('pdf-selected');
        selectedOutputFormat = this.classList.contains('pdf-selected') ? 'pdf' : 'word';
        updateStatus(`格式切换为: ${selectedOutputFormat.toUpperCase()}`);
    });

    mergeToggle.addEventListener('click', function() {
        this.classList.toggle('combined-selected');
        selectedMergeMode = this.classList.contains('combined-selected') ? 'combined' : 'separate';
        updateStatus(`导出方式切换为: ${selectedMergeMode === 'combined' ? '合并保存' : '逐张保存'}`);
    });

    processBtn.addEventListener('click', async () => {
        if (selectedFiles.length === 0) { 
            updateStatus('请先选择图片文件', true); 
            return; 
        }
        
        // 防止重复处理
        if (isAsyncProcessing && currentTaskIds.length > 0) {
            updateStatus('正在处理中，请稍候...', true);
            return;
        }
        
        const fileCount = selectedFiles.length;
        const processingMode = fileCount > IMAGE_COUNT_THRESHOLD ? '异步' : '同步';
        updateStatus(`开始${processingMode}处理 ${fileCount} 个文件...`);
        
        try {
            // 获取实际文件路径
            const imagePaths = selectedFiles.map(file => file.path);
            
            if (fileCount > IMAGE_COUNT_THRESHOLD) {
                // 异步处理模式
                isAsyncProcessing = true;
                const response = await window.pywebview.api.start_async_ocr(
                    imagePaths, 
                    selectedOutputFormat, 
                    selectedMergeMode
                );
                
                if (response.status === '成功') {
                    currentTaskIds = response.task_ids || [];
                    updateStatus('异步处理已启动，正在监控进度...');
                    
                    // 开始监控进度
                    monitorAsyncProgress(currentTaskIds);
                    
                } else {
                    updateStatus(`启动异步处理失败: ${response.message || '未知错误'}`, true);
                    isAsyncProcessing = false;
                }
                
            } else {
                // 同步处理模式
                const response = await window.pywebview.api.process_images(
                    imagePaths, 
                    selectedOutputFormat, 
                    selectedMergeMode
                );
                
                if (response.status === '成功') {
                    extractedTextArea.value = response.text || '提取完成';
                    updateStatus('同步处理完成！');
                } else {
                    updateStatus(`同步处理失败: ${response.error || '未知错误'}`, true);
                }
            }
            
        } catch (error) {
            console.error('处理过程中出错:', error);
            updateStatus(`处理失败: ${error.message || '未知错误'}`, true);
            isAsyncProcessing = false;
            currentTaskIds = [];
        }
    });

    // --- 初始化 ---
    applyTheme(localStorage.getItem('theme') || 'light');
    const savedApiKey = localStorage.getItem('llm_api_key');
    if (savedApiKey) {
        apiKeyInput.value = savedApiKey;
        console.log("已加载保存的 API Key。");
    }
    
    // 初始化API密钥状态检查
    const triggerApiKeyStatusCheck = () => { checkApiKeyStatus(); };

    if (window.pywebview && window.pywebview.api) {
        triggerApiKeyStatusCheck();
    } else {
        window.addEventListener('pywebviewready', () => {
            triggerApiKeyStatusCheck();
        }, { once: true });

        waitForPywebviewApi().then(isReady => {
            if (isReady) {
                triggerApiKeyStatusCheck();
            }
        });
    }
});
