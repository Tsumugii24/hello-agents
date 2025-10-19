"""
NoteTool 基本操作示例

展示 NoteTool 的核心操作：
1. 创建笔记 (create)
2. 读取笔记 (read)
3. 更新笔记 (update)
4. 搜索笔记 (search)
5. 列出笔记 (list)
6. 笔记摘要 (summary)
7. 删除笔记 (delete)
"""

from hello_agents.tools import NoteTool
import json


def main():
    print("=" * 80)
    print("NoteTool 基本操作示例")
    print("=" * 80 + "\n")

    # 初始化 NoteTool
    notes = NoteTool(workspace="./project_notes")

    # 1. 创建笔记
    print("1. 创建笔记...")
    note_id_1 = notes.run({
        "action": "create",
        "title": "重构项目 - 第一阶段",
        "content": """## 完成情况
已完成数据模型层的重构,测试覆盖率达到85%。

## 下一步
重构业务逻辑层""",
        "note_type": "task_state",
        "tags": ["refactoring", "phase1"]
    })
    print(f"✅ 笔记创建成功,ID: {note_id_1}\n")

    # 创建第二个笔记
    note_id_2 = notes.run({
        "action": "create",
        "title": "依赖冲突问题",
        "content": """## 问题描述
发现某些第三方库版本不兼容,需要解决。

## 影响范围
业务逻辑层的3个模块

## 下一步
1. 使用虚拟环境隔离
2. 锁定版本
3. 使用 pipdeptree 分析依赖树""",
        "note_type": "blocker",
        "tags": ["dependency", "urgent"]
    })
    print(f"✅ 笔记创建成功,ID: {note_id_2}\n")

    # 2. 读取笔记
    print("2. 读取笔记...")
    note = notes.run({
        "action": "read",
        "note_id": note_id_1
    })
    print(f"标题: {note['metadata']['title']}")
    print(f"类型: {note['metadata']['type']}")
    print(f"内容:\n{note['content']}\n")

    # 3. 更新笔记
    print("3. 更新笔记...")
    result = notes.run({
        "action": "update",
        "note_id": note_id_1,
        "content": """## 完成情况
已完成数据模型层的重构,测试覆盖率达到85%。

## 问题
遇到依赖版本冲突,已记录到单独笔记。

## 下一步
先解决依赖冲突,再继续重构业务逻辑层"""
    })
    print(f"{result}\n")

    # 4. 搜索笔记
    print("4. 搜索笔记...")
    search_results = notes.run({
        "action": "search",
        "query": "依赖",
        "limit": 5
    })
    print(f"找到 {len(search_results)} 个相关笔记:")
    for note in search_results:
        print(f"  - {note['title']} ({note['type']})")
    print()

    # 5. 列出笔记
    print("5. 列出所有 blocker 类型的笔记...")
    blockers = notes.run({
        "action": "list",
        "note_type": "blocker",
        "limit": 10
    })
    print(f"找到 {len(blockers)} 个 blocker:")
    for blocker in blockers:
        print(f"  - {blocker['title']} (更新于: {blocker['updated_at']})")
    print()

    # 6. 笔记摘要
    print("6. 生成笔记摘要...")
    summary = notes.run({
        "action": "summary"
    })
    print("笔记摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print()

    # 7. 删除笔记 (演示，实际使用时谨慎)
    print("7. 删除笔记 (演示)...")
    # result = notes.run({
    #     "action": "delete",
    #     "note_id": note_id_2
    # })
    # print(f"{result}\n")
    print("(已跳过实际删除操作)\n")

    print("=" * 80)
    print("NoteTool 操作演示完成!")
    print("=" * 80)


if __name__ == "__main__":
    main()
