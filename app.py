"""应用入口：构建 Gradio 应用并启动。
在 AutoDL 上运行：`python app.py`（首次会下载基座权重）。
"""
from llm_platform.ui.app_layout import build_app
from llm_platform.model_manager import warm_up


demo = build_app()

if __name__ == "__main__":
    # 启动前加载模型（首次会下载权重），避免用户首条消息等待过久。
    # 若无 GPU，模型预热失败也不阻断——数据治理等 CPU 功能仍可用；仅对话需挂 GPU 卡。
    try:
        warm_up()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 模型预热失败（可能无 GPU）：{e}", flush=True)
        print("[warn] 应用继续启动；数据治理等 CPU 功能可用，点击对话时需 GPU。", flush=True)
    demo.queue()          # 流式输出必需
    # 绑定 127.0.0.1：通过本地 `ssh -L 7860:localhost:7860 autodl` 端口转发访问，
    # 避免容器内 0.0.0.0 绑定导致的 Gradio 回环自检失败。
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
