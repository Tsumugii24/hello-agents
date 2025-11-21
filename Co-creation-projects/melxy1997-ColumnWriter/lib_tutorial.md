# HelloAgents 库使用教程

本文档基于 `helloagents-examples` 官方案例集和 `helloagents-trip-planner` 真实项目，总结使用 `hello_agents` 库构建智能体系统的编码方式和最佳实践。

## 目录

1. [基础概念](#基础概念)
2. [核心组件](#核心组件)
3. [Agent 类型详解](#agent-类型详解)
4. [工具系统](#工具系统)
5. [多智能体系统](#多智能体系统)
6. [项目架构模式](#项目架构模式)
7. [最佳实践](#最佳实践)

---

## 基础概念

### HelloAgents 设计理念

- **默认优秀**：开箱即用的高质量 Agent
- **完全可定制**：用户可以完全替换提示词模板
- **简洁 API**：最少的参数，最大的灵活性
- **渐进式**：从简单到复杂的学习路径

### 核心导入

```python
from hello_agents import (
    HelloAgentsLLM,
    SimpleAgent, 
    ReActAgent, 
    ReflectionAgent, 
    PlanAndSolveAgent,
    FunctionCallAgent,
    ToolRegistry,
    MCPTool
)
```

---

## 核心组件

### 1. HelloAgentsLLM - LLM 统一接口

`HelloAgentsLLM` 是统一的 LLM 接口，自动从环境变量读取配置。

#### 基本使用

```python
from hello_agents import HelloAgentsLLM

# 方式1: 使用默认配置（从环境变量读取）
llm = HelloAgentsLLM()

# 方式2: 指定模型
llm = HelloAgentsLLM(model="gpt-4o-mini")

# 方式3: 自定义配置
llm = HelloAgentsLLM(
    api_key="your-api-key",
    base_url="https://api.openai.com/v1",
    model="gpt-4"
)
```

#### 环境变量配置

```bash
# .env 文件
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# 或者使用 HelloAgents 的命名
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_ID=gpt-4
```

#### 单例模式（推荐）

在实际项目中，建议使用单例模式管理 LLM 实例：

```python
# services/llm_service.py
from hello_agents import HelloAgentsLLM

_llm_instance = None

def get_llm() -> HelloAgentsLLM:
    """获取LLM实例(单例模式)"""
    global _llm_instance
    
    if _llm_instance is None:
        _llm_instance = HelloAgentsLLM()
        print(f"✅ LLM服务初始化成功")
        print(f"   提供商: {_llm_instance.provider}")
        print(f"   模型: {_llm_instance.model}")
    
    return _llm_instance
```

---

## Agent 类型详解

### 1. SimpleAgent - 基础对话 Agent

最简单的 Agent 类型，适用于基础对话场景。

#### 基本使用

```python
from hello_agents import SimpleAgent, HelloAgentsLLM

llm = HelloAgentsLLM()

# 创建简单 Agent
agent = SimpleAgent(
    name="助手",
    llm=llm,
    system_prompt="你是一个有用的AI助手，请用中文回答问题。"
)

# 运行对话
response = agent.run("你好，请介绍一下自己")
print(response)
```

#### 特点

- ✅ 最简单易用
- ✅ 适合基础对话
- ✅ 不支持工具调用
- ✅ 可自定义系统提示词

---

### 2. ReActAgent - 推理与行动结合

结合推理（Reasoning）和行动（Acting）的 Agent，支持工具调用。

#### 基本使用

```python
from hello_agents import ReActAgent, HelloAgentsLLM, ToolRegistry, search, calculate

llm = HelloAgentsLLM()

# 创建工具注册表
tool_registry = ToolRegistry()

# 注册工具
tool_registry.register_function(
    name="search",
    description="一个网页搜索引擎。当你需要回答关于时事、事实以及在你的知识库中找不到的信息时，应使用此工具。",
    func=search
)

tool_registry.register_function(
    name="calculate",
    description="执行数学计算。支持基本运算、数学函数等。例如：2+3*4, sqrt(16), sin(pi/2)等。",
    func=calculate
)

# 创建 ReAct Agent
agent = ReActAgent(
    name="通用助手",
    llm=llm,
    tool_registry=tool_registry,
    max_steps=3  # 最大推理步骤
)

# 运行任务
response = agent.run("计算 15 * 23 + 45 的结果")
print(response)
```

#### 自定义提示词

```python
custom_prompt = """
你是一个专业的研究助手，擅长信息收集和分析。

可用工具如下：
{tools}

请按照以下格式进行研究：

Thought: 分析问题，确定需要什么信息，制定研究策略。
Action: 选择合适的工具获取信息，格式为：
- `{tool_name}[{tool_input}]`：调用工具获取信息。
- `Finish[研究结论]`：当你有足够信息得出结论时。

研究问题：{question}
已完成的研究：{history}
"""

research_agent = ReActAgent(
    name="研究助手",
    llm=llm,
    tool_registry=tool_registry,
    custom_prompt=custom_prompt,
    max_steps=3
)
```

#### 特点

- ✅ 支持工具调用
- ✅ 推理-行动循环
- ✅ 可自定义提示词模板
- ✅ 适合需要外部工具的场景

---

### 3. ReflectionAgent - 自我反思与迭代优化

通过自我反思和迭代优化来改进输出的 Agent。

#### 基本使用

```python
from hello_agents import ReflectionAgent, HelloAgentsLLM

llm = HelloAgentsLLM()

# 默认配置
agent = ReflectionAgent(
    name="通用助手",
    llm=llm,
    max_iterations=2  # 最大迭代次数
)

response = agent.run("解释什么是递归算法，并给出一个简单的例子")
print(response)
```

#### 自定义提示词

```python
code_prompts = {
    "initial": """
你是一位资深的程序员。请根据以下要求编写代码：

要求: {task}

请提供完整的代码实现，包含必要的注释和文档。
""",
    "reflect": """
你是一位严格的代码评审专家。请审查以下代码：

# 原始任务: {task}
# 待审查的代码: {content}

请分析代码的质量，包括算法效率、可读性、错误处理等。
如果代码质量良好，请回答"无需改进"。否则请提出具体的改进建议。
""",
    "refine": """
请根据代码评审意见优化你的代码：

# 原始任务: {task}
# 上一轮代码: {last_attempt}
# 评审意见: {feedback}

请提供优化后的代码。
"""
}

code_agent = ReflectionAgent(
    name="代码专家",
    llm=llm,
    custom_prompts=code_prompts,
    max_iterations=2
)
```

#### 特点

- ✅ 自我反思机制
- ✅ 迭代优化输出
- ✅ 适合需要高质量输出的场景
- ✅ 可自定义反思和优化提示词

---

### 4. PlanAndSolveAgent - 分解规划与逐步执行

将复杂任务分解为子任务，然后逐步执行的 Agent。

#### 基本使用

```python
from hello_agents import PlanAndSolveAgent, HelloAgentsLLM

llm = HelloAgentsLLM()

# 默认配置
agent = PlanAndSolveAgent(
    name="通用助手",
    llm=llm
)

response = agent.run("如何学习Python编程？请制定一个详细的学习计划。")
print(response)
```

#### 自定义提示词

```python
math_prompts = {
    "planner": """
你是一个数学问题分解专家。请将以下数学问题分解为清晰的计算步骤。
每个步骤应该是一个具体的数学运算或逻辑推理。

数学问题: {question}

请按以下格式输出计算计划:
```python
["步骤1: 具体计算", "步骤2: 具体计算", ...]
```
""",
    "executor": """
你是一个数学计算专家。请严格按照计划执行数学计算。

# 原始问题: {question}
# 计算计划: {plan}
# 已完成的计算: {history}
# 当前计算步骤: {current_step}

请执行当前步骤的计算，只输出计算结果:
"""
}

math_agent = PlanAndSolveAgent(
    name="数学专家",
    llm=llm,
    custom_prompts=math_prompts
)
```

#### 特点

- ✅ 任务分解能力
- ✅ 逐步执行计划
- ✅ 适合复杂任务
- ✅ 可自定义规划器和执行器提示词

---

### 5. FunctionCallAgent - 函数调用 Agent

专门用于函数调用的 Agent，支持 OpenAI 的函数调用功能。

#### 基本使用

```python
from hello_agents.agents import FunctionCallAgent
from hello_agents.core.llm import HelloAgentsLLM
from hello_agents.tools.registry import ToolRegistry

def get_horoscope(sign: str) -> str:
    """获取星座运势"""
    sample_data = {
        "白羊座": "保持耐心，合作能带来额外好运。",
        "金牛座": "适合整理计划，财务上保持谨慎。",
        "双子座": "沟通顺畅，适合推进新想法。",
    }
    return sample_data.get(sign.strip(), "今天以平静面对生活，一切都会慢慢变好。")

# 创建 LLM
llm = HelloAgentsLLM(model="gpt-4o-mini")

# 创建工具注册表
registry = ToolRegistry()
registry.register_function(
    name="get_horoscope",
    description="Get today's horoscope for an astrological sign.",
    func=get_horoscope,
)

# 创建 FunctionCallAgent
agent = FunctionCallAgent(
    name="demo-agent",
    llm=llm,
    tool_registry=registry,
)

# 运行
question = "请告诉我金牛座今天的运势，并说明是如何得到信息的。"
answer = agent.run(question)
print("Agent:", answer)
```

#### 特点

- ✅ 使用 OpenAI 函数调用
- ✅ 自动参数解析
- ✅ 适合需要精确函数调用的场景

---

## 工具系统

### ToolRegistry - 工具注册表

用于注册和管理 Agent 可用的工具。

#### 基本使用

```python
from hello_agents import ToolRegistry, search, calculate

# 创建工具注册表
tool_registry = ToolRegistry()

# 注册内置工具
tool_registry.register_function(
    name="search",
    description="网页搜索引擎",
    func=search
)

tool_registry.register_function(
    name="calculate",
    description="数学计算工具",
    func=calculate
)

# 注册自定义函数
def custom_function(param: str) -> str:
    """自定义函数"""
    return f"处理结果: {param}"

tool_registry.register_function(
    name="custom_function",
    description="自定义处理函数",
    func=custom_function
)
```

---

### MCPTool - MCP 协议工具

用于集成 MCP (Model Context Protocol) 服务器的工具。

#### 基本使用

```python
from hello_agents.tools import MCPTool

# 创建 MCP 工具
amap_tool = MCPTool(
    name="amap",
    description="高德地图服务",
    server_command=["uvx", "amap-mcp-server"],
    env={"AMAP_MAPS_API_KEY": "your-api-key"},
    auto_expand=True  # 自动展开工具
)

# 添加到 Agent
agent = SimpleAgent(name="地图助手", llm=llm)
agent.add_tool(amap_tool)
```

#### 共享 MCP 工具

在多智能体系统中，可以共享同一个 MCP 工具实例：

```python
class MultiAgentSystem:
    def __init__(self):
        # 创建共享的 MCP 工具（只创建一次）
        self.amap_tool = MCPTool(
            name="amap",
            description="高德地图服务",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=True
        )
        
        # 多个 Agent 共享同一个工具
        self.agent1 = SimpleAgent(name="Agent1", llm=llm)
        self.agent1.add_tool(self.amap_tool)
        
        self.agent2 = SimpleAgent(name="Agent2", llm=llm)
        self.agent2.add_tool(self.amap_tool)
```

---

### 工具调用格式

在 Agent 的提示词中，可以使用特定的工具调用格式：

```python
# 在提示词中指导 Agent 使用工具
ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。

**重要提示:**
你必须使用工具来搜索景点!不要自己编造景点信息!

**工具调用格式:**
使用maps_text_search工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=景点关键词,city=城市名]`

**示例:**
用户: "搜索北京的历史文化景点"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=北京]
"""
```

---

## 多智能体系统

### 架构模式

在实际项目中，多智能体系统通常采用以下架构：

```
用户请求
    ↓
协调层（可选）
    ↓
┌─────────────┬─────────────┬─────────────┐
│  Agent 1    │  Agent 2    │  Agent 3    │
│  (专业1)    │  (专业2)    │  (专业3)    │
└─────────────┴─────────────┴─────────────┘
    ↓              ↓              ↓
共享工具层（MCP工具、API等）
    ↓
最终结果
```

### 实现示例

基于 `helloagents-trip-planner` 项目的多智能体系统：

```python
class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""
    
    def __init__(self):
        """初始化多智能体系统"""
        self.llm = get_llm()
        
        # 创建共享的 MCP 工具
        self.amap_tool = MCPTool(
            name="amap",
            description="高德地图服务",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=True
        )
        
        # 创建专业 Agent
        self.attraction_agent = SimpleAgent(
            name="景点搜索专家",
            llm=self.llm,
            system_prompt=ATTRACTION_AGENT_PROMPT
        )
        self.attraction_agent.add_tool(self.amap_tool)
        
        self.weather_agent = SimpleAgent(
            name="天气查询专家",
            llm=self.llm,
            system_prompt=WEATHER_AGENT_PROMPT
        )
        self.weather_agent.add_tool(self.amap_tool)
        
        self.hotel_agent = SimpleAgent(
            name="酒店推荐专家",
            llm=self.llm,
            system_prompt=HOTEL_AGENT_PROMPT
        )
        self.hotel_agent.add_tool(self.amap_tool)
        
        # 规划 Agent（不需要工具）
        self.planner_agent = SimpleAgent(
            name="行程规划专家",
            llm=self.llm,
            system_prompt=PLANNER_AGENT_PROMPT
        )
    
    def plan_trip(self, request: TripRequest) -> TripPlan:
        """使用多智能体协作生成旅行计划"""
        # 步骤1: 景点搜索
        attraction_query = self._build_attraction_query(request)
        attraction_response = self.attraction_agent.run(attraction_query)
        
        # 步骤2: 天气查询
        weather_query = f"请查询{request.city}的天气信息"
        weather_response = self.weather_agent.run(weather_query)
        
        # 步骤3: 酒店推荐
        hotel_query = f"请搜索{request.city}的{request.accommodation}酒店"
        hotel_response = self.hotel_agent.run(hotel_query)
        
        # 步骤4: 整合信息生成计划
        planner_query = self._build_planner_query(
            request, 
            attraction_response, 
            weather_response, 
            hotel_response
        )
        planner_response = self.planner_agent.run(planner_query)
        
        # 解析最终计划
        trip_plan = self._parse_response(planner_response, request)
        return trip_plan
```

### 单例模式

在多智能体系统中，使用单例模式管理 Agent 实例：

```python
# 全局多智能体系统实例
_multi_agent_planner = None

def get_trip_planner_agent() -> MultiAgentTripPlanner:
    """获取多智能体旅行规划系统实例(单例模式)"""
    global _multi_agent_planner
    
    if _multi_agent_planner is None:
        _multi_agent_planner = MultiAgentTripPlanner()
    
    return _multi_agent_planner
```

---

## 项目架构模式

### 1. 前后端分离架构

```
helloagents-trip-planner/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── agents/       # Agent 层
│   │   │   └── trip_planner_agent.py
│   │   ├── api/          # API 层
│   │   │   ├── main.py
│   │   │   └── routes/
│   │   │       └── trip.py
│   │   ├── services/     # 服务层
│   │   │   ├── llm_service.py
│   │   │   └── amap_service.py
│   │   ├── models/       # 数据模型
│   │   │   └── schemas.py
│   │   └── config.py     # 配置管理
│   └── requirements.txt
└── frontend/             # Vue.js 前端
    └── src/
```

### 2. 配置管理

使用 Pydantic Settings 管理配置：

```python
# config.py
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """应用配置"""
    app_name: str = "HelloAgents智能旅行助手"
    app_version: str = "1.0.0"
    
    # API 配置
    amap_api_key: str = ""
    
    # LLM 配置（从环境变量读取）
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

def get_settings() -> Settings:
    """获取配置实例"""
    return settings
```

### 3. API 路由

使用 FastAPI 创建 RESTful API：

```python
# api/routes/trip.py
from fastapi import APIRouter, HTTPException
from ...agents.trip_planner_agent import get_trip_planner_agent
from ...models.schemas import TripRequest, TripPlanResponse

router = APIRouter(prefix="/trip", tags=["旅行规划"])

@router.post("/plan", response_model=TripPlanResponse)
async def plan_trip(request: TripRequest):
    """生成旅行计划"""
    try:
        # 获取 Agent 实例
        agent = get_trip_planner_agent()
        
        # 生成旅行计划
        trip_plan = agent.plan_trip(request)
        
        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )
```

### 4. 错误处理和降级

实现错误处理和降级方案：

```python
def plan_trip(self, request: TripRequest) -> TripPlan:
    """使用多智能体协作生成旅行计划"""
    try:
        # 多智能体协作流程
        attraction_response = self.attraction_agent.run(query)
        weather_response = self.weather_agent.run(query)
        planner_response = self.planner_agent.run(query)
        
        # 解析响应
        trip_plan = self._parse_response(planner_response, request)
        return trip_plan
        
    except Exception as e:
        print(f"❌ 生成旅行计划失败: {str(e)}")
        # 降级方案：返回基础计划
        return self._create_fallback_plan(request)

def _create_fallback_plan(self, request: TripRequest) -> TripPlan:
    """创建备用计划(当Agent失败时)"""
    # 返回基础的计划结构
    # ...
```

---

## 最佳实践

### 1. LLM 实例管理

✅ **推荐**：使用单例模式管理 LLM 实例

```python
_llm_instance = None

def get_llm() -> HelloAgentsLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = HelloAgentsLLM()
    return _llm_instance
```

❌ **不推荐**：每次创建新实例

```python
def process_request():
    llm = HelloAgentsLLM()  # 每次都创建新实例
    agent = SimpleAgent(llm=llm)
```

### 2. Agent 提示词设计

✅ **推荐**：清晰的工具调用指导

```python
PROMPT = """你是专家。你必须使用工具来完成任务。

**工具调用格式:**
`[TOOL_CALL:tool_name:param1=value1,param2=value2]`

**示例:**
用户: "搜索北京景点"
你的回复: [TOOL_CALL:search:keywords=北京景点]
"""
```

❌ **不推荐**：模糊的提示词

```python
PROMPT = "你是专家，可以帮助用户。"  # 太模糊
```

### 3. 工具共享

✅ **推荐**：在多智能体系统中共享工具实例

```python
class MultiAgentSystem:
    def __init__(self):
        # 创建一次，共享使用
        self.shared_tool = MCPTool(...)
        self.agent1.add_tool(self.shared_tool)
        self.agent2.add_tool(self.shared_tool)
```

❌ **不推荐**：每个 Agent 创建独立工具

```python
agent1.add_tool(MCPTool(...))  # 创建多个实例
agent2.add_tool(MCPTool(...))
```

### 4. 错误处理

✅ **推荐**：完善的错误处理和降级方案

```python
try:
    result = agent.run(query)
    return result
except Exception as e:
    logger.error(f"Agent执行失败: {e}")
    return fallback_result()
```

❌ **不推荐**：忽略错误

```python
result = agent.run(query)  # 没有错误处理
return result
```

### 5. 配置管理

✅ **推荐**：使用环境变量和配置类

```python
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    api_key: str = ""
    model: str = "gpt-4"
    class Config:
        env_file = ".env"
```

❌ **不推荐**：硬编码配置

```python
api_key = "sk-xxx"  # 硬编码
```

### 6. 响应解析

✅ **推荐**：健壮的 JSON 解析

```python
def _parse_response(self, response: str) -> TripPlan:
    """解析Agent响应"""
    try:
        # 尝试多种方式提取 JSON
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
        elif "{" in response and "}" in response:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            json_str = response[json_start:json_end]
        else:
            raise ValueError("响应中未找到JSON数据")
        
        data = json.loads(json_str)
        return TripPlan(**data)
    except Exception as e:
        # 降级处理
        return self._create_fallback_plan()
```

### 7. 日志和调试

✅ **推荐**：详细的日志输出

```python
print(f"\n{'='*60}")
print(f"🚀 开始多智能体协作规划旅行...")
print(f"目的地: {request.city}")
print(f"日期: {request.start_date} 至 {request.end_date}")
print(f"{'='*60}\n")

print("📍 步骤1: 搜索景点...")
attraction_response = self.attraction_agent.run(query)
print(f"景点搜索结果: {attraction_response[:200]}...\n")
```

### 8. Agent 职责划分

✅ **推荐**：每个 Agent 专注于单一职责

```python
# 景点搜索专家 - 只负责搜索景点
self.attraction_agent = SimpleAgent(
    name="景点搜索专家",
    system_prompt="你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。"
)

# 天气查询专家 - 只负责查询天气
self.weather_agent = SimpleAgent(
    name="天气查询专家",
    system_prompt="你是天气查询专家。你的任务是查询指定城市的天气信息。"
)

# 行程规划专家 - 整合信息生成计划
self.planner_agent = SimpleAgent(
    name="行程规划专家",
    system_prompt="你是行程规划专家。你的任务是根据景点信息和天气信息,生成详细的旅行计划。"
)
```

---

## 总结

### 核心要点

1. **选择合适的 Agent 类型**
   - SimpleAgent：基础对话
   - ReActAgent：需要工具调用
   - ReflectionAgent：需要高质量输出
   - PlanAndSolveAgent：复杂任务分解
   - FunctionCallAgent：精确函数调用

2. **工具系统**
   - 使用 `ToolRegistry` 注册工具
   - 使用 `MCPTool` 集成外部服务
   - 在多智能体系统中共享工具实例

3. **多智能体协作**
   - 每个 Agent 专注单一职责
   - 通过工作流串联多个 Agent
   - 使用单例模式管理 Agent 实例

4. **项目架构**
   - 前后端分离
   - 分层架构（API → Agent → Service）
   - 配置管理和错误处理

5. **最佳实践**
   - LLM 实例单例管理
   - 清晰的提示词设计
   - 完善的错误处理
   - 详细的日志输出

### 学习路径

1. **入门**：从 SimpleAgent 开始，理解基础概念
2. **进阶**：学习 ReActAgent 和工具系统
3. **高级**：掌握多智能体协作和自定义提示词
4. **实战**：参考 `helloagents-trip-planner` 项目构建完整系统

---

## 参考资源

- **官方案例**：`helloagents-examples/`
- **实战项目**：`helloagents-trip-planner/`
- **文档**：HelloAgents 官方文档

---

*本文档基于 `helloagents-examples` 和 `helloagents-trip-planner` 项目源码总结，最后更新时间：2024年12月*

