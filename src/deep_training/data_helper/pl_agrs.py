# -*- coding: utf-8 -*-
# @Author  : ssbuild
# @Time    : 2023/10/9 10:29
import os
from dataclasses import dataclass, field
from typing import Optional
from transformers.utils import logging
from .base_args import _ArgumentsBase

logger = logging.get_logger(__name__)  # pylint: disable=invalid-name


@dataclass
class TrainingArguments(_ArgumentsBase):

    optimizer: str = field(
        default='adamw',
        metadata={"help": "one of lamb,adam,adamw_hf,adamw,adamw_torch,adamw_torch_fused,adamw_torch_xla,adamw_apex_fused,"
                          "adafactor,adamw_anyprecision,sgd,adagrad,adamw_bnb_8bit,adamw_8bit,lion,lion_8bit,lion_32bit,"
                          "paged_adamw_32bit,paged_adamw_8bit,paged_lion_32bit,paged_lion_8bit,"
                          "lamb_fused_dp adagrad_cpu_dp adam_cpu_dp adam_fused_dp"},
    )
    optimizer_args: Optional[str] = field(default=None,metadata={"help": "sample a=100,b=10 "})
    scheduler_type: str = field(
        default='linear',
        metadata={"help": "one of [linear,WarmupCosine,CAWR,CAL,Step,ReduceLROnPlateau, "
                          "cosine,cosine_with_restarts,polynomial,constant,constant_with_warmup,inverse_sqrt,reduce_lr_on_plateau]"},
    )

    scheduler: dict = field(
        default=None,
        # {
        #     # StepLR
        #     "decay_rate": 0.999,
        #     "decay_steps": 100,
        # }

        # {
        #     # CosineAnnealingWarmRestarts
        #     "T_mult": 1,
        #     "rewarm_epoch_num": 2,
        # }
        metadata={"help": "StepLR:  { 'decay_rate': 0.999,'decay_steps': 100,'verbose': True} ,\
                          CAWR {'T_mult': 1, 'rewarm_epoch_num': 2,'verbose': True} ,\
                          CAL: {'rewarm_epoch_num': 2,'verbose': True} \
                          "},
    )
    adv: dict = field(
        # default_factory= lambda: {
        #     'mode': None, # None, fgm, fgsm_local, fgsm, pgd, free_local, free
        #     'emb_name=': 'embedding',
        #     'attack_iters': 2, # pgd
        #     'minibatch_replays': 2, # free
        #     'alpha': 0.1, # pgd
        #     'epsilon': 1.0 # pgd,fgm
        # },
        default=None,
        metadata={"help": "对抗训练"},
    )
    hierarchical_position: float = field(
        default=None,
        metadata={"help": "层次分解位置编码，让transformer可以处理超长文本 , 绝对位置编码有效 , None禁用 , 0 - 1 启用 "},
    )

    learning_rate : float = field(
        default=5e-5,
        metadata={"help": "模型任务层训练时的学习率"},
    )
    learning_rate_for_task: float = field(
        default=None,
        metadata={"help": "模型任务层训练时的学习率"},
    )
    max_epochs: int = field(
        default=-1,
        metadata={"help": "模型训练的轮数"},
    )
    max_steps: int = field(
        default=-1,
        metadata={"help": "max_steps"},
    )
    optimizer_betas : tuple = field (
        default=(0.9, 0.999),
        metadata={"help": "优化器的betas值"},
    )
    adam_epsilon: float = field(
        default=1e-8,
        metadata={"help": "Adam优化器的epsilon值"},
    )
    gradient_accumulation_steps: int = field(
        default=1,
        metadata={"help": "gradient_accumulation_steps"},
    )
    max_grad_norm: float = field(
        default=1.0,
        metadata={"help": "max_grad_norm"},
    )
    weight_decay: float = field(
        default=0,
        metadata={"help": "weight_decay"},
    )

    warmup_steps: float = field(
        default=0,
        metadata={"help": "warmup_steps"},
    )

    train_batch_size: int = field(
        default=16,
        metadata={"help": "train_batch_size"},
    )

    eval_batch_size: int = field(
        default=1,
        metadata={"help": "eval_batch_size"},
    )

    test_batch_size: int = field(
        default=1,
        metadata={"help": "test_batch_size"},
    )
    seed: Optional[float] = field(
        default=42,
        metadata={"help": "seed"},
    )
    dataloader_drop_last: bool = field(
        default=False, metadata={"help": "Drop the last incomplete batch if it is not divisible by the batch size."}
    )
    dataloader_num_workers: int = field(
        default=0,
        metadata={
            "help": (
                "Number of subprocesses to use for data loading (PyTorch only). 0 means that the data will be loaded"
                " in the main process."
            )
        },
    )
    dataloader_pin_memory: bool = field(
        default=True, metadata={"help": "Whether or not to pin memory for DataLoader."}
    )

    torch_compile: bool = field(
        default=False, metadata={"help": "If set to `True`, the model will be wrapped in `torch.compile`."}
    )
    torch_compile_backend: Optional[str] = field(
        default=None,
        metadata={
            "help": "Which backend to use with `torch.compile`, passing one will trigger a model compilation.",
        },
    )
    torch_compile_mode: Optional[str] = field(
        default=None,
        metadata={
            "help": "Which mode to use with `torch.compile`, passing one will trigger a model compilation.",
        },
    )
    def __post_init__(self):
        if self.learning_rate_for_task is None:
            self.learning_rate_for_task = self.learning_rate

        if self.seed is not None:
            from lightning_fabric.utilities.seed import seed_everything
            seed_everything(int(self.seed))


        assert self.hierarchical_position is None or (self.hierarchical_position >0 and self.hierarchical_position <1)

