# helloagents-column-writer 专栏编写系统

基于 HelloAgents 框架构建的智能专栏写作系统，能够自动规划、撰写、评审和优化专栏文章。

## 系统特点

- **树形递归架构**：支持3层深度的内容展开（子话题 → 小节 → 细节）
- **智能评审机制**：评分 + 详细反馈 + 修改建议
- **一次修改策略**：避免反复迭代，提高效率
- **完整质量追踪**：记录评审分数、修改历史、统计数据
- **🔍 联网搜索能力**：WriterAgent 可以使用搜索工具获取最新信息（通过 MCPTool）

## 系统架构

```
专栏编写系统
├── Planner Agent（规划专家）- 负责生成专栏大纲
├── Writer Agent（写作专家）- 负责生成和修改内容
├── Reviewer Agent（评审专家）- 负责评审内容质量
└── Orchestrator（主控）- 负责整体流程控制
```

## 工作流程

```
1. 规划阶段：Planner Agent 生成专栏大纲
   ↓
2. 写作阶段：Writer Agent 按层级递归生成内容
   ↓
3. 评审阶段：Reviewer Agent 评审并给出修改建议
   ↓
4. 优化阶段：根据评分决定（直接通过/修改/重写）
   ↓
5. 递归展开：处理子节点（最多3层）
   ↓
6. 导出阶段：生成文章和统计报告
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

复制 `env.example` 为 `.env` 并配置：

```bash
cp env.example .env
```

编辑 `.env` 文件：

```env
# LLM Configuration
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# Search API Keys (至少配置一个以启用搜索功能)
TAVILY_API_KEY=your-tavily-api-key      # 推荐
# SERPAPI_API_KEY=your-serpapi-api-key  # 或者使用这个

# System Configuration
MAX_DEPTH=3
APPROVAL_THRESHOLD=75
REVISION_THRESHOLD=60
ENABLE_SEARCH=true  # 启用搜索功能
```

### 搜索功能配置

WriterAgent 支持联网搜索以获取最新信息。你需要至少配置一个搜索 API：

**选项1：Tavily API（推荐）**
- 获取地址：https://tavily.com/
- 优点：AI 优化的搜索结果，更适合内容创作
- 安装：`pip install tavily-python`

**选项2：SerpAPI**
- 获取地址：https://serpapi.com/
- 优点：Google 搜索结果，数据更全面
- 安装：`pip install google-search-results`

搜索功能可选，如果不配置，WriterAgent 将在没有搜索能力的情况下运行。

## 使用方法

### 方式1：交互式运行

```bash
python main.py
```

然后输入专栏主题。

### 方式2：命令行参数

```bash
python main.py "Python异步编程完全指南"
```

## 输出文件

运行后会在 `output_YYYYMMDD_HHMMSS/` 目录下生成：

```
output_20241205_143000/
├── column_data.json          # 完整的专栏数据（JSON格式）
├── REPORT.md                 # 统计报告
├── topic_001_文章标题1.md     # 第一篇文章
├── topic_002_文章标题2.md     # 第二篇文章
└── ...
```

### 文章结构

每篇文章包含：
- 完整的 Markdown 内容
- 元数据（评审分数、字数、修改记录等）

### 统计报告

报告包含：
- 专栏信息（标题、简介、目标读者）
- 内容统计（总字数、节点数、通过率等）
- 质量报告（平均分数、评级分布）
- 创作统计（耗时、生成次数、修改次数等）
- 文章列表

## 配置说明

### 质量控制参数

- `APPROVAL_THRESHOLD`: 直接通过分数线（默认75分）
- `REVISION_THRESHOLD`: 修改分数线（默认60分）
  - ≥75分：直接通过
  - 60-74分：修改优化
  - <60分：重新生成

### 内容深度

- `MAX_DEPTH`: 最大递归深度（默认3层）
  - Level 1: 子话题（2500字）
  - Level 2: 小节（600字）
  - Level 3: 细节（400字）

## 项目结构

```
helloagents-column-writer/
├── README.md                # 本文档
├── QUICKSTART.md            # 快速入门指南
├── requirements.txt         # 依赖列表
├── env.example              # 环境变量示例
├── config.py                # 配置管理
├── models.py                # 数据模型
├── prompts.py               # Agent 提示词
├── agents.py                # 核心 Agent 实现
├── orchestrator.py          # 主系统编排
├── exporter.py              # 导出工具
├── search_mcp_server.py     # 搜索 MCP 服务器
├── main.py                  # 程序入口
├── example.py               # 使用示例
└── lib_tutorial.md          # HelloAgents 使用教程
```

## Agent 提示词

系统包含4个核心提示词：

1. **PLANNER_PROMPT**: 规划专栏大纲
2. **WRITER_PROMPT**: 生成文章内容
3. **REVIEWER_PROMPT**: 评审内容质量
4. **REVISION_PROMPT**: 修改优化内容

所有提示词在 `prompts.py` 中定义，可根据需要自定义。

## 评审维度

内容评审包含4个维度：

1. **内容质量** (40分)
   - 准确性、完整性、深度、原创性

2. **结构逻辑** (30分)
   - 层次清晰、逻辑连贯、过渡自然

3. **语言表达** (20分)
   - 易读性、专业性、准确性

4. **格式规范** (10分)
   - 字数达标、格式正确、排版美观

## 最佳实践

1. **合理设置阈值**
   - 通过阈值（75分）：平衡质量和效率
   - 修改阈值（60分）：区分修改和重写

2. **层级深度控制**
   - 建议最大深度为3层
   - 避免过度细分导致内容碎片化

3. **模型选择**
   - 推荐使用 GPT-4 以获得最佳质量
   - 可使用 GPT-3.5 以降低成本（质量可能下降）

## 注意事项

1. **API 调用成本**
   - 每篇文章需要多次 API 调用
   - 建议先测试小规模专栏（2-3篇文章）

2. **生成时间**
   - 单篇文章约需 2-5 分钟
   - 完整专栏（5-10篇）约需 10-30 分钟

3. **内容质量**
   - 评审标准较严格，可能需要多次修改
   - 可根据需要调整阈值

## 故障排除

### 问题1：API 调用失败

检查 `.env` 文件中的 API 配置：
- `OPENAI_API_KEY` 是否正确
- `OPENAI_BASE_URL` 是否可访问

### 问题2：JSON 解析失败

可能原因：
- LLM 返回格式不符合要求
- 尝试重新运行或降低复杂度

### 问题3：评分过低导致重写过多

调整配置：
- 降低 `APPROVAL_THRESHOLD`（如改为70）
- 降低 `REVISION_THRESHOLD`（如改为55）

## 扩展开发

### 添加新的 Agent

1. 在 `agents.py` 中创建新的 Agent 类
2. 在 `prompts.py` 中定义提示词
3. 在 `orchestrator.py` 中集成到流程

### 自定义评审标准

修改 `prompts.py` 中的 `REVIEWER_PROMPT`，调整：
- 评审维度和分值
- 评分标准
- 反馈格式

### 并行处理

修改 `config.py`：
```env
ENABLE_PARALLEL=true
```

注意：并行处理可能导致 API 限流。

## 参考资源

- [HelloAgents 官方文档](https://github.com/helloagents/hello-agents)
- [使用教程](./lib_tutorial.md)
- [设计方案](./idea.md)