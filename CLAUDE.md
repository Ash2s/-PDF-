# PDF 表格填写工具

## 项目概述
FastAPI + PyMuPDF + MIMO API 驱动的 PDF 表格自动填写工具。
上传学生简历 + PDF 申请表，AI 自动识别字段并填充，支持多表单同时处理。

## 技术栈
- **后端**: Python 3.13+, FastAPI, uvicorn
- **PDF处理**: PyMuPDF (fitz)
- **AI识别**: MIMO API（视觉识别表单字段）
- **前端**: 原生 HTML/CSS/JS，无框架

## 目录结构
```
├── app.py                  # FastAPI 主程序
├── services/
│   ├── pdf_service.py      # PDF 处理：文字坐标提取、表格检测、字段匹配
│   ├── extractor.py        # AI 检测提示词（学生资料提取 + 表单字段识别）
│   └── mimo.py             # MIMO API 封装
├── static/
│   ├── index.html          # 前端页面
│   ├── app.js              # 前端逻辑
│   ├── style.css           # 样式
│   └── watermark.png       # 水印图片
├── uploads/                # 上传文件（gitignore）
├── outputs/                # 生成PDF（gitignore）
├── requirements.txt
└── .env.example
```

## 启动
```bash
# 复制 .env.example 为 .env 并填入 MIMO_API_KEY
python app.py
# 访问 http://localhost:8001/
```

## 核心流程
1. 上传学生简历 → AI 提取结构化信息
2. 上传 PDF 申请表 → AI 逐页识别字段 + 匹配
3. 生成填写版 PDF（含视觉审核修正）
4. 支持通过修改意见自然语言调整字段

## 多表单
- 一份简历可同时处理多份申请表
- Tab 切换预览、修改、下载
- 修改意见按表单独立隔离

## 环境要求
- Python 3.13+
- MIMO_API_KEY 环境变量（申请见 mimo.py）
- Windows 系统代理自动绕过（trust_env=False）
