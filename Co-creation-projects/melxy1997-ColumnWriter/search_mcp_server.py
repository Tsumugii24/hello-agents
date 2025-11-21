"""搜索 MCP 服务器 - 为 Agent 提供联网搜索能力"""

import os
from typing import Optional
try:
    from fastmcp import FastMCP
except ImportError:
    print("⚠️  需要安装 fastmcp: pip install fastmcp")
    exit(1)

# 创建 MCP 服务器
mcp = FastMCP("search-server")


@mcp.tool()
def web_search(query: str, max_results: int = 3) -> str:
    """
    联网搜索工具
    
    Args:
        query: 搜索查询词
        max_results: 返回结果数量（默认3条）
        
    Returns:
        搜索结果摘要
    """
    print(f"🔍 执行搜索: {query}")
    
    # 尝试使用 Tavily（推荐）
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_key)
            response = client.search(query=query, max_results=max_results)
            
            result = ""
            if response.get('answer'):
                result += f"💡 AI 答案：{response['answer']}\n\n"
            
            result += "🔗 相关结果：\n"
            for i, item in enumerate(response.get('results', [])[:max_results], 1):
                result += f"[{i}] {item.get('title', '')}\n"
                result += f"    {item.get('content', '')[:200]}...\n"
                result += f"    来源: {item.get('url', '')}\n\n"
            
            return result
        except Exception as e:
            print(f"⚠️  Tavily 搜索失败: {e}")
    
    # 尝试使用 SerpAPI
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if serpapi_key:
        try:
            from serpapi import GoogleSearch
            
            search = GoogleSearch({
                "q": query,
                "api_key": serpapi_key,
                "num": max_results,
                "gl": "cn",
                "hl": "zh-cn"
            })
            
            results = search.get_dict()
            
            result = "🔗 搜索结果：\n"
            
            # 优先返回答案框
            if "answer_box" in results and "answer" in results["answer_box"]:
                result += f"💡 直接答案：{results['answer_box']['answer']}\n\n"
            
            # 知识图谱
            if "knowledge_graph" in results and "description" in results["knowledge_graph"]:
                result += f"📚 知识图谱：{results['knowledge_graph']['description']}\n\n"
            
            # 有机结果
            if "organic_results" in results:
                for i, res in enumerate(results["organic_results"][:max_results], 1):
                    result += f"[{i}] {res.get('title', '')}\n"
                    result += f"    {res.get('snippet', '')}\n"
                    result += f"    {res.get('link', '')}\n\n"
            
            return result
        except Exception as e:
            print(f"⚠️  SerpAPI 搜索失败: {e}")
    
    # 如果都不可用
    return """❌ 搜索功能不可用，请配置以下 API 密钥之一：

1. Tavily API（推荐）
   - 设置环境变量: TAVILY_API_KEY
   - 获取地址: https://tavily.com/
   - 安装: pip install tavily-python

2. SerpAPI
   - 设置环境变量: SERPAPI_API_KEY
   - 获取地址: https://serpapi.com/
   - 安装: pip install google-search-results

配置后重新启动系统。"""


@mcp.tool()
def search_recent_info(topic: str) -> str:
    """
    搜索最新信息（近期新闻、技术更新等）
    
    Args:
        topic: 搜索主题
        
    Returns:
        最新信息摘要
    """
    # 添加时间限定词
    query = f"{topic} 最新 2024"
    return web_search(query, max_results=3)


@mcp.tool()
def search_code_examples(technology: str, task: str) -> str:
    """
    搜索代码示例
    
    Args:
        technology: 技术栈（如 Python、JavaScript）
        task: 任务描述（如 "异步编程"、"文件处理"）
        
    Returns:
        代码示例和说明
    """
    query = f"{technology} {task} 代码示例 教程"
    return web_search(query, max_results=3)


@mcp.tool()
def verify_facts(statement: str) -> str:
    """
    验证事实准确性
    
    Args:
        statement: 需要验证的陈述
        
    Returns:
        验证结果
    """
    query = f"{statement} 事实验证"
    return web_search(query, max_results=3)


if __name__ == "__main__":
    # 运行 MCP 服务器
    print("🚀 启动搜索 MCP 服务器...")
    print("   提供工具: web_search, search_recent_info, search_code_examples, verify_facts")
    mcp.run()

