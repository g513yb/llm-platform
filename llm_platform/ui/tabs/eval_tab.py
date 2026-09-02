"""多维度评测 Tab（Sprint 0 占位，Sprint 5 实现）。"""
import gradio as gr

from llm_platform.ui.placeholder import render

TITLE = "多维度评测"


def build(domain: str):
    render("多维度评测（领域知识 / 推理 / 指令遵循 / 防幻觉 / 安全合规）", "Sprint 5")
