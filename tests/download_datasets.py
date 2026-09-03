"""下载 docs/DATASETS.md 列出的全部数据集，落到 tests/fixtures/_downloads/（不入库，供云端重建 fixtures）。

设计取向（配合"本地只写代码、云端负责下载、下载内容不入库"的流水线）：
- 零第三方运行时依赖：GitHub 源用系统 git shelve clone/sparse；HuggingFace 源用标准库 urllib 走
  HF API(resolve URL) 直下文件，不依赖 huggingface_hub/datasets；
  MedQA 的 Google Drive 数据为可选（装了 gdown 才自动拉，否则警告并跳过，可用 --source medqa 提示手动）。
- 幂等：每源成功后写 `.done.json`（含指纹），再次运行直接跳过；文件已存在且大小达标也跳过（断点续传 .part）。
- 重试：git clone 与单文件下载均指数退避重试；单源失败不阻断其它源，末尾汇总表 + manifest.json。
- 选择性：`--source slug[,slug...]` 或 `--all`；`--list` 仅列源；`--dry-run` 只模拟不落盘。
- 校验：HF 文件与 API tree 的 size 比对；本地非空检查；`.done.json` 记录文件数/字节。
- 镜像：HuggingFace 经 HF_ENDPOINT 环境变量支持镜像（国内可设 https://hf-mirror.com）。

用法示例（云端流水线由 tests/cloud_run.sh 调用）：
    python tests/download_datasets.py --list
    python tests/download_datasets.py --all
    python tests/download_datasets.py --source cmb,toyhom,lawbench
    python tests/download_datasets.py --all --dest /root/autodl-tmp/scratch --force --quiet
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# 每次改动下载/指纹逻辑时 +1，使旧 .done.json 失效并强制重下
SCHEMA_VERSION = 1

# 默认落盘：tests/fixtures/_downloads（被 .gitignore 忽略，不入库）
DEFAULT_DEST = Path(__file__).resolve().parent / "fixtures" / "_downloads"

USER_AGENT = "llm-platform-fixtures/1.0 (+https://github.com/g513yb/llm-platform)"
GIT_MAX_RETRY = 3
HTTP_MAX_RETRY = 3
BACKOFF_BASE = 2.0  # 退避基数（秒）

# 各 HF 源默认最多下载文件数（Huatuo-26M 等巨型 parquet 集限流），可用 --limit-files 覆盖
HF_LIMIT_DEFAULT = 10


@dataclass
class GitSource:
    slug: str
    name: str
    url: str
    subdir: str = ""
    sparse_dirs: tuple[str, ...] = ()   # 稀疏检出目录（大仓库必填，节省下载量与磁盘）
    note: str = ""


@dataclass
class HFSource:
    slug: str
    name: str
    repo: str
    subdir: str = ""
    note: str = ""
    limit: int = HF_LIMIT_DEFAULT


@dataclass
class DriveSource:
    slug: str
    name: str
    url: str
    subdir: str = ""
    folder: bool = False   # True=整个 Google Drive 文件夹（需 gdown）
    note: str = ""


GIT_SOURCES: list[GitSource] = [
    GitSource("cmb", "CMB(CMB-Exam/CMB-Clin)", "https://github.com/FreedomIntelligence/CMB.git",
              note="含 data/CMB.zip（考卷+临床）"),
    GitSource("toyhom", "Toyhom 中文医患对话", "https://github.com/Toyhom/Chinese-medical-dialogue-data.git",
              sparse_dirs=("Data_数据",), note="GBK CSV，6 科室约 79 万条"),
    GitSource("lawbench", "LawBench", "https://github.com/open-compass/LawBench.git",
              sparse_dirs=("data",), note="20 任务×500 例，每任务一 jsonl"),
    GitSource("lawcrime", "LawCrimeMining(中文法律文书)", "https://github.com/liuhuanyong/LawCrimeMining.git",
              sparse_dirs=("corpus_lawsuit",), note="裁判文书≈10.8 万 + 犯罪案例≈6.3 万 raw 文本"),
    GitSource("crimekg", "CrimeKgAssitant(犯罪知识图谱)", "https://github.com/liuhuanyong/CrimeKgAssitant.git",
              sparse_dirs=("data",), note="856 类+约 20 万法务问答（较大，可选）"),
    GitSource("fineval", "FinEval", "https://github.com/SUFE-AIFLM-Lab/FinEval.git",
              sparse_dirs=("data-v2",), note="选择题 4661 + 开放问答 1434"),
    GitSource("mmlu", "MMLU(hendrycks/test)", "https://github.com/hendrycks/test.git",
              sparse_dirs=("data",), note="57 科目 CSV question,A..D,answer"),
    GitSource("cmmlu", "CMMLU", "https://github.com/haonan-li/CMMLU.git",
              sparse_dirs=("data",), note="约 67 科目 CSV Question,A..D,Answer"),
    GitSource("educhat", "EduChat", "https://github.com/ECNU-ICALK/EduChat.git",
              note="教育对话/指令数据可见性以仓库为准"),
    GitSource("medqa", "MedQA", "https://github.com/jind11/MedQA.git",
              note="仓库仅脚本/说明；题库数据在 Google Drive（drive 源）"),
]

HF_SOURCES: list[HFSource] = [
    HFSource("huatuo", "Huatuo-26M", "FreedomIntelligence/Huatuo-26M",
             note="约 2600 万条，极大；默认按 limit 限流下载，够 build_fixtures 抽样即可", limit=2),
    HFSource("disc-law", "DISC-Law-SFT", "ShengbinYue/DISC-Law-SFT",
             note="Alpaca instruction/input/output"),
    HFSource("fingpt", "fingpt-sentiment-train", "FinGPT/fingpt-sentiment-train",
             note="input/output 情感标签"),
    HFSource("cmb-hf", "CMB(HF 镜像)", "FreedomIntelligence/CMB",
             note="GitHub 源公开时无需；镜像备用", limit=5),
]

DRIVE_SOURCES: list[DriveSource] = [
    DriveSource("medqa-drive", "MedQA 题库(Google Drive)", "https://drive.google.com/drive/folders/1HtYbZzF8DZD8V8zw5UzH2F9yFgmIoVkq",
                subdir="medqa_drive", folder=True,
                note="README 内 Google Drive 链接；需 gdown。若不可达请手动下载后解压到 _downloads/medqa/"),
]

def _finalize(slug: str) -> tuple[str, object]:
    s = ALL_BASE[slug]
    if not s.subdir:
        s.subdir = slug  # 每个源独立子目录，避免落盘冲突
    return slug, s


ALL_BASE = {s.slug: s for s in GIT_SOURCES} | {s.slug: s for s in HF_SOURCES} | {s.slug: s for s in DRIVE_SOURCES}
ALL = dict(_finalize(s) for s in ALL_BASE)


# ---------------------------------------------------------------- 基础工具
class Color:
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; CYAN = "\033[36m"; BOLD = "\033[1m"; DIM = "\033[2m"; END = "\033[0m"


def c(text: str, code: str) -> str:
    return f"{code}{text}{Color.END}" if sys.stdout.isatty() else text


def err(msg: str) -> None:
    print(c(f"[err] {msg}", Color.RED), file=sys.stderr)


def warn(msg: str) -> None:
    print(c(f"[warn] {msg}", Color.YELLOW), file=sys.stderr)


def ok(msg: str) -> None:
    print(c(f"[ok] {msg}", Color.GREEN))


def info(msg: str) -> None:
    print(c(msg, Color.CYAN))


def format_bytes(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TiB"


class Progress:
    """极简进度条：无第三方依赖；--quiet 时静默。"""

    def __init__(self, quiet: bool) -> None:
        self.quiet = quiet
        self.last = 0.0

    def _emit(self, line: str) -> None:
        if self.quiet or not sys.stdout.isatty():
            return
        now = time.time()
        if now - self.last < 0.1 and "%" not in line:
            return
        self.last = now
        sys.stdout.write("\r" + line)
        sys.stdout.flush()

    def begin(self, label: str, total: int | None) -> None:
        self.label, self.total, self.done = label, total or 0, 0
        if not sys.stdout.isatty():
            print(f"[down] {label} 0/{format_bytes(total) if total else '?'}")
        self._emit(f"{label} 0%")

    def add(self, n: int) -> None:
        self.done += n
        if self.total:
            pct = min(100, self.done * 100 // self.total)
            if not sys.stdout.isatty():
                if self.done % max(1, self.total // 5) == 0 or self.done >= self.total:
                    print(f"[down] {self.label} {pct}%")
            else:
                self._emit(f"{self.label} {pct}% {format_bytes(self.done)}/{format_bytes(self.total)}")
        elif not sys.stdout.isatty():
            # 未知大小：每 ~50MiB 打印一次
            if self.done % (50 * 1024 * 1024) < max(n, 1):
                print(f"[down] {self.label} {format_bytes(self.done)}")

    def end(self, msg: str = "") -> None:
        if not sys.stdout.isatty():
            print(f"[down] {self.label} done {msg}")
            return
        suffix = f" {msg}" if msg else ""
        print(f"\r{self.label} 100%{suffix}" + " " * 20)


def run_cmd(cmd: list[str], cwd: Path, quiet: bool, retries: int = GIT_MAX_RETRY,
            env: dict | None = None) -> subprocess.CompletedProcess:
    """执行外部命令（git 等），失败指数退避重试。git 默认非交互（不弹凭据提示）。"""
    merged_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})}
    log = subprocess.DEVNULL if quiet else None
    for attempt in range(1, retries + 1):
        try:
            return subprocess.run(cmd, cwd=str(cwd), stdout=log, stderr=log, env=merged_env,
                                  check=True, text=True, timeout=1800)
        except (subprocess.CalledProcessError, OSError) as e:
            if attempt < retries:
                wait = BACKOFF_BASE ** attempt
                warn(f"{cmd[0]} 失败(第 {attempt} 次): {e}，{wait:.0f}s 后重试")
                time.sleep(wait)
    raise RuntimeError(f"命令失败: {cmd[0]} {cmd[1:]} -> {e}")


def check_done(savedir: Path) -> dict | None:
    """幂等：目录存在且 `.done.json` 指纹匹配则返回其内容（跳过下载）。"""
    f = savedir / ".done.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("schema") != SCHEMA_VERSION:
        return None
    return data


def write_done(savedir: Path, payload: dict) -> None:
    savedir.mkdir(parents=True, exist_ok=True)
    payload = {"schema": SCHEMA_VERSION, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **payload}
    (savedir / ".done.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- Git 源
def download_git(src: GitSource, dest: Path, quiet: bool) -> dict:
    git_cmd = ["git"]
    repo_dir = dest / src.subdir  # 子目录直存，避免重复 mkdir
    if check_done(repo_dir):
        info(f"  {src.slug}: 已下载过（.done.json），跳过")
        return {"status": "skipped", "files": 0, "bytes": 0}
    if repo_dir.exists():
        # 已存在目录：若是 git 仓库则增量同步，否则删除重克隆
        try:
            subprocess.run(git_cmd + ["rev-parse", "--git-dir"], cwd=str(repo_dir),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            info(f"  {src.slug}: 目录已是 git 仓库，fetch+reset 增量同步")
            run_cmd(git_cmd + ["fetch", "--depth=1", "origin"], repo_dir, quiet=quiet)
            run_cmd(git_cmd + ["reset", "--hard", "FETCH_HEAD"], repo_dir, quiet=quiet)
            _apply_sparse(repo_dir, src, quiet)
            rev = subprocess.check_output([*git_cmd, "rev-parse", "HEAD"], cwd=str(repo_dir), text=True).strip()[:12]
            stat = _dir_stats(repo_dir)
            write_done(repo_dir, {"kind": "git", "name": src.name, "url": src.url, "rev": rev, **stat})
            return {"status": "synced", "rev": rev, **stat}
        except subprocess.CalledProcessError:
            info(f"  {src.slug}: 目录残缺，删除重克隆")
            subprocess.run(["rm", "-rf", str(repo_dir)], check=False)
    info(f"  {src.slug}: git clone {src.url} ...")
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    clone = ["git", "clone", "--depth=1", "--no-tags"]

    clone += [src.url, str(repo_dir)]
    run_cmd(clone, repo_dir.parent, quiet=quiet)
    _apply_sparse(repo_dir, src, quiet)
    rev = subprocess.check_output([*git_cmd, "rev-parse", "HEAD"], cwd=str(repo_dir), text=True).strip()[:12]
    stat = _dir_stats(repo_dir)
    write_done(repo_dir, {"kind": "git", "name": src.name, "url": src.url, "rev": rev, **stat})
    return {"status": "ok", "rev": rev, **stat}


def _apply_sparse(repo_dir: Path, src: GitSource, quiet: bool) -> None:
    if not src.sparse_dirs:
        return
    info(f"  {src.slug}: 稀疏检出保留目录 {','.join(src.sparse_dirs)}")
    run_cmd(["git", "sparse-checkout", "init", "--cone"], repo_dir, quiet=quiet)
    run_cmd(["git", "sparse-checkout", "set", *src.sparse_dirs], repo_dir, quiet=quiet)


def _dir_stats(d: Path) -> dict:
    files = bytes_total = 0
    for p in d.rglob("*"):
        if p.is_file() and p.name != ".done.json":
            files += 1
            bytes_total += p.stat().st_size
    return {"files": files, "bytes": bytes_total}


# ---------------------------------------------------------------- HuggingFace 源
def hf_api_cmd(endpoint: str, repo: str, rev: str) -> str:
    return f"{endpoint.rstrip('/')}/api/datasets/{repo}/tree/{rev}?recursive=true"


def hf_resolve(endpoint: str, repo: str, rev: str, path: str) -> str:
    return f"{endpoint.rstrip('/')}/datasets/{repo}/resolve/{rev}/{urllib.parse.quote(path)}"


def hf_list_files(endpoint: str, repo: str, rev: str = "main", quiet: bool = False) -> list[dict]:
    url = hf_api_cmd(endpoint, repo, rev)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        entries = json.loads(r.read().decode("utf-8"))
    files = [e for e in entries if e.get("type") == "file" and not e.get("path", "").endswith("/.gitattributes")
             and e.get("path") != ".gitattributes"]
    if not quiet:
        info(f"  [hf] {repo}@{rev} 共 {len(files)} 个文件")
    return files


def _get_size_remote(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.headers.get("Content-Length") or 0) or None
    except Exception:
        return None


def download_file(url: str, target: Path, expected_size: int | None, quiet: bool,
                  progress: Progress | None = None) -> tuple[bool, int]:
    """单文件下载：断点续传(.part) + 指数退避重试。返回 (是否新增/完成, 最终字节)。"""
    part = target.with_name(target.name + ".part")
    for attempt in range(1, HTTP_MAX_RETRY + 1):
        try:
            already = (target.exists() and target.stat().st_size > 0
                       and (expected_size is None or target.stat().st_size >= expected_size))
            if already:
                return False, target.stat().st_size
            offset = part.stat().st_size if part.exists() else 0
            headers = {"User-Agent": USER_AGENT, "Range": f"bytes={offset}-"} if offset else {"User-Agent": USER_AGENT}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r, part.open("ab" if offset else "wb") as f:
                total = expected_size or int(r.headers.get("Content-Length") or 0) or 0
                if progress and attempt == 1 and not offset:
                    progress.begin(url.rsplit("/", 1)[-1], total or None)
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    if progress:
                        progress.add(len(chunk))
            if expected_size and part.stat().st_size < expected_size:
                raise RuntimeError(f"大小不符: {part.stat().st_size} < {expected_size}")
            part.replace(target)
            if progress:
                progress.end()
            return True, target.stat().st_size
        except (urllib.error.URLError, OSError, RuntimeError) as e:
            if attempt < HTTP_MAX_RETRY:
                wait = BACKOFF_BASE ** attempt
                warn(f"  {url.rsplit('/', 1)[-1]} 下载失败(第 {attempt} 次): {e}，{wait:.0f}s 后重试")
                time.sleep(wait)
            else:
                raise


def download_hf(src: HFSource, dest: Path, quiet: bool, limit: int | None) -> dict:
    repo_dir = dest / src.subdir
    if check_done(repo_dir):
        info(f"  {src.slug}: 已下载过（.done.json），跳过")
        return {"status": "skipped", "files": 0, "bytes": 0}
    endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co") or "https://huggingface.co"
    rev = os.environ.get("HF_REVISION", "main")
    info(f"  {src.slug}: HF {src.repo}@{rev} (endpoint={endpoint})")
    files = hf_list_files(endpoint, src.repo, rev, quiet=quiet)
    if limit:
        files = files[:limit]
        info(f"  {src.slug}: 按 --limit-files 限流，仅下载前 {limit} 个")
    repo_dir.mkdir(parents=True, exist_ok=True)
    progress = Progress(quiet)
    n_ok = n_total = 0
    total_bytes = 0
    n_skip = 0
    for e in files:
        path = e["path"]
        expected = int(e.get("size") or 0) or None
        target = repo_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and expected and target.stat().st_size >= expected:
            n_skip += 1
            total_bytes += target.stat().st_size
            continue
        url = hf_resolve(endpoint, src.repo, rev, path)
        added, size = download_file(url, target, expected, quiet, progress)
        total_bytes += size
        if added:
            n_ok += 1
        else:
            n_skip += 1
        n_total += 1
    if n_total == 0:
        raise RuntimeError(f"{src.repo} 没有可下载文件")
    stat = _dir_stats(repo_dir)
    write_done(repo_dir, {"kind": "hf", "name": src.name, "repo": src.repo, "rev": rev,
                          "endpoint": endpoint, "files_downloaded": n_ok, "files_skipped": n_skip,
                          "limit": limit, **stat})
    return {"status": "ok", "rev": rev, "files_downloaded": n_ok, "files_skipped": n_skip, **stat}


# ---------------------------------------------------------------- Google Drive 源（可选 gdown）
def download_drive(src: DriveSource, dest: Path, quiet: bool) -> dict:
    repo_dir = dest / src.subdir
    if check_done(repo_dir):
        info(f"  {src.slug}: 已下载过（.done.json），跳过")
        return {"status": "skipped", "files": 0, "bytes": 0}
    try:
        import gdown  # noqa: F401   # 可选依赖
    except ImportError:
        warn(f"{src.slug}({src.name}): 未安装 gdown，无法自动下载 Google Drive 数据。"
             f"请 `pip install gdown` 后重试，或手动下载 {src.url} 到 {repo_dir}")
        return {"status": "manual-required", "files": 0, "bytes": 0, "hint": src.url}
    info(f"  {src.slug}: 使用 gdown 下载 {src.url} ...")
    repo_dir.mkdir(parents=True, exist_ok=True)
    if src.folder:
        subprocess.run(["python", "-m", "gdown", "--folder", src.url, "-O", str(repo_dir)],
                       check=True, timeout=3600)
    else:
        subprocess.run(["python", "-m", "gdown", src.url, "-O", str(repo_dir)],
                       check=True, timeout=3600)
    stat = _dir_stats(repo_dir)
    write_done(repo_dir, {"kind": "drive", "name": src.name, "url": src.url, **stat})
    return {"status": "ok", **stat}


# ---------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="download_datasets.py",
        description="下载 docs/DATASETS.md 列出的数据集到 tests/fixtures/_downloads/（不入库）。",
        epilog="示例: python tests/download_datasets.py --all ; --source cmb,toyhom ; 云端流水线见 tests/cloud_run.sh")
    sel = p.add_mutually_exclusive_group()
    sel.add_argument("--all", action="store_true", help="下载全部源")
    sel.add_argument("--source", metavar="SLUGS", help="逗号分隔的源 slug（见 --list）")
    sel.add_argument("--list", action="store_true", help="仅列出所有源及获取方式")
    p.add_argument("--dry-run", action="store_true",
                   help="仅模拟：结合 --all/--source 检查幂等与目标，不实际下载")
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST, help=f"落盘目录（默认 {DEFAULT_DEST}）")
    p.add_argument("--force", action="store_true", help="忽略 .done.json 强制重下")
    p.add_argument("--quiet", action="store_true", help="静默进度（只输出摘要）")
    p.add_argument("--limit-files", type=int, default=None, metavar="N",
                   help=f"每个 HF 源最多下载前 N 个文件（默认 {HF_LIMIT_DEFAULT}，huatuo 独立小值）")
    return p


def list_sources() -> None:
    print("== Git 源（git clone --depth=1[/稀疏]）==")
    for s in GIT_SOURCES:
        print(f"  {s.slug:<12} {s.name}<{s.url}>" + (f"\n     稀疏: {','.join(s.sparse_dirs)}" if s.sparse_dirs else ""))
    print("== HuggingFace 源（HF API resolve 直下，HF_ENDPOINT 可指镜像）==")
    for s in HF_SOURCES:
        print(f"  {s.slug:<12} {s.name}<datasets/{s.repo}> limit={s.limit}")
    print("== Google Drive 源（需 gdown 可选依赖）==")
    for s in DRIVE_SOURCES:
        print(f"  {s.slug:<12} {s.name}<{s.url}>")
    print("\n提示: `--all` 为完整获取；`--source` 按需取子集；`--force` 重下；`--dry-run` 模拟。")


def main() -> int:
    args = build_parser().parse_args()
    if args.list:
        list_sources()
        return 0

    if not (args.all or args.source):
        print("请指定 --all 或 --source <slug,...>（--list 查看可选项）", file=sys.stderr)
        return 2

    if args.force:
        for s in ALL.values():
            d = args.dest / s.subdir
            f = d / ".done.json"
            if f.exists():
                f.unlink()
        info("已清除全部 .done.json（--force），将全量重下")

    slugs = list(ALL) if args.all else [x.strip() for x in args.source.split(",") if x.strip()]
    unknown = [s for s in slugs if s not in ALL]
    if unknown:
        err(f"未知源: {', '.join(unknown)}（--list 查看）")
        return 2

    summary: dict[str, dict] = {}

    if args.dry_run:
        info("== dry-run 模拟 ==")
        for sl in slugs:
            s = ALL[sl]
            dest = args.dest / s.subdir
            if args.force and (dest / ".done.json").exists():
                status = "would-redownload"
            elif check_done(dest):
                status = "skipped (already done)"
            else:
                status = "would-download"
            print(f"  {sl:<12} {s.name:<30} {status} -> {dest}")
        print(f"目标目录: {args.dest}")
        return 0

    info(f"目标目录: {args.dest}")
    args.dest.mkdir(parents=True, exist_ok=True)

    for sl in slugs:
        s = ALL[sl]
        try:
            if isinstance(s, GitSource):
                r = download_git(s, args.dest, args.quiet)
            elif isinstance(s, HFSource):
                limit = args.limit_files if args.limit_files is not None else s.limit
                r = download_hf(s, args.dest, args.quiet, limit)
            else:
                r = download_drive(s, args.dest, args.quiet)
            summary[sl] = {"name": s.name, **r}
            ok(f"[{sl}] {s.name} -> {r.get('status')} files={r.get('files', r.get('files_downloaded', 0))} bytes={format_bytes(r.get('bytes', 0))}")
        except (urllib.error.URLError, OSError, RuntimeError, subprocess.CalledProcessError) as e:
            summary[sl] = {"name": s.name, "status": "error", "error": str(e)}
            err(f"[{sl}] {s.name} 失败: {e}")

    # manifest 汇总（不进 git）
    manifest = {"schema": SCHEMA_VERSION, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "sources": summary}
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n==== 下载汇总 ====")
    ok_count = error_count = 0
    for sl, r in summary.items():
        if r.get("status") in ("ok", "synced", "skipped"):
            ok_count += 1
            icon = "✓"
        else:
            error_count += 1
            icon = "✗"
        desc = f"{r.get('status')}" + (f" err={r.get('error')}" if r.get("error") else "")
        print(f"  {icon} {sl:<12} {r['name']:<30} {desc}")
    print(f"成功/跳过 {ok_count}  未就绪 {error_count}  详情: {args.dest / 'manifest.json'}")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())