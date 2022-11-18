# -*- coding: utf-8 -*-
import json
import os
import sys

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)),'../..'))
import typing
import numpy as np
from deep_training.data_helper import DataHelper
import torch
from pytorch_lightning import Trainer
from deep_training.data_helper import make_all_dataset_with_args, load_all_dataset_with_args, \
    load_tokenizer_and_config_with_args
from deep_training.model.nlp.models.hphtlinker import TransformerForHphtlinker
from transformers import HfArgumentParser, BertTokenizer
from deep_training.data_helper import ModelArguments, TrainingArguments, DataArguments


class NN_DataHelper(DataHelper):
    # 切分词
    def on_data_process(self, data: typing.Any, user_data: tuple):

        tokenizer: BertTokenizer
        tokenizer,max_seq_length,predicate2id,mode = user_data
        sentence,entities,re_list = data
        spo_list = re_list
        tokens = list(sentence)

        if len(tokens) > max_seq_length - 2:
            tokens = tokens[0:(max_seq_length - 2)]
        input_ids = tokenizer.convert_tokens_to_ids(['CLS'] +tokens + ['SEP'] )
        seqlen = len(input_ids)
        attention_mask = [1] * seqlen

        input_ids = np.asarray(input_ids, dtype = np.int64)
        attention_mask = np.asarray(attention_mask, dtype=np.int64)


        spoes = {}
        for s, p, o in spo_list:
            if s[1] < max_seq_length - 2 and o[1] < max_seq_length - 2:
                s = (s[0], s[1])
                o = (o[0], o[1], predicate2id[p])
                if s not in spoes:
                    spoes[s] = []
                spoes[s].append(o)

        subject_labels = np.zeros((max_seq_length, 2),dtype=np.float32)
        subject_ids = np.zeros((2,),dtype=np.int64)
        object_labels = np.zeros((max_seq_length, len(predicate2id), 2),dtype=np.float32)
        if spoes:
            for s in spoes:
                subject_labels[s[0], 0] = 1
                subject_labels[s[1], 1] = 1
            # 随机选一个subject（这里没有实现错误！这就是想要的效果！！）
            start, end = np.array(list(spoes.keys())).T
            start = np.random.choice(start)
            end = np.random.choice(end[end >= start])
            #subject_ids = (start, end)
            subject_ids[0] = start
            subject_ids[1] = end

            for o in spoes.get((start,end), []):
                object_labels[o[0], o[2], 0] = 1
                object_labels[o[1], o[2], 1] = 1
        pad_len = max_seq_length - seqlen
        if pad_len > 0:
            pad_val = tokenizer.pad_token_id
            input_ids = np.pad(input_ids, (0, pad_len), 'constant', constant_values=(pad_val, pad_val))
            attention_mask = np.pad(attention_mask, (0, pad_len), 'constant', constant_values=(pad_val, pad_val))
        d = {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'subject_labels': subject_labels,
            'subject_ids':subject_ids,
            'object_labels': object_labels,
            'seqlen': seqlen
        }
        return d

    #读取标签
    @staticmethod
    def read_labels_from_file(files: typing.List):
        labels = []
        label_filename = files[0]
        with open(label_filename,mode='r',encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                jd = json.loads(line)
                if not jd:
                    continue
                larr = [jd['subject'],jd['predicate'],jd['object']]
                labels.append('+'.join(larr))
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

                    entities = jd.get('entities', None)
                    re_list = jd.get('re_list', None)


                    if entities:
                        entities_label = []
                        for k,v in entities.items():
                            pts = list(v.values())[0]
                            for pt in pts:
                                entities_label.append((k,pt[0],pt[1]))
                    else:
                        entities_label = None

                    if re_list is not None:
                        re_list_label = []
                        for re_node in re_list:
                            for l,relation in re_node.items():
                                s = relation[0]
                                o = relation[1]
                                re_list_label.append((
                                    # (s['pos'][0], s['pos'][1],s['label']),
                                    # l,
                                    # (o['pos'][0], o['pos'][1],o['label'])
                                    (s['pos'][0], s['pos'][1]),
                                    '+'.join([s['label'],l,o['label']]),
                                    (o['pos'][0], o['pos'][1])
                                ))
                    else:
                        re_list_label = None


                    D.append((jd['text'],entities_label, re_list_label))
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

        o['subject_labels'] = o['subject_labels'][:, :max_len]
        # o['subject_ids'] = o['subject_ids']
        o['object_labels'] = o['object_labels'][:, :max_len]

        return o




class MyTransformer(TransformerForHphtlinker):
    def __init__(self, *args,**kwargs):
        super(MyTransformer, self).__init__(with_efficient=True,*args,**kwargs)


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
