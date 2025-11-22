"""使用多 Agent 模式的主系统编排逻辑"""

from datetime import datetime
from typing import Dict, Any, List
from models import ContentNode, ContentLevel, ColumnPlan
from agents import (
    AdvancedPlannerAgent,
    AdvancedWriterAgent,
    AdvancedReflectionWriterAgent
)
from config import get_settings, get_word_count


class AdvancedColumnWriterOrchestrator:
    """
    提供多 Agent 模式的专栏写作系统
    
    架构设计：
    1. PlannerAgent → PlanAndSolveAgent（任务分解和规划）
    2. WriterAgent → ReActAgent（推理和工具调用）
    3. 评审+修改 → ReflectionAgent（自我反思优化）
    """
    
    def __init__(self, use_reflection_mode: bool = False):
        """
        初始化编排器
        
        Args:
            use_reflection_mode: 是否使用 ReflectionAgent 模式
                - True: 使用 ReflectionAgent（自动评审和优化）
                - False: 使用 ReActAgent + 独立评审流程
        """
        self.settings = get_settings()
        self.use_reflection_mode = use_reflection_mode
        
        # 创建各个 Agent
        print("\n 初始化专栏写作系统...")
        print(f"   模式选择: {'ReflectionAgent（自我反思）' if use_reflection_mode else 'ReActAgent（推理行动）+ 评审'}")
        
        # 规划 Agent - 使用 PlanAndSolveAgent
        self.planner = AdvancedPlannerAgent()
        
        # 写作 Agent - 根据模式选择
        if use_reflection_mode:
            self.writer = AdvancedReflectionWriterAgent()
            print("   WriterAgent: ReflectionAgent（内置评审优化）")
        else:
            self.writer = AdvancedWriterAgent(enable_search=self.settings.enable_search)
            print("   WriterAgent: ReActAgent（推理-行动-搜索）")
        
        # 统计信息
        self.stats = {
            'total_generations': 0,
            'total_reviews': 0,
            'total_revisions': 0,
            'total_rewrites': 0,
            'start_time': None,
            'end_time': None
        }
        
        print("✅ 系统初始化完成\n")
    
    def create_column(self, main_topic: str) -> Dict[str, Any]:
        """
        创建完整专栏
        
        Args:
            main_topic: 专栏主题
            
        Returns:
            包含专栏完整信息的字典
        """
        self.stats['start_time'] = datetime.now()
        
        print(f"\n{'='*70}")
        print(f"🎯 开始创建专栏：{main_topic}")
        print(f"{'='*70}\n")
        
        # Step 1: 规划专栏结构（使用 PlanAndSolveAgent）
        print("📋 第一步：规划专栏结构（PlanAndSolveAgent）")
        print("-" * 70)
        column_plan = self.planner.plan_column(main_topic)
        print(f"   标题：{column_plan.column_title}")
        print(f"   话题数：{column_plan.get_topic_count()} 个")
        print(f"   目标读者：{column_plan.target_audience}\n")
        
        # Step 2: 为每个子话题创建内容树
        mode_name = "ReflectionAgent" if self.use_reflection_mode else "ReActAgent"
        print(f"✍️  第二步：撰写专栏文章（{mode_name}）")
        print("-" * 70)
        
        content_trees = self._write_topics_sequential(column_plan)
        
        # Step 3: 组装完整专栏
        print("\n📦 第三步：组装专栏内容")
        print("-" * 70)
        full_column = self._assemble_column(column_plan, content_trees)
        
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"✅ 专栏创建完成！耗时 {duration:.1f} 秒")
        print(f"{'='*70}\n")
        
        # 添加统计信息
        full_column['creation_stats'] = self.stats
        full_column['agent_modes'] = {
            'planner': 'PlanAndSolveAgent',
            'writer': 'ReflectionAgent' if self.use_reflection_mode else 'ReActAgent'
        }
        
        return full_column
    
    def _write_topics_sequential(self, column_plan: ColumnPlan) -> List[ContentNode]:
        """顺序写作各个话题"""
        content_trees = []
        
        for idx, topic in enumerate(column_plan.topics, 1):
            print(f"\n{'─'*70}")
            print(f"📝 正在写作第 {idx}/{column_plan.get_topic_count()} 个话题")
            print(f"   话题：{topic['title']}")
            print(f"{'─'*70}")
            
            tree = self._write_topic_tree(topic, column_plan)
            content_trees.append(tree)
            
            # 显示进度
            progress = idx / column_plan.get_topic_count() * 100
            print(f"\n📊 总体进度：{progress:.0f}% ({idx}/{column_plan.get_topic_count()})")
        
        return content_trees
    
    def _write_topic_tree(
        self,
        topic: Dict[str, Any],
        column_context: ColumnPlan
    ) -> ContentNode:
        """递归写作话题树"""
        root = ContentNode(
            id=topic['id'],
            title=topic['title'],
            level=ContentLevel.TOPIC,
            description=topic['description']
        )
        
        context = {
            'column_title': column_context.column_title,
            'column_description': column_context.column_description,
            'target_audience': column_context.target_audience,
            'current_topic': topic
        }
        
        self._recursive_write(root, context, level=1)
        return root
    
    def _recursive_write(
        self,
        node: ContentNode,
        context: Dict[str, Any],
        level: int
    ):
        """递归写作核心逻辑"""
        if level > self.settings.max_depth:
            indent = "  " * level
            print(f"{indent}⚠️  达到最大深度 {self.settings.max_depth}，停止展开")
            return
        
        indent = "  " * level
        print(f"\n{indent}{'┈'*40}")
        print(f"{indent}📄 Level {level}: {node.title}")
        print(f"{indent}{'┈'*40}")
        
        if self.use_reflection_mode:
            # 模式1: 使用 ReflectionAgent（内置评审优化）
            self._write_with_reflection(node, context, level, indent)
        else:
            # 模式2: 使用 ReActAgent（推理-行动）
            self._write_with_react(node, context, level, indent)
    
    def _write_with_reflection(
        self,
        node: ContentNode,
        context: Dict[str, Any],
        level: int,
        indent: str
    ):
        """使用 ReflectionAgent 模式写作"""
        print(f"{indent}✍️  使用 ReflectionAgent 生成并优化内容...")
        
        content_data = self.writer.generate_and_refine_content(node, context, level)
        self.stats['total_generations'] += 1
        
        # ReflectionAgent 已经完成了自我评审和优化
        node.content = content_data['content']
        node.metadata = content_data.get('metadata', {})
        node.metadata['agent_mode'] = 'ReflectionAgent'
        node.metadata['auto_refined'] = True
        
        word_count = content_data.get('word_count', len(content_data['content']))
        print(f"{indent}   字数：{word_count}")
        print(f"{indent}✅ 内容已通过自我反思优化")
        
        # 处理子节点
        self._process_children(node, content_data, context, level, indent)
    
    def _write_with_react(
        self,
        node: ContentNode,
        context: Dict[str, Any],
        level: int,
        indent: str
    ):
        """使用 ReActAgent 模式写作"""
        print(f"{indent}✍️  使用 ReActAgent 生成内容（推理-行动）...")
        
        content_data = self.writer.generate_content(node, context, level)
        self.stats['total_generations'] += 1
        
        node.content = content_data['content']
        node.metadata = content_data.get('metadata', {})
        node.metadata['agent_mode'] = 'ReActAgent'
        
        word_count = content_data.get('word_count', len(content_data['content']))
        print(f"{indent}   字数：{word_count}")
        print(f"{indent}✅ ReActAgent 完成推理和行动")
        
        # 处理子节点
        self._process_children(node, content_data, context, level, indent)
    
    def _process_children(
        self,
        node: ContentNode,
        content_data: Dict[str, Any],
        context: Dict[str, Any],
        level: int,
        indent: str
    ):
        """处理子节点"""
        if content_data.get('needs_expansion') and level < self.settings.max_depth:
            subsections = content_data.get('subsections', [])
            if subsections:
                print(f"{indent}📂 需要展开 {len(subsections)} 个子节点")
                
                for subsection in subsections:
                    child = ContentNode(
                        id=subsection['id'],
                        title=subsection['title'],
                        level=ContentLevel(level + 1),
                        description=subsection['description']
                    )
                    node.add_child(child)
                    
                    # 递归写作子节点
                    self._recursive_write(child, context, level + 1)
    
    def _assemble_column(
        self,
        plan: ColumnPlan,
        trees: List[ContentNode]
    ) -> Dict[str, Any]:
        """组装完整专栏"""
        articles = []
        
        for tree in trees:
            article_content = self._tree_to_markdown(tree)
            
            articles.append({
                'id': tree.id,
                'title': tree.title,
                'content': article_content,
                'metadata': tree.metadata,
                'word_count': tree.count_words()
            })
        
        return {
            'column_info': {
                'title': plan.column_title,
                'description': plan.column_description,
                'target_audience': plan.target_audience,
                'topic_count': plan.get_topic_count()
            },
            'articles': articles,
            'statistics': self._calculate_statistics(trees)
        }
    
    def _tree_to_markdown(self, node: ContentNode, depth: int = 0) -> str:
        """将内容树转换为markdown"""
        markdown = []
        
        heading_level = "#" * (depth + 1)
        markdown.append(f"{heading_level} {node.title}\n")
        
        if node.content:
            markdown.append(node.content)
            markdown.append("\n")
        
        for child in node.children:
            child_md = self._tree_to_markdown(child, depth + 1)
            markdown.append(child_md)
        
        return "\n".join(markdown)
    
    def _calculate_statistics(self, trees: List[ContentNode]) -> Dict[str, Any]:
        """计算统计信息"""
        total_words = 0
        total_nodes = 0
        
        def count_tree(node: ContentNode):
            nonlocal total_words, total_nodes
            total_nodes += 1
            total_words += len(node.content) if node.content else 0
            
            for child in node.children:
                count_tree(child)
        
        for tree in trees:
            count_tree(tree)
        
        return {
            'total_articles': len(trees),
            'total_nodes': total_nodes,
            'total_words': total_words,
            'avg_words_per_article': total_words // len(trees) if trees else 0
        }

