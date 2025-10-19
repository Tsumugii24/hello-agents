"""
CodebaseMaintainer 三天工作流演示

完整展示长程智能体在三天内的工作流程:
- 第一天: 探索代码库
- 第二天: 分析代码质量
- 第三天: 规划重构任务
- 一周后: 检查进度
"""

from hello_agents import HelloAgentsLLM
from datetime import datetime
import json
import time

# 导入 CodebaseMaintainer
import sys
sys.path.append('.')
from codebase_maintainer import CodebaseMaintainer


def day_1_exploration(maintainer):
    """第一天: 探索代码库"""
    print("\n" + "=" * 80)
    print("第一天: 探索代码库")
    print("=" * 80 + "\n")

    # 1. 初步探索
    print("### 1. 初步探索项目结构 ###")
    response = maintainer.explore()
    print(f"\n助手总结:\n{response[:500]}...\n")

    # 2. 深入分析某个模块
    print("### 2. 深入分析数据模型 ###")
    response = maintainer.run("请分析 app/models/ 目录下的数据模型设计")
    print(f"\n助手总结:\n{response[:500]}...\n")

    # 模拟时间流逝
    time.sleep(1)


def day_2_analysis(maintainer):
    """第二天: 分析代码质量"""
    print("\n" + "=" * 80)
    print("第二天: 分析代码质量")
    print("=" * 80 + "\n")

    # 1. 整体质量分析
    print("### 1. 整体代码质量分析 ###")
    response = maintainer.analyze()
    print(f"\n助手总结:\n{response[:500]}...\n")

    # 2. 查看具体问题
    print("### 2. 深入分析问题方法 ###")
    response = maintainer.run(
        "请查看 order_service.py 的 process_order 方法,给出重构建议"
    )
    print(f"\n助手总结:\n{response[:500]}...\n")

    # 模拟时间流逝
    time.sleep(1)


def day_3_planning(maintainer):
    """第三天: 规划重构任务"""
    print("\n" + "=" * 80)
    print("第三天: 规划重构任务")
    print("=" * 80 + "\n")

    # 1. 回顾进度
    print("### 1. 回顾当前进度 ###")
    response = maintainer.plan_next_steps()
    print(f"\n助手总结:\n{response[:500]}...\n")

    # 2. 手动创建详细的重构计划
    print("### 2. 创建详细重构计划 ###")
    maintainer.create_note(
        title="本周重构计划 - Week 1",
        content="""## 目标
完成数据模型层的优化

## 任务清单
- [ ] 为 User.email 添加唯一约束
- [ ] 为 Order 添加 created_at, updated_at 字段
- [ ] 编写数据库迁移脚本
- [ ] 更新相关测试用例

## 时间安排
- 周一: 设计迁移脚本
- 周二-周三: 执行迁移并测试
- 周四: 更新测试用例
- 周五: Code Review

## 风险
- 数据库迁移可能影响线上环境,需要在非高峰期执行
- 现有数据中可能存在重复email,需要先清理
""",
        note_type="task_state",
        tags=["refactoring", "week1", "high_priority"]
    )
    print("✅ 已创建详细的重构计划\n")

    # 模拟时间流逝
    time.sleep(1)


