import asyncio
import websockets
import torch
from load__model import load_model 
from logging_colors import logger
from generate_reply_hf import generate_reply_HF

model, tokenizer = load_model('facebook_opt-1.3b')
logger.info("Loaded model and tokenizer.", model=model, tokenizer=tokenizer)



