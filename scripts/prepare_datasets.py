"""一键生成各领域参考数据集的结果数据（alpaca jsonl）。

克隆后运行一次即可补齐被 .gitignore 忽略的结果大文件：
    python scripts/prepare_datasets.py

机制：扫描 data/reference/*/manifest.json，对每个数据集若结果文件不存在，
则调用其 source.convertScript 生成。已存在则跳过。后期新增领域/数据集只需
放原始数据 + 转换脚本 + manifest，本脚本自动覆盖，无需修改。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = ROOT / "data" / "reference"


def main():
    if not REFERENCE_DIR.exists():
        print("无 data/reference/ 目录，跳过")
        return

    found = 0
    for manifest in sorted(REFERENCE_DIR.glob("*/manifest.json")):
        domain = manifest.parent.name
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for ds in data.get("datasets", []):
            found += 1
            result_file = manifest.parent / ds["file"]
            if result_file.exists():
                print(f"[跳过] {domain}/{ds['name']}（结果已存在）")
                continue
            convert_script = ROOT / ds.get("source", {}).get("convertScript", "")
            if not convert_script.exists():
                print(f"[警告] {domain}/{ds['name']} 转换脚本不存在: {convert_script}")
                continue
            print(f"[生成] {domain}/{ds['name']}  <-  {convert_script.relative_to(ROOT)}")
            subprocess.check_call([sys.executable, str(convert_script)])

    if found == 0:
        print("未发现任何参考数据集 manifest")
    else:
        print(f"\n完成，共处理 {found} 个数据集")


if __name__ == "__main__":
    main()