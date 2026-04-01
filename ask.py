from qwen import ask_qwen


chatlogs = 'chatlogs/demo.json'

question = \
"""
"""
question = question.strip()


ask_qwen(chatlogs, question, True)