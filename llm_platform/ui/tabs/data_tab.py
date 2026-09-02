"""数据处理 Tab（Sprint 1）：上传语料 -> 领域清洗/质量过滤 -> ShareGPT 落盘 + 统计。

数据来源=仅用户上传（示例数据仅作开发/测试）。换领域用本 Tab 内的下拉（解决"构建时一次性"约束）。
"""
import re

import gradio as gr

from llm_platform.data_pipeline import format_summary, run_pipeline
from llm_platform.domain import labels, slug as label_to_slug
from llm_platform.domain_presets import preset_options

TITLE = "数据处理"

PREVIEW_HEADERS = ["id", "状态", "处置原因", "主要问题"]


def build(domain: str):
    with gr.Column():
        gr.Markdown("### 数据处理")
        with gr.Accordion("数据源（仅用户上传）", open=True):
            domain_dd = gr.Dropdown(choices=labels(), value=domain, label="领域（清洗预设按此切换）")
            opts = preset_options(label_to_slug(domain))
            preset_dd = gr.Dropdown(choices=opts, value=(opts[0][1] if opts else None),
                                    label="领域预设（资源驱动，改 resources/ 词表即可扩展）")
            files = gr.File(file_count="multiple", type="filepath",
                            label="上传数据（.json / .jsonl / .csv / .txt）")
        with gr.Accordion("纯文本输入（自动生成问答对）", open=False):
            paste = gr.Textbox(label="粘贴原始文本：每段（以空行分隔）= 一条样本",
                               lines=6, placeholder="例如：\n主诉：反复胸闷3天。现病史：…诊断：冠心病；高血压病。…\n\n（空行分隔另一段，如一段法条）")
        with gr.Accordion("清洗与过滤参数", open=False):
            with gr.Row():
                min_len = gr.Number(value=10, label="最小字符数", precision=0)
                max_len = gr.Number(value=2000, label="最大字符数", precision=0)
                score_cutoff = gr.Slider(0.0, 1.0, value=0.40, step=0.05, label="质量过滤阈值")
            dedup = gr.Checkbox(value=True, label="启用去重（精确 + 近似）")
            run_btn = gr.Button("运行治理", variant="primary")

        stats = gr.Markdown("")
        preview = gr.Dataframe(headers=PREVIEW_HEADERS, label="样本明细（前 20 条）", interactive=False)
        out_path = gr.Textbox(label="输出文件（jsonl / json / config）", interactive=False,
                              lines=2, show_copy_button=True)
        out_file = gr.File(label="下载 Alpaca jsonl（instruction/input/output）", interactive=True)

        def _refresh_presets(dom):
            o = preset_options(label_to_slug(dom))
            return gr.update(choices=o, value=(o[0][1] if o else None))

        def _run(preset, domain_lab, fpaths, mn, mx, cut, dd, paste):
            paths = _as_list(fpaths)
            texts = _split_paste(paste)
            if not paths and not texts:
                return "⚠ 请上传数据文件，或粘贴纯文本。", [], "", gr.update()
            try:
                res = run_pipeline(domain_lab, file_paths=paths, texts=texts,
                                   min_len=mn or 0, max_len=mx or 2000,
                                   dedup=bool(dd), score_cutoff=cut or 0.0,
                                   preset=preset or None)
            except ValueError as e:
                return f"⚠ {e}", [], "", gr.update()
            except Exception as e:  # noqa: BLE001
                return f"⚠ 运行出错：{e}", [], "", gr.update()
            download = res.output_files[0] if res.output_files else None
            rows = [[p["id"], p["status"], p["drop_reason"], p["top_issues"][:60]] for p in res.preview]
            return (format_summary(res), rows,
                    "\n".join(res.output_files), gr.update(value=download))

        domain_dd.change(_refresh_presets, [domain_dd], [preset_dd])
        run_btn.click(_run, [preset_dd, domain_dd, files, min_len, max_len, score_cutoff, dedup, paste],
                      [stats, preview, out_path, out_file])


def _as_list(x):
    if not x:
        return []
    if isinstance(x, str):
        return [x]
    if isinstance(x, (list, tuple)):
        return [p for p in x if p]
    return [x]


def _split_paste(s):
    if not s or not s.strip():
        return None
    parts = re.split(r"\n\s*\n", s)
    return [p.strip() for p in parts if p.strip()] or None
