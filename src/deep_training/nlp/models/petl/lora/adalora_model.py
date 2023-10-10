# -*- coding: utf-8 -*-
# @Time:  10:45
# @Author: tk
# @File：adalora_model
import re
import warnings
import torch
from transformers import Conv1D
from ....layers.petl.lora.layer import mark_only_lora_as_trainable, is_bnb_available, LoraLayer, is_bnb_4bit_available
from ....layers.petl.adalora.layer import RankAllocator, SVDLinear,  AdaLoraLayer
from ....layers.petl.utils import _freeze_adapter, _get_submodules, \
    TRANSFORMERS_MODELS_TO_ADALORA_TARGET_MODULES_MAPPING, prepare_model_for_kbit_training, get_quantization_config, \
    get_auto_gptq_quant_linear
from .lora_model import LoraModule,LoraConfig

__all__ = [
    'is_bnb_available',
    'AdaLoraModule'
]

from ....layers.petl.adalora.gptq import SVDQuantLinear

if is_bnb_available():
    import bitsandbytes as bnb
    from ....layers.petl.adalora.bnb import SVDLinear8bitLt
if is_bnb_4bit_available():
    from ....layers.petl.adalora.bnb import SVDLinear4bit

class AdaLoraModule(LoraModule):
    """
    Creates AdaLoRA (Adaptive LoRA) model from a pretrained transformers model. Paper:
    https://openreview.net/pdf?id=lq62uWRJjiY

    Args:
        model ([`transformers.PreTrainedModel`]): The model to be adapted.
        config ([`AdaLoraConfig`]): The configuration of the AdaLora model.

    Returns:
        `torch.nn.Module`: The AdaLora model.


    **Attributes**:
        - **model** ([`transformers.PreTrainedModel`]) -- The model to be adapted.
        - **petl_config** ([`AdaLoraConfig`]): The configuration of the AdaLora model.
    """

    def __init__(self, model, config, adapter_name,
                 auto_prepare_kbit_training=True,
                 use_input_require_grads=True,
                 use_gradient_checkpointing=True
                 ):
        super().__init__(model, config, adapter_name,
                         auto_prepare_kbit_training=auto_prepare_kbit_training,
                         use_input_require_grads=use_input_require_grads,
                         use_gradient_checkpointing=use_gradient_checkpointing)
        traininable_mode_counter = 0
        for config in self.petl_config.values():
            if not config.inference_mode:
                traininable_mode_counter += 1

        if traininable_mode_counter > 1:
            raise ValueError(
                "AdaLoraModel supports only 1 trainable adapter. "
                "When using multiple adapters, set inference_mode to True for all adapters except the one you want to train."
            )

        if self.petl_config[adapter_name].inference_mode:
            _freeze_adapter(self.model, adapter_name)
        else:
            self.trainable_adapter_name = adapter_name
            self.rankallocator = RankAllocator(self.model, self.petl_config[adapter_name], self.trainable_adapter_name)

    def _check_new_adapter_config(self, config: LoraConfig) -> None:
        """
        A helper method to check the config when a new adapter is being added.

        Raise a ValueError if there is something wrong with the config or if it conflicts with existing adapters.

        """
        super()._check_new_adapter_config(config)

        traininable_mode_counter = 0
        for config_ in self.petl_config.values():
            if not config_.inference_mode:
                traininable_mode_counter += 1

        if traininable_mode_counter > 1:
            raise ValueError(
                f"{self.__class__.__name__} supports only 1 trainable adapter. "
                "When using multiple adapters, set inference_mode to True for all adapters except the one "
                "you want to train."
            )

    def _create_and_replace(
            self,
            lora_config,
            adapter_name,
            target,
            target_name,
            parent,
            **optional_kwargs,
    ):
        loaded_in_8bit = optional_kwargs.get("loaded_in_8bit", False)
        loaded_in_4bit = optional_kwargs.get("loaded_in_4bit", False)
        if (loaded_in_8bit or loaded_in_4bit) and not is_bnb_available():
            raise ImportError(
                "To use Lora with 8-bit quantization, please install the `bitsandbytes` package. "
                "You can install it with `pip install bitsandbytes`."
            )
        kwargs = {
            "r": lora_config.init_r,
            "lora_alpha": lora_config.lora_alpha,
            "lora_dropout": lora_config.lora_dropout,
            "fan_in_fan_out": lora_config.fan_in_fan_out,
            "init_lora_weights": lora_config.init_lora_weights,
            "loaded_in_8bit": loaded_in_8bit,
            "loaded_in_4bit": loaded_in_4bit,
        }

        quantization_config = get_quantization_config(self.model, method="gptq")
        if quantization_config is not None:
            kwargs["gptq_quantization_config"] = quantization_config

        # If it is not a LoraLayer, create a new module, else update it with new adapters
        if not isinstance(target, AdaLoraLayer):
            new_module = self._create_new_module(lora_config, adapter_name, target, **kwargs)
            if adapter_name != self.active_adapter:
                # adding an additional adapter: it is not automatically trainable
                new_module.requires_grad_(False)
            self._replace_module(parent, target_name, new_module, target)
        else:
            target.update_layer(
                adapter_name,
                lora_config.init_r,
                lora_config.lora_alpha,
                lora_config.lora_dropout,
                lora_config.init_lora_weights,
            )

    @staticmethod
    def _create_new_module(lora_config, adapter_name, target, **kwargs):
        gptq_quantization_config = kwargs.get("gptq_quantization_config", None)
        AutoGPTQQuantLinear = get_auto_gptq_quant_linear(gptq_quantization_config)

        bias = target.bias is not None
        loaded_in_8bit = kwargs.pop("loaded_in_8bit", False)
        loaded_in_4bit = kwargs.pop("loaded_in_4bit", False)

        if loaded_in_8bit and isinstance(target, bnb.nn.Linear8bitLt):
            kwargs.update(
                {
                    "has_fp16_weights": target.state.has_fp16_weights,
                    "memory_efficient_backward": target.state.memory_efficient_backward,
                    "threshold": target.state.threshold,
                    "index": target.index,
                }
            )
            new_module = SVDLinear8bitLt(adapter_name, target.in_features, target.out_features, bias=bias, **kwargs)
        elif loaded_in_4bit and is_bnb_4bit_available() and isinstance(target, bnb.nn.Linear4bit):
            fourbit_kwargs = kwargs.copy()
            fourbit_kwargs.update(
                {
                    "compute_dtype": target.compute_dtype,
                    "compress_statistics": target.weight.compress_statistics,
                    "quant_type": target.weight.quant_type,
                }
            )
            new_module = SVDLinear4bit(
                adapter_name, target.in_features, target.out_features, bias=bias, **fourbit_kwargs
            )
        elif AutoGPTQQuantLinear is not None and isinstance(target, AutoGPTQQuantLinear):
            new_module = SVDQuantLinear(adapter_name, target, **kwargs)
            target.weight = target.qweight
        else:
            if isinstance(target, torch.nn.Linear):
                in_features, out_features = target.in_features, target.out_features
                if kwargs["fan_in_fan_out"]:
                    warnings.warn(
                        "fan_in_fan_out is set to True but the target module is `torch.nn.Linear`. "
                        "Setting fan_in_fan_out to False."
                    )
                    kwargs["fan_in_fan_out"] = lora_config.fan_in_fan_out = False
            elif isinstance(target, Conv1D):
                in_features, out_features = (
                    target.weight.ds_shape if hasattr(target.weight, "ds_shape") else target.weight.shape
                )
                if not kwargs["fan_in_fan_out"]:
                    warnings.warn(
                        "fan_in_fan_out is set to False but the target module is `Conv1D`. "
                        "Setting fan_in_fan_out to True."
                    )
                    kwargs["fan_in_fan_out"] = lora_config.fan_in_fan_out = True
            else:
                raise ValueError(
                    f"Target module {target} is not supported. "
                    f"Currently, only `torch.nn.Linear` and `Conv1D` are supported."
                )
            new_module = SVDLinear(adapter_name, in_features, out_features, bias=bias, **kwargs)

        return new_module

    @staticmethod
    def _prepare_adapter_config(petl_config, model_config):
        if petl_config.target_modules is None:
            if model_config["model_type"] not in TRANSFORMERS_MODELS_TO_ADALORA_TARGET_MODULES_MAPPING:
                raise ValueError("Please specify `target_modules` in `petl_config`")
            petl_config.target_modules = TRANSFORMERS_MODELS_TO_ADALORA_TARGET_MODULES_MAPPING[
                model_config["model_type"]
            ]
        return petl_config

    def __getattr__(self, name: str):
        """Forward missing attributes to the wrapped module."""
        try:
            return super().__getattr__(name)  # defer to nn.Module's logic
        except AttributeError:
            if hasattr(self.model, name):
                return getattr(self.model, name)
            return getattr(self.model.model, name)
    def forward(self, *args, **kwargs):
        outputs = self.model.forward(*args, **kwargs)

        if getattr(outputs, "loss", None) is not None:
            # Calculate the orthogonal regularization
            orth_reg_weight = self.petl_config[self.trainable_adapter_name].orth_reg_weight

            if orth_reg_weight <= 0:
                raise ValueError("orth_reg_weight should be greater than 0. ")

            regu_loss = 0
            num_param = 0
            for n, p in self.model.named_parameters():
                if ("lora_A" in n or "lora_B" in n) and self.trainable_adapter_name in n:
                    para_cov = p @ p.T if "lora_A" in n else p.T @ p
                    I = torch.eye(*para_cov.size(), out=torch.empty_like(para_cov))
                    I.requires_grad = False
                    num_param += 1
                    regu_loss += torch.norm(para_cov - I, p="fro")
            if num_param > 0:
                regu_loss = regu_loss / num_param
            else:
                regu_loss = 0
            outputs.loss += orth_reg_weight * regu_loss
        return outputs

    def resize_modules_by_rank_pattern(self, rank_pattern, adapter_name):
        lora_config = self.petl_config[adapter_name]
        for name, rank_idx in rank_pattern.items():
            if isinstance(rank_idx, list):
                rank = sum(rank_idx)
            elif isinstance(rank_idx, torch.Tensor):
                rank_idx = rank_idx.view(-1)
                rank = rank_idx.sum().item()
            else:
                raise ValueError("Unexcepted type of rank_idx")
            key = ".".join(name.split(".")[0:-2]) if adapter_name in name else ".".join(name.split(".")[0:-1])
            _, target, _ = _get_submodules(self.model, key)
            lora_E_weights = target.lora_E[adapter_name][rank_idx]
            lora_A_weights = target.lora_A[adapter_name][rank_idx]
            lora_B_weights = target.lora_B[adapter_name][:, rank_idx]
            ranknum = target.ranknum[adapter_name]
            target.update_layer(
                adapter_name,
                rank,
                lora_config.lora_alpha,
                lora_config.lora_dropout,
                lora_config.init_lora_weights,
            )
            with torch.no_grad():
                if rank > 0:
                    target.lora_E[adapter_name].copy_(lora_E_weights)
                    target.lora_A[adapter_name].copy_(lora_A_weights)
                    target.lora_B[adapter_name].copy_(lora_B_weights)
                    # The scaling is exactly as the previous
                    target.ranknum[adapter_name].copy_(ranknum)

    def resize_state_dict_by_rank_pattern(self, rank_pattern, state_dict, adapter_name):
        for name, rank_idx in rank_pattern.items():
            rank = sum(rank_idx)
            prefix = ".".join(name.split(".")[0:-2]) if adapter_name in name else ".".join(name.split(".")[0:-1])
            for layer in ["lora_E", "lora_A", "lora_B"]:
                key = f"base_model.model.{prefix}.{layer}.{adapter_name}"
                if layer != "lora_B":
                    state_dict[key] = (
                        state_dict[key][rank_idx] if rank != state_dict[key].shape[0] else state_dict[key]
                    )
                else:
                    state_dict[key] = (
                        state_dict[key][:, rank_idx] if rank != state_dict[key].shape[1] else state_dict[key]
                    )
        return state_dict

    def update_and_allocate(self, global_step):
        lora_config = self.petl_config[self.trainable_adapter_name]
        # Update the importance score and allocate the budget
        if global_step < lora_config.total_step - lora_config.tfinal:
            _, rank_pattern = self.rankallocator.update_and_allocate(self.model, global_step)
            if rank_pattern:
                lora_config.rank_pattern = rank_pattern
        # Finalize the budget allocation
        elif global_step == lora_config.total_step - lora_config.tfinal:
            _, rank_pattern = self.rankallocator.update_and_allocate(self.model, global_step, force_mask=True)
            # for some reason, this freezes the trainable parameters and nothing gets updates
            # self.resize_modules_by_rank_pattern(rank_pattern, self.trainable_adapter_name)
            lora_config.rank_pattern = rank_pattern
            self.rankallocator.reset_ipt()
        # Currently using inefficient way to mask the unimportant weights using the rank pattern
        #  due to problem mentioned above
        elif global_step > lora_config.total_step - lora_config.tfinal:
            self.rankallocator.mask_using_rank_pattern(self.model, lora_config.rank_pattern)
        # Pass the function and do forward propagation
        else:
            return None