import gc
import logging
import os
import pprint
import re
import time
import traceback
from models_settings import get_model_metadata
import shared
from logging_colors import logger
import transformers
from transformers import (
    AutoConfig,
    AutoModel,
    AutoModelForCausalLM,
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    GPTQConfig
)
import time
import torch
from accelerate import infer_auto_device_map, init_empty_weights
from accelerate.utils import is_ccl_available, is_xpu_available
from pathlib import Path
import sampler_hijack


transformers.logging.set_verbosity_error()

local_rank = None
if shared.args.deepspeed:
    import deepspeed
    from transformers.deepspeed import (
        HfDeepSpeedConfig,
        is_deepspeed_zero3_enabled
    )

    from deepspeed_parameters import generate_ds_config

    # Distributed setup
    local_rank = shared.args.local_rank if shared.args.local_rank is not None else int(os.getenv("LOCAL_RANK", "0"))
    world_size = int(os.getenv("WORLD_SIZE", "1"))
    if is_xpu_available() and is_ccl_available():
        torch.xpu.set_device(local_rank)
        deepspeed.init_distributed(backend="ccl")
    else:
        torch.cuda.set_device(local_rank)
        deepspeed.init_distributed()
    ds_config = generate_ds_config(shared.args.bf16, 1 * world_size, shared.args.nvme_offload_dir)
    dschf = HfDeepSpeedConfig(ds_config)  # Keep this object alive for the Transformers integration

sampler_hijack.hijack_samplers()


def load_model(model_name, loader=None):
    logger.info(f"Loading \"{model_name}\"")
    t0 = time.time()

    shared.is_seq2seq = False
    shared.model_name = model_name
    load_func_map = {
        'Transformers': huggingface_loader
        # 'AutoGPTQ': AutoGPTQ_loader,
        # 'GPTQ-for-LLaMa': GPTQ_loader,
        # 'llama.cpp': llamacpp_loader,
        # 'llamacpp_HF': llamacpp_HF_loader,
        # 'ExLlamav2': ExLlamav2_loader,
        # 'ExLlamav2_HF': ExLlamav2_HF_loader,
        # 'AutoAWQ': AutoAWQ_loader,
        # 'QuIP#': QuipSharp_loader,
        # 'HQQ': HQQ_loader,
    }

    metadata = get_model_metadata(model_name)
    if loader is None:
        if shared.args.loader is not None:
            loader = shared.args.loader
        else:
            loader = metadata['loader']
            if loader is None:
                logger.error('The path to the model does not exist. Exiting.')
                raise ValueError

    shared.args.loader = loader
    output = load_func_map[loader](model_name)
    if type(output) is tuple:
        model, tokenizer = output
    else:
        model = output
        if model is None:
            return None, None
        else:
            tokenizer = load_tokenizer(model_name)

    shared.settings.update({k: v for k, v in metadata.items() if k in shared.settings})
    if loader.lower().startswith('exllama'):
        shared.settings['truncation_length'] = shared.args.max_seq_len
    elif loader in ['llama.cpp', 'llamacpp_HF']:
        shared.settings['truncation_length'] = shared.args.n_ctx

    logger.info(f"LOADER: \"{loader}\"")
    logger.info(f"TRUNCATION LENGTH: {shared.settings['truncation_length']}")
    logger.info(f"INSTRUCTION TEMPLATE: \"{metadata['instruction_template']}\"")
    logger.info(f"Loaded the model in {(time.time()-t0):.2f} seconds.")
    return model, tokenizer


from config import tokenizer

def load_tokenizer(model_name='facebook/opt-1.3b'):
    global tokenizer
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        print("Tokenizer loaded successfully.")
        return tokenizer
    except Exception as e:
        print(f"Error loading tokenizer: {e}")
        return None

def get_tokenizer():
    global tokenizer
    if tokenizer is None:
        print("Tokenizer not loaded, attempting to load...")
        load_tokenizer()
    return tokenizer


