# OCR图像扫描工具

## 📖 项目简介
基于现代Web技术的OCR图像扫描工具，支持多种图像格式的文字识别和导出功能。

## 📁 项目结构

```
D:\PythonProject\扫描\
├── app.pyw                 # 主应用程序入口
├── requirements.txt        # 依赖包列表
├── config/                 # 配置和数据文件
│   ├── config.json        # 应用配置文件
│   └── scan_history.json  # 扫描历史记录
├── src/                    # 核心业务模块
│   ├── main_api.pyw       # 主API接口模块
│   ├── ocr_service.pyw    # OCR服务模块
│   ├── async_processor.pyw # 异步任务处理器
│   ├── file_exporter.pyw  # 文件导出模块
│   └── config_manager.pyw # 配置管理模块
├── ui/                     # 用户界面文件
│   └── ui.html            # 现代化主界面HTML文件
├── debug/                  # 调试工具
├── logs/                   # 日志文件目录
├── tests/                  # 调试和测试文件
└── docs/                   # 项目文档
```

## 📂 文件分类说明

### 核心应用文件
- `app.pyw` - 主应用程序入口
- `src/main_api.pyw` - 主API接口模块
- `src/ocr_service.pyw` - OCR服务模块
- `src/async_processor.pyw` - 异步任务处理器
- `src/file_exporter.pyw` - 文件导出模块
- `src/config_manager.pyw` - 配置管理模块

### 用户界面文件
- `ui/ui.html` - 现代化主界面HTML文件

### 配置和数据文件
- `config/config.json` - 应用配置文件
- `config/scan_history.json` - 扫描历史记录
- `requirements.txt` - 依赖包列表

## 🚀 核心功能
- **多格式支持**: JPG、PNG、BMP、TIFF、WEBP等图像格式
- **批量处理**: 支持多图像同时OCR识别
- **拖拽上传**: 便捷的文件拖拽上传功能
- **异步处理**: 高效的异步OCR任务处理

## 🛠️ 技术特性
- **现代化UI**: 基于HTML5的响应式界面设计
- **玻璃拟态**: 现代化的视觉效果和交互体验
- **模块化架构**: 清晰的代码结构和模块分离
- **配置管理**: 灵活的配置文件管理系统
- **日志系统**: 完整的应用运行日志记录

## 🔧 技术改进历程
- ✅ 导入路径与结构优化
- ✅ 配置与日志路径更新
- ✅ 异步OCR修复与交互完善
- ✅ 拖拽上传功能修复
- ✅ UI现代化升级
- ✅ 项目结构进一步优化
- ✅ 渐变滑块显示修复
- ✅ 文档完善

## 📋 最新版本
**版本 1.3.1** - 渐变滑块修复版
- 修复渐变滑块显示异常问题
- 优化UI层级设置和视觉效果
- 提升用户交互体验

## 🎯 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 运行应用：`python app.pyw`
3. 在浏览器中访问本地界面进行OCR操作

## 📊 应用状态
- **初始化时间**: 0.00秒 ⚡
- **中文字体支持**: ✅ C:/Windows/Fonts/simsun.ttc
- **应用状态**: 🟢 正常运行

*最后更新: 2025-10-07*
