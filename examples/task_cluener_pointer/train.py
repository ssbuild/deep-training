# -*- coding: utf-8 -*-
import json
import os
import sys
import typing

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)),'../..'))
from deep_training.data_helper import DataHelper
from typing import Union, List
import torch
import numpy as np
from pytorch_lightning.utilities.types import EPOCH_OUTPUT
from deep_training.model.nlp.layers.seq_pointer import f1_metric
from pytorch_lightning import Trainer
from deep_training.data_helper import make_all_dataset_with_args, load_all_dataset_with_args, \
    load_tokenizer_and_config_with_args

from deep_training.model.nlp.models.pointer import TransformerForPointer
from deep_training.model.nlp.metrics.pointer import metric_for_pointer
from transformers import HfArgumentParser, BertTokenizer
from deep_training.data_helper import ModelArguments, DataArguments, TrainingArguments



class NN_DataHelper(DataHelper):
    # 切分词
    def on_data_process(self, data: typing.Any, user_data: tuple):

        tokenizer: BertTokenizer
        tokenizer,max_seq_length,label2id,mode = user_data
        sentence,label_dict = data

        input_ids = tokenizer.convert_tokens_to_ids(list(sentence))
        if len(input_ids) > max_seq_length - 2:
            input_ids = input_ids[:max_seq_length - 2]
        input_ids = [tokenizer.cls_token_id] + input_ids + [tokenizer.sep_token_id]
        attention_mask = [1] * len(input_ids)

        input_ids = np.asarray(input_ids, dtype=np.int64)
        attention_mask = np.asarray(attention_mask, dtype=np.int64)
        seqlen = np.asarray(len(input_ids), dtype=np.int64)

        labels = np.zeros(shape=(len(label2id),max_seq_length,max_seq_length),dtype=np.int32)
        real_label = []
        for label_str, o in label_dict.items():
            pts = list(o.values())[0]
            labelid = label2id[label_str]
            for pt in pts:
                if pt[1] < max_seq_length:
                    labels[labelid, pt[0], pt[1]] = 1
                real_label.append((labelid, pt[0], pt[1]))

        pad_len = max_seq_length - len(input_ids)
        if pad_len > 0:
            pad_val = tokenizer.pad_token_id
            input_ids = np.pad(input_ids, (0, pad_len), 'constant', constant_values=(pad_val, pad_val))
            attention_mask = np.pad(attention_mask, (0, pad_len), 'constant', constant_values=(pad_val, pad_val))
        d = {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'labels': labels,
            'seqlen': seqlen,
        }
        if mode == 'eval':
            d['real_label'] = np.asarray(bytes(json.dumps(real_label,ensure_ascii=False),encoding='utf-8'))
        return d

    #读取标签
    @staticmethod
    def read_labels_from_file(label_fname: str):
        labels = [
            'address','book','company','game','government','movie','name','organization','position','scene'
        ]
        label2id = {label: i for i, label in enumerate(labels)}
        id2label = {i: label for i, label in enumerate(labels)}
        return label2id, id2label

    # 读取文件
    @staticmethod
    def read_data_from_file(files: typing.List,mode:str):
        D = []
        for filename in files:
            with open(filename, mode='r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    jd = json.loads(line)
                    if not jd:
                        continue
                    D.append((jd['text'], jd.get('label',None)))
        return D


    @staticmethod
    def collect_fn(batch):
        o = {}
        for i, b in enumerate(batch):
            if i == 0:
                for k in b:
                    o[k] = [torch.tensor(b[k])]
            else:
                for k in b:
                    o[k].append(torch.tensor(b[k]))
        for k in o:
            o[k] = torch.stack(o[k])

        seqlen = o.pop('seqlen')
        max_len = torch.max(seqlen)

        o['input_ids'] = o['input_ids'][:, :max_len]
        o['attention_mask'] = o['attention_mask'][:, :max_len]
        if 'token_type_ids' in o:
            o['token_type_ids'] = o['token_type_ids'][:, :max_len]

        o['labels'] = o['labels'][:,:, :max_len,:max_len]
        return o


class MyTransformer(TransformerForPointer):
    def __init__(self, *args,**kwargs):
        super(MyTransformer, self).__init__(with_efficient=True,*args,**kwargs)

    def validation_step(self, batch, batch_idx, dataloader_idx=0):
        labels: torch.Tensor = batch.pop('labels')
        real_label = batch.pop("real_label")
        outputs = self(**batch)
        val_loss, logits = outputs[:2]
        f1 = f1_metric(labels,logits)
        return {"losses": val_loss, "logits": logits.item(),"labels": real_label,'f1':f1}

    def validation_epoch_end(self, outputs: Union[EPOCH_OUTPUT, List[EPOCH_OUTPUT]]) -> None:
        id2label = self.config.id2label
        threshold = 1e-7
        preds,labels = [],[]
        for o in outputs:
            logits = o['logits']
            label = o['labels']
            for tag in logits:
                one_result = []
                for (l, s, e) in zip(*np.where(tag > threshold)):
                    one_result.append((l, s, e))
                preds.append(one_result)
            labels.append(label)
        m = metric_for_pointer(labels,preds,id2label)
        print(m)

    def test_step(self, batch, batch_idx):
        x, y = batch
        # implement your own
        out = self(x)
        return out



if __name__== '__main__':
    parser = HfArgumentParser((ModelArguments, TrainingArguments, DataArguments))
    if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
        model_args, training_args, data_args = parser.parse_json_file(json_file=os.path.abspath(sys.argv[1]))
    else:
        model_args, training_args, data_args = parser.parse_args_into_dataclasses()

    dataHelper = NN_DataHelper(data_args.data_backend)
    tokenizer, config, label2id, id2label = load_tokenizer_and_config_with_args(dataHelper, model_args, training_args,data_args)
    save_fn_args = (tokenizer, data_args.max_seq_length,label2id)


    N = 1
    train_files, eval_files, test_files = [], [], []
    for i in range(N):
        intermediate_name = data_args.intermediate_name + '_{}'.format(i)
        train_file, eval_file, test_file = make_all_dataset_with_args(dataHelper, save_fn_args, data_args,
                                                                      intermediate_name=intermediate_name,num_process_worker=0)
        train_files.append(train_file)
        eval_files.append(eval_file)
        test_files.append(test_file)


    dm = load_all_dataset_with_args(dataHelper, training_args, train_files, eval_files, test_files)

    dm.setup("fit")

    model = MyTransformer(config=config,model_args=model_args,training_args=training_args)
    trainer = Trainer(
        # callbacks=[progress_bar],
        max_epochs=training_args.max_epochs,
        max_steps=training_args.max_steps,
        accelerator="gpu",
        devices=data_args.devices,  # limiting got iPython runs
        enable_progress_bar=True,
        default_root_dir=data_args.output_dir,
        gradient_clip_val=training_args.max_grad_norm,
        accumulate_grad_batches = training_args.gradient_accumulation_steps
    )

    if data_args.do_train:
        trainer.fit(model, datamodule=dm)

    if data_args.do_eval:
        trainer.validate(model, datamodule=dm)

    if data_args.do_test:
        trainer.test(model, datamodule=dm)
