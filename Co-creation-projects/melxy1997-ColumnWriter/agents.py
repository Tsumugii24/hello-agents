"""核心 Agent"""

import json
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from hello_agents import (
    HelloAgentsLLM,
    ReActAgent,
    ReflectionAgent,
    PlanAndSolveAgent
)
from hello_agents.tools import MCPTool, ToolRegistry, SearchTool
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
            print(f"▸ LLM服务初始化成功")
            print(f"   提供商: {cls._instance.provider}")
            print(f"   模型: {cls._instance.model}")
        return cls._instance


class PlannerAgent:
    """
    使用 PlanAndSolveAgent 模式
    
    PlanAndSolveAgent 将任务分解为子任务并逐步执行，非常适合专栏规划场景：
    1. 分析主题（理解用户需求）
    2. 规划子话题（分解任务）
    3. 组织结构（逐步执行）
    
    支持缓存机制，以主题为key缓存规划结果
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        """
        初始化规划 Agent
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.llm = LLMService.get_llm()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
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
    "步骤3: 规划2-4个子话题，确保逻辑递进",
    "步骤4: 为每个子话题设定学习目标和要点",
    "步骤5: 组装完整的专栏大纲"
]
```
不能超过10个步骤。

""",
            "executor": """
你是专栏规划执行专家。请按照规划步骤执行专栏大纲的生成。

# 原始主题: {question}
# 规划步骤: {plan}
# 已完成步骤: {history}
# 当前步骤: {current_step}

▸️ **关键要求**：
- 不能超过10个步骤。
- 如果当前步骤是"步骤5: 组装完整的专栏大纲"或包含"组装"、"完整"、"大纲"等关键词，**必须**输出完整的 JSON 格式专栏大纲
- 如果不是最后一步，请输出当前步骤的分析结果（文本格式）

**最后一步的输出格式（必须是 JSON，不要添加任何其他文本）**：
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
      "estimated_words": 200,
      "key_points": ["要点1", "要点2", "要点3"],
      "prerequisites": ["前置知识1", "前置知识2"]
    }}
  ]
}}
```

**重要**：如果是最后一步，请直接输出 JSON，不要添加"当前步骤分析结果"等前缀文本。

