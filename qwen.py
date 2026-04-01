import os
from openai import OpenAI
import json

# 模型列表: https://help.aliyun.com/model-studio/getting-started/models

client = OpenAI(
    api_key = os.getenv("DASHSCOPE_API_KEY"),
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1",
)



chatlogs = 'test.json'

question = \
"""
OpenAI的SDK里, llm call有四个role分别是system、user、assistant、tool，共同组成了上下文。先不管tool，想问你哪个是大家常说的prompt？system和assistant区别在哪？
"""
question = question.strip()



def ask_qwen(chatlogs_json, user_query):

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
    
    return llm_reply['content']





if __name__ == '__main__':
    print(ask_qwen(chatlogs, question), file='render.md')