def week_later_review(maintainer):
    """一周后: 检查进度"""
    print("\n" + "=" * 80)
    print("一周后: 检查进度")
    print("=" * 80 + "\n")

    # 1. 查看笔记摘要
    print("### 1. 笔记摘要 ###")
    summary = maintainer.note_tool.run({"action": "summary"})
    print("📊 笔记摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print()

    # 2. 生成完整报告
    print("### 2. 会话报告 ###")
    report = maintainer.generate_report()
    print("\n📄 会话报告:")
    print(json.dumps(report, indent=2, ensure_ascii=False))


def demonstrate_cross_session_continuity():
    """演示跨会话的连贯性"""
    print("\n" + "=" * 80)
    print("演示跨会话的连贯性")
    print("=" * 80 + "\n")

    # 第一次会话
    print("### 第一次会话 (session_1) ###")
    maintainer_1 = CodebaseMaintainer(
        project_name="my_flask_app",
        codebase_path="./my_flask_app",
        llm=HelloAgentsLLM()
    )

    # 创建一些笔记
    maintainer_1.create_note(
        title="数据模型问题",
        content="User.email 缺少唯一约束",
        note_type="blocker",
        tags=["database", "urgent"]
    )

    stats_1 = maintainer_1.get_stats()
    print(f"会话1统计: {stats_1['activity']}\n")

    # 模拟会话结束
    time.sleep(1)

    # 第二次会话 (新的会话ID,但笔记被保留)
    print("### 第二次会话 (session_2) ###")
    maintainer_2 = CodebaseMaintainer(
        project_name="my_flask_app",  # 同一个项目
        codebase_path="./my_flask_app",
        llm=HelloAgentsLLM()
    )

    # 检索之前的笔记
    response = maintainer_2.run(
        "我们之前发现了什么问题?现在应该如何处理?"
    )
    print(f"\n助手回答:\n{response[:300]}...\n")

    stats_2 = maintainer_2.get_stats()
    print(f"会话2统计: {stats_2['activity']}\n")

    # 展示笔记摘要
    summary = maintainer_2.note_tool.run({"action": "summary"})
    print("📊 跨会话笔记摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def demonstrate_tool_synergy():
    """演示三大工具的协同"""
    print("\n" + "=" * 80)
    print("演示三大工具的协同")
    print("=" * 80 + "\n")

    maintainer = CodebaseMaintainer(
        project_name="synergy_demo",
        codebase_path="./demo_project",
        llm=HelloAgentsLLM()
    )

    # 1. TerminalTool 发现问题
    print("### 1. TerminalTool 发现项目结构 ###")
    structure = maintainer.execute_command("ls -la")
    print(f"项目结构:\n{structure[:200]}...\n")

    # 2. NoteTool 记录发现
    print("### 2. NoteTool 记录发现 ###")
    maintainer.create_note(
        title="项目结构分析",
        content=f"项目包含以下主要目录:\n{structure}",
        note_type="conclusion",
        tags=["structure", "analysis"]
    )
    print("✅ 已记录到笔记\n")

    # 3. MemoryTool 存储关键信息 (通过对话)
    print("### 3. MemoryTool 存储关键信息 ###")
    response = maintainer.run("项目的主要结构是什么?")
    print(f"助手回答:\n{response[:200]}...\n")

    # 4. ContextBuilder 整合所有信息
    print("### 4. ContextBuilder 整合所有信息 ###")
    response = maintainer.run(
        "基于我们之前的分析,项目有哪些需要改进的地方?"
    )
    print(f"助手回答:\n{response[:300]}...\n")

    # 展示统计信息
    stats = maintainer.get_stats()
    print("📊 工具使用统计:")
    print(f"  - 执行的命令: {stats['activity']['commands_executed']}")
    print(f"  - 创建的笔记: {stats['activity']['notes_created']}")
    print(f"  - 发现的问题: {stats['activity']['issues_found']}")


def main():
    """主函数"""
    print("=" * 80)
    print("CodebaseMaintainer 三天工作流演示")
    print("=" * 80)

    # 初始化助手
    maintainer = CodebaseMaintainer(
        project_name="my_flask_app",
        codebase_path="./my_flask_app",
        llm=HelloAgentsLLM()
    )

    # 执行三天工作流
    day_1_exploration(maintainer)
    day_2_analysis(maintainer)
    day_3_planning(maintainer)
    week_later_review(maintainer)

    # 额外演示
    print("\n\n" + "=" * 80)
    print("额外演示")
    print("=" * 80)

    demonstrate_cross_session_continuity()
    demonstrate_tool_synergy()

    print("\n" + "=" * 80)
    print("完整演示结束!")
    print("=" * 80)


if __name__ == "__main__":
    main()
