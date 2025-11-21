"""核心 Agent 实现"""

import json
import os
from typing import Dict, Any, Optional
from hello_agents import SimpleAgent, HelloAgentsLLM
from hello_agents.tools import MCPTool
from models import ColumnPlan, ReviewResult, ContentNode
from prompts import (
    PLANNER_PROMPT,
    WRITER_PROMPT,
    REVIEWER_PROMPT,
    REVISION_PROMPT,
    get_structure_requirements
)
from config import get_settings, get_word_count


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


class PlannerAgent:
    """规划 Agent - 负责生成专栏大纲"""
    
    def __init__(self):
        self.llm = LLMService.get_llm()
        self.agent = SimpleAgent(
            name="专栏规划专家",
            llm=self.llm,
            system_prompt="你是一位经验丰富的专栏策划专家，擅长将大话题拆解为结构清晰的专栏大纲。"
        )
    
    def plan_column(self, main_topic: str) -> ColumnPlan:
        """
        规划专栏大纲
        
        Args:
            main_topic: 专栏主题
            
        Returns:
            ColumnPlan 实例
        """
        print(f"\n📋 规划 Agent 开始规划专栏...")
        print(f"   主题: {main_topic}")
        
        prompt = PLANNER_PROMPT.format(topic=main_topic)
        response = self.agent.run(prompt)
        
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
            # 尝试直接解析
            if response.strip().startswith('{'):
                return json.loads(response)
            
            # 查找 JSON 代码块
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


class WriterAgent:
    """写作 Agent - 负责生成和修改内容"""
    
    def __init__(self, enable_search: bool = True):
        """
        初始化写作 Agent
        
        Args:
            enable_search: 是否启用搜索功能
        """
        self.llm = LLMService.get_llm()
        self.enable_search = enable_search
        
        # 根据是否启用搜索调整提示词
        if enable_search:
            system_prompt = """你是一位专业的内容创作者，擅长按照树形结构递归地撰写文章内容。

🔍 你可以使用搜索工具获取最新信息：
- web_search: 搜索最新资讯、技术文档、代码示例等
- search_recent_info: 搜索最新动态和趋势
- search_code_examples: 搜索代码示例和教程
- verify_facts: 验证事实的准确性

当你需要最新信息、技术细节、代码示例或验证事实时，请主动使用搜索工具。"""
        else:
            system_prompt = "你是一位专业的内容创作者，擅长按照树形结构递归地撰写文章内容。"
        
        self.agent = SimpleAgent(
            name="内容创作专家",
            llm=self.llm,
            system_prompt=system_prompt
        )
        
        # 添加搜索工具（如果启用）
        if enable_search:
            self._setup_search_tool()
    
    def _setup_search_tool(self):
        """设置搜索工具（使用 MCPTool）"""
        settings = get_settings()
        
        # 检查是否配置了搜索 API
        has_search_api = bool(settings.tavily_api_key or settings.serpapi_api_key)
        
        if not has_search_api:
            print("⚠️  未配置搜索 API Key，搜索功能将不可用")
            print("   请在 .env 文件中配置 TAVILY_API_KEY 或 SERPAPI_API_KEY")
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
                description="联网搜索工具，提供最新信息、代码示例、事实验证等功能",
                server_command=["python", "search_mcp_server.py"],
                env=env,
                auto_expand=True  # 自动展开所有子工具
            )
            
            self.agent.add_tool(search_tool)
            print("✅ 搜索工具已添加到 WriterAgent")
            print(f"   可用工具数量: {len(self.agent.list_tools())}")
            
        except Exception as e:
            print(f"⚠️  添加搜索工具失败: {e}")
            print("   WriterAgent 将在没有搜索功能的情况下运行")
    
    def generate_content(
        self,
        node: ContentNode,
        context: Dict[str, Any],
        level: int,
        additional_requirements: str = ""
    ) -> Dict[str, Any]:
        """
        生成内容
        
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
        
        prompt = WRITER_PROMPT.format(
            level=level,
            topic_title=node.title,
            description=node.description,
            word_count=word_count,
            context=json.dumps(context, ensure_ascii=False, indent=2),
            structure_requirements=structure_requirements,
            additional_requirements=additional_requirements
        )
        
        response = self.agent.run(prompt)
        content_data = self._extract_json(response)
        
        return content_data
    
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
        # 格式化评审信息
        strengths = "\n".join([f"- {s}" for s in review_result.detailed_feedback.get('strengths', [])])
        
        issues = []
        for issue in review_result.detailed_feedback.get('issues', []):
            issues.append(
                f"[{issue.get('severity', '未知')}] {issue.get('location', '未知位置')}\n"
                f"问题：{issue.get('problem', '')}\n"
                f"建议：{issue.get('suggestion', '')}\n"
                f"影响：{issue.get('impact', '')}"
            )
        issues_text = "\n\n".join(issues)
        
        priority_changes = "\n\n".join([
            f"{i+1}. {change.get('section', '')} - {change.get('action', '')}\n   {change.get('detail', '')}"
            for i, change in enumerate(review_result.revision_plan.get('priority_changes', []))
        ])
        
        minor_improvements = "\n".join([
            f"- {change.get('section', '')}: {change.get('detail', '')}"
            for change in review_result.revision_plan.get('minor_improvements', [])
        ])
        
        word_count = get_word_count(level)
        current_word_count = len(original_content)
        word_count_range = f"{int(word_count * 0.9)}-{int(word_count * 1.1)}"
        
        # 计算字数调整
        if current_word_count < word_count * 0.9:
            word_count_adjustment = f"需要增加约 {int(word_count * 0.9 - current_word_count)} 字"
        elif current_word_count > word_count * 1.1:
            word_count_adjustment = f"需要精简约 {int(current_word_count - word_count * 1.1)} 字"
        else:
            word_count_adjustment = "字数合适，保持当前水平"
        
        prompt = REVISION_PROMPT.format(
            original_content=original_content,
            score=review_result.score,
            grade=review_result.grade,
            strengths=strengths,
            issues=issues_text,
            reviewer_notes=review_result.reviewer_notes,
            priority_changes=priority_changes,
            minor_improvements=minor_improvements,
            word_count_range=word_count_range,
            current_word_count=current_word_count,
            word_count_adjustment=word_count_adjustment
        )
        
        response = self.agent.run(prompt)
        revised_data = self._extract_json(response)
        
        return revised_data
    
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


class ReviewerAgent:
    """评审 Agent - 负责评审内容质量"""
    
    def __init__(self):
        self.llm = LLMService.get_llm()
        self.agent = SimpleAgent(
            name="内容评审专家",
            llm=self.llm,
            system_prompt="你是一位严格而专业的内容评审专家，擅长评审文章质量并提供详细的、可操作的修改建议。"
        )
    
    def review_content(
        self,
        content: str,
        level: int,
        requirements: Dict[str, Any]
    ) -> ReviewResult:
        """
        评审内容
        
        Args:
            content: 待评审内容
            level: 层级
            requirements: 要求（包括字数、要点等）
            
        Returns:
            ReviewResult 实例
        """
        target_word_count = requirements.get('word_count', get_word_count(level))
        key_points = requirements.get('key_points', [])
        
        prompt = REVIEWER_PROMPT.format(
            level=level,
            target_word_count=target_word_count,
            key_points=json.dumps(key_points, ensure_ascii=False),
            content=content
        )
        
        response = self.agent.run(prompt)
        review_data = self._extract_json(response)
        review_result = ReviewResult.from_dict(review_data)
        
        return review_result
    
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

