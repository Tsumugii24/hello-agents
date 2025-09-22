# test_simple_agent.py
from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM
from my_simple_agent import MySimpleAgent

# 加载环境变量
load_dotenv()

# 创建LLM实例
llm = HelloAgentsLLM()

# 创建自定义SimpleAgent
agent = MySimpleAgent(
    name="我的简单助手",
    llm=llm,
    system_prompt="你是一个友好的AI助手，请用简洁明了的方式回答问题。"
)

# 测试标准调用
response1 = agent.run("你好，请介绍一下自己")
print(f"标准响应: {response1}")

# 测试流式调用
print("\n流式响应:")
for chunk in agent.stream_run("请解释什么是人工智能"):
    pass  # 内容已在stream_run中实时打印

# 查看对话历史
print(f"\n对话历史: {len(agent.get_history())} 条消息")