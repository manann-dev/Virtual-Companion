import base64
from pathlib import Path
from logging_colors import logger
import yaml
import shared
import json
from chat import generate_pfp_cache


def load_character(character, name1, name2):
    # context = greeting = ""
    # greeting_field = 'greeting'
    # picture = None

    filepath = None
    for extension in ["yml", "yaml", "json"]:
        filepath = Path(f'characters/{character}.{extension}')
        if filepath.exists():
            break

    if filepath is None or not filepath.exists():
        logger.error(f"Could not find the character \"{character}\" inside characters/. No character has been loaded.")
        raise ValueError

    file_contents = open(filepath, 'r', encoding='utf-8').read()
    data = json.loads(file_contents) if extension == "json" else yaml.safe_load(file_contents)
    cache_folder = Path(shared.args.disk_cache_dir)

    for path in [Path(f"{cache_folder}/pfp_character.png"), Path(f"{cache_folder}/pfp_character_thumb.png")]:
        if path.exists():
            path.unlink()

    picture = generate_pfp_cache(character)

    if picture:
        with open(picture, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    # Finding the bot's name
    for k in ['name', 'bot', '<|bot|>', 'char_name']:
        if k in data and data[k] != '':
            name2 = data[k]
            break

    # Find the user name (if any)
    for k in ['your_name', 'user', '<|user|>']:
        if k in data and data[k] != '':
            name1 = data[k]
            break

    if 'context' in data:
        context = data['context'].strip()
    elif "char_persona" in data:
        context = build_pygmalion_style_context(data)
        greeting_field = 'char_greeting'

    # greeting = data.get(greeting_field, greeting)
    greeting = data.get("greeting", "")
    context = data.get("context", "")
    logger.info(f"Loaded character \"{character}\".")
    character_info = {
        "name1": name1,
        "name2": name2,
        "encoded_string": encoded_string,
        "greeting": greeting,
        "context": context
    }

    return character_info