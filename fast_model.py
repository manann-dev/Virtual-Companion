import transformers
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import torch.nn.functional as F
from models import load_model
from fastapi import FastAPI, Depends, APIRouter, Form, WebSocket, WebSocketDisconnect
import asyncio
import jwt
import redis
import json
import yaml
import base64
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt
from redis__db import create_user, authenticate_user, get_user, update_user, delete_user, get_user_character, set_user_character
from auth import get_current_user
from characters import load_character
from starlette.middleware.sessions import SessionMiddleware
import jinja2
from jinja2 import Environment, FileSystemLoader
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from starlette.status import HTTP_200_OK
from text_generation import generate_reply_HF
from grammer_utils import initialize_grammar
import websockets

async def create_websocket_object():
    uri = "ws://127.0.0.1:9696/ws" 
    try:
        websocket = await websockets.connect(uri)
        return websocket
    except Exception as e:
        print("Failed to connect to WebSocket server:", e)
        raise



redis_client = redis.Redis(
    host='redis-16428.c330.asia-south1-1.gce.redns.redis-cloud.com',
    port=16428,
    password='hftcJafy6dKQ1gQYkxCfCqGeYhsQWmHe')

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

templates = Jinja2Templates(directory="templates")



app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
router = APIRouter()

connected_clients = []

@app.on_event("startup")
async def load_model():
    ModelSingleton.get_instance()

def get_model_singleton():
    return ModelSingleton.get_instance()

@app.post("/users/")
def create_user_api(user: UserCreate):
    try:
        create_user(user.username, user.password)
        return {"message": "User created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username
    password = form_data.password

    user = authenticate_user(username, password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {
        "username": user["username"], 
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token, "token_type": "bearer"}


@app.get("/protected")
async def protected_route(user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {user['username']}! This is a protected route."}


@app.post("/select_character")
async def handle_character_selection(request: Request, user: dict = Depends(get_current_user)):
    form_data = await request.form()
    character = form_data.get("character")
    if character:
        try:
            character_info = load_character(character, user["username"], "Bot")
            user_key = f"user:{user['username']}"
            redis_client.hset(user_key, character, json.dumps(character_info))
            return {"message": f"Character '{character}' selected successfully!"}
        except Exception as e:
            return {"error": str(e)}
    else:
        return {"error": "No character selected"}


@app.get("/select_character", response_class=HTMLResponse)
async def select_character(request: Request, user: dict = Depends(get_current_user)):
    user_key = f"user:{user['username']}"
    selected_characters = redis_client.hgetall(user_key)
    characters = [json.loads(character_info) for character_info in selected_characters.values()]
    return templates.TemplateResponse("select_character.html", {"request": request, "username": user["username"], "characters": characters})


@app.post("/chat_with_character")
async def chat_with_character(question: str = Form(...), user: dict = Depends(get_current_user)):
    user_key = f"user:{user['username']}"
    print(user_key)
    character_state = redis_client.hget(user_key, 'state') 
    print(character_state)
    if not character_info:
        raise HTTPException(status_code=404, detail="Character not selected or found.")
    
    character_data = json.loads(character_info)
    preset_name = character_data.get('preset_name', '') 

    state = load_preset(preset_name)

    try:
        response = generate_reply_HF(question, question, None, state)
        return {"character_response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept the WebSocket connection
    await websocket.accept()

    # Add the new client to the list
    connected_clients.append(websocket)

    try:
        # Get the JWT token from the WebSocket headers or query parameters
        token = websocket.query_params.get("token") or websocket.headers.get("Authorization")

        # Continuously receive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            await handle_message(data, websocket, token)

    except WebSocketDisconnect:
        # Remove the disconnected client from the list
        connected_clients.remove(websocket)


async def run(user_input, history, websocket):

        request = {
            'user_input': user_input,
            'max_new_tokens': 250,
            'auto_max_new_tokens': False,
            'history': history,
            'mode': 'instruct',  # Valid options: 'chat', 'chat-instruct', 'instruct'
            'character': 'Example',
            'instruction_template': 'Vicuna-v1.1',  # Will get autodetected if unset
            'your_name': 'You',
        }

        # Send the request as JSON
        await websocket.send(json.dumps(request))

        # Receive the response
        response = await websocket.recv()
        result = json.loads(response)

        # Process the result
        print(json.dumps(result, indent=4))
        print()
        print(result['visible'][-1][1])


async def handle_message(message: str, websocket: WebSocket, token: str = None):
    if token is None:
        return await websocket.send_text("Authentication required")

    try:
        # Get the current user and character information
        user = await get_current_user(token)
        character_info = await get_user_character(user["username"])

        # Parse the incoming request
        request = json.loads(message)

        # Initialize the grammar and generate the reply
        grammar = initialize_grammar(character_info["c"])
        state = character_info["state"]
        response_generator = generate_reply_HF(request['user_input'], request['user_input'], None, state, grammar=grammar)
        reply = next(response_generator)

        # Construct the response
        response = {
            'results': [
                {
                    'history': {
                        'internal': [],
                        'visible': [
                            [request['user_input'], reply]
                        ]
                    }
                }
            ]
        }

        # Broadcast the response to the client
        await websocket.send_text(json.dumps(response))
    except Exception as e:
        print(f"Error: {e}")
        await websocket.send_text(f"Error: {e}")

async def main():
    user_input = "Please give me a step-by-step guide on how to plant a tree in my backyard."
    history = {'internal': [], 'visible': []}
    websocket = await create_websocket_object()
    await run(user_input, history, websocket)

if __name__ == '__main__':
    asyncio.run(main())