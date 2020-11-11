# This file is generated from object_detection/dataset.md automatically through:
#    d2lbook build lib
# Don't edit it directly

#@save_all
#@hide_all
import pathlib
import pandas as pd
import random
from matplotlib import pyplot as plt
import dataclasses
import collections
import PIL
from typing import Union, Tuple, Callable, List, Any, Optional
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET  # type: ignore
import logging

from d8 import base_dataset


@dataclasses.dataclass
class BBox:
    file_path: str
    class_name: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def project_bbox(self):
        self.xmin = max(0, self.xmin)
        self.ymin = max(0, self.ymin)
        self.xmax = min(1.0, self.xmax)
        self.ymax = min(1.0, self.ymax)

    def is_bbox_valid(self) -> bool:
        if not (0 <= self.xmin <= 1 and 0 <= self.ymin <= 1 and
                self.xmin <= self.xmax <= 1 and self.ymin <= self.ymax <= 1):
            return False
        return True

def parse_voc_annotation(xml_fp) -> List[BBox]:
    root = ET.parse(xml_fp).getroot()
    get_text = lambda node: '' if node is None else node.text.strip()
    file_path = get_text(root.find('filename'))
    size = get_text(root.find('size'))
    width = float(get_text(size.find('width')))
    height = float(get_text(size.find('height')))
    labels = []
    for obj in root.iter('object'):
        class_name = get_text(obj.find('name')).lower()
        xml_box = get_text(obj.find('bndbox'))
        xmin = float(get_text(xml_box.find('xmin'))) / width
        ymin = float(get_text(xml_box.find('ymin'))) / height
        xmax = float(get_text(xml_box.find('xmax'))) / width
        ymax = float(get_text(xml_box.find('ymax'))) / height
        label = BBox(file_path, class_name, xmin, ymin, xmax, ymax)
        label.project_bbox()
        if not label.is_bbox_valid():
            logging.warning(f'Invalid bounding box {label}')
        else:
            labels.append(label)
    return labels


def _parse_voc(reader, image_dir, annotation_dir):
    entries = []
    annotation_dir = str(pathlib.Path(annotation_dir))
    image_dir = str(pathlib.Path(image_dir))
    # don't use .is_relative_to as it requires python >= 3.9
    xmls = [xml for xml in reader.list_files(['.xml'], [annotation_dir])]
    imgs = set([img for img in reader.list_images([image_dir])])
    for xml in xmls:
        labels = parse_voc_annotation(reader.open(xml))
        if labels:
            image_path = pathlib.Path(image_dir)/labels[0].file_path
            if image_path not in imgs:
                logging.warning(f'Not found image {limage_path}')
            else:
                for l in labels: l.file_path = str(image_path)
                entries.extend(labels)
    return pd.DataFrame(entries)

class Dataset(base_dataset.ClassificationDataset):
    TYPE = 'object_detection'

    def show(self, layout=(2,4)) -> None:
        """Show several random examples with their labels.

        :param layout: A tuple of (number of rows, number of columns).
        """
        nrows, ncols = layout
        max_width=500
        scale = 10 / ncols
        figsize = (ncols * scale, nrows * scale)
        _, axes = plt.subplots(nrows, ncols, figsize=figsize)
        random.seed(0)
        samples = random.sample(list(self.df.groupby('file_path')), nrows*ncols)
        colors = ['b', 'g', 'r', 'm', 'c']
        class_to_color = {c:colors[i%len(colors)] for i, c in enumerate(self.classes)}
        for ax, sample in zip(axes.flatten(), samples):
            img = self.reader.read_image(sample[0], max_width=max_width)
            ax.imshow(img, aspect='auto')
            img_width, img_height = img.size
            ax.axis("off")
            for _, row in sample[1].iterrows():
                bbox = plt.Rectangle(
                    xy=(row['xmin']*img_width, row['ymin']*img_height),
                    width=(row['xmax']-row['xmin'])*img_width,
                    height=(row['ymax']-row['ymin'])*img_height,
                    fill=False, edgecolor=class_to_color[row['class_name']], linewidth=2)
                ax.add_patch(bbox)
                ax.text(bbox.xy[0], bbox.xy[1], row['class_name'],
                      va='center', ha='center', fontsize=7, color='w',
                      bbox=dict(facecolor=class_to_color[row['class_name']],
                                lw=0, alpha=1, pad=2))

    def summary(self):
        """Returns a summary about this dataset."""
        path = self._get_summary_path()
        if path and path.exists(): return pd.read_pickle(path)
        get_mean_std = lambda col: f'{col.mean():.1f} ± {col.std():.1f}'
        img_df = self.reader.get_image_info(self.df['file_path'].unique())
        merged_df = pd.merge(self.df, img_df, on='file_path')
        summary = pd.DataFrame([{'# images':len(img_df),
                                 '# bboxes':len(self.df),
                                 '# bboxes / image':get_mean_std(self.df.groupby('file_path')['file_path'].count()),
                                 '# classes':len(self.classes),
                                 'image width':get_mean_std(img_df['width']),
                                 'image height':get_mean_std(img_df['height']),
                                 'bbox width':get_mean_std((merged_df['xmax']-merged_df['xmin'])*merged_df['width']),
                                 'bbox height':get_mean_std((merged_df['ymax']-merged_df['ymin'])*merged_df['height']),
                                 'size (GB)':img_df['size (KB)'].sum()/2**20}])
        if path and path.parent.exists(): summary.to_pickle(path)
        return summary

    @classmethod
    def from_voc(cls, data_path: str,
                 image_folders: str, annotation_folders: str):
        """Create a dataset when data are stored in the VOC format.

        :param data_path: Either a URL or a local path. For the former, data will be downloaded automatically.
        :param folders: The folders containing all example images.
        :return: The created dataset.
        """
        listify = lambda x: x if isinstance(x, (tuple, list)) else [x]

        def get_df_func(image_folders, annotation_folders):
            def df_func(reader):
                dfs = []
                for image_folder, annotation_folder in zip(image_folders, annotation_folders):
                    dfs.append(_parse_voc(reader, image_folder, annotation_folder))
                return pd.concat(dfs, axis=0)
            return df_func
        return cls.from_df_func(data_path, get_df_func(listify(image_folders), listify(annotation_folders)))

    @classmethod
    def summary_all(cls, quick=False):
        df = super().summary_all(quick)
        return df.sort_values('# images')


