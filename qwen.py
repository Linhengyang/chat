import os
from openai import OpenAI
import json

client = OpenAI(
    api_key = os.getenv("DASHSCOPE_API_KEY"),
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

conversation_fp = 'test.json'

with open(conversation_fp) as f:
    conversation_history = json.load(f)


user_input = \
"""OpenAI的SDK里, llm call有四个role分别是system、user、assistant、tool，共同组成了上下文。先不管tool，想问你哪个是大家常说的prompt？system和assistant区别在哪？"""


def chat():

    conversation_history.append({
        "role": "user", 
        "content": user_input
    })

    try:
        response = client.chat.completions.create(
            model="qwen3.5-plus",               # 模型列表: https://help.aliyun.com/model-studio/getting-started/models
            messages=conversation_history
        )

    except Exception as e:
        print(f"错误信息：{e}")
        print("请参考文档: https://help.aliyun.com/model-studio/developer-reference/error-code")
    
    llm_reply = {
        "role": "assistant", 
        "content": response.choices[0].message.content
    }

    conversation_history.append(llm_reply)

    with open(conversation_fp, 'w') as f:
        json.dump(conversation_history, f, indent=4, ensure_ascii=False)
    
    return llm_reply['content']





if __name__ == '__main__':
    print(chat(), file='render.md')