@dataclass
class ModelArguments(_ArgumentsBase):
    """
    Arguments pertaining to which model/config/tokenizer we are going to fine-tune, or train from scratch.
    """

    model_name_or_path: Optional[str] = field(
        default=None,
        metadata={
            "help": (
                "The model checkpoint for weights initialization.Don't set if you want to train a model from scratch."
            )
        },
    )
    model_type: Optional[str] = field(
        default=None,
        metadata={"help": "If training from scratch"},
    )
    config_overrides: Optional[str] = field(
        default=None,
        metadata={
            "help": (
                "Override some existing default config settings when a model is trained from scratch. Example: "
                "n_embd=10,resid_pdrop=0.2,scale_attn_weights=false,summary_type=cls_index"
            )
        },
    )
    config_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained config name or path if not the same as model_name"}
    )
    tokenizer_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained tokenizer name or path if not the same as model_name"}
    )
    cache_dir: Optional[str] = field(
        default=None,
        metadata={"help": "Where do you want to store the pretrained models downloaded from huggingface.co"},
    )
    do_lower_case: bool = field(
        default=None,
        metadata={"help": "Whether to lower case the input text. Should be True for uncased deep_training and False for cased deep_training."},
    )
    use_fast_tokenizer: bool = field(
        default=None,
        metadata={"help": "Whether to use one of the fast tokenizer (backed by the tokenizers library) or not."},
    )
    model_revision: str = field(
        default="main",
        metadata={"help": "The specific model version to use (can be a branch name, tag name or commit id)."},
    )
    use_auth_token: bool = field(
        default=False,
        metadata={
            "help": (
                "Will use the token generated when running `transformers-cli login` (necessary to use this script "
                "with private models)."
            )
        },
    )

    def __post_init__(self):
        if self.config_overrides is not None and (self.config_name is not None or self.model_name_or_path is not None):
            raise ValueError(
                "--config_overrides can't be used in combination with --config_name or --model_name_or_path"
            )


@dataclass
class PrefixModelArguments(_ArgumentsBase):
    # prompt参数
    prompt_type: int = field(
        default=0,
        metadata={
            "help": "0 : prefix model , 1 prompt model"
        }
    )

    prefix_projection: bool = field(
        default=False,
        metadata={
            "help": "prefix_projection"
        }
    )
    prefix_hidden_size: int = field(
        default=512,
        metadata={
            "help": "The hidden size of the MLP projection head in Prefix Encoder if prefix projection is used'"
        }
    )
    pre_seq_len: int = field(
        default=16,
        metadata={
            "help": "The length of prompt"
        }
    )



