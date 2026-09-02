"""工作台 Tab 注册表：加新 Tab = 建一个模块(暴露 TITLE + build) + 追加进此列表。"""
from . import chat_tab, data_tab, train_tab, weights_tab, eval_tab

TAB_REGISTRY = [chat_tab, data_tab, train_tab, weights_tab, eval_tab]
