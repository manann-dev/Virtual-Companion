import time
from logging_colors import logger
from callbacks import (
    Iteratorize,
    Stream,
    _StopEverythingStoppingCriteria
)
import shared
from grammer_utils import initialize_grammar
from extensions import available_extensions


def generate_reply_HF(question, original_question, seed, state, stopping_strings=None, is_chat=False):
    t0 = time.time()
    t1 = None  # Initialize t1
    try:
        generate_params = {}
        for k in ['auto_max_new_tokens','custom_token_bans','ban_eos_token','eta_cutoff','epsilon_cutoff','max_new_tokens', 'temperature', 'temperature_last', 'dynamic_temperature', 'dynatemp_low', 'dynatemp_high', 'dynatemp_exponent', 'smoothing_factor', 'smoothing_curve', 'top_p', 'min_p', 'top_k', 'repetition_penalty', 'presence_penalty', 'frequency_penalty', 'repetition_penalty_range', 'typical_p', 'tfs', 'top_a', 'guidance_scale', 'penalty_alpha', 'mirostat_mode', 'mirostat_tau', 'mirostat_eta', 'do_sample', 'encoder_repetition_penalty', 'no_repeat_ngram_size']:
            if k in state:
                generate_params[k] = state[k]

        if isinstance(state['sampler_priority'], list) and len(state['sampler_priority']) > 0:
            generate_params['sampler_priority'] = state['sampler_priority']
        elif isinstance(state['sampler_priority'], str) and state['sampler_priority'].strip() != '':
            generate_params['sampler_priority'] = [x.strip() for x in state['sampler_priority'].replace('\n', ',').split(',') if x.strip()]

        if 'negative_prompt' in state and state['negative_prompt'] != '':
            generate_params['negative_prompt_ids'] = encode(state['negative_prompt'])
        else:
            logger.info("No negative_prompt found in the state; proceeding without it.")

        prompt_lookup_num_tokens = state.get('prompt_lookup_num_tokens', 0)
        if prompt_lookup_num_tokens > 0:
            generate_params['prompt_lookup_num_tokens'] = prompt_lookup_num_tokens

        for k in ['epsilon_cutoff', 'eta_cutoff']:
            if state[k] > 0:
                generate_params[k] = state[k] * 1e-4

        if state['ban_eos_token']:
            generate_params['suppress_tokens'] = [shared.tokenizer.eos_token_id]

        if state['custom_token_bans']:
            to_ban = [int(x) for x in state['custom_token_bans'].split(',')]
            if len(to_ban) > 0:
                if generate_params.get('suppress_tokens', None):
                    generate_params['suppress_tokens'] += to_ban
                else:
                    generate_params['suppress_tokens'] = to_ban

        generate_params.update({'use_cache': not shared.args.no_cache})
        if shared.args.deepspeed:
            generate_params.update({'synced_gpus': True})

        input_ids = encode(question, add_bos_token=state['add_bos_token'], truncation_length=get_max_prompt_length(state))
        print("input_ids length:",len(input_ids))
        if input_ids.numel() > 0:
            output = input_ids[0]
        else:
            raise ValueError("Encoded input_ids are empty")
        cuda = not any((shared.args.cpu, shared.args.deepspeed))
        if state['auto_max_new_tokens']:
            generate_params['max_new_tokens'] = state['truncation_length'] - input_ids.shape[-1]
        
        question, input_ids, inputs_embeds = apply_extensions('tokenizer', state, question, input_ids, None)
        original_input_ids = input_ids
        generate_params.update({'inputs': input_ids})
        if inputs_embeds is not None:
            generate_params.update({'inputs_embeds': inputs_embeds})

        if shared.tokenizer is not None:
            eos_token_ids = [shared.tokenizer.eos_token_id] if shared.tokenizer.eos_token_id is not None else []
        else:
            raise ValueError("Tokenizer has not been initialized.")
        generate_params['stopping_criteria'] = transformers.StoppingCriteriaList()
        generate_params['stopping_criteria'].append(_StopEverythingStoppingCriteria())

        processor = state.get('logits_processor', LogitsProcessorList([]))
        if not isinstance(processor, LogitsProcessorList):
            processor = LogitsProcessorList([processor])

        # if state['grammar_string'].strip() != '':
        #     grammar = initialize_grammar(state['grammar_string'])
        #     grammar_processor = GrammarConstrainedLogitsProcessor(grammar)
        #     processor.append(grammar_processor)
        grammar_file_name = state.get('grammar_file_name', 'None')
        grammar = initialize_grammar(grammar_file_name)

        if grammar is not None:
            grammar_processor = GrammarConstrainedLogitsProcessor(grammar)
            processor.append(grammar_processor)

        apply_extensions('logits_processor', processor, input_ids)
        generate_params['logits_processor'] = processor

        if shared.args.verbose:
            logger.info("GENERATE_PARAMS=")
            filtered_params = {key: value for key, value in generate_params.items() if not isinstance(value, torch.Tensor)}
            pprint.PrettyPrinter(indent=4, sort_dicts=False).pprint(filtered_params)
            print()

            logger.info("PROMPT=")
            print(decode(input_ids[0], skip_special_tokens=False))
            print()

        if shared.model.__class__.__name__ == 'LlamacppHF' and shared.args.streaming_llm:
            tmp = process_llamacpp_cache(shared.model.model, input_ids[-1].tolist(), shared.model.model._input_ids.tolist())
            shared.model.past_seq = torch.tensor(tmp)
            shared.model.save_cache()

        t1 = time.time()  # Set t1 when appropriate

        yield ''  # Existing code and continuation

    except Exception as e:
        traceback.print_exc()
        if t1 is None:
            t1 = time.time()  # Ensure t1 is set if not already
        print(f'Error occurred. Time until error: {(t1-t0):.2f} seconds')
        raise
    finally:
        if t1 is not None:  # Check if t1 is set before using it
            print(f'Generation completed. Time taken: {(t1-t0):.2f} seconds')