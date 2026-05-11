import os
from openai import OpenAI
import json
from render import render_json
from dotenv import load_dotenv

# 模型列表: https://help.aliyun.com/model-studio/getting-started/models

# 加载 .env 环境变量
load_dotenv()

def ask_qwen(chatlogs_json, user_query, render=True):

    client = OpenAI(
        api_key = os.getenv("DASHSCOPE_API_KEY"),
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    with open(chatlogs_json) as f:
        conversation_context = json.load(f)

    conversation_context.append({
        "role": "user", 
        "content": user_query
    })

    try:
        response = client.chat.completions.create(
            model = "qwen3.5-plus",
            messages = conversation_context
        )

    except Exception as e:
        print(f"错误信息：{e}")
        print("请参考文档: https://help.aliyun.com/model-studio/developer-reference/error-code")
    
    llm_reply = {
        "role": "assistant", 
        "content": response.choices[0].message.content
    }

    conversation_context.append(llm_reply)

    with open(chatlogs_json, 'w') as f:
        json.dump(conversation_context, f, indent=4, ensure_ascii=False)
    
    if render:
        render_json(chatlogs_json)






if __name__ == '__main__':
    question = \
"""
who are you?
"""
    question = question.strip()

    ask_qwen('chatlogs/demo.json', question, True)