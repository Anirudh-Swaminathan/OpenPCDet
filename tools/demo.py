import argparse
import glob
from pathlib import Path

# import mayavi.mlab as mlab
import numpy as np
import torch

from pcdet.config import cfg, cfg_from_yaml_file
from pcdet.datasets import DatasetTemplate
from pcdet.models import build_network, load_data_to_gpu
from pcdet.utils import common_utils
# from visual_utils import visualize_utils as V

# CSV tools
import csv

class DemoDataset(DatasetTemplate):
    def __init__(self, dataset_cfg, class_names, training=True, root_path=None, logger=None, ext='.bin'):
        """
        Args:
            root_path:
            dataset_cfg:
            class_names:
            training:
            logger:
        """
        super().__init__(
            dataset_cfg=dataset_cfg, class_names=class_names, training=training, root_path=root_path, logger=logger
        )
        self.root_path = root_path
        self.ext = ext
        data_file_list = glob.glob(str(root_path / f'*{self.ext}')) if self.root_path.is_dir() else [self.root_path]

        data_file_list.sort()
        self.sample_file_list = data_file_list

    def __len__(self):
        return len(self.sample_file_list)

    def __getitem__(self, index):
        if self.ext == '.bin':
            points = np.fromfile(self.sample_file_list[index], dtype=np.float32).reshape(-1, 4)
        elif self.ext == '.npy':
            points = np.load(self.sample_file_list[index])
        else:
            raise NotImplementedError

        input_dict = {
            'points': points,
            'frame_id': index,
        }

        data_dict = self.prepare_data(data_dict=input_dict)
        return data_dict


def parse_config():
    parser = argparse.ArgumentParser(description='arg parser')
    parser.add_argument('--cfg_file', type=str, default='cfgs/kitti_models/second.yaml',
                        help='specify the config for demo')
    # parser.add_argument('--data_path', type=str, default='demo_data',
    #                     help='specify the point cloud data file or directory')
    parser.add_argument('--data_root', type=str, default='demo_data', help='specify the root of calib, velodyne and image files')
    parser.add_argument('--file_number', type=str, default='000008', help='specify file number to detect objects for')
    parser.add_argument('--ckpt', type=str, default=None, help='specify the pretrained model')
    parser.add_argument('--ext', type=str, default='.bin', help='specify the extension of your point cloud data file')
    # parser.add_argument('--ext')
    parser.add_argument('--res', type=str, default="../results/3dod/vis/", help="specify the results folder of the detection result")

    args = parser.parse_args()

    cfg_from_yaml_file(args.cfg_file, cfg)

    return args, cfg


def main():
    print("Starting main()")
    args, cfg = parse_config()
    logger = common_utils.create_logger()
    logger.info('-----------------Quick Demo of OpenPCDet-------------------------')
    # add data path that is required by the config
    data_path = args.data_root + "velodyne/" + args.file_number + ".bin"
    # build image path from given command line arguments
    img_path = args.data_root + "image_2/" + args.file_number + ".png"
    # build the calibration file path from given command line arguments
    calib_path = args.data_root + "calib/" + args.file_number + ".txt"
    # build the result file path from given command line arguments
    # this is just to save one particular image to file
    res_img = args.res + args.file_number + ".png"
    # this is to save all detections from a particular sequence to file
    res_seq = args.res + "seq_" + args.file_number + ".csv"
    print("data_path: {}".format(data_path))
    print("img_path: {}".format(img_path))
    print("calib_path: {}".format(calib_path))
    demo_dataset = DemoDataset(
        dataset_cfg=cfg.DATA_CONFIG, class_names=cfg.CLASS_NAMES, training=False,
        # root_path=Path(args.data_path), ext=args.ext, logger=logger
        root_path = Path(data_path), ext=args.ext, logger=logger
    )
    logger.info(f'Total number of samples: \t{len(demo_dataset)}')

    model = build_network(model_cfg=cfg.MODEL, num_class=len(cfg.CLASS_NAMES), dataset=demo_dataset)
    model.load_params_from_file(filename=args.ckpt, logger=logger, to_cpu=True)
    model.cuda()
    model.eval()
    with torch.no_grad():
        for idx, data_dict in enumerate(demo_dataset):
            logger.info(f'Visualized sample index: \t{idx + 1}')
            data_dict = demo_dataset.collate_batch([data_dict])
            load_data_to_gpu(data_dict)
            pred_dicts, _ = model.forward(data_dict)

            # V.draw_scenes(
            #     points=data_dict['points'][:, 1:], ref_boxes=pred_dicts[0]['pred_boxes'],
            #     ref_scores=pred_dicts[0]['pred_scores'], ref_labels=pred_dicts[0]['pred_labels']
            # )
            # mlab.show(stop=True)
            print(pred_dicts)
            # list of dictionaries - append to results text file
            len_preds = len(pred_dicts)
            assert(len_preds == 1)
            l0 = pred_dicts[0]
            assert(type(l0) == dict)
            l0_pbox = l0['pred_boxes']
            print(l0_pbox.shape)
            l0_pscore = l0['pred_scores']
            print(l0_pscore.shape)
            l0_plab = l0['pred_labels']
            print(l0_plab.shape)
            with open(res_seq, "w") as f:
                wr = csv.writer(f, delimiter=' ')
                for i in range(l0_pbox.shape[0]):
                    wr.writerow([idx] + [l0_plab[i].item()] + [0] * 4 + [l0_pscore[i].item()] + list(l0_pbox[i][3:6].data.tolist()) + list(l0_pbox[i][0:3].data.tolist()) + list(l0_pbox[i][6:].data.tolist()) + [0])

    logger.info('Demo done.')


if __name__ == '__main__':
    main()

