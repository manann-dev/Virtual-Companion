from flask import Flask, request, jsonify, session, g, current_app, abort
import websockets
import threading
import json
from functools import partial
from chat import (
    get_generation_prompt, 
    generate_chat_prompt, 
    load_character, 
    upload_character, 
    save_character, 
    upload_tavern_character,
    delete_character,
    generate_chat_reply
)
from loaders import make_loader_params_visible, loaders_samplers, transformers_samplers
from models import load_model, unload_model, load_tokenizer, get_tokenizer
from pathlib import Path
from utils import delete_file
from text_generation import (
    generate_reply_HF, 
    generate_reply_custom, 
    logger,
    _generate_reply,
    generate_reply,
    generate_reply_wrapper,
    encode,
    decode
)
from presets import default_preset, load_preset
from jinja2 import Environment, FileSystemLoader
import traceback
# from chat import character_is_loaded, chatbot_wrapper, generate_chat_reply_wrapper, replace_character_names, get_encoded_length, get_max_prompt_length
from extensions import apply_extensions
import jinja2
from transformers import AutoTokenizer,AutoModelForCausalLM
from tokenizer_auto import initialize_shared_components
from grammer_utils import initialize_grammar
from html_generator import generate_basic_html
import shared as shared
import asyncio



app = Flask(__name__)




jinja_env = jinja2.Environment()
loaded_model = load_model('facebook_opt-1.3b', 'Transformers')
initialize_shared_components('facebook/opt-1.3b')
model = AutoModelForCausalLM.from_pretrained("facebook/opt-1.3b")
tokenizer = AutoTokenizer.from_pretrained("facebook/opt-1.3b")
shared.model = model
shared.tokenizer = tokenizer
# loaded_model = load_model('facebook/opt-1.3b', 'Transformers')

state = {
    'dark_theme': True,
    'show_controls': True,
    'start_with': '',
    'mode': 'chat',
    'chat_style': 'cai-chat',
    'prompt-default': 'QA',
    'prompt-notebook': 'QA',
    'preset': 'simple-1',
    'history': {'internal': []},
    'max_new_tokens': 512,
    'max_new_tokens_min': 1,
    'max_new_tokens_max': 4096,
    'negative_prompt': '',
    'seed': -1,
    'truncation_length': 2048,
    'truncation_length_min': 0,
    'truncation_length_max': 200000,
    'max_tokens_second': 0,
    'prompt_lookup_num_tokens': 0,
    'custom_stopping_strings': '',
    'custom_token_bans': '',
    'auto_max_new_tokens': False,
    'ban_eos_token': False,
    'add_bos_token': True,
    'grammar_string ': '',
    'skip_special_tokens': True,
    'stream': True,
    'character': 'Assistant',
    'name1': 'You',
    'user_bio': '',
    'custom_system_message': '',
    'instruction_template_str': "{%- set ns = namespace(found=false) -%}\n{%- for message in messages -%}\n    {%- if message['role'] == 'system' -%}\n        {%- set ns.found = true -%}\n    {%- endif -%}\n{%- endfor -%}\n{%- if not ns.found -%}\n    {{- '' + 'Below is an instruction that describes a task. Write a response that appropriately completes the request.' + '\\n\\n' -}}\n{%- endif %}\n{%- for message in messages %}\n    {%- if message['role'] == 'system' -%}\n        {{- '' + message['content'] + '\\n\\n' -}}\n    {%- else -%}\n        {%- if message['role'] == 'user' -%}\n            {{-'### Instruction:\\n' + message['content'] + '\\n\\n'-}}\n        {%- else -%}\n            {{-'### Response:\\n' + message['content'] + '\\n\\n' -}}\n        {%- endif -%}\n    {%- endif -%}\n{%- endfor -%}\n{%- if add_generation_prompt -%}\n    {{-'### Response:\\n'-}}\n{%- endif -%}",
    'chat_template_str': "{%- for message in messages %}\n    {%- if message['role'] == 'system' -%}\n        {%- if message['content'] -%}\n            {{- message['content'] + '\\n\\n' -}}\n        {%- endif -%}\n        {%- if user_bio -%}\n            {{- user_bio + '\\n\\n' -}}\n        {%- endif -%}\n    {%- else -%}\n        {%- if message['role'] == 'user' -%}\n            {{- name1 + ': ' + message['content'] + '\\n'-}}\n        {%- else -%}\n            {{- name2 + ': ' + message['content'] + '\\n' -}}\n        {%- endif -%}\n    {%- endif -%}\n{%- endfor -%}",
    'chat-instruct_command': 'Continue the chat dialogue below. Write a single reply for the character "<|character|>".\n\n<|prompt|>',
    'autoload_model': False,
    'default_extensions': [],
}