请执行当前步骤：
"""
        }
        
        # 创建带缓存的 Executor 包装器
        from hello_agents.agents.plan_solve_agent import Executor
        
        class CachedExecutor(Executor):
            """带缓存的 Executor，缓存每个步骤的执行结果"""
            def __init__(self, llm_client, prompt_template, cache_dir, main_topic):
                super().__init__(llm_client, prompt_template)
                self.cache_dir = cache_dir
                self.main_topic = main_topic
                self.steps_cache_dir = cache_dir / "steps_cache"
                self.steps_cache_dir.mkdir(exist_ok=True)
            
            def _get_step_cache_key(self, step_index: int, step_content: str) -> Path:
                """生成步骤缓存文件路径"""
                # 使用主题 + 步骤索引 + 步骤内容的hash作为key
                step_hash = hashlib.md5(
                    f"{self.main_topic}_{step_index}_{step_content}".encode('utf-8')
                ).hexdigest()
                return self.steps_cache_dir / f"step_{step_index}_{step_hash}.json"
            
            def _load_step_from_cache(self, step_index: int, step_content: str) -> Optional[str]:
                """从缓存加载步骤结果"""
                cache_file = self._get_step_cache_key(step_index, step_content)
                if not cache_file.exists():
                    return None
                
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    # 验证缓存的主题和步骤是否匹配
                    if (cache_data.get('topic') == self.main_topic and 
                        cache_data.get('step_index') == step_index and
                        cache_data.get('step_content') == step_content):
                        print(f"   ▸ 从缓存加载步骤 {step_index} 的结果")
                        return cache_data.get('result')
                except Exception as e:
                    print(f"   ▸️  加载步骤缓存失败: {e}")
                return None
            
            def _save_step_to_cache(self, step_index: int, step_content: str, result: str):
                """保存步骤结果到缓存"""
                cache_file = self._get_step_cache_key(step_index, step_content)
                try:
                    cache_data = {
                        'topic': self.main_topic,
                        'step_index': step_index,
                        'step_content': step_content,
                        'result': result
                    }
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"   ▸️  保存步骤缓存失败: {e}")
            
            def execute(self, question: str, plan: List[str], **kwargs) -> str:
                """按计划执行任务（带缓存）"""
                history = ""
                final_answer = ""
                
                print("\n--- 正在执行计划 ---")
                for i, step in enumerate(plan, 1):
                    print(f"\n-> 正在执行步骤 {i}/{len(plan)}: {step}")
                    
                    # 尝试从缓存加载
                    cached_result = self._load_step_from_cache(i, step)
                    if cached_result:
                        response_text = cached_result
                    else:
                        # 缓存未命中，执行步骤
                        prompt = self.prompt_template.format(
                            question=question,
                            plan=plan,
                            history=history if history else "无",
                            current_step=step
                        )
                        messages = [{"role": "user", "content": prompt}]
                        response_text = self.llm_client.invoke(messages, **kwargs) or ""
                        
                        # 保存到缓存
                        self._save_step_to_cache(i, step, response_text)
                    
                    history += f"步骤 {i}: {step}\n结果: {response_text}\n\n"
                    final_answer = response_text
                    print(f"▸ 步骤 {i} 已完成，结果: {final_answer[:100] if len(final_answer) > 100 else final_answer}...")
                
                return final_answer
        
        # 创建 PlanAndSolveAgent，但替换 Executor
        self.agent = PlanAndSolveAgent(
            name="专栏规划专家",
            llm=self.llm,
            custom_prompts=planner_prompts
        )
        
        # 替换 Executor 为带缓存的版本
        cached_executor = CachedExecutor(
            llm_client=self.llm,
            prompt_template=planner_prompts["executor"],
            cache_dir=self.cache_dir,
            main_topic=""  # 将在 plan_column 中设置
        )
        self.agent.executor = cached_executor
    
    def _get_cache_key(self, main_topic: str) -> str:
        """
        生成缓存key（使用主题的hash值）
        
        Args:
            main_topic: 专栏主题
            
        Returns:
            缓存文件名
        """
        # 使用主题的hash值作为文件名
        topic_hash = hashlib.md5(main_topic.encode('utf-8')).hexdigest()
        return f"plan_{topic_hash}.json"
    
    def _load_from_cache(self, main_topic: str) -> Optional[ColumnPlan]:
        """
        从缓存加载规划结果
        
        Args:
            main_topic: 专栏主题
            
        Returns:
            ColumnPlan 实例，如果缓存不存在则返回 None
        """
        cache_file = self.cache_dir / self._get_cache_key(main_topic)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 验证缓存的主题是否匹配
            if cache_data.get('topic') != main_topic:
                print(f"▸️  缓存主题不匹配，忽略缓存")
                return None
            
            plan_data = cache_data.get('plan')
            if not plan_data:
                return None
            
            plan = ColumnPlan.from_dict(plan_data)
            print(f"▸ 从缓存加载规划结果")
            print(f"   缓存文件: {cache_file}")
            return plan
        except Exception as e:
            print(f"▸️  加载缓存失败: {e}")
            return None
    
    def _save_to_cache(self, main_topic: str, plan: ColumnPlan):
        """
        保存规划结果到缓存
        
        Args:
            main_topic: 专栏主题
            plan: ColumnPlan 实例
        """
        cache_file = self.cache_dir / self._get_cache_key(main_topic)
        
        try:
            cache_data = {
                'topic': main_topic,
                'plan': plan.to_dict(),
                'cached_at': str(Path(__file__).stat().st_mtime)  # 简单的缓存时间戳
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"▸ 规划结果已保存到缓存: {cache_file}")
        except Exception as e:
            print(f"▸️  保存缓存失败: {e}")
    
    def plan_column(self, main_topic: str, use_cache: bool = True) -> ColumnPlan:
        """
        规划专栏大纲
        
        Args:
            main_topic: 专栏主题
            use_cache: 是否使用缓存（默认True）
            
        Returns:
            ColumnPlan 实例
        """
        # 尝试从缓存加载
        if use_cache:
            cached_plan = self._load_from_cache(main_topic)
            if cached_plan:
                print(f"   专栏标题: {cached_plan.column_title}")
                print(f"   话题数量: {cached_plan.get_topic_count()}")
                return cached_plan
        
        # 缓存未命中，调用 LLM 进行规划
        print(f"\n▸ PlanAndSolve Agent 开始规划专栏...")
        print(f"   使用模式: 任务分解 → 逐步执行")
        print(f"   主题: {main_topic}")
        
        # 更新 Executor 的主题（用于缓存key）
        if hasattr(self.agent.executor, 'main_topic'):
            self.agent.executor.main_topic = main_topic
        
        response = self.agent.run(main_topic)
        
        # 解析 JSON 响应
        plan_data = self._extract_json(response)
        plan = ColumnPlan.from_dict(plan_data)
        
        print(f"▸ 规划完成")
        print(f"   专栏标题: {plan.column_title}")
        print(f"   话题数量: {plan.get_topic_count()}")
        
        # 保存到缓存
        if use_cache:
            self._save_to_cache(main_topic, plan)
        
        return plan
    
    def _extract_json(self, response: str) -> Dict[str, Any]:
        """从响应中提取 JSON（增强版，支持从历史记录中提取）"""
        try:
            # 方法1: 直接是 JSON
            if response.strip().startswith('{'):
                return json.loads(response.strip())
            
            # 方法2: Markdown 代码块中的 JSON
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                if json_end != -1:
                    json_str = response[json_start:json_end].strip()
                    return json.loads(json_str)
            
            # 方法3: 普通代码块中的 JSON
            if "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                if json_end != -1:
                    json_str = response[json_start:json_end].strip()
                    # 移除可能的语言标识符
                    if json_str.startswith("json"):
                        json_str = json_str[4:].strip()
                    if json_str.startswith('{'):
                        return json.loads(json_str)
            
            # 方法4: 查找所有可能的 JSON 对象（从最大的开始尝试）
            # 找到所有 { 和 } 的位置
            brace_positions = []
            for i, char in enumerate(response):
                if char == '{':
                    brace_positions.append(('{', i))
                elif char == '}':
                    brace_positions.append(('}', i))
            
            # 尝试从最后一个 { 到最后一个 } 提取 JSON
            if brace_positions:
                first_open = next((i for char, i in brace_positions if char == '{'), None)
                last_close = next((i for char, i in reversed(brace_positions) if char == '}'), None)
                
                if first_open is not None and last_close is not None and last_close > first_open:
                    # 尝试提取完整的 JSON
                    potential_json = response[first_open:last_close + 1]
                    try:
                        return json.loads(potential_json)
                    except json.JSONDecodeError:
                        pass
                    
                    # 如果失败，尝试找到包含 "column_title" 或 "topics" 的 JSON（专栏规划的特征字段）
                    # 使用正则表达式找到包含这些字段的 JSON 块
                    import re
                    json_pattern = r'\{[^{}]*(?:"column_title"|"topics")[^{}]*\{[^{}]*\}[^{}]*\}'
                    matches = re.finditer(json_pattern, response, re.DOTALL)
                    for match in matches:
                        try:
                            return json.loads(match.group(0))
                        except json.JSONDecodeError:
                            continue
                    
                    # 更宽松的匹配：找到包含 "column_title" 的 JSON
                    column_title_match = re.search(r'\{[^{}]*"column_title"[^{}]*\{[^{}]*"topics"[^{}]*\[.*?\][^{}]*\}[^{}]*\}', response, re.DOTALL)
                    if column_title_match:
                        try:
                            return json.loads(column_title_match.group(0))
                        except json.JSONDecodeError:
                            pass
            
            # 如果都失败了，抛出错误
            raise ValueError("响应中未找到有效的 JSON 数据")
            
        except json.JSONDecodeError as e:
            print(f"▸️  JSON 解析失败: {e}")
            print(f"   响应内容（前1000字符）: {response[:1000]}...")
            # 尝试从历史记录中查找 JSON（如果响应中包含历史信息）
            if "步骤" in response and "结果" in response:
                print("   尝试从历史记录中提取 JSON...")
                # 查找所有包含 JSON 的步骤结果
                import re
                json_matches = re.findall(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if not json_matches:
                    json_matches = re.findall(r'(\{"column_title".*?"topics".*?\})', response, re.DOTALL)
                
                for json_str in json_matches:
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
            
            raise ValueError(f"响应中未找到有效的 JSON 数据: {str(e)}")
        except Exception as e:
            print(f"▸️  JSON 提取失败: {e}")
            print(f"   响应内容（前500字符）: {response[:500]}...")
            raise


def improved_parse_output(self, text: str):
    """
    改进的解析方法，支持更多格式和边界情况
    
    Args:
        self: Agent 实例（当作为方法绑定时需要）
        text: LLM 的原始响应文本
        
    Returns:
        (thought, action) 元组
    """
    if not text or not text.strip():
        print("▸️  警告: LLM 返回了空响应")
        return None, None
    
    # 尝试多种格式解析 Thought
    thought = None
    thought_patterns = [
        r"Thought:\s*(.*?)(?=\nAction:|\nFinish:|$)",  # 标准格式
        r"思考:\s*(.*?)(?=\n行动:|\n完成:|$)",  # 中文格式
        r"▸\s*(.*?)(?=\n▸|\n▸|$)",  # emoji格式
    ]
    
    thought_end_pos = 0
    for pattern in thought_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            thought = match.group(1).strip()
            if thought:
                thought_end_pos = match.end()
                break
    
    # 尝试多种格式解析 Action
    action = None
    action_patterns = [
        r"Action:\s*(.*?)(?=\nThought:|\nObservation:|\nFinish:|$)",  # 标准格式
        r"行动:\s*(.*?)(?=\n思考:|\n观察:|\n完成:|$)",  # 中文格式
        r"▸\s*(.*?)(?=\n▸|\n▸|\n▸|$)",  # emoji格式
        r"Finish\[(.*?)\]",  # Finish格式（可能没有Action前缀）
    ]
    
    for pattern in action_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            action = match.group(1).strip()
            if action:
                # 如果是 Finish 格式，需要加上 Finish 前缀
                if pattern == r"Finish\[(.*?)\]":
                    action = f"Finish[{action}]"
                break
    
    # 如果仍然没有找到 Action，尝试查找 Finish 关键字（可能格式不标准）
    if not action:
        finish_patterns = [
            r"Finish\s*\[(.*?)\]",
            r"完成\s*\[(.*?)\]",
            r"最终答案:\s*(.*?)(?=\n|$)",
        ]
        for pattern in finish_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if content:
                    action = f"Finish[{content}]"
                    break
    
    # 如果仍然没有找到 Action，检查 Thought 之后是否有正文内容
    # 或者即使没有 Thought，也检查是否有直接的内容（JSON 或正文）
    if not action:
        # 首先尝试从整个文本中提取 JSON（因为 Thought 的正则可能包含了后续内容）
        # 查找第一个 { 到最后一个 } 之间的内容（可能是 JSON）
        json_match = None
        brace_start = text.find('{')
        if brace_start != -1:
            # 找到最后一个 }
            brace_end = text.rfind('}')
            if brace_end > brace_start:
                potential_json = text[brace_start:brace_end + 1]
                # 检查是否包含 content 字段
                if '"content"' in potential_json or "'content'" in potential_json:
                    json_match = re.search(r'\{.*?"content".*?\}', potential_json, re.DOTALL)
        
        # 如果没有找到 JSON，检查 Thought 之后或 Thought 内容中的其他内容
        if thought:
            remaining_text = text[thought_end_pos:].strip()
            if not remaining_text:
                # Thought 内容可能包含了完整的正文
                remaining_text = thought
        else:
            # 没有 Thought，直接检查整个文本
            remaining_text = text.strip()
        
        # 移除可能的 Action: 或 Finish: 前缀（如果格式不标准）
        remaining_text = re.sub(r'^(Action|Finish|行动|完成)[:：]\s*', '', remaining_text, flags=re.IGNORECASE)
        
        if remaining_text or json_match:
            # 如果找到了 JSON，使用 JSON 内容
            if json_match:
                remaining_text = json_match.group(0)
                has_json = True
                json_str = remaining_text
                # 检查 JSON 是否完整（有配对的括号）
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                json_complete = (open_braces == close_braces) and open_braces > 0
            else:
                # 检查是否包含 JSON 结构（可能是完整的文章内容）
                json_match = re.search(r'\{.*?"content".*?\}', remaining_text, re.DOTALL)
                has_json = bool(json_match)
                
                # 如果找到 JSON，检查是否完整（有配对的括号）
                json_complete = False
                if has_json:
                    json_str = json_match.group(0)
                    # 简单检查：大括号是否配对
                    open_braces = json_str.count('{')
                    close_braces = json_str.count('}')
                    json_complete = (open_braces == close_braces) and open_braces > 0
            
            has_content_field = bool(re.search(r'"content"\s*:\s*"', remaining_text, re.DOTALL))
            
            # 检查是否有明显的结尾标记
            has_ending = bool(re.search(r'(总结|结论|结语|小结|综上所述|总之|最后|end|conclusion)', remaining_text[-500:], re.IGNORECASE))
            
            # 检查是否有"未完待续"的标记（表示还想继续写）
            has_continuation_marker = bool(re.search(r'(未完待续|待续|继续|to be continued|未完|待补充)', remaining_text, re.IGNORECASE))
            
            # 检查内容长度（如果超过一定长度，可能是完整内容）
            content_length = len(remaining_text)
            is_substantial = content_length > 200  # 至少200字符
            
            # 判断是否应该自动添加 Finish
            # 优先级：1. 完整的 JSON 结构 > 2. 有结尾标记（即使内容稍短）> 3. 内容足够长且没有未完标记
            is_complete = False
            completion_reason = []
            
            if json_complete:
                is_complete = True
                completion_reason.append("完整的 JSON 结构")
            elif has_ending:
                # 有结尾标记，即使内容稍短也认为是完整的（模型已经表达了完成意图）
                is_complete = True
                if is_substantial:
                    completion_reason.append("有结尾标记且内容足够长")
                else:
                    completion_reason.append("有结尾标记（模型表达了完成意图）")
            elif is_substantial and not has_continuation_marker:
                # 内容足够长且没有未完标记，可能是完整内容
                is_complete = True
                completion_reason.append("内容足够长且无未完标记")
            
            if is_complete:
                print(f"▸ 检测到完整正文内容（长度: {content_length} 字符），自动添加 Finish 前缀")
                print(f"   - 判断依据: {', '.join(completion_reason)}")
                action = f"Finish[{remaining_text}]"
            else:
                # 内容不完整，可能还想继续写
                print(f"▸️  检测到部分正文内容（长度: {content_length} 字符），但可能未完成")
                if has_continuation_marker:
                    print(f"   - 检测到'未完待续'标记，继续循环让模型完成写作")
                elif not is_substantial:
                    print(f"   - 内容长度不足，继续循环让模型完成写作")
                else:
                    print(f"   - 未检测到明确的完成标记，继续循环让模型完成写作")
                # 不设置 action，让循环继续
                return thought, None
    
    # 调试信息
    if not action:
        print(f"▸️  警告: 未能解析出 Action")
        print(f"   响应内容（前500字符）: {text[:500]}")
        print(f"   已解析的 Thought: {thought[:100] if thought else 'None'}...")
    
    return thought, action


class ReActAgentWrapper:
    """
    ReActAgent 包装器，用于捕获历史信息和处理错误
    """
    def __init__(self, agent: ReActAgent):
        self.agent = agent
        self.last_history = []  # 保存最后一次运行的历史
        self.last_response = None  # run() 方法的返回值（通常是 final_answer）
        self.last_raw_responses = []  # 保存所有原始 LLM 响应，用于调试
    
    def run(self, question: str, max_retries: int = 2):
        """
        运行 Agent 并捕获历史信息
        
        Args:
            question: 问题
            max_retries: 最大重试次数（当解析失败时）
        """
        try:
            # 清空上次的原始响应
            self.last_raw_responses = []
            
            # 尝试访问 agent 的 history 属性（如果存在）
            if hasattr(self.agent, 'current_history'):
                original_history = self.agent.current_history.copy() if self.agent.current_history else []
            elif hasattr(self.agent, 'history'):
                original_history = self.agent.history.copy() if self.agent.history else []
            else:
                original_history = []
            
            # 如果 agent 有 _parse_output 方法，保存原始方法并替换为改进版本
            original_parse = None
            original_invoke = None
            
            if hasattr(self.agent, '_parse_output'):
                original_parse = self.agent._parse_output
                # 使用改进的解析方法（绑定到实例）
                import types
                self.agent._parse_output = types.MethodType(improved_parse_output, self.agent)
            
            # 拦截 LLM 调用以捕获原始响应
            if hasattr(self.agent, 'llm') and hasattr(self.agent.llm, 'invoke'):
                original_invoke = self.agent.llm.invoke
                
                def wrapped_invoke(messages, **kwargs):
                    """包装 LLM invoke 方法以捕获原始响应"""
                    response = original_invoke(messages, **kwargs)
                    if response:
                        self.last_raw_responses.append(response)
                    return response
                
                self.agent.llm.invoke = wrapped_invoke
            
            try:
                response = self.agent.run(question)
                self.last_response = response
                
                # 尝试获取最终的历史信息
                if hasattr(self.agent, 'current_history'):
                    self.last_history = self.agent.current_history.copy() if self.agent.current_history else []
                elif hasattr(self.agent, 'history'):
                    self.last_history = self.agent.history.copy() if self.agent.history else []
                else:
                    self.last_history = original_history
                
                return response
            finally:
                # 恢复原始方法
                if original_parse:
                    self.agent._parse_output = original_parse
                if original_invoke and hasattr(self.agent, 'llm'):
                    self.agent.llm.invoke = original_invoke
                    
        except Exception as e:
            # 即使出错也尝试保存历史
            if hasattr(self.agent, 'current_history'):
                self.last_history = self.agent.current_history.copy() if self.agent.current_history else []
            elif hasattr(self.agent, 'history'):
                self.last_history = self.agent.history.copy() if self.agent.history else []
            print(f"▸️  ReActAgentWrapper 捕获到异常: {e}")
            raise


class WriterAgent:
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

        # 创建 ReActAgent（将在包装器中替换解析方法）
        react_agent = ReActAgent(
            name="内容创作专家",
            llm=self.llm,
            tool_registry=self.tool_registry,
            custom_prompt=react_prompt,
            max_steps=10  # 增加到 10 步，给 Agent 更多机会完成任务
        )
        
        self.agent = ReActAgentWrapper(react_agent)
    
    def _setup_search_tool(self):
        """设置搜索工具（使用 SearchTool 和 MCPTool）"""
        settings = get_settings()
        
        # 保存 search_tool 实例供 wrappers 使用
        self.search_tool = None
        
        # 1. 初始化内置 SearchTool
        try:
            # 检查是否配置了搜索 API
            if settings.tavily_api_key or settings.serpapi_api_key:
                self.search_tool = SearchTool(
                    tavily_key=settings.tavily_api_key,
                    serpapi_key=settings.serpapi_api_key
                )
                print("▸ SearchTool (内置) 已初始化")
            else:
                print("▸️  未配置搜索 API Key (Tavily/SerpApi)，跳过 SearchTool 初始化")
        except Exception as e:
            print(f"▸️  初始化 SearchTool 失败: {e}")

        # 2. 注册 wrapper 函数 (如果 search_tool 可用)
        if self.search_tool:
            self._register_search_wrappers()
            
        # 3. 注册 GitHub MCPTool
        try:
            # 检查是否有 GitHub Token (通常在环境变量 GITHUB_PERSONAL_ACCESS_TOKEN)
            if os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
                github_tool = MCPTool(
                    name="github",
                    description="GitHub 操作工具，支持搜索仓库、查看代码等",
                    server_command=["npx", "-y", "@modelcontextprotocol/server-github"],
                    auto_expand=True
                )
                self.tool_registry.register_tool(github_tool)
                print("▸ GitHub MCPTool 已注册")
            else:
                print("▸️  未配置 GITHUB_PERSONAL_ACCESS_TOKEN，跳过 GitHub MCPTool 注册")
        except Exception as e:
            print(f"▸️  注册 GitHub MCPTool 失败: {e}")

    def _register_search_wrappers(self):
        """注册适配 Prompt 的搜索函数 wrappers"""
        
        def web_search(query: str) -> str:
            """通用网页搜索，获取最新资讯和资料"""
            # SearchTool.run 接受 dict 参数
            return str(self.search_tool.run({"query": query}))
        
        def search_recent_info(topic: str) -> str:
            """搜索最新信息和动态"""
            return str(self.search_tool.run({"query": f"{topic} latest info"}))
        
        def search_code_examples(technology: str, task: str) -> str:
            """搜索代码示例和教程"""
            return str(self.search_tool.run({"query": f"{technology} {task} code examples tutorial"}))
        
        def verify_facts(statement: str) -> str:
            """验证事实准确性"""
            return str(self.search_tool.run({"query": f"verify fact: {statement}"}))
        
        self.tool_registry.register_function("web_search", "通用网页搜索，获取最新资讯和资料", web_search)
        self.tool_registry.register_function("search_recent_info", "搜索最新信息和动态", search_recent_info)
        self.tool_registry.register_function("search_code_examples", "搜索代码示例和教程", search_code_examples)
        self.tool_registry.register_function("verify_facts", "验证事实准确性", verify_facts)
        print("▸ 搜索函数 wrappers 已注册")
            
    
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
- 完成写作后，必须使用 `\n\nFinish[JSON内容]` 格式输出结果
- JSON 中的 `level` 字段必须是 {level}
- `content` 字段必须包含完整的文章正文（Markdown格式）
- 文章必须包含：引言、主体内容（3-5个小节）、实践案例、总结
"""
        
        try:
            response = self.agent.run(task_description)
            
            # 调试：打印真正的原始 LLM 响应（最后一次的响应）
            print(f"\n{'='*70}")
            print("▸ ReActAgent 原始 LLM 响应:")
            print(f"{'='*70}")
            if self.agent.last_raw_responses:
                # 打印最后一次的原始响应（通常是包含 Finish[...] 的那次）
                last_raw = self.agent.last_raw_responses[-1]
                print(last_raw)
                # print(last_raw[:2000] if len(last_raw) > 2000 else last_raw)
                # if len(last_raw) > 2000:
                    # print(f"\n... (响应过长，已截断，总长度: {len(last_raw)} 字符)")
            else:
                print("▸️  未捕获到原始响应")
            print(f"{'='*70}\n")
            
            # 打印 run() 方法的返回值（通常是 final_answer）
            print(f"▸ ReActAgent.run() 返回值:")
            print(f"   {response[:500] if response and len(response) > 500 else response}")
            print()
            
            # 检查响应是否有效
            # 注意：即使 response 为空或错误，也要检查是否有原始响应可以提取
            if not response or (isinstance(response, str) and not response.strip()):
                print("▸️  ReActAgent 返回了空响应或空白响应")
                print(f"   已收集的历史信息: {len(self.agent.last_history)} 条")
                
                # 尝试从最后一次原始响应中提取内容
                if self.agent.last_raw_responses:
                    last_raw = self.agent.last_raw_responses[-1]
                    print(f"   尝试从最后一次原始响应中提取内容（长度: {len(last_raw)} 字符）...")
                    # 尝试直接提取 JSON
                    try:
                        content_data = self._extract_json(last_raw)
                        # 验证提取的 JSON 是否包含必需的字段
                        if not isinstance(content_data, dict):
                            raise ValueError("提取的内容不是字典格式")
                        if 'content' not in content_data:
                            print(f"   ▸️  提取的 JSON 缺少 'content' 字段")
                            print(f"   可用字段: {list(content_data.keys())}")
                            raise ValueError("提取的 JSON 缺少 'content' 字段")
                        print("▸ 成功从原始响应中提取到内容")
                        return content_data
                    except Exception as e:
                        print(f"   ▸️  从原始响应提取失败: {e}")
                
                # 如果提取失败，使用 fallback
                return self._generate_content_with_history(
                    node, context, level, structure_requirements, word_count,
                    self.agent.last_history, task_description
                )
            
            # 检查是否是错误消息
            if "无法在限定步数内完成" in response or "抱歉" in response or "流程终止" in response:
                print("▸️  ReActAgent 达到最大步数限制或无法完成任务")
                print(f"   已收集的历史信息: {len(self.agent.last_history)} 条")
                
                # 即使返回错误消息，也尝试从最后一次原始响应中提取内容
                if self.agent.last_raw_responses:
                    last_raw = self.agent.last_raw_responses[-1]
                    print(f"   尝试从最后一次原始响应中提取内容（长度: {len(last_raw)} 字符）...")
                    try:
                        content_data = self._extract_json(last_raw)
                        # 验证提取的 JSON 是否包含必需的字段
                        if not isinstance(content_data, dict):
                            raise ValueError("提取的内容不是字典格式")
                        if 'content' not in content_data:
                            print(f"   ▸️  提取的 JSON 缺少 'content' 字段")
                            print(f"   可用字段: {list(content_data.keys())}")
                            raise ValueError("提取的 JSON 缺少 'content' 字段")
                        print("▸ 成功从原始响应中提取到内容（尽管 ReActAgent 返回了错误消息）")
                        return content_data
                    except Exception as e:
                        print(f"   ▸️  从原始响应提取失败: {e}")
                
                # 如果提取失败，基于历史信息生成内容
                return self._generate_content_with_history(
                    node, context, level, structure_requirements, word_count,
                    self.agent.last_history, task_description
                )
            
            # 如果 response 是 "JSON内容" 这样的占位符，从原始响应中提取
            if response.strip() in ["JSON内容", "JSON", "内容"]:
                print(f"▸️  ReActAgent 返回了占位符 '{response}'，尝试从原始响应中提取...")
                if self.agent.last_raw_responses:
                    last_raw = self.agent.last_raw_responses[-1]
                    print(f"   从最后一次原始响应中提取（长度: {len(last_raw)} 字符）...")
                    try:
                        content_data = self._extract_json(last_raw)
                        if isinstance(content_data, dict) and 'content' in content_data:
                            print("▸ 成功从原始响应中提取到内容")
                            return content_data
                    except Exception as e:
                        print(f"   ▸️  从原始响应提取失败: {e}")
            
            content_data = self._extract_json(response)
            
            # 验证提取的 JSON 是否包含必需的字段
            if not isinstance(content_data, dict):
                raise ValueError(f"提取的内容不是字典格式: {type(content_data)}")
            if 'content' not in content_data:
                print(f"▸️  提取的 JSON 缺少 'content' 字段")
                print(f"   可用字段: {list(content_data.keys())}")
                print(f"   响应内容（前500字符）: {response[:500]}")
                
                # 如果从 response 提取失败，尝试从原始响应中提取
                if self.agent.last_raw_responses:
                    last_raw = self.agent.last_raw_responses[-1]
                    print(f"   尝试从最后一次原始响应中提取（长度: {len(last_raw)} 字符）...")
                    try:
                        content_data = self._extract_json(last_raw)
                        if isinstance(content_data, dict) and 'content' in content_data:
                            print("▸ 成功从原始响应中提取到内容")
                            return content_data
                    except Exception as e:
                        print(f"   ▸️  从原始响应提取失败: {e}")
                
                raise ValueError("提取的 JSON 缺少 'content' 字段")
            
            return content_data
        except Exception as e:
            print(f"▸️  ReActAgent 执行失败: {e}")
            import traceback
            traceback.print_exc()
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
        
        print(f"▸ 使用 SimpleAgent 基于历史信息生成内容...")
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
                print(f"▸ 找到 Finish 格式，内容长度: {len(finish_content)}")
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
            
            # 方法5: 尝试提取所有可能的 JSON 对象，优先选择包含 'content' 字段的
            # 找到所有 { 的位置
            json_candidates = []
            i = 0
            while i < len(response):
                if response[i] == '{':
                    brace_count = 0
                    brace_start = i
                    brace_end = i
                    for j in range(i, len(response)):
                        if response[j] == '{':
                            brace_count += 1
                        elif response[j] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                brace_end = j + 1
                                break
                    
                    if brace_end > brace_start:
                        json_str = response[brace_start:brace_end]
                        try:
                            # 尝试解析这个 JSON
                            parsed = extract_json_with_retry(json_str)
                            # 检查是否包含必需的字段
                            if isinstance(parsed, dict):
                                json_candidates.append((parsed, json_str))
                        except:
                            pass
                        i = brace_end
                    else:
                        i += 1
                else:
                    i += 1
            
            # 优先选择包含 'content' 字段的 JSON
            if json_candidates:
                # 首先尝试找到包含 'content' 字段的
                for parsed, json_str in json_candidates:
                    if 'content' in parsed and parsed.get('content'):
                        print(f"▸ 找到包含 'content' 字段的 JSON（长度: {len(json_str)} 字符）")
                        return parsed
                
                # 如果没有找到包含 'content' 的，选择最完整的 JSON（字段最多的）
                best_candidate = max(json_candidates, key=lambda x: len(x[0]))
                print(f"▸️  未找到包含 'content' 字段的 JSON，使用最完整的 JSON（字段数: {len(best_candidate[0])}）")
                return best_candidate[0]
            
            # 如果都失败了，抛出错误并显示响应内容
            print(f"▸️  无法从响应中提取 JSON")
            print(f"   响应完整内容（前2000字符）:\n{response[:2000]}")
            raise ValueError("响应中未找到有效的 JSON 数据")
            
        except Exception as e:
            print(f"▸️  提取 JSON 时发生错误: {e}")
            print(f"   响应内容（前1000字符）: {response[:1000]}")
            raise


class ReflectionWriterAgent:
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
        print(f"\n▸ ReflectionAgent 开始写作并自我反思...")
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
        
        print(f"▸ ReflectionAgent 完成反思优化")
        
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
            print(f"▸️  JSON 解析失败: {e}")
            raise

