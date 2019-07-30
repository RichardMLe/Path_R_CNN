#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 12 14:57:57 2018

@author: wenyuan
"""
import os
import sys
sys.path.append(os.path.dirname(os.getcwd()))
import model as modellib

import prostate
import numpy as np

# Root directory of the project
ROOT_DIR = os.path.dirname(os.getcwd())

# Path to trained weights file
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")

# Directory to save logs and model checkpoints, if not provided
# through the command line argument --logs
DEFAULT_LOGS_DIR = os.path.join(ROOT_DIR, "logs")
DEFAULT_DATASET_PATH = "/data/wenyuan/Path_R_CNN/Data_Pre_Processing/cedars-224"
## local dataset_dir
# DEFAULT_DATASET_PATH = "/Users/wenyuan/Documents/MII/Mask-RCNN/Data_Pre_Processing/cedars-224"

############################################################
#  Prostate Evaluation
############################################################
## create prostate evaluation metrics here

############################################################
#  Training
############################################################


if __name__ == '__main__':
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Train Mask R-CNN on ProstateDataset.')
    parser.add_argument("command",
                        metavar="<command>",
                        default='train',
                        help="'train' or 'evaluate' on ProstateDataset")
    parser.add_argument('--model', required=True,
                        metavar="/path/to/weights.h5",
                        help="Path to weights .h5 file or 'coco'")
    parser.add_argument('--held_out_set', required=False,
                        default=4,
                        metavar="<held_out_dataset>",
                        help='held out dataset index from 0 to 4, default=4')
    parser.add_argument('--mode', required=False,
                        default=16,
                        metavar="<mode for the data importing>",
                        help='which mode is used to import data, default=16',
                        type=int)
    parser.add_argument('--dataset', required=False,
                        default=DEFAULT_DATASET_PATH,
                        metavar="/path/to/coco/",
                        help='Directory of the Prostate dataset')
    parser.add_argument('--logs', required=False,
                        default=DEFAULT_LOGS_DIR,
                        metavar="/path/to/logs/",
                        help='Logs and checkpoints directory (default=logs/)')
    parser.add_argument('--limit', required=False,
                        default=500,
                        metavar="<image count>",
                        help='Images to use for evaluation (default=500)')
    args = parser.parse_args()
    print("Command: ", args.command)
    print("Model: ", args.model)
    print("Dataset: ", args.dataset)
    print("Logs: ", args.logs)

    # Configurations
    if args.command == "train":
        mean_pixel = prostate.Mean_pixel(args.dataset, int(args.held_out_set))
        class TrainConfig(prostate.ProstateConfig):
            MEAN_PIXEL = np.array(mean_pixel)
        config = TrainConfig()
    else:
        class InferenceConfig(prostate.ProstateConfig):
            # Set batch size to 1 since we'll be running inference on
            # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
            GPU_COUNT = 1
            IMAGES_PER_GPU = 1
            DETECTION_MIN_CONFIDENCE = 0
        config = InferenceConfig()
    config.display()

    # Create model
    if args.command == "train":
        model = modellib.MaskRCNN(mode="training", config=config,
                                  model_dir=args.logs)
    else:
        model = modellib.MaskRCNN(mode="inference", config=config,
                                  model_dir=args.logs)

    # Select weights file to load
    if args.model.lower() == "coco":
        model_path = COCO_MODEL_PATH
    elif args.model.lower() == "last":
        # Find last trained weights
        model_path = model.find_last()[1]
    elif args.model.lower() == "imagenet":
        # Start from ImageNet trained weights
        model_path = model.get_imagenet_weights()
    else:
        model_path = args.model

    # Load weights
    exclude = ["mrcnn_class_logits", "mrcnn_bbox_fc", 
               "mrcnn_bbox", "mrcnn_mask"]
    # if train from scratch
    with open("structure_file.txt") as txtfile:
        lines = [line.strip() for line in txtfile]
    exclude = lines
    ###########################################
    # Add tumor head as exclude
    ###########################################
    if config.USE_TUMORCLASS:
        tumor_head = ["tumor_class_conv1", "tumor_class_bn1", "tumor_class_conv2",
                     "tumor_class_conv2", "tumor_class_bn2", "tumor_class_dense",
                     "tumor_class_dropout", "tumor_class_logits", "tumor_class"]
        exclude = exclude + tumor_head
    
    print("Loading weights ", model_path)
    model.load_weights(model_path, by_name=True, exclude=exclude)

    # Train or evaluate
    if args.command == "train":
        # Training dataset. Use the training set and 35K from the
        # validation set, as as in the Mask RCNN paper.
        dataset_train = prostate.ProstateDataset()
        train_list, val_list = dataset_train.generator_patition(args.dataset, 
                                                                int(args.held_out_set))

        dataset_train.load_prostate(args.dataset, train_list, mode = args.mode)
        dataset_train.prepare()

        # Validation dataset
        dataset_val = prostate.ProstateDataset()
        dataset_val.load_prostate(args.dataset, val_list, mode = args.mode)
        dataset_val.prepare()

        # *** This training schedule is an example. Update to your needs ***
        print("Training the whole network!")
# =============================================================================
#         model.train(dataset_train, dataset_val,
#                      learning_rate=config.LEARNING_RATE,
#                      epochs= 70,
#                      layers='all')
# =============================================================================
        
#        model.train(dataset_train, dataset_val,
#             learning_rate=config.LEARNING_RATE / 10,
#             epochs= 75,
#             layers='all')
        #此处与keras自带函数类似，将输入与输出处理成了input和output，但其中内容不同。
        #input[batch_images, batch_image_meta, batch_rpn_match, batch_rpn_bbox,batch_gt_class_ids, batch_gt_boxes, batch_gt_masks,batch_rpn_rois(可能有）,batch_rois(可能有)]
        #output[batch_mrcnn_class_ids, batch_mrcnn_bbox, batch_mrcnn_mask]
        model.train(dataset_train, dataset_val,
             learning_rate=config.LEARNING_RATE / 100,
             epochs= 120,
             layers='all')

=============================================================================
        # Training - Stage 1
        print("Training network heads")
        model.train(dataset_train, dataset_val,
                    learning_rate=config.LEARNING_RATE,
                    epochs=25,
                    layers='heads')

        # Training - Stage 2
        # Finetune layers from ResNet stage 4 and up
        print("Fine tune Resnet stage 4 and up")
        model.train(dataset_train, dataset_val,
                    learning_rate=config.LEARNING_RATE,
                    epochs=40,
                    layers='4+')

        model.train(dataset_train, dataset_val,
                    learning_rate=config.LEARNING_RATE / 10,
                    epochs=55,
                    layers='4+')

        # Training - Stage 3
        # Fine tune all layers
        print("Fine tune Resnet stage 3 and up")
        model.train(dataset_train, dataset_val,
                    learning_rate=config.LEARNING_RATE / 100,
                    epochs=70,
                    layers='3+')
=============================================================================

    elif args.command == "evaluate":
        print("Running Prostate evaluation on images.")
        # todo: evaluate_coco(model, dataset_val, coco, "bbox", limit=int(args.limit))
    else:
        print("'{}' is not recognized. "
              "Use 'train' or 'evaluate'".format(args.command))