app.secret_key = 'manan' 



# async def handle_websocket(websocket, path):
#     async for message in websocket:
#         try:
#             data = json.loads(message)
#             print(f"data = {data}")
#             question = data['question']
#             print(f"question = {question}")
#             state = data['state']
#             state['ban_eos_token'] = False
#             state['custom_token_bans'] = False 
#             state['auto_max_new_tokens'] = False
#             print(f"state = {state}")
#             # required_keys = ['auto_max_new_tokens', 'sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
#             # print(f"required_keys = {required_keys}")
#             # if not all(key in state for key in required_keys):
#             #     error_msg = 'Missing required state keys: {}'.format(', '.join(required_keys))
#             #     await websocket.send(error_msg)
#             #     return

#             grammar_file_name = 'roleplay'
#             grammar = initialize_grammar(grammar_file_name)
#             if grammar is None:
#                 error_msg = 'Invalid grammar file'
#                 await websocket.send(error_msg)
#                 return

#             response = None
#             response_generator = generate_reply_HF(question, question, None, state)
#             print(f"response_generator = {response_generator}")
#             for output in response_generator:
#                 print(f"output chunk: {output}")
#                 response1 = {
#                     'results': [
#                         {
#                             'history': {
#                                 'internal': [],
#                                 'visible': [question, output]
#                             }
#                         }
#                     ]
#                 }
#                 print(f"response1 = {response1}")
#                 await websocket.send(json.dumps(response1))
#         except Exception as e:
#             error_msg = str(e)
#             await websocket.send(error_msg)



async def handle_websocket(websocket, path):
    async for message in websocket:
        try:
            data = json.loads(message)
            question = data['question']
            character_name = data['character_name']
            name1 = data['name1']
            name2 = data['name2']
            state = data['state']

            # Load the character information
            character = load_character(character_name,name1,name2)

            # Generate a response using the text generation WebSocket
            response_generator = generate_reply(question, state, character)
            for output in response_generator:
                response = {'results': [{'history': {'internal': [], 'visible': [question, output]}}]}
                await websocket.send(json.dumps(response))
        except Exception as e:
            error_msg = str(e)
            await websocket.send(error_msg)


async def start_websocket_server():
    async with websockets.serve(handle_websocket, "localhost", 8000):
        await asyncio.Future()  # run forever

def run_websocket_server():
    asyncio.run(start_websocket_server())

@app.route('/start_websocket')
def start_websocket():
    thread = threading.Thread(target=run_websocket_server)
    thread.start()
    return 'WebSocket server started'


def get_default_state():
    return {
        'mode': 'chat',
        'chat_template_str': "Hello, {{ name1 }}. How can I assist you today?",
        'instruction_template_str': "Please follow these instructions: {{ instructions }}",
        'name1': 'User',
        'name2': 'Assistant',
        'user_bio': '',
        'context': '',
        'custom_system_message': '',
        'history': [],
        'chat-instruct_command': '',
        'truncation_length': 512,
        'max_new_tokens': 150
    }


if __name__ == '__main__':
    app.run(debug=True)

