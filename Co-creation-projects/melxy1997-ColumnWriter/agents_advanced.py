"""核心 Agent"""

import json
import os
from typing import Dict, Any, Optional, List
from hello_agents import (
    HelloAgentsLLM,
    ReActAgent,
    ReflectionAgent,
    PlanAndSolveAgent
)
from hello_agents.tools import MCPTool, ToolRegistry
from models import ColumnPlan, ReviewResult, ContentNode, ContentLevel
from prompts import get_structure_requirements, get_react_writer_prompt, get_reflection_writer_prompts, get_planner_prompts
from config import get_settings, get_word_count
import re # Added for JSON parsing

settings = get_settings()

class LLMService:
    """LLM 服务单例"""
    _instance: Optional[HelloAgentsLLM] = None
    
    @classmethod
    def get_llm(cls) -> HelloAgentsLLM:
        """获取 LLM 实例（单例模式）"""
        if cls._instance is None:
            cls._instance = HelloAgentsLLM()
            print(f"✅ LLM服务初始化成功")
            print(f"   提供商: {cls._instance.provider}")
            print(f"   模型: {cls._instance.model}")
        return cls._instance


class AdvancedPlannerAgent:
    """
    使用 PlanAndSolveAgent 模式
    
    PlanAndSolveAgent 将任务分解为子任务并逐步执行，非常适合专栏规划场景：
    1. 分析主题（理解用户需求）
    2. 规划子话题（分解任务）
    3. 组织结构（逐步执行）
    """
    
    def __init__(self):
        self.llm = LLMService.get_llm()
        
        # 自定义 PlanAndSolve 提示词
        planner_prompts = {
            "planner": """
你是一位经验丰富的专栏策划专家。请将以下专栏主题分解为清晰的子话题规划步骤。

主题: {question}

请按以下格式输出规划步骤:
```python
[
    "步骤1: 分析主题的核心概念和目标读者",
    "步骤2: 确定知识体系的整体框架",
    "步骤3: 规划5-10个子话题，确保逻辑递进",
    "步骤4: 为每个子话题设定学习目标和要点",
    "步骤5: 组装完整的专栏大纲"
]
```
""",
            "executor": """
你是专栏规划执行专家。请按照规划步骤执行专栏大纲的生成。

# 原始主题: {question}
# 规划步骤: {plan}
# 已完成步骤: {history}
# 当前步骤: {current_step}

请执行当前步骤。如果这是最后一步，请输出完整的 JSON 格式专栏大纲：

```json
{{
  "column_title": "专栏总标题",
  "column_description": "专栏简介（100-200字）",
  "target_audience": "目标读者群体",
  "topics": [
    {{
      "id": "topic_001",
      "title": "子话题标题",
      "description": "子话题简介（50-100字）",
      "estimated_words": 2500,
      "key_points": ["要点1", "要点2", "要点3"],
      "prerequisites": ["前置知识1", "前置知识2"]
    }}
  ]
}}
```

如果不是最后一步，请输出当前步骤的分析结果。
"""
        }
        
        self.agent = PlanAndSolveAgent(
            name="专栏规划专家",
            llm=self.llm,
            custom_prompts=planner_prompts
        )
    
    def plan_column(self, main_topic: str) -> ColumnPlan:
        """
        规划专栏大纲
        
        Args:
            main_topic: 专栏主题
            
        Returns:
            ColumnPlan 实例
        """
        print(f"\n📋 PlanAndSolve Agent 开始规划专栏...")
        print(f"   使用模式: 任务分解 → 逐步执行")
        print(f"   主题: {main_topic}")
        
        response = self.agent.run(main_topic)
        
        # 解析 JSON 响应
        plan_data = self._extract_json(response)
        plan = ColumnPlan.from_dict(plan_data)
        
        print(f"✅ 规划完成")
        print(f"   专栏标题: {plan.column_title}")
        print(f"   话题数量: {plan.get_topic_count()}")
        
        return plan
    
    def _extract_json(self, response: str) -> Dict[str, Any]:
        """从响应中提取 JSON"""
        try:
            if response.strip().startswith('{'):
                return json.loads(response)
            
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                raise ValueError("响应中未找到 JSON 数据")
            
            return json.loads(json_str)
        except Exception as e:
            print(f"⚠️  JSON 解析失败: {e}")
            print(f"   响应内容: {response[:500]}...")
            raise


