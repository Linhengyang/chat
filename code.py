from qwen import ask_qwen


chatlogs = 'chatlogs/ner.json'

question = \
r"""
我希望写一个服务，
""".strip()


ask_qwen(chatlogs, question, True)