"""真实聊天 Tab：多轮对话 + 流式输出（Sprint 0）。

用 gr.Chatbot(type="messages") 自身持有并回传对话历史，天然保留多轮上下文。
"""
import gradio as gr

from llm_platform.chat import stream_chat

TITLE = "对话"


def build(domain: str):
    chatbot = gr.Chatbot(type="messages", height=520, label=f"{domain} · 对话")
    with gr.Row():
        msg = gr.Textbox(placeholder="输入消息，回车发送…", scale=7, container=False)
        submit = gr.Button("发送", scale=1)

    def respond(prompt, history):
        # history 由 Chatbot 组件回传，是 [{"role","content"}, ...]，天然带上下文
        if not prompt or not prompt.strip():
            yield history
            return
        messages = list(history) + [{"role": "user", "content": prompt}]
        partial = ""
        for chunk in stream_chat(messages):
            partial += chunk
            yield messages + [{"role": "assistant", "content": partial}]
        yield messages + [{"role": "assistant", "content": partial}]

    msg.submit(respond, [msg, chatbot], [chatbot]).then(lambda: "", None, msg)
    submit.click(respond, [msg, chatbot], [chatbot]).then(lambda: "", None, msg)