class ReActAgentWrapper:
    """
    ReActAgent 包装器，用于捕获历史信息和处理错误
    """
    def __init__(self, agent: ReActAgent):
        self.agent = agent
        self.last_history = []  # 保存最后一次运行的历史
        self.last_response = None
    
    def run(self, question: str):
        """运行 Agent 并捕获历史信息"""
        try:
            # 尝试访问 agent 的 history 属性（如果存在）
            if hasattr(self.agent, 'history'):
                original_history = self.agent.history.copy() if self.agent.history else []
            else:
                original_history = []
            
            response = self.agent.run(question)
            self.last_response = response
            
            # 尝试获取最终的历史信息
            if hasattr(self.agent, 'history'):
                self.last_history = self.agent.history.copy() if self.agent.history else []
            else:
                self.last_history = original_history
            
            return response
        except Exception as e:
            # 即使出错也尝试保存历史
            if hasattr(self.agent, 'history'):
                self.last_history = self.agent.history.copy() if self.agent.history else []
            raise


class AdvancedWriterAgent:
    """
    写作 Agent - 使用 ReActAgent 模式
    
    ReActAgent 结合推理（Reasoning）和行动（Acting），非常适合需要工具调用的写作场景：
    1. 分析写作需求（推理）
    2. 决定是否需要搜索（推理）
    3. 调用搜索工具（行动）
    4. 整合信息写作（行动）
    """
    
    def __init__(self, enable_search: bool = True):
        """
        初始化写作 Agent
        
        Args:
            enable_search: 是否启用搜索功能
        """
        self.llm = LLMService.get_llm()
        self.enable_search = enable_search
        
        # 创建工具注册表
        self.tool_registry = ToolRegistry()
        
        # 添加搜索工具（如果启用）
        if enable_search:
            self._setup_search_tool()
        
        # 自定义 ReAct 提示词（参考示例代码的简洁格式）
        react_prompt = get_react_writer_prompt() # 从 prompts.py 获取

        # 创建 ReActAgent 并用包装器包装
        react_agent = ReActAgent(
            name="内容创作专家",
            llm=self.llm,
            tool_registry=self.tool_registry,
            custom_prompt=react_prompt,
            max_steps=10  # 增加到 10 步，给 Agent 更多机会完成任务
        )
        
        self.agent = ReActAgentWrapper(react_agent)
    
    def _setup_search_tool(self):
        """设置搜索工具（使用 MCPTool）"""
        settings = get_settings()
        
        # 检查是否配置了搜索 API
        has_search_api = bool(settings.tavily_api_key or settings.serpapi_api_key)
        
        if not has_search_api:
            print("⚠️  未配置搜索 API Key，WriterAgent 将使用 ReAct 模式但无搜索能力")
            return
        
        try:
            # 准备环境变量
            env = {}
            if settings.tavily_api_key:
                env["TAVILY_API_KEY"] = settings.tavily_api_key
            if settings.serpapi_api_key:
                env["SERPAPI_API_KEY"] = settings.serpapi_api_key
            
            # 创建搜索 MCP 工具
            search_tool = MCPTool(
                name="search",
                description="联网搜索工具，提供 web_search, search_recent_info, search_code_examples, verify_facts 等功能",
                server_command=["python", "search_mcp_server.py"],
                env=env,
                auto_expand=True
            )
            
            # 将 MCP 工具的所有子工具注册到 ToolRegistry
            # 注意：这里我们需要手动注册，因为 ReActAgent 使用 ToolRegistry
            self._register_search_functions()
            
            print("✅ 搜索工具已添加到 ReActAgent")
            
        except Exception as e:
            print(f"⚠️  添加搜索工具失败: {e}")
    
    def _register_search_functions(self):
        """注册搜索函数到 ToolRegistry"""
        # 这里注册模拟的搜索函数（实际项目中应该调用 MCP 服务器）
        def web_search(query: str) -> str:
            """网页搜索"""
            return f"[模拟搜索结果] 关于 '{query}' 的搜索结果..."
        
        def search_recent_info(topic: str) -> str:
            """搜索最新信息"""
            return f"[模拟最新信息] 关于 '{topic}' 的最新动态..."
        
        def search_code_examples(technology: str, task: str) -> str:
            """搜索代码示例"""
            return f"[模拟代码示例] {technology} 实现 {task} 的示例代码..."
        
        def verify_facts(statement: str) -> str:
            """验证事实"""
            return f"[模拟验证结果] 关于 '{statement}' 的验证信息..."
        
        self.tool_registry.register_function(
            "web_search",
            "通用网页搜索，获取最新资讯和资料",
            web_search
        )
        self.tool_registry.register_function(
            "search_recent_info",
            "搜索最新信息和动态",
            search_recent_info
        )
        self.tool_registry.register_function(
            "search_code_examples",
            "搜索代码示例和教程",
            search_code_examples
        )
        self.tool_registry.register_function(
            "verify_facts",
            "验证事实准确性",
            verify_facts
        )
    
    def generate_content(
        self,
        node: ContentNode,
        context: Dict[str, Any],
        level: int,
        additional_requirements: str = ""
    ) -> Dict[str, Any]:
        """
        生成内容（使用 ReAct 模式）
        
        Args:
            node: 当前节点
            context: 写作上下文
            level: 当前层级
            additional_requirements: 额外要求
            
        Returns:
            生成的内容数据
        """
        structure_requirements = get_structure_requirements(level)
        word_count = get_word_count(level)
        
        # 构建写作任务描述（简化格式，参考示例代码）
        task_description = f"""
请撰写一篇技术专栏文章。

层级: Level {level}/3
话题: {node.title}
描述: {node.description}
要求字数: {word_count} 字（允许误差±10%）

上下文信息:
{json.dumps(context, ensure_ascii=False, indent=2)}

结构要求:
{structure_requirements}

额外要求:
{additional_requirements if additional_requirements else "无"}

重要提示：
- 完成写作后，必须使用 `Finish[JSON内容]` 格式输出结果
- JSON 中的 `level` 字段必须是 {level}
- `content` 字段必须包含完整的文章正文（Markdown格式）
- 文章必须包含：引言、主体内容（3-5个小节）、实践案例、总结
"""
        
        try:
            response = self.agent.run(task_description)
            
            # 调试：打印原始响应
            print(f"\n{'='*70}")
            print("📋 ReActAgent 原始响应:")
            print(f"{'='*70}")
            print(response[:1000] if len(response) > 1000 else response)
            print(f"{'='*70}\n")
            
            # 检查是否是错误消息
            if response and ("无法在限定步数内完成" in response or "抱歉" in response):
                print("⚠️  ReActAgent 达到最大步数限制或无法完成任务")
                print(f"   已收集的历史信息: {len(self.agent.last_history)} 条")
                # 如果达到步数限制，基于历史信息生成内容
                return self._generate_content_with_history(
                    node, context, level, structure_requirements, word_count,
                    self.agent.last_history, task_description
                )
            
            content_data = self._extract_json(response)
            
            return content_data
        except Exception as e:
            print(f"⚠️  ReActAgent 执行失败: {e}")
            print(f"   已收集的历史信息: {len(self.agent.last_history)} 条")
            print("   尝试基于历史信息生成内容...")
            return self._generate_content_with_history(
                node, context, level, structure_requirements, word_count,
                self.agent.last_history, task_description
            )
    
    def _generate_content_with_history(
        self,
        node: ContentNode,
        context: Dict[str, Any],
        level: int,
        structure_requirements: str,
        word_count: int,
        history: List[str],
        original_task: str
    ) -> Dict[str, Any]:
        """
        当 ReActAgent 失败时，基于历史信息使用 SimpleAgent 生成内容
        
        Args:
            history: ReActAgent 收集的历史信息（Thought、Action、Observation）
        """
        from hello_agents import SimpleAgent
        
        fallback_agent = SimpleAgent(
            name="内容创作专家（备用）",
            llm=self.llm,
            system_prompt="你是一位专业的内容创作者，擅长撰写技术专栏文章。"
        )
        
        # 构建包含历史信息的任务描述
        history_summary = ""
        if history:
            history_summary = "\n\n## 已撰写的部分历史:\n"
            for i, item in enumerate(history[-10:], 1):  # 只取最后10条历史
                history_summary += f"{i}. {item}\n"
            history_summary += "\n请基于以上信息继续完成写作任务。\n"
        
        task = f"""
请撰写一篇技术专栏文章。

话题: {node.title}
描述: {node.description}
要求字数: {word_count} 字

结构要求:
{structure_requirements}
{history_summary}

请直接输出 JSON 格式的内容：
{{
  "title": "{node.title}",
  "level": {level},
  "content": "完整的文章正文（markdown格式，包含引言、主体、案例、总结）",
  "word_count": 实际字数,
  "needs_expansion": false,
  "subsections": [],
  "metadata": {{}}
}}
"""
        
        print(f"📝 使用 SimpleAgent 基于历史信息生成内容...")
        response = fallback_agent.run(task)
        return self._extract_json(response)
    
    def revise_content(
        self,
        original_content: str,
        review_result: ReviewResult,
        level: int
    ) -> Dict[str, Any]:
        """
        根据评审意见修改内容
        
        Args:
            original_content: 原始内容
            review_result: 评审结果
            level: 层级
            
        Returns:
            修改后的内容数据
        """
        # 构建修改任务
        task_description = f"""
## 修改任务

**原始内容**:
{original_content[:500]}...

**评审分数**: {review_result.score}/100
**评审等级**: {review_result.grade}

**主要问题**:
{json.dumps(review_result.detailed_feedback.get('issues', [])[:3], ensure_ascii=False, indent=2)}

**修改建议**:
{json.dumps(review_result.revision_plan.get('priority_changes', []), ensure_ascii=False, indent=2)}

请使用 ReAct 模式完成修改：
1. 思考评审意见的核心要求
2. 决定是否需要搜索新信息
3. 修改内容
4. 使用 Finish[修改后的JSON内容] 输出结果
"""
        
        response = self.agent.run(task_description)
        revised_data = self._extract_json(response)
        
        return revised_data
    
    def _extract_json(self, response: str) -> Dict[str, Any]:
        """
        从响应中提取 JSON（支持多种格式，包括 Finish[...] 格式）
        增强的 JSON 解析，能够处理包含复杂字符串的 JSON
        """
        import re
        import json.encoder
        
        def extract_json_with_retry(json_str: str) -> Dict[str, Any]:
            """尝试多种方式解析 JSON"""
            # 方法1: 直接解析
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
            
            # 方法2: 尝试修复常见的 JSON 问题
            # 修复未转义的换行符
            fixed = json_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            
            # 方法3: 尝试提取并重新构建 JSON
            # 提取各个字段
            title_match = re.search(r'"title"\s*:\s*"([^"]*)"', json_str)
            level_match = re.search(r'"level"\s*:\s*(\d+)', json_str)
            word_count_match = re.search(r'"word_count"\s*:\s*(\d+)', json_str)
            needs_expansion_match = re.search(r'"needs_expansion"\s*:\s*(true|false)', json_str)
            
            # 提取 content（可能跨多行）
            content_match = re.search(r'"content"\s*:\s*"(.*?)"(?=\s*[,}])', json_str, re.DOTALL)
            if not content_match:
                # 尝试另一种格式
                content_match = re.search(r'"content"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', json_str, re.DOTALL)
            
            result = {}
            if title_match:
                result['title'] = title_match.group(1)
            if level_match:
                result['level'] = int(level_match.group(1))
            if content_match:
                # 处理转义字符
                content = content_match.group(1)
                content = content.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
                result['content'] = content
            if word_count_match:
                result['word_count'] = int(word_count_match.group(1))
            else:
                result['word_count'] = len(result.get('content', ''))
            if needs_expansion_match:
                result['needs_expansion'] = needs_expansion_match.group(1) == 'true'
            else:
                result['needs_expansion'] = False
            result['subsections'] = []
            result['metadata'] = {}
            
            return result
        
        try:
            # 方法1: 尝试从 Finish[...] 格式中提取（ReAct 标准格式）
            finish_match = re.search(r"Finish\[(.*?)\]", response, re.DOTALL)
            if finish_match:
                finish_content = finish_match.group(1).strip()
                print(f"🔍 找到 Finish 格式，内容长度: {len(finish_content)}")
                return extract_json_with_retry(finish_content)
            
            # 方法2: 直接是 JSON 对象
            if response.strip().startswith('{'):
                return extract_json_with_retry(response.strip())
            
            # 方法3: Markdown 代码块中的 JSON
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
                return extract_json_with_retry(json_str)
            
            # 方法4: 普通代码块中的 JSON
            if "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
                if json_str.startswith("json"):
                    json_str = json_str[4:].strip()
                return extract_json_with_retry(json_str)
            
            # 方法5: 尝试提取第一个完整的 JSON 对象（使用更宽松的正则）
            # 匹配从第一个 { 到最后一个 } 之间的内容
            brace_start = response.find('{')
            if brace_start != -1:
                brace_count = 0
                brace_end = brace_start
                for i in range(brace_start, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            brace_end = i + 1
                            break
                
                if brace_end > brace_start:
                    json_str = response[brace_start:brace_end]
                    return extract_json_with_retry(json_str)
            
            # 如果都失败了，抛出错误并显示响应内容
            print(f"⚠️  无法从响应中提取 JSON")
            print(f"   响应完整内容（前2000字符）:\n{response[:2000]}")
            raise ValueError("响应中未找到有效的 JSON 数据")
            
        except Exception as e:
            print(f"⚠️  提取 JSON 时发生错误: {e}")
            print(f"   响应内容（前1000字符）: {response[:1000]}")
            raise


class AdvancedReflectionWriterAgent:
    """
    反思写作 Agent - 使用 ReflectionAgent 模式
    
    ReflectionAgent 通过自我反思和迭代优化来改进输出，将评审和修改整合为一个 Agent：
    1. 生成初稿
    2. 自我评审（反思）
    3. 根据反思修改（优化）
    4. 达到质量标准
    """
    
    def __init__(self):
        self.llm = LLMService.get_llm()
        
        # 自定义 Reflection 提示词
        reflection_prompts = {
            "initial": """
你是一位专业的内容创作者。请撰写以下内容的初稿：

{task}

请输出完整的 JSON 格式内容。
""",
            "reflect": """
你是一位严格的内容评审专家。请评审以下内容：

# 写作任务: {task}
# 内容初稿: {content}

请从以下维度评审：
1. **内容质量** (40分): 准确性、完整性、深度、原创性
2. **结构逻辑** (30分): 层次清晰、逻辑连贯、过渡自然
3. **语言表达** (20分): 易读性、专业性、准确性
4. **格式规范** (10分): 字数达标、格式正确、排版美观

如果内容质量很好（85分以上），请回答"无需改进"。
否则，请详细指出问题并提供具体的修改建议。
""",
            "refine": """
请根据评审意见优化你的内容：

# 原始任务: {task}
# 当前内容: {last_attempt}
# 评审意见: {feedback}

请输出优化后的完整 JSON 格式内容。
"""
        }
        
        self.agent = ReflectionAgent(
            name="反思写作专家",
            llm=self.llm,
            custom_prompts=reflection_prompts,
            max_iterations=2  # 最多反思 2 次
        )
    
    def generate_and_refine_content(
        self,
        node: ContentNode,
        context: Dict[str, Any],
        level: int
    ) -> Dict[str, Any]:
        """
        生成并反思优化内容
        
        Args:
            node: 当前节点
            context: 写作上下文
            level: 当前层级
            
        Returns:
            优化后的内容数据
        """
        print(f"\n🔄 ReflectionAgent 开始写作并自我反思...")
        print(f"   使用模式: 初稿 → 自我评审 → 优化")
        
        structure_requirements = get_structure_requirements(level)
        word_count = get_word_count(level)
        
        task_description = f"""
## 写作任务

**层级**: Level {level}/3
**话题**: {node.title}
**描述**: {node.description}
**要求字数**: {word_count} 字（允许误差±10%）

**结构要求**:
{structure_requirements}

**上下文**:
{json.dumps(context, ensure_ascii=False, indent=2)}

请输出完整的 JSON 格式内容：
```json
{{
  "title": "章节标题",
  "level": {level},
  "content": "正文内容（markdown格式）",
  "word_count": 实际字数,
  "needs_expansion": true/false,
  "subsections": [...],
  "metadata": {{...}}
}}
```
"""
        
        response = self.agent.run(task_description)
        content_data = self._extract_json(response)
        
        print(f"✅ ReflectionAgent 完成反思优化")
        
        return content_data
    
    def _extract_json(self, response: str) -> Dict[str, Any]:
        """从响应中提取 JSON"""
        try:
            if response.strip().startswith('{'):
                return json.loads(response)
            
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                raise ValueError("响应中未找到 JSON 数据")
            
            return json.loads(json_str)
        except Exception as e:
            print(f"⚠️  JSON 解析失败: {e}")
            raise

