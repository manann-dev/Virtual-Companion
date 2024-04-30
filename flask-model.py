import transformers
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import torch.nn.functional as F
from models import load_model
import redis
import json
import yaml
import base64
import datetime
from flask import Flask, jsonify, request, abort
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, decode_token
from passlib.context import CryptContext
from datetime import timedelta
from typing import Optional
from redis__db import create_user, get_user, update_user, delete_user, set_user_character, get_user_character
from pydantic import BaseModel
from pathlib import Path
from redis__db import create_user, authenticate_user, get_user, update_user, delete_user, get_user_character, set_user_character
from flask_auth import get_current_user
from characters import load_character
import jinja2
from jinja2 import Environment, FileSystemLoader
from starlette.responses import StreamingResponse
from text_generation import generate_reply_HF
from grammer_utils import initialize_grammar
from flask import Flask, request, jsonify, abort, render_template
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
import redis
from flask_socketio import SocketIO, emit, disconnect

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-secret-key'
redis_host = "redis-16428.c330.asia-south1-1.gce.redns.redis-cloud.com"
redis_port = 16428
redis_password = "hftcJafy6dKQ1gQYkxCfCqGeYhsQWmHe"
redis_db = 0

redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
redis_client = redis.Redis.from_url(redis_url)
jwt = JWTManager(app)
socketio = SocketIO(app)

connected_clients = []
# redis_client = redis.Redis(
#     host='redis-16428.c330.asia-south1-1.gce.redns.redis-cloud.com',
#     port=16428,
#     password='hftcJafy6dKQ1gQYkxCfCqGeYhsQWmHe')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Secret and algorithm
SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"
HF_TOKEN = "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"

class ModelSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if ModelSingleton._instance is None:
            ModelSingleton()
        return ModelSingleton._instance
    
    def __init__(self):
        if ModelSingleton._instance is not None:
            raise Exception("Only one instance of ModelSingleton is allowed")
        else:
            model_dir = "./models/facebook_opt-1.3b"
            self.model = AutoModelForCausalLM.from_pretrained(model_dir)
            self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
            ModelSingleton._instance = self

            print("Model has been loaded successfully!")
            # print(self.model)
            print("Tokenizer has been loaded successfully!")
            # print(self.tokenizer)    
    def get_model(self):
        return self.model
    
    def get_tokenizer(self):
        return self.tokenizer

class UserCreate(BaseModel):
    username: str
    password: str




@app.before_request
def load_model():
    ModelSingleton.get_instance()

def get_model_singleton():
    return ModelSingleton.get_instance()

@app.route('/users/', methods=['POST'])
def create_user_api():
    user = request.json
    try:
        create_user(user.get('username'), user.get('password'))
        return jsonify({"message": "User created successfully"}),201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')

    user = authenticate_user(username, password)
    if user is None:
        abort(401, description="Incorrect username or password")

    token_data = {
        "username": user["username"], 
    }
    token = create_access_token(identity=token_data)
    return jsonify(access_token=token, token_type='bearer')


@app.route('/protected', methods=['GET'])
@jwt_required()
def protected_route():
    current_user = get_current_user()
    return jsonify({"message": f"Hello, {current_user['username']}! This is a protected route."})


@app.route('/select_character', methods=['POST'])
@jwt_required()
def handle_character_selection():
    user = get_current_user()
    character = request.form.get('character')
    if character:
        try:
            character_info = load_character(character, user["username"], "Bot")
            user_key = f"user:{user['username']}"
            redis_client.hset(user_key, character, json.dumps(character_info))
            return jsonify({"message": f"Character '{character}' selected successfully!"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "No character selected"}), 400


@app.route('/select_character', methods=['GET'])
@jwt_required()
def select_character():
    user = get_current_user()
    user_key = f"user:{user['username']}"
    selected_characters = redis_client.hgetall(user_key)
    characters = [json.loads(character_info.decode('utf-8')) for character_info in selected_characters.values()]
    
#     return render_template("select_character.html", username=user["username"], characters=characters)

# @app.route('/generate', methods=['POST'])
# @jwt_required()
# def handle_message():
#     try:
#         token = request.headers.get('Authorization')
#         if not token:
#             return jsonify({'data': 'Authentication required'}), 401

