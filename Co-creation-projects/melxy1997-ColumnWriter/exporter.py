"""专栏导出工具"""

import os
import json
from typing import Dict, Any
from datetime import datetime


class ColumnExporter:
    """专栏导出工具"""
    
    @staticmethod
    def export_to_files(column_data: Dict[str, Any], output_dir: str = "column_output"):
        """
        导出专栏到文件
        
        Args:
            column_data: 专栏数据
            output_dir: 输出目录
        """
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n{'='*70}")
        print(f"📁 开始导出专栏文件...")
        print(f"{'='*70}\n")
        
        # 导出完整JSON
        json_path = os.path.join(output_dir, 'column_data.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(column_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"✅ 已保存完整数据：{json_path}")
        
        # 导出每篇文章
        for article in column_data['articles']:
            # 安全的文件名
            safe_title = "".join(c for c in article['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"{article['id']}_{safe_title}.md"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入文章内容
                f.write(article['content'])
                
                # 附加元数据
                f.write(f"\n\n---\n\n")
                f.write(f"## 文章元数据\n\n")
                f.write(f"- **文章ID**: {article['id']}\n")
                f.write(f"- **字数**: {article['word_count']}\n")
                f.write(f"- **评审分数**: {article['metadata'].get('review_score', 'N/A')}\n")
                f.write(f"- **评审等级**: {article['metadata'].get('review_grade', 'N/A')}\n")
                
                if article.get('has_revisions'):
                    f.write(f"- **修改次数**: {article['revision_count']}\n")
                    if 'revision_summary' in article['metadata']:
                        f.write(f"- **主要修改**:\n")
                        for change in article['metadata']['revision_summary'].get('major_changes', []):
                            f.write(f"  - {change}\n")
            
            print(f"✅ 已保存文章：{filepath}")
        
        # 导出统计报告
        report_path = os.path.join(output_dir, 'REPORT.md')
        ColumnExporter._export_report(column_data, report_path)
        print(f"✅ 已保存统计报告：{report_path}")
        
        print(f"\n{'='*70}")
        print(f"✅ 导出完成！输出目录：{output_dir}")
        print(f"{'='*70}\n")
    
    @staticmethod
    def _export_report(column_data: Dict[str, Any], filepath: str):
        """导出统计报告"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {column_data['column_info']['title']}\n\n")
            f.write(f"## 专栏信息\n\n")
            f.write(f"- **简介**: {column_data['column_info']['description']}\n")
            f.write(f"- **目标读者**: {column_data['column_info']['target_audience']}\n")
            f.write(f"- **文章数量**: {column_data['column_info']['topic_count']}\n\n")
            
            f.write(f"## 内容统计\n\n")
            stats = column_data['statistics']
            f.write(f"- **总字数**: {stats['total_words']:,}\n")
            f.write(f"- **平均每篇**: {stats['avg_words_per_article']:,} 字\n")
            f.write(f"- **内容节点**: {stats['total_nodes']}\n")
            
            # 适配旧版字段（如果存在）
            if 'approval_rate' in stats:
                f.write(f"- **直接通过**: {stats.get('approved_nodes', 0)} ({stats['approval_rate']})\n")
                f.write(f"- **修改优化**: {stats.get('revised_nodes', 0)} ({stats['revision_rate']})\n")
            
            # 质量报告（如果有）
            if 'quality_report' in column_data:
                f.write(f"\n## 质量报告\n\n")
                quality = column_data['quality_report']
                f.write(f"- **平均分数**: {quality['average_score']:.1f}/100\n")
                f.write(f"- **分数范围**: {quality['min_score']}-{quality['max_score']}\n")
                f.write(f"- **评估节点数**: {quality['total_evaluated']}\n\n")
                
                f.write(f"### 评级分布\n\n")
                for grade, count in quality['grade_distribution'].items():
                    if count > 0:
                        percentage = count / quality['total_evaluated'] * 100 if quality['total_evaluated'] > 0 else 0
                        f.write(f"- **{grade}**: {count} 个 ({percentage:.1f}%)\n")
            
            # Agent 模式信息（新版）
            if 'agent_modes' in column_data:
                f.write(f"\n## Agent 模式\n\n")
                modes = column_data['agent_modes']
                f.write(f"- **Planner**: {modes.get('planner', 'N/A')}\n")
                f.write(f"- **Writer**: {modes.get('writer', 'N/A')}\n")
            
            # 创作统计
            if 'creation_stats' in column_data:
                creation = column_data['creation_stats']
                if creation.get('start_time') and creation.get('end_time'):
                    # 处理可能是字符串或datetime对象的情况
                    start_time = creation['start_time']
                    end_time = creation['end_time']
                    
                    if isinstance(start_time, str):
                        try:
                            start_time = datetime.fromisoformat(start_time)
                            end_time = datetime.fromisoformat(end_time)
                        except:
                            pass

                    if isinstance(start_time, datetime) and isinstance(end_time, datetime):
                        duration = (end_time - start_time).total_seconds()
                        
                        f.write(f"\n## 创作统计\n\n")
                        f.write(f"- **开始时间**: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"- **结束时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"- **总耗时**: {duration:.1f} 秒 ({duration/60:.1f} 分钟)\n")
                
                f.write(f"- **生成调用**: {creation.get('total_generations', 0)}\n")
                if creation.get('total_reviews') > 0:
                    f.write(f"- **评审次数**: {creation.get('total_reviews')}\n")
                if creation.get('total_revisions') > 0:
                    f.write(f"- **修改次数**: {creation.get('total_revisions')}\n")
            
            f.write(f"\n## 文章列表\n\n")
            for idx, article in enumerate(column_data['articles'], 1):
                f.write(f"{idx}. **{article['title']}** ({article['word_count']} 字)\n")
                
                # 显示 Agent 模式生成的元数据
                meta = article.get('metadata', {})
                if 'agent_mode' in meta:
                    f.write(f"   - 模式: {meta['agent_mode']}\n")
                
                if 'review_score' in meta:
                    f.write(f"   - 评分: {meta['review_score']}/100\n")
                
                f.write("\n")

