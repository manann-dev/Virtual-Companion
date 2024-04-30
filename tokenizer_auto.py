from transformers import AutoTokenizer
import shared

def initialize_shared_components(model_name='facebook/opt-1.3b'):  # Replace with your model
    global shared
    shared.tokenizer = AutoTokenizer.from_pretrained(model_name)
    print("Tokenizer initialized:", shared.tokenizer is not None)  # This should print True
