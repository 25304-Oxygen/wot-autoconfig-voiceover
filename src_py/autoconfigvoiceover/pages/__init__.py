# coding=utf-8
"""页面模块。

每个 Flash 页面对应一个 Python 模块，负责:
  - 准备该页面的初始数据（下拉选项、Tooltip、默认值等）
  - 处理该页面的业务逻辑回调（按钮点击、选择变更等）
  - 与 WoT API、配置文件等其他模块协作

不负责:
  - UI 渲染、动画、视觉反馈（Flash/AS3 端处理）
  - DAAPI 桥接（menu.py 的 ACVMenuMeta 处理）

用法:
    from .settings_page import SettingsPage

    page = SettingsPage(meta)
    page.push_data()   # 推送初始数据到 Flash
    # Flash 用户操作 → 回调 → page.handle_xxx()
"""
