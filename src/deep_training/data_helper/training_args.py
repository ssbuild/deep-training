# @Time    : 2022/11/17 22:18
# @Author  : tk
# @FileName: training_args.py
import os
from dataclasses import field, dataclass
from typing import Optional, Dict
from .base_args import _ArgumentsBase
from .ac_args import TrainingArgumentsAC
from .cl_args import TrainingArgumentsCL
from .hf_args import TrainingArgumentsHF
from .pl_agrs import TrainingArguments


__all__ = [
    'TrainingArguments',
    'TrainingArgumentsHF',
    'TrainingArgumentsCL',
    'TrainingArgumentsAC',
    'ModelArguments',
    'PrefixModelArguments',
    'DataArguments',
    'MlmDataArguments',
]



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
    processer_name: Optional[ str ] = field(
        default=None, metadata={"help": "Pretrained processer name  or path if not the same as model_name"}
    )
    imageprocesser_name: Optional[ str ] = field(
        default=None, metadata={"help": "Pretrained imageprocesser name or path if not the same as model_name"}
    )
    feature_extractor_name: Optional[ str ] = field(
        default=None, metadata={"help": "Pretrained feature_extractor name or path if not the same as model_name"}
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

    gradient_checkpointing: bool = field(
        default=False,
        metadata={
            "help": "If True, use gradient checkpointing to save memory at the expense of slower backward pass."
        },
    )
    gradient_checkpointing_kwargs: dict = field(
        default=None,
        metadata={
            "help": "Gradient checkpointing key word arguments such as `use_reentrant`. Will be passed to `torch.utils.checkpoint.checkpoint` through `model.gradient_checkpointing_enable`."
        },
    )

    model_custom: Optional[Dict] = field(
        default=None, metadata={"help": "自定义参数 for model args"})

    def __post_init__(self):
        if self.model_custom is None:
            self.model_custom = {}

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

    max_duration_in_seconds: float = field(
        default=20.0,
        metadata={
            "help": (
                "Truncate audio files that are longer than `max_duration_in_seconds` seconds to"
                " 'max_duration_in_seconds`"
            )
        },
    )
    min_duration_in_seconds: float = field(
        default=0.0, metadata={"help": "Filter audio files that are shorter than `min_duration_in_seconds` seconds"}
    )

    sampling_rate: int = field(
        default=None, metadata={"help": "audio files sampling_rate"}
    )

    data_custom: Optional[Dict] = field(
        default_factory=lambda: {}, metadata={"help": "自定义参数 for data args"})

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