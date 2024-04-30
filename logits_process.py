import math

import torch
from transformers.generation.logits_process import LogitsProcessor
from transformers.utils import add_start_docstrings

LOGITS_PROCESSOR_INPUTS_DOCSTRING = r"""
    Args:
        input_ids (`torch.LongTensor` of shape `(batch_size, sequence_length)`):
            Indices of input sequence tokens in the vocabulary. [What are input IDs?](../glossary#input-ids)
        scores (`torch.FloatTensor` of shape `(batch_size, config.vocab_size)`):
            Prediction scores of a language modeling head. These can be logits for each vocabulary when not using beam
            search or log softmax for each vocabulary token when using beam search

    Return:
        `torch.FloatTensor` of shape `(batch_size, config.vocab_size)`: The processed prediction scores.

"""


class GrammarConstrainedLogitsProcessor(LogitsProcessor):
    def __init__(self, grammar_constraint):
        self.last_size = None
        self.grammar_constraint = grammar_constraint
        self.batch_stacks = None

    def filter_logits(self, logits, device):

        acceptance = self.grammar_constraint.batch_filter_vocab(self.batch_stacks, device)

        logits[~acceptance] = -math.inf

    # TODO: batching
    def process_logits(self, input_ids, scores, parse_start_index=None):
  
        if self.batch_stacks is None:
            self.batch_stacks = [self.grammar_constraint.init_stacks() for _ in range(len(input_ids))]

        if self.last_size is None:
            prefix_to_parse = [
                single_input_ids[parse_start_index:] if parse_start_index is not None else []
                for single_input_ids in input_ids
            ]
            self.batch_stacks = [
                self.grammar_constraint.accept_token_ids(prefix, stack)
                for prefix, stack in zip(prefix_to_parse, self.batch_stacks)
            ]
        elif len(input_ids[0]) == self.last_size + 1:
            self.batch_stacks = [
                self.grammar_constraint.accept_token_id(single_input_ids[-1], stack)
                for single_input_ids, stack in zip(input_ids, self.batch_stacks)
            ]
        else:
            raise RuntimeError(
                "Input ID's length is inconsistent with the current state of "
                "the GrammarConstrainedLogitsProcessor. If you want to process "
                "another input sequence, please instantiate a new "
                "GrammarConstrainedLogitsProcessor."
            )

        self.filter_logits(scores, scores.device)

        self.last_size = len(input_ids[0])
        return scores

    @add_start_docstrings(LOGITS_PROCESSOR_INPUTS_DOCSTRING)
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        return self.process_logits(input_ids, scores)
