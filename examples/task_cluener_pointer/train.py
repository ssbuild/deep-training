# -*- coding: utf-8 -*-
import os
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)),'../..'))
import logging
from typing import Union, List
import torch
import numpy as np
from pytorch_lightning.utilities.types import EPOCH_OUTPUT
from deep_training.model.nlp.layers.seq_pointer import f1_metric
from pytorch_lightning import Trainer
from deep_training.data_helper.data_args_func import make_all_dataset_with_args, load_all_dataset_with_args, \
    load_tokenizer_and_config_with_args
from data_loader import NN_DataHelper as DataHelper

from deep_training.model.nlp.models.pointer import TransformerForPointer
from deep_training.model.nlp.metrics.pointer import metric_for_pointer
from transformers import HfArgumentParser
from deep_training.data_helper.training_args import ModelArguments, DataArguments, TrainingArguments


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

    dataHelper = DataHelper(data_args.data_backend)
    tokenizer, config, label2id, id2label = load_tokenizer_and_config_with_args(dataHelper, model_args, data_args,
                                                                                training_args)
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


    dm = load_all_dataset_with_args(dataHelper, data_args, train_files, eval_files, test_files)

    dm.setup("fit")

    model = MyTransformer(config=config,model_args=model_args,training_args=training_args)
    trainer = Trainer(
        # callbacks=[progress_bar],
        max_epochs=training_args.max_epochs,
        max_steps=training_args.max_steps,
        accelerator="gpu",
        devices=data_args.devices,  # limiting got iPython runs
        enable_progress_bar=True,
        default_root_dir=training_args.output_dir,
        gradient_clip_val=training_args.max_grad_norm,
        accumulate_grad_batches = training_args.gradient_accumulation_steps
    )

    if training_args.do_train:
        trainer.fit(model, datamodule=dm)

    if training_args.do_eval:
        trainer.validate(model, datamodule=dm)

    if training_args.do_test:
        trainer.test(model, datamodule=dm)