#         user = get_current_user(token)
#         character_info = get_user_character(user["username"])
#         request_data = request.get_json()
#         user_input = request_data['user_input']
#         reply = generate_reply_HF(user_input, character_info)
#         response = {
#             'results': [
#                 {
#                     'history': {
#                         'internal': [],
#                         'visible': [[user_input, reply]]
#                     }
#                 }
#             ]
#         }
#         return jsonify({'data': response})
#     except Exception as e:
#         print(f"Error: {e}")
#         return jsonify({'data': f"Error: {e}"}), 500


# @app.route('/generate', methods=['POST'])
# @jwt_required()
# def handle_message():
#     try:
#         user = get_current_user()  # No token argument is needed
#         character_info = get_user_character(user["username"])
#         request_data = request.get_json()
#         user_input = request_data['user_input']
#         reply = generate_reply_HF(user_input, character_info)
#         response = {
#             'results': [
#                 {
#                     'history': {
#                         'internal': [],
#                         'visible': [[user_input, reply]]
#                     }
#                 }
#             ]
#         }
#         return jsonify({'data': response})
#     except Exception as e:
#         print(f"Error: {e}")
#         return jsonify({'data': f"Error: {e}"}), 500

@app.route('/generate', methods=['POST'])
@jwt_required()
def handle_message():
    try:
        # Get the current user from the token
        user = get_current_user()
        # Fetch character information based on the username
        character_info = get_user_character(user["username"])
        
        # Retrieve the request data
        request_data = request.get_json()
        
        # Define the required keys for state validation
        required_keys = ['auto_max_new_tokens', 'sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
        
        # Extract 'question' and 'state' from the request
        question = request_data.get('question')
        state = request_data.get('state')
        
        # Validate if all required keys are present in the state
        if not all(key in state for key in required_keys):
            return jsonify({'error': 'Missing required state keys: {}'.format(', '.join(required_keys))}), 400
        
        # Initialize grammar based on a predefined grammar file name
        grammar_file_name = 'c'  # Example file name
        grammar = initialize_grammar(grammar_file_name)
        if grammar is None:
            return jsonify({'error': 'Invalid grammar file'}), 400
        
        # Generate a response using the provided question, character info, and state
        response_generator = generate_reply_HF(question, character_info, None, state)
        response = next(response_generator)
        
        # Send the generated response
        return jsonify({'reply': response}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500




@socketio.on('connect', namespace='/test')
def handle_connect():
    connected_clients.append(request.sid)
    print('Client connected')
    emit('my_response', {'data': 'Connected'})

@socketio.on('disconnect', namespace='/test')
def handle_disconnect():
    connected_clients.remove(request.sid)

@socketio.on('message')
def handle_message(message):
    try:
        request_data = json.loads(message)
        reply = generate_reply_HF(request_data['user_input'], character_info)
        response = {
            'results': [
                {
                    'history': {
                        'internal': [],
                        'visible': [[request_data['user_input'], reply]]
                    }
                }
            ]
        }
        emit('my_response', {'data': json.dumps(response)})
    except Exception as e:
        print(f"Error: {e}")
        emit('my_response', {'data': f"Error: {e}"})

@app.route('/new_reply', methods=['POST'])
@jwt_required()
def new_reply():
    try:
        data = request.json
        print(f"data ={data}")
        question = data['question']
        print(f"question = {question}")
        state = data['state']
        print(f"state = {state}")
        required_keys = ['auto_max_new_tokens', 'sampler_priority', 'max_new_tokens', 'temperature', 'add_bos_token', 'truncation_length']
        print(f"required_keys = {required_keys}")
        if not all(key in state for key in required_keys):
            return jsonify({'error': 'Missing required state keys: {}'.format(', '.join(required_keys))}), 400

        grammar_file_name = 'roleplay'
        grammar = initialize_grammar(grammar_file_name)
        if grammar is None:
            return jsonify({'error': 'Invalid grammar file'}), 400

        # response = None
        user = get_current_user()
        user_key = f"user:{user['username']}"
        selected_characters = redis_client.hgetall(user_key)
        character_info = None
        for character, info in selected_characters.items():
            character_info = json.loads(info.decode('utf-8'))
            break  # Assuming only one character is selected

        response_generator = generate_reply_HF(question, question, character_info, state)
        print(f"response_generator = {response_generator}")
        response = next(response_generator, "No response generated")
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
        return jsonify({'reply': response1}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)