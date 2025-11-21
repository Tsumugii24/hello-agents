"""主程序入口"""

import sys
from orchestrator import AdvancedColumnWriterOrchestrator
from exporter import ColumnExporter
from config import get_settings


def main():
    """主函数"""
    print("\n" + "="*70)
    print("HelloAgents 专栏编写系统")
    print("="*70)
    
    # 获取配置
    settings = get_settings()
    
    # 获取主题
    if len(sys.argv) > 1:
        main_topic = " ".join(sys.argv[1:])
    else:
        print("\n请输入专栏主题（或直接回车使用默认主题）：")
        main_topic = input("> ").strip()
        if not main_topic:
            main_topic = "Python异步编程完全指南"
            print(f"使用默认主题：{main_topic}")
    
    # 选择模式
    print("\n请选择写作模式：")
    print("1. ReActAgent 模式 (默认) - 推理、行动、工具调用")
    print("2. ReflectionAgent 模式 - 自我反思、自动优化")
    mode_choice = input("> ").strip()
    use_reflection = mode_choice == "2"
    
    try:
        # 创建高级编排器
        orchestrator = AdvancedColumnWriterOrchestrator(use_reflection_mode=use_reflection)
        
        # 创建专栏
        result = orchestrator.create_column(main_topic)
        
        # 导出结果
        from datetime import datetime
        output_dir = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ColumnExporter.export_to_files(result, output_dir)
        
        # 打印统计
        print(f"\n{'='*70}")
        print(f"📊 创作统计")
        print(f"{'='*70}")
        stats = result['statistics']
        print(f"文章总数: {stats['total_articles']}")
        print(f"总字数: {stats['total_words']:,}")
        print(f"平均字数: {stats['avg_words_per_article']:,}")
        
        if 'agent_modes' in result:
            print(f"\nAgent 模式:")
            print(f"  Planner: {result['agent_modes']['planner']}")
            print(f"  Writer: {result['agent_modes']['writer']}")
        
        print(f"\n{'='*70}")
        print(f"✅ 专栏创建完成！")
        print(f"   输出目录: {output_dir}")
        print(f"{'='*70}\n")
        
    except KeyboardInterrupt:
        print("\n\n⏸️  用户中断，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

