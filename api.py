from flask import Flask, request, jsonify, session, g, current_app, abort
# from flask_socketio import SocketIO, emit
import websockets
import threading
import json
# from flask_socketio import SocketIO, emit
# import tornado.web
# import tornado.websocket
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
# import autobahn
# from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
import asyncio



app = Flask(__name__)
# socketio = SocketIO(app)



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

@app.route('/chat_api', methods=['POST'])
def chat_api():
    data = request.json
    action = data.get('action')

    if action == 'load_model':
        model_name = "facebook_opt-1.3b"  
        loader = "Transformers"  
        try:
            if 'model_loaded' not in session or data.get('force_reload', False):
                load_model(model_name, loader)
                session['model_loaded'] = True
                return jsonify({"message": "Model loaded successfully"}), 200
            else:
                return jsonify({"message": "Model already loaded"}), 200
        except Exception as e:
            return jsonify({"error": "Error loading model: " + str(e)}), 500

    elif action == 'load_character':
        character = data.get('character')
        name1 = data.get('name1', 'default_name1') 
        name2 = data.get('name2', 'default_name2')

        if not character:
            return jsonify({'error': 'Character name is required.'}), 400

        try:
            name1, name2, picture, greeting, context = load_character(character, name1, name2)
            session['character'] = character
            session['context'] = context
            return jsonify({
                'message': 'Character loaded successfully',
                'name1': name1,
                'name2': name2,
                'picture': picture,
                'greeting': greeting,
                'context': context
            }), 200
        except Exception as e:
            traceback.print_exc()
            return jsonify({'error': "Error loading character: " + str(e)}), 500


    elif action == 'generate_api':
        try:
            data = request.json
            question = data.get('question')
            original_question = data.get('original_question', question)
            seed = data.get('seed', -1)

            state = data.get('state', {})
            preset_name = state.get('preset_name', 'simple-1') 
            state.update(load_preset(preset_name))

            if not question:
                return jsonify({'error': 'Question is required.'}), 400

            try:
                response_generator = generate_reply_HF(question, original_question, seed, state)
                responses = list(response_generator)
                return jsonify({'responses': responses}), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Invalid action specified.'}), 400


# @app.route('/new_reply', methods=['POST'])
# def new_reply():
#     try:
#         data = request.json
#         question = data['question']
#         state = data['state']

#         required_keys = ['sampler_priority','max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
#         if not all(key in state for key in required_keys):
#             return jsonify({'error': 'Missing required state keys: {}'.format(', '.join(required_keys))}), 400
        
#         state['grammar_string'] = """
#         root ::= (expr "=" ws term "\\n")+
#         expr ::= term ([\\-+\\*/] term)*
#         term ::= ident | num | "(" ws expr ")"
#         ident ::= [a-z][a-z0-9_]*
#         ws
#         num ::= [0-9]+
#         ws
#         ws ::= [\\t\\n]*
#         """

#         response_generator = generate_reply_HF(question, question, None, state)
#         response = next(response_generator)
#         return jsonify({'reply': response}), 200

#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/new_reply', methods=['POST'])
# def new_reply():
#     try:
#         data = request.json
#         question = data['question']
#         state = data['state']
#         required_keys = ['auto_max_new_tokens','sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']

#         if not all(key in state for key in required_keys):
#             return jsonify({'error': 'Missing required state keys: {}'.format(', '.join(required_keys))}), 400


#         grammar_file_name = 'c' 
#         grammar = initialize_grammar(grammar_file_name)

#         if grammar is None:
#             return jsonify({'error': 'Invalid grammar file'}), 400

#         response_generator = generate_reply_HF(question, question, None, state)
#         response = {
#             'results' : [
#                 {
#                     'history' : {
#                         'internal' : [],
#                         'visible' : [question, response]
#                     }
#                 }
#             ]
#         }
#         response1 = generate_basic_html(response)
        
#         # response = next(response_generator)
#         print(f"response: {response1}")
#         return jsonify({'reply': response1}), 200
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