@dataclass
class DataArguments(_ArgumentsBase):
    """
    Arguments pertaining to what data we are going to input our model for training and eval.
    """
    devices: Optional[int] = field(
        default="1",metadata={
            "help": "device str"
        }
    )
    convert_onnx: Optional[bool] =  field(
        default=False, metadata={"help": "是否转换onnx"}
    )
    data_backend: Optional[str] = field(
        default=None, metadata={"help": "record,leveldb,lmdb,memory,memory_raw"}
    )
    convert_file: Optional[bool] = field(
        default=True, metadata={"help": "是否需要转换语料到record记录"}
    )
    train_file: Optional = field(
        default_factory=lambda: [], metadata={"help": "训练语料list"}
    )
    eval_file: Optional = field(
        default_factory=lambda: [], metadata={"help": "评估语料list"}
    )
    test_file: Optional = field(
        default_factory=lambda: [],metadata={"help": "测试语料list"}
    )
    label_file: Optional = field(
        default_factory=lambda: [], metadata={"help": "标签文件list"}
    )
    intermediate_name: Optional[str] = field(
        default='dataset', metadata={"help": "dataset文件名前缀"}
    )
    output_dir: Optional[str] = field(
        default='./output', metadata={"help": "模型输出路径"}
    )
    overwrite_cache: bool = field(
        default=False, metadata={"help": "Overwrite the cached training and evaluation sets"}
    )

    train_max_seq_length: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "The maximum total input sequence length after tokenization. Sequences longer "
                "than this will be truncated. Default to the max input length of the model."
            )
        },
    )
    eval_max_seq_length: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "The maximum total input sequence length after tokenization. Sequences longer "
                "than this will be truncated. Default to the max input length of the model."
            )
        },
    )
    test_max_seq_length: Optional[int] = field(
        default=None,
        metadata={
            "help": (
                "The maximum total input sequence length after tokenization. Sequences longer "
                "than this will be truncated. Default to the max input length of the model."
            )
        },
    )
    max_seq_length: Optional[int] = field(
        default=512,
        metadata={
            "help": (
                "The maximum total input sequence length after tokenization. Sequences longer "
                "than this will be truncated. Default to the max input length of the model."
            )
        },
    )
    max_target_length: Optional[int] = field(
        default=64,
        metadata={
            "help": (
                "语言生成标题的最大长度 "
            )
        },
    )
    do_train: bool = field(
        default=False, metadata={"help": "是否训练"}
    )
    do_eval: bool = field(
        default=False, metadata={"help": "是否评估"}
    )
    do_test: bool = field(
        default=False, metadata={"help": "是否测试"}
    )

    def __post_init__(self):

        if not self.train_file:
            self.do_train = False

        if not self.eval_file:
            self.do_eval = False

        if not self.test_file:
            self.do_test = False

        if self.convert_onnx:
            self.do_train = False
            self.do_eval = False
            self.do_test = False



        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)

        if self.train_max_seq_length is None:
            self.train_max_seq_length = self.max_seq_length
        if self.eval_max_seq_length is None:
            self.eval_max_seq_length = self.max_seq_length
        if self.test_max_seq_length is None:
            self.test_max_seq_length = self.max_seq_length

@dataclass
class MlmDataArguments(_ArgumentsBase):
    do_whole_word_mask: bool = field(
        default=True,
        metadata={
            "help": "Whether to use whole word masking rather than per-WordPiece masking."
        }
    )
    max_predictions_per_seq: int = field(
        default=20,
        metadata={
            "help": "Maximum number of masked LM predictions per sequence."
        }
    )
    masked_lm_prob: float = field(
        default=0.15,
        metadata={
            "help": "Masked LM probability."
        }
    )
    dupe_factor: int = field(
        default=5,
        metadata={
            "help": "Number of times to duplicate the input data (with different masks)."
        }
    )
