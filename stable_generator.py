import requests
import os
from time import sleep

api_key = os.getenv('api_key')

def generate_stable_image_from_text(text_input, num_images, negative_prompt, width, height, track_id, seed, self_attention):
    try:
        url = 'https://stablediffusionapi.com/api/v4/dreambooth'



        payload = {
            "key": api_key,
            "model_id": "anything-v4",
            "prompt": text_input,
            "negative_prompt": negative_prompt,
            # "negative_prompt": "mini, (( son )), (( daughter )), (( shota )), little, years old, (( teen )) (( loli )), (( young )), (( adolescent )), painting, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, deformed, ugly, blurry, bad anatomy, bad proportions, extra limbs, cloned face, skinny, glitchy, double torso, extra arms, extra hands, mangled fingers, missing lips, ugly face, distorted face, extra legs, anime",
            "width": str(width),
            "height": str(height),
            "samples": str(num_images),
            "num_inference_steps": "30",
            "safety_checker": "no",
            "enhance_prompt": "yes",
            "seed": seed,
            "guidance_scale": 7.5,
            "multi_lingual": "no",
            "panorama": "panorama",
            "self_attention": self_attention,
            "upscale": "upscale",
            "embeddings_model": None,
            "lora_model": None,
            "tomesd": "yes",
            "use_karras_sigmas": "yes",
            "vae": None,
            "lora_strength": None,
            "scheduler": "UniPCMultistepScheduler",
            "webhook": "https://fec7-2001-1970-5f5e-2a00-5d9e-4425-cfa4-c424.ngrok-free.app/webhook",
            "track_id": track_id

        }
        return url, payload
    except requests.RequestException as e:
        import os, sys
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_tb.tb_lineno)

        print("Error:", e)

    return None
