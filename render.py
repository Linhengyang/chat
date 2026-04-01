# render a .json file into a .md file

import json
import os




def render_json(chatlogs_json):
    chatlogs_md = chatlogs_json.replace('.json', '.md')

    rendered = f''''''

    with open(chatlogs_json, 'r') as f:
        conversations = json.load(f)

    for paragraph in conversations:
        role = f'''\n>**{paragraph['role']}**:\n'''
        if paragraph['role'] != 'user':
            content = f'''\n{paragraph['content']}\n\n'''
        else:
            content = f'''{paragraph['content']}\n\n'''

        chunk_render = role+content
        rendered += chunk_render

    with open(chatlogs_md, 'w', encoding='utf-8') as f:
        f.write(rendered)



if __name__ == "__main__":
    render_json('test.json')