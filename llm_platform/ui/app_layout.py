"""构建 Gradio 应用：领域选择 → 进入工作台 → 一组工作台 Tab。"""
import gradio as gr

from config import APP_TITLE
from llm_platform.domain import labels, describe
from llm_platform.ui.tabs import TAB_REGISTRY


def build_app():
    with gr.Blocks(title=APP_TITLE) as demo:
        gr.Markdown(f"# {APP_TITLE}")
        with gr.Row():
            domain_dd = gr.Dropdown(choices=labels(), value=labels()[0], label="选择领域")
            enter = gr.Button("进入工作台", variant="primary")
        header = gr.Markdown("")

        workspace = gr.Group(visible=False)
        with workspace:
            with gr.Tabs():
                for tab in TAB_REGISTRY:
                    with gr.Tab(tab.TITLE):
                        tab.build(domain_dd.value)

        def open_workspace(domain: str):
            return gr.update(visible=True), f"## 当前领域：{domain}　·　{describe(domain)}"

        enter.click(open_workspace, [domain_dd], [workspace, header])
    return demo