def huggingface_loader(model_name):
    path_to_model = Path(f'{shared.args.model_dir}/{model_name}')
    params = {
        'low_cpu_mem_usage': True,
        'torch_dtype': torch.bfloat16 if shared.args.bf16 else torch.float16,
    }

    if shared.args.trust_remote_code:
        params['trust_remote_code'] = True

    if shared.args.use_flash_attention_2:
        params['use_flash_attention_2'] = True

    if shared.args.force_safetensors:
        params['force_safetensors'] = True

    config = AutoConfig.from_pretrained(path_to_model, trust_remote_code=shared.args.trust_remote_code)

    if 'chatglm' in model_name.lower():
        LoaderClass = AutoModel
    else:
        if config.to_dict().get('is_encoder_decoder', False):
            LoaderClass = AutoModelForSeq2SeqLM
            shared.is_seq2seq = True
        else:
            LoaderClass = AutoModelForCausalLM

    # Load the model without any special settings
    if not any([shared.args.cpu, shared.args.load_in_8bit, shared.args.load_in_4bit, shared.args.auto_devices, shared.args.disk, shared.args.deepspeed, shared.args.gpu_memory is not None, shared.args.cpu_memory is not None, shared.args.compress_pos_emb > 1, shared.args.alpha_value > 1, shared.args.disable_exllama, shared.args.disable_exllamav2]):
        logger.info("TRANSFORMERS_PARAMS=")
        pprint.PrettyPrinter(indent=4, sort_dicts=False).pprint(params)
        print()

        model = LoaderClass.from_pretrained(path_to_model, **params)
        if not (hasattr(model, 'is_loaded_in_4bit') and model.is_loaded_in_4bit):
            if torch.backends.mps.is_available():
                device = torch.device('mps')
                model = model.to(device)
            elif is_xpu_available():
                device = torch.device("xpu")
                model = model.to(device)
            else:
                model = model.cuda()

    # DeepSpeed ZeRO-3
    elif shared.args.deepspeed:
        model = LoaderClass.from_pretrained(path_to_model, torch_dtype=params['torch_dtype'], trust_remote_code=params['trust_remote_code'])
        model = deepspeed.initialize(model=model, config_params=ds_config, model_parameters=None, optimizer=None, lr_scheduler=None)[0]
        model.module.eval()  # Inference
        logger.info(f'DeepSpeed ZeRO-3 is enabled: {is_deepspeed_zero3_enabled()}')

    # Load with quantization and/or offloading
    else:
        if not any((shared.args.cpu, torch.cuda.is_available(), is_xpu_available(), torch.backends.mps.is_available())):
            logger.warning('torch.cuda.is_available() and is_xpu_available() returned False. This means that no GPU has been detected. Falling back to CPU mode.')
            shared.args.cpu = True

        if shared.args.cpu:
            params['torch_dtype'] = torch.float32
        else:
            params['device_map'] = 'auto'
            if x := get_max_memory_dict():
                params['max_memory'] = x

            if shared.args.load_in_4bit:
                # See https://github.com/huggingface/transformers/pull/23479/files
                # and https://huggingface.co/blog/4bit-transformers-bitsandbytes
                quantization_config_params = {
                    'load_in_4bit': True,
                    'bnb_4bit_compute_dtype': eval("torch.{}".format(shared.args.compute_dtype)) if shared.args.compute_dtype in ["bfloat16", "float16", "float32"] else None,
                    'bnb_4bit_quant_type': shared.args.quant_type,
                    'bnb_4bit_use_double_quant': shared.args.use_double_quant,
                }

                params['quantization_config'] = BitsAndBytesConfig(**quantization_config_params)

            elif shared.args.load_in_8bit:
                if any((shared.args.auto_devices, shared.args.gpu_memory)):
                    params['quantization_config'] = BitsAndBytesConfig(load_in_8bit=True, llm_int8_enable_fp32_cpu_offload=True)
                else:
                    params['quantization_config'] = BitsAndBytesConfig(load_in_8bit=True)

                if params['max_memory'] is not None:
                    with init_empty_weights():
                        model = LoaderClass.from_config(config, trust_remote_code=params['trust_remote_code'])

                    model.tie_weights()
                    params['device_map'] = infer_auto_device_map(
                        model,
                        dtype=torch.int8,
                        max_memory=params['max_memory'],
                        no_split_module_classes=model._no_split_modules
                    )

            if shared.args.disk:
                params['offload_folder'] = shared.args.disk_cache_dir

        if shared.args.disable_exllama or shared.args.disable_exllamav2:
            try:
                gptq_config = GPTQConfig(
                    bits=config.quantization_config.get('bits', 4),
                    disable_exllama=shared.args.disable_exllama,
                    disable_exllamav2=shared.args.disable_exllamav2,
                )

                params['quantization_config'] = gptq_config
                logger.info(f'Loading with disable_exllama={shared.args.disable_exllama} and disable_exllamav2={shared.args.disable_exllamav2}.')
            except:
                exc = traceback.format_exc()
                logger.error('Failed to disable exllama. Does the config.json for this model contain the necessary quantization info?')
                print(exc)

        if shared.args.compress_pos_emb > 1:
            params['rope_scaling'] = {'type': 'linear', 'factor': shared.args.compress_pos_emb}
        elif shared.args.alpha_value > 1:
            params['rope_scaling'] = {'type': 'dynamic', 'factor': RoPE.get_alpha_value(shared.args.alpha_value, shared.args.rope_freq_base)}

        logger.info("TRANSFORMERS_PARAMS=")
        pprint.PrettyPrinter(indent=4, sort_dicts=False).pprint(params)
        print()
        model = LoaderClass.from_pretrained(path_to_model, **params)

    return model

def clear_torch_cache():
    gc.collect()
    if not shared.args.cpu:
        if is_xpu_available():
            torch.xpu.empty_cache()
        else:
            torch.cuda.empty_cache()