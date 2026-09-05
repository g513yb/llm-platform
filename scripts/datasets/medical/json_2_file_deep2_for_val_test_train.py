import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/reference/medical/raw/CMB-train-merge.json"


def split_json_to_folders(json_file_path):
    # 打开并读取json文件
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 按照exam_type和exam_class将数据进行分类
    categorized_data = {}
    for item in data:
        exam_type = item['exam_type']
        exam_class = item['exam_class']
        if exam_type not in categorized_data:
            categorized_data[exam_type] = {}
        if exam_class not in categorized_data[exam_type]:
            categorized_data[exam_type][exam_class] = []
        categorized_data[exam_type][exam_class].append(item)

    # 为每个类别创建目录和子目录，并在其中存储json文件
    for exam_type, subjects in categorized_data.items():
        for exam_class, items in subjects.items():
            directory = os.path.join(os.path.dirname(json_file_path), exam_type)
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, f'{exam_class}.json'), 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False, indent=4)

    print(f"拆分完成：{len(data)} 条 -> {sum(len(s) for s in categorized_data.values())} 条，{sum(len(v) for v in categorized_data.values())} 个类别")


if __name__ == "__main__":
    split_json_to_folders(str(SRC))
