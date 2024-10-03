#!/usr/bin/env python3

import ast
import requests
import json
import operator as op
import os
import argparse

import xml.etree.ElementTree as ET


def togetherxyz_complete(txt, max_tokens = 64):
    data = {
        'model': 'meta-llama/Llama-3.2-3B-Instruct-Turbo',
        'max_tokens': max_tokens,
        'stream_tokens': False,
        "stop": ["</s>", "[/INST]"],
        'temperature': 0.20,
    }

    api_key = os.environ['TOGETHERXYZ_APIKEY']
    headers = {'Content-Type': 'application/json', "Authorization": f'Bearer {api_key}'}
    data['prompt'] = prompt + txt
    response = requests.post('https://api.together.xyz/inference', data=json.dumps(data), headers=headers)
    if response.status_code != 200:
        print("Failed infering", response.text)
        return "Error"
    return json.loads(response.text)['output']['choices'][0]['text']

def llamacpp_complete(txt):
    data = {
        'stream': False,
        'n_predict': 1024,
        "stop": ["</s>", "[/INST]"],
        'temperature': 0.35,
        'top_k': 40,
        'top_p': 0.95,
        'min_p': 0.05,
        'typical_p': 1,
    }
    
    headers = {'Content-Type': 'application/json'}
    data['prompt'] = prompt + txt
    response = requests.post(os.environ['LLAMACPP_SERVER'], data=json.dumps(data), headers=headers)
    return json.loads(response.text)['content']

def continue_prompt(backend, discussion):

    if backend == 'togetherxyz':
        content = togetherxyz_complete(discussion)
    elif backend == 'llamacpp':
        content = llamacpp_complete(discussion)
    else:
        print("unknown llm backend")
        sys.exit(1)
    okay_lines = [line for line in content.split("\n") if
                  line.startswith('Assistant:') or line.startswith('Thoughts:')]
    return okay_lines


prompt = """
You are a helpful assistant to 'User'. You do not respond as 'User' or pretend to be 'User'. 'System' will give you data. Always explain why you do what you do with lines starting with 'Thoughts:'.
Your role is to answer user's requests, using pseudo-python commands serialized to JSON.
Your pseudo-python commands will have lines starting with 'Assistant:'
Your pseudo-python also has math operators + - * /
Finish every command with </s>

Available functions are:
- headlines: Get the newspaper's headlines. Example: headlines()</s> returns ["Michel Barnier invité de France 2", "La FIFA repousse encore sa décision"]
- say: You can say anything. Example: say("Il fait beau aujourd'hui")</s>
- end: End your turn. Example: end</s>

Example:
User: Combien font 3+4?
Thoughts: Let's compute 3+4 then show the result to the user
Assistant: 3+4</s>
System: 7
Assistant: say("Le résultat est 7")</s>
Assistant: end()</s>

Example:
"""

def headlines():
    url = "https://www.lemonde.fr/rss/une.xml"
    resp = requests.get(url)
    resp.raise_for_status()

    xmlroot = ET.fromstring(resp.content)
    items = xmlroot.findall('//item')
    titles = [item.find('title').text for item in items]

    return titles

def say(s):
    print("<", s)
    return None

operators = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
             ast.Div: op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
             ast.USub: op.neg}
funcs = {"headlines": headlines, "say": say}

def pseudo_py_eval(node, oob):
    if isinstance(node, ast.Module):
        return pseudo_py_eval(node.body[0].value, oob)
    if isinstance(node, ast.Call):
        if node.func.id == 'end':
            oob['end'] = True
            return None
        else:
            args = [pseudo_py_eval(arg, oob) for arg in node.args]
            return funcs[node.func.id](*args)
    elif isinstance(node, ast.List):
        return [pseudo_py_eval(item, oob) for item in node.elts]
    elif isinstance(node, ast.Tuple):
        return tuple(pseudo_py_eval(item, oob) for item in node.elts)
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        l = node.left
        o = node.op
        r = node.right
        return operators[type(o)](pseudo_py_eval(l, oob), pseudo_py_eval(r, oob))
    else:
        return None

def pseudo_py(s, oob):
    try:
        tree = ast.parse(s)
        return pseudo_py_eval(tree, oob)
    except SyntaxError as e:
        print(f"Invalid syntax: {e}")
        return None

if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-d', '--debug', action='store_true')
    argparser.add_argument('-b', '--backend', default = 'togetherxyz', choices = ['togetherxyz', 'llamacpp'])
    args = argparser.parse_args()

    r = input("> ")
    discussion = "User:" + r + '\n'
    lines = continue_prompt(args.backend, discussion)

    while True:
        res = None
        oob = {}
        while len(lines) > 0:
            line = lines.pop(0)
            if args.debug:
                print("RX: " + line)

            discussion += line + "\n"
            executed = False
            if line.startswith("Assistant:"):
                l = line[len("Assistant:"):]
                # Sometimes the APIs send the final </s> tag, sometimes they don't
                # Remove it if it does
                if l.endswith("</s>"):
                    l = l[:-4]
                l = l.strip()
                print("$", l)
                res = pseudo_py(l, oob)
                executed = True
                break

        if res is not None:
            discussion += "System: " + str(res) + "\n"

        if not executed:
            break
        if 'end' in oob and oob['end']:
            r = input("> ")
            discussion += "\nUser:" + r + '\n'

        lines = continue_prompt(args.backend, discussion)