@app.route('/new_reply', methods=['POST'])
def new_reply():
    try:
        data = request.json
        print(f"data ={data}")
        question = data['question']
        print(f"questionm = {question}")
        state = data['state']
        print(f"state = {state}")
        required_keys = ['auto_max_new_tokens','sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
        print(f"required_keys = {required_keys}")
        if not all(key in state for key in required_keys):
            return jsonify({'error': 'Missing required state keys: {}'.format(', '.join(required_keys))}), 400

        grammar_file_name = 'roleplay' 
        grammar = initialize_grammar(grammar_file_name)

        if grammar is None:
            return jsonify({'error': 'Invalid grammar file'}), 400

        response = None  # Declare response initially as None or suitable default
        response_generator = generate_reply_HF(question, question, None, state)
        print(f"response_generator = {response_generator}")
        response = next(response_generator, "No response generated")  # This should set 'response' appropriately
        for output in response_generator:
            print(f"output chunk: {output}")
        response1 = {
            'results' : [
                {
                    'history' : {
                        'internal' : [],
                        'visible' : [question, output]
                    }
                }
            ]
        }
        print(f"response1 = {response1}")
        
        
        # print(f"response: {response_html}")
        return jsonify({'reply': response1}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# class MyServerProtocol(WebSocketServerProtocol):
#     def onConnect(self, request):
#         print("Client connecting: {}".format(request.peer))
#
#     def onOpen(self):
#         print("WebSocket connection open.")
#
#     def onMessage(self, payload, isBinary):
#         try:
#             data = payload.decode('utf-8')
#             print(f"data ={data}")
#             question = data['question']
#             print(f"questionm = {question}")
#             state = data['state']
#             print(f"state = {state}")
#             required_keys = ['auto_max_new_tokens', 'sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
#             print(f"required_keys = {required_keys}")
#             if not all(key in state for key in required_keys):
#                 error_msg = 'Missing required state keys: {}'.format(', '.join(required_keys))
#                 self.sendMessage(error_msg.encode('utf-8'), isBinary)
#                 return
#
#             grammar_file_name = 'roleplay'
#             grammar = initialize_grammar(grammar_file_name)
#             if grammar is None:
#                 error_msg = 'Invalid grammar file'
#                 self.sendMessage(error_msg.encode('utf-8'), isBinary)
#                 return
#
#             response = None
#             response_generator = generate_reply_HF(question, question, None, state)
#             print(f"response_generator = {response_generator}")
#             response = next(response_generator, "No response generated")
#             print(f"output chunk: {response}")
#             response1 = {
#                 'results': [
#                     {
#                         'history': {
#                             'internal': [],
#                             'visible': [question, response]
#                         }
#                     }
#                 ]
#             }
#             print(f"response1 = {response1}")
#             self.sendMessage(str(response1).encode('utf-8'), isBinary)
#         except Exception as e:
#             error_msg = str(e)
#             self.sendMessage(error_msg.encode('utf-8'), isBinary)
#
#     def onClose(self, wasClean, code, reason):
#         print("WebSocket connection closed: {}".format(reason))
#
#
# @app.route('/start_websocket')
# def start_websocket():
#     # Start the WebSocket server in a separate thread or process
#     factory = WebSocketServerFactory()
#     factory.protocol = MyServerProtocol
#
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     coro = loop.create_server(factory, '127.0.0.1', 8000)
#     server = loop.run_until_complete(coro)
#
#     def run_server():
#         try:
#             loop.run_forever()
#         except KeyboardInterrupt:
#             pass
#         finally:
#             server.close()
#             loop.close()
#
#     import threading
#     server_thread = threading.Thread(target=run_server)
#     server_thread.start()
#
#     return 'WebSocket server started'






# @app.route('/new_reply', methods=['POST'])
# def new_reply():
#     try:
#         data = request.json
#         question = data['question']
#         state = data['state']
#         seed = -1
#         required_keys = ['auto_max_new_tokens', 'sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']

#         if not all(key in state for key in required_keys):
#             return jsonify({'error': 'Missing required state keys: {}'.format(', '.join(required_keys))}), 400

#         grammar_file_name = 'c' 
#         grammar = initialize_grammar(grammar_file_name)

#         if grammar is None:
#             return jsonify({'error': 'Invalid grammar file'}), 400

#         response_generator = generate_reply_HF(question, seed, None, state)
#         response = next(response_generator, "No response generated")  # Provide a default message if no response

#         response1 = {
#             'results' : [
#                 {
#                     'history' : {
#                         'internal' : [],
#                         'visible' : [question, response]
#                     }
#                 }
#             ]
#         }
#         response_html = generate_basic_html(response1)
        
#         print(f"response: {response_html}")
#         return jsonify({'reply': response_html}), 200
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500








# @socketio.on('new__reply')
# def handle_new_reply(data):
#     try:
#         print(f"data ={data}")
#         question = data['question']
#         print(f"questionm = {question}")
#         state = data['state']
#         print(f"state = {state}")
#         required_keys = ['auto_max_new_tokens', 'sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
#         print(f"required_keys = {required_keys}")
#         if not all(key in state for key in required_keys):
#             emit('error', {'error': 'Missing required state keys: {}'.format(', '.join(required_keys))})
#             return

#         grammar_file_name = 'roleplay'
#         grammar = initialize_grammar(grammar_file_name)
#         if grammar is None:
#             emit('error', {'error': 'Invalid grammar file'})
#             return

#         response = None
#         response_generator = generate_reply_HF(question, question, None, state)
#         print(f"response_generator = {response_generator}")
#         response = next(response_generator, "No response generated")
#         print(f"output chunk: {response}")
#         response1 = {
#             'results': [
#                 {
#                     'history': {
#                         'internal': [],
#                         'visible': [question, response]
#                     }
#                 }
#             ]
#         }
#         print(f"response1 = {response1}")
#         emit('reply', response1)
#     except Exception as e:
#         emit('error', {'error': str(e)})


async def handle_websocket(websocket, path):
    async for message in websocket:
        try:
            data = json.loads(message)
            print(f"data ={data}")
            question = data['question']
            print(f"questionm = {question}")
            state = data['state']
            print(f"state = {state}")
            required_keys = ['auto_max_new_tokens', 'sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
            print(f"required_keys = {required_keys}")
            if not all(key in state for key in required_keys):
                error_msg = 'Missing required state keys: {}'.format(', '.join(required_keys))
                await websocket.send(error_msg)
                return

            grammar_file_name = 'roleplay'
            grammar = initialize_grammar(grammar_file_name)
            if grammar is None:
                error_msg = 'Invalid grammar file'
                await websocket.send(error_msg)
                return

            response = None
            response_generator = generate_reply_HF(question, question, None, state)
            print(f"response_generator = {response_generator}")
            response = next(response_generator, "No response generated")
            for output in response_generator:
                print(f"output chunk: {output}")
            response1 = {
                'results': [
                    {
                        'history': {
                            'internal': [],
                            'visible': [question, output]
                        }
                    }
                ]
            }
            print(f"response1 = {response1}")
            await websocket.send(json.dumps(response1))
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



@app.before_request
def setup_app():
        load_tokenizer()





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

# @app.route('/setup', methods=['POST'])
# def setup_conversation():
#     data = request.json
#     state.update(data)  # Update state with provided data
#     return jsonify({"message": "Setup successful", "state": state}), 200


# @app.route('/generate_prompt', methods=['POST'])
# def generate_prompt():
#     user_input = request.json.get('user_input', '')
#     mode = state.get('mode', 'chat')
#     template_str = state['chat_template_str'] if mode == 'chat' else state['instruction_template_str']
    
#     template = jinja_env.from_string(template_str)
#     messages = [{"role": "user", "content": user_input.strip()}]  # Example: Starting with user input

#     prompt = template.render(messages=messages, name1=state['name1'], name2=state['name2'], user_bio=state['user_bio'])
#     return jsonify({"prompt": prompt}), 200


# @app.route('/load_model', methods=['POST'])
# def load_model_route():
#     data = request.json
#     model_name = data['model_name']
#     loader = data.get('loader')

#     try:
#         load_model(model_name, loader)
#         return jsonify({'message': 'Model loaded successfully'})
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500


# @app.route('/upload_character', methods=['POST'])
# def upload_character_endpoint():
#     file = request.files['file']
#     img = request.files.get('img')
#     tavern = request.form.get('tavern', False)

#     try:
#         result = upload_character(file.read(), img=img, tavern=tavern)
#         return jsonify({'message': 'Character uploaded successfully', 'result': result})
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500


# @app.route('/load_character', methods=['POST'])
# def load_character_endpoint():
#     character = request.args.get('character')
#     name1 = request.args.get('name1')
#     name2 = request.args.get('name2')
    
#     try:
#         name1, name2, picture, greeting, context = load_character(character, name1, name2)
#         return jsonify({'name1': name1, 'name2': name2, 'picture': picture, 'greeting': greeting, 'context': context})
#     except ValueError:
#         return jsonify({'error': 'Character not found.'}), 404


# # Define the delete file endpoint
# @app.route('/delete_character', methods=['POST'])
# def delete_file_endpoint():
#     # Parse request data
#     data = request.json
#     file_name = data.get('file_name', '')

#     # Call delete_file function and return response
#     return delete_file(file_name)


# @app.route('/unload_model', methods=['POST'])
# def unload_model_endpoint():
#     unload_model()
#     return jsonify({'message': 'Model unloaded successfully'}), 200


if __name__ == '__main__':
    app.run(debug=True)
    # socketio.run(app)

