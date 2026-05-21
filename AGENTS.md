# 网课逐字稿 -> Markdown 笔记（longtext2md）

## 项目目标

网课视频逐字稿（可达 6w 字）+ 课件/代码 → 高质量 Markdown 笔记。

## 核心设计原则

- 每个 LLM 调用只干一件事：纠错/润色/结构化分离，不混杂
- 推迟结构理解到拥有完整干净文本后，一次性交给大窗口模型
- 每块 LLM 必须有上下文视野（全局摘要 + 前文结尾 + 后文开头 + 位置标签，全部零 LLM 成本）
- 代码必须嵌入叙事流，不是附录式堆砌

## 技术栈

Python 3.11+ | DeepSeek API (`api.deepseek.com`) | asyncio + aiohttp | ChromaDB | tiktoken | Streamlit

## 快速开始

```bash
pip install -r requirements.txt
python -m src.pipeline.orchestrator --input <逐字稿.txt>
streamlit run gui/app.py
```

## 模型分配

| 步骤 | 模型 | 模式 | 说明 |
|------|------|------|------|
| 纠错 (~8次) | Flash | non-thinking | 机械性术语替换，8K字/块 |
| 全局摘要 (1次) | Flash | non-thinking | 采样后基础总结 |
| 并行润色 (20-30次) | Flash | non-thinking | 中文书面语转换 |
| 标题+代码注入 (1次) | Pro | thinking | 全局结构化，推理链精准 |

## 架构概览

```
逐字稿 → 阶段0 预处理（清洗→纠错→摘要→切割）
      → 阶段1 全并行润色（28块并行，四层上下文）
      → 阶段2 全局结构化+代码注入（大窗口一次性）
      → Markdown 笔记
```

## 关键约定

- 纠错/润色用 Flash（non-thinking），结构化用 Pro（thinking）
- 润色时不加标题、不插代码——那是阶段2的事
- 话题切割目标：≤ 2000 字/块，在语义边界上
- 代码风格：类型注解 + 异步优先

## 项目结构

```
src/pipeline/    orchestrator.py, stage0_preprocess.py, stage1_polish.py, stage2_structure.py
src/rag/         glossary.py, indexer.py, retriever.py, parsers/
src/chunking/    boundary_detector.py
src/llm/         client.py
src/utils/       text_utils.py, token_counter.py, config.py
prompts/         correct_errors.md, global_summary.md, polish_chunk.md, structure_and_inject.md
gui/             app.py (Streamlit)
docs/            architecture.md (详细架构文档)
```

## 详细文档

- 完整流水线设计、技术选型理由、实施计划 → `docs/architecture.md`
- Prompt 模板 → `prompts/`
