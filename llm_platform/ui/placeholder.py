"""统一占位 stub：后续 Sprint 的 Tab 沿用同一形态，便于替换。"""
import gradio as gr


def render(label: str, sprint: str):
    gr.Markdown(f"### {label}")
    gr.Markdown(f"该模块将在 **{sprint}** 实现，当前为占位页面。")
    gr.Info("功能开发中，敬请期待")
