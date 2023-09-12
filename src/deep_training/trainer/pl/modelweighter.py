# -*- coding: utf-8 -*-
# @Author  : ssbuild
# @Time    : 2023/5/29 9:49
import os
import re
from typing import Union,Optional,List,Callable
from collections import OrderedDict
import torch
from torch import nn
from transformers import PreTrainedModel, HfArgumentParser, AutoConfig
from ...data_helper import ModelArguments, TrainingArguments, DataArguments
from ...nlp.models.petl.prompt import PromptLearningConfig, PromptModel,PromptArguments,get_prompt_model
from ...nlp.models.petl import PetlModel, PetlArguments, LoraConfig, AdaLoraConfig, IA3Config
from ...nlp.models.transformer_base import TransformerBase
from ...utils.save_checkpoint import save_checkpoint_to_hf_format

__all__ = [
    'ModelWeightMixin',
    'PetlModel',
    'LoraConfig',
    'AdaLoraConfig',
    'IA3Config',
    'PetlArguments',
    'AutoConfig',
    'PromptLearningConfig',
    'PromptModel',
    'PromptArguments',
    'get_prompt_model',
    'ModelArguments',
    'TrainingArguments',
    'DataArguments',
    'PreTrainedModel',
    'HfArgumentParser'
]

def default_peft_weight_preprocess(weight):
    w = OrderedDict()
    for k,v in weight.items():
        if k.startswith('base_model.model'):
            a = k.split('.')
            p = a[2]
            if p == "model":
                p += "_"
            a.insert(2,p)
            w['.'.join(a)] = v
        else:
            w[k] = v
    return w

class ModelWeightMixin:
    lora_args = None
    prompt_args = None
    def save_pretrained_merge_lora(self,sft_weight_path: str,llm_weight_only = True,max_shard_size="10GB"):
        assert os.path.exists(os.path.dirname(sft_weight_path))
        assert self.lora_args is not None and self.lora_args.with_lora
        lora_model: PetlModel = self.backbone
        model: nn.Module = lora_model.merge_and_unload()

        if llm_weight_only:
            model.model.save_pretrained(sft_weight_path,max_shard_size=max_shard_size)
        else:
            #torch.save(model.model.state_dict(), sft_weight_path)
            save_checkpoint_to_hf_format(self,sft_weight_path,max_shard_size=max_shard_size)
        return model

    # def save_pretrained_merge_lora_and_restore(self, sft_weight_path: str):
    #     assert os.path.exists(os.path.dirname(sft_weight_path))
    #     assert self.lora_args is not None and self.lora_args.with_lora
    #     lora_model: LoraModel = self.backbone
    #     lora_model.merge_adapter()
    #     # 保存hf权重，可用infer.py推理
    #     #torch.save(lora_model.model.model.state_dict(), weight_path_file)
    #     lora_model.model.model.save_pretrained(sft_weight_path)
    #     lora_model.unmerge_adapter()

    def load_sft_weight(self, sft_weight_path: str,
                        is_trainable=False,
                        strict=False,
                        adapter_name="default",
                        lora_config=None,
                        map_preprocess: Optional[Callable] = None):
        assert os.path.exists(sft_weight_path)
        if self.lora_args is not None and self.lora_args.with_lora:
            # 恢复权重
            lora_model: PetlModel = self.backbone
            lora_model.load_adapter(sft_weight_path,
                                    adapter_name=adapter_name,
                                    config=lora_config,
                                    is_trainable=is_trainable,
                                    strict=strict,
                                    map_preprocess=map_preprocess)

        elif self.prompt_args is not None and self.prompt_args.with_prompt:
            # 恢复权重
            lora_model: PromptModel = self.backbone
            lora_model.load_adapter(sft_weight_path,
                                    adapter_name=adapter_name,
                                    config=lora_config,
                                    is_trainable=is_trainable,
                                    strict=strict,
                                    map_preprocess=map_preprocess)
        else:
            weight_dict = torch.load(sft_weight_path)
            if map_preprocess is not None:
                weights_dict_new = map_preprocess(weight_dict)
            else:
                weights_dict_new = OrderedDict()
                valid_keys = ['module', 'state_dict']
                for k in valid_keys:
                    if k in weight_dict:
                        weight_dict = weight_dict[k]
                        break
                pl_model_prefix = 'transformer_base'
                is_pl_weight = pl_model_prefix in ','.join(list(weight_dict.keys()))
                base_model_prefix = self.backbone.base_model_prefix
                model_prefix = r'{}.{}'.format(pl_model_prefix, base_model_prefix)
                for k, v in weight_dict.items():
                    if is_pl_weight:
                        k = re.sub(r'_forward_module.', '', k)
                        #llm module
                        if k.startswith(model_prefix):
                            k = re.sub(r'{}.'.format(model_prefix), '', k)
                            k = model_prefix + '.' + k
                        #TransformerBase module
                        if not k.startswith(pl_model_prefix):
                            k = pl_model_prefix + '.' + k
                    else:
                        # hf module weight
                        k = model_prefix + '.' + k
                    weights_dict_new[k] = v

            # TransformerBase 可能有自定义模块
            self.load_state_dict(weights_dict_new, strict=strict)
            del weight_dict
            del weights_dict_new




    #保存模型权重，除了llm之外可能还有其他模块
    def save_sft_weight(self, sft_weight_path,
                        merge_lora_weight=False,
                        llm_weight_only = True,
                        max_shard_size="10GB"):
        if self.lora_args is not None and self.lora_args.with_lora:
            if merge_lora_weight:
                # lora 合并权重 转换 hf权重
                self.save_pretrained_merge_lora(sft_weight_path,
                                                llm_weight_only=llm_weight_only,
                                                max_shard_size=max_shard_size)
            else:
                if llm_weight_only:
                    self.backbone.save_pretrained(sft_weight_path)
                else:
                    self.backbone.model.save_pretrained(sft_weight_path)
        elif self.prompt_args is not None and self.prompt_args.with_prompt:
            if llm_weight_only:
                self.backbone.save_pretrained(sft_weight_path)
            else:
                self.backbone.model.save_pretrained(sft_weight_path)
        else:
            # 保存hf权重
            config = self.get_llm_model().config
            config.save_pretrained(os.path.dirname(sft_weight_path))
            #torch.save(self.state_dict(),sft_weight_path)
            if llm_weight_only:
                self.get_llm_model().save_pretrained(sft_weight_path, max_shard_size=max_shard_size)
            else:
                save_checkpoint_to_hf_format(self, sft_weight_path, max_shard_size=max_shard_size)


    #只保存llm hf 权重
    def save_llm_sft_weight(self, sft_weight_path, merge_lora_weight=False,
                            llm_weight_only = True,
                            max_shard_size="10GB"):

        self.save_sft_weight(sft_weight_path,
                             merge_lora_weight=merge_lora_weight,
                             llm_weight_only=llm_weight_only,
                             max_shard_size=max_shard_size)


