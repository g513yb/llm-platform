"""数据处理 Tab：选领域 -> 上传 -> 自动识别 -> 处理。

交互：领域 + 文件上传后自动识别，识别通过则"处理"按钮可用，不支持则报错并禁用按钮。
领域仅标注，不影响处理逻辑——实际处理只关注 schema。
"""
import gradio as gr

from llm_platform.data_pipeline import SUPPORTED, format_summary, inspect, run_pipeline

TITLE = "数据处理"

PREVIEW_HEADERS = ["问题（截断）", "答案（截断）"]


def build(domain: str):
    with gr.Column():
        gr.Markdown("### 数据处理")
        domain_dd = gr.Dropdown(
            choices=SUPPORTED, value=domain if domain in SUPPORTED else SUPPORTED[0],
            label="领域（仅标注，不影响数据处理）",
        )
        files = gr.File(
            file_count="multiple", type="filepath",
            label="上传数据（.json / .jsonl / .csv / .parquet）",
        )
        inspect_md = gr.Markdown("上传后将自动识别数据格式。")
        run_btn = gr.Button("处理", variant="primary", interactive=False)

        gr.Markdown(
            "支持类型：病例问答、选择题、问答"
            "（schema 见 readers.py SCHEMAS，reader 自动识别）"
        )

        stats = gr.Markdown("")
        preview = gr.Dataframe(
            headers=PREVIEW_HEADERS, label="样本明细（前 20 条）", interactive=False
        )
        out_path = gr.Textbox(
            label="输出文件", interactive=False, lines=2, show_copy_button=True
        )
        out_file = gr.File(label="下载 Alpaca jsonl", interactive=True)

        def _inspect(domain_lab, fpaths):
            paths = _as_list(fpaths)
            if not paths:
                return "⏳ 请上传数据文件。", gr.update(interactive=False)
            try:
                summary, err = inspect(domain_lab, paths)
            except Exception as e:  # noqa: BLE001
                return f"⚠ 识别出错：{e}", gr.update(interactive=False)
            if err:
                return f"⚠ {err}", gr.update(interactive=False)
            type_str = "、".join(f"{k}: {v}" for k, v in summary.type_counts.items())
            return (
                f"✅ 识别通过：{type_str}（预览前 100 条，丢弃 {summary.dropped}）",
                gr.update(interactive=True),
            )

        def _run(domain_lab, fpaths):
            paths = _as_list(fpaths)
            if not paths:
                return "⚠ 请上传数据文件。", [], "", gr.update()
            try:
                res = run_pipeline(domain_lab, paths)
            except ValueError as e:
                return f"⚠ {e}", [], "", gr.update()
            except Exception as e:  # noqa: BLE001
                return f"⚠ 运行出错：{e}", [], "", gr.update()
            download = res.output_files[0] if res.output_files else None
            rows = [[p["question"], p["answer"]] for p in res.preview]
            return (format_summary(res), rows, "\n".join(res.output_files), gr.update(value=download))

        files.change(_inspect, [domain_dd, files], [inspect_md, run_btn])

        run_btn.click(_run, [domain_dd, files], [stats, preview, out_path, out_file])


def _as_list(x):
    if not x:
        return []
    if isinstance(x, str):
        return [x]
    if isinstance(x, (list, tuple)):
        return [p for p in x if p]
    return [x]
