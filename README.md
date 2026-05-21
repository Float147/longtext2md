# longtext2md — 网课逐字稿 → 高质量 Markdown 笔记

将网课视频的 ASR 逐字稿（可达 6 万字）自动转换为结构清晰、不遗漏知识点的 Markdown 笔记。支持上传课件（PDF/PPTX/DOCX/MD）和代码文件构建 RAG 知识库，辅助代码嵌入和术语纠错。

## 核心架构

```
原始逐字稿 (6w字)
     |
     v
┌──────────────────────────────────────────────────────┐
│  阶段0：预处理                                         │
│  0.0 正则噪音清洗    0.2 LLM 错别字纠正                 │
│  0.3 课程全局摘要    0.4 话题边界检测                   │
│  0.5 RAG 索引构建（可选）                               │
└────────────────────┬─────────────────────────────────┘
                     |
         无错别字逐字稿 + N 个话题块
                     |
                     v
┌──────────────────────────────────────────────────────┐
│  阶段1：全并行上下文润色（28 块 → 28 次并行 LLM）       │
│  每块拿到四层上下文：全局摘要 + 位置标签 + 前文结尾       │
│  + 后文开头 + RAG 代码指纹，全部零额外 LLM 成本          │
└────────────────────┬─────────────────────────────────┘
                     |
               干净全文
                     |
                     v
┌──────────────────────────────────────────────────────┐
│  阶段2：全局结构化 + 代码/课件注入                       │
│  2a. 段落标记法生成层级标题（##/###/####）               │
│  2b. 按 ## 标题切分，并行注入代码块 + 课件引用           │
└────────────────────┬─────────────────────────────────┘
                     |
                     v
           高质量 Markdown 笔记
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- DeepSeek API Key（[获取地址](https://platform.deepseek.com)）
- SiliconFlow API Key（[获取地址](https://siliconflow.cn)，用于 RAG 检索）

### 2. 安装

```bash
git clone git@github.com:Float147/longtext2md.git
cd longtext2md
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek 和 SiliconFlow 的 API Key
```

### 4. 启动

```bash
streamlit run gui/app.py
```

浏览器打开 http://localhost:8501，上传逐字稿 + 参考资料即可。

## 配置项说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 必填 |
| `ECONOMY_MODEL` | 经济档模型（纠错/摘要/润色） | `deepseek-chat` |
| `PREMIUM_MODEL` | 高端档模型（结构化/代码注入） | `deepseek-reasoner` |
| `SILICONFLOW_API_KEY` | SiliconFlow API 密钥（嵌入+精排） | 必填 |
| `EMBEDDING_MODEL` | 向量嵌入模型 | `BAAI/bge-m3` |
| `MAX_CHUNK_CHARS` | 润色每块最大字符数 | `2000` |
| `MAX_PARALLEL_TASKS` | 最大并行任务数 | `3` |
| `MAX_LLM_CONCURRENCY` | LLM 最大并发调用数 | `50` |
| `STREAMLIT_PORT` | GUI 端口 | `8501` |

详见 `.env.example` 中的完整注释。

## 使用流程

1. **上传逐字稿**：拖拽 `.txt` 或 `.md` 文件到侧边栏
2. **上传参考资料（可选）**：代码文件 + 课件文件（PDF/PPTX/DOCX/MD）
3. **创建并开始**：点击按钮启动流水线
4. **查看进度**：点击任务详情，实时查看各阶段状态和中间产物
5. **获取笔记**：完成后直接在详情页查看完整 Markdown，一键复制或下载

## 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| LLM | DeepSeek V4 Flash + Pro | 1M 上下文，中文能力极强，价格低 |
| 嵌入 | BAAI/bge-m3 (via SiliconFlow) | 中文嵌入效果好，性价比高 |
| 向量库 | ChromaDB | 轻量纯 Python，零部署依赖 |
| 并行 | asyncio + aiohttp | 阶段1 全并行润色，30 次调用 30 秒 |
| 文档解析 | PyPDF2 / python-pptx / python-docx | 课件多格式支持 |
| GUI | Streamlit | 最快出原型 |

## 项目结构

```
longtext2md/
├── src/
│   ├── pipeline/          # 两阶段流水线
│   │   ├── orchestrator.py
│   │   ├── stage0_preprocess.py
│   │   ├── stage1_polish.py
│   │   └── stage2_structure.py
│   ├── rag/               # RAG 检索
│   │   ├── indexer.py
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   └── parsers/       # 文件解析器
│   ├── chunking/          # 话题边界检测
│   ├── llm/               # LLM 调用封装
│   ├── task/              # 任务管理
│   ├── kb/                # 知识库管理
│   └── utils/             # 工具
├── prompts/               # LLM 提示词模板
├── gui/                   # Streamlit 界面
├── tests/                 # 测试
├── .env.example           # 配置模板
└── requirements.txt
```

## 模型成本

| 步骤 | 模型 | 调用次数 | 预估成本 |
|------|------|---------|---------|
| 0.2 纠错 | Flash | ~8 次 | ¥0.05 |
| 0.3 摘要 | Flash | 1 次 | ¥0.01 |
| 阶段1 润色 | Flash | 20-30 次 | ¥0.40 |
| 阶段2a 标题 | Pro | 1 次 | ¥0.05 |
| 阶段2b 注入 | Pro | 2-15 次（并行） | ¥0.30 |
| **合计** | | | **≈ ¥0.80** |

按 DeepSeek 官方定价估算，实际因逐字稿长度和课程复杂度浮动。
