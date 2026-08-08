# coding=utf-8
"""字幕渲染数据组装。

将 SubtitleEntry + SubtitleStyle → Flash 可消费的 dict。
所有四个排队策略共享此模块。
"""


def assemble_entry_data(entry, style, settings, offsets):
    """将 SubtitleEntry + SubtitleStyle → Flash 可消费的 dict。

    :param entry:    SubtitleEntry 实例
    :param style:    SubtitleStyle 实例
    :param settings: dict（display_mode / text_speed / subtitle_anim）
    :param offsets:  dict（组件位置偏移）
    :return: dict {mode, text_speed, ...}
    """
    mode = settings.get('display_mode', 'standard')
    text_speed = settings.get('text_speed', 0.0)

    base = {
        'mode': mode,
        'text_speed': text_speed,
    }

    if mode == 'concise':
        return _assemble_concise(entry, base, style, offsets)
    else:
        return _assemble_standard(entry, base, style, settings, offsets)


def _assemble_concise(entry, base, style, offsets):
    """简洁模式：角色名 + 正文拼接，无额外动画。

    [角色名：][正文正文...]
     ←右对齐→|间隙|← 左对齐自动换行 →

    位置/宽度/间距取自 simple_mode 配置（缺省回退到 tf_messages），
    名称颜色取自 tf_titles 样式，其余（字号/字体/颜色）取自 tf_messages 样式。
    """
    name_code = entry.tf_title
    msg_style = style.get_tf_message(entry.tf_message)
    title_style = style.get_tf_title(name_code if name_code else '')
    sm = style.get_simple_mode()

    # 角色名后加全角冒号（展示层，不污染原始数据）
    # 若标题样式为空字典 {}（用户标记"不显示该组件"）→ 角色名也隐藏
    if len(title_style) == 0:
        display_name = ''
    else:
        display_name = (name_code + '：') if name_code else ''

    base['concise'] = {
        'name': display_name,
        'name_color': title_style.get('color', '#FFFFFF'),
        'text': entry.text,
        'text_color': msg_style.get('color', '#FFFFFF'),
        'position': sm['msg_position'],
        'width': sm['msg_width'],
        'font': msg_style.get('font', '$FieldFont'),
        'size': msg_style.get('size', 14),
        'gap': sm['title_msg_gap'],
    }

    # 简洁模式不播放额外动画
    base['anime'] = []
    base['anime_start_at'] = []

    # 叠加简洁模式独立位置偏移
    _apply_offsets(base, offsets)

    return base


def _assemble_standard(entry, base, style, settings, offsets):
    """标准模式：四层完整渲染数据。

    poster / background / tf_title / tf_message 各自独立样式。
    tf_title 的文本 = 样式代号（除非样式含 img 路径→则为图片标题，文本留空）。
    """
    poster = dict(style.get_poster(entry.poster))
    background = dict(style.get_background(entry.background))
    tf_title = dict(style.get_tf_title(entry.tf_title))
    tf_message = dict(style.get_tf_message(entry.tf_message))

    # 图片组件自动检测尺寸：
    # 若 img 有值但 size 未指定（为 [0,0] 或非列表），从 PNG 文件读取实际宽高
    from .base import _get_png_native_size

    for comp, default_w, default_h in [
        (poster,      64, 64),
        (background, 300, 80),
        (tf_title,   200, 40),
    ]:
        img_path = comp.get('img', '')
        if not img_path:
            continue
        sz = comp.get('size')
        # 需要自动检测: size 不是列表，或者是 [0, 0]（默认未指定）
        need_detect = (not isinstance(sz, list)
                       or (len(sz) >= 1 and sz[0] == 0 and len(sz) >= 2 and sz[1] == 0))
        if need_detect:
            native = _get_png_native_size(img_path)
            if native is not None:
                comp['size'] = [native[0], native[1]]
            elif not isinstance(sz, list):
                comp['size'] = [default_w, default_h]

    # tf_title：图片类型保留 img，文本类型删除 img 并用 font_size 做字号
    # 类型检测区分：size 是列表→默认值/图片尺寸，用 font_size；是数字→用户显式设了字号，保留
    if not tf_title.get('img', ''):
        tf_title.pop('img', None)
        sz = tf_title.get('size', [0, 0])
        if isinstance(sz, list):
            tf_title['size'] = tf_title.get('font_size', 14)

    # tf_message 永远是文字；font_size（来自 "字号" 键）仅在用户显式书写时存在，
    # 此时优先于 size（默认 14）
    if 'font_size' in tf_message:
        tf_message['size'] = tf_message['font_size']

    # 标题文本: 样式代号即文本内容。
    # 跳过条件: ①无代号 ②图片标题 ③空字典 {}（不显示）
    title_text = ''
    if entry.tf_title and not tf_title.get('img', '') and len(tf_title) > 0:
        title_text = entry.tf_title

    base['poster'] = poster
    base['background'] = background
    base['tf_title'] = tf_title
    base['tf_title']['text'] = title_text
    base['tf_message'] = dict(tf_message)
    base['tf_message']['text'] = entry.text

    # 额外动画序列（受"字幕动画"设置控制，关闭时清空）
    # 拷贝列表而非引用：queue_s3 复用补偿会原地改写 anime_start_at[0]，
    # 直接传 entry 的列表会把补偿值写回 entry，二次组装时叠加偏移。
    if settings.get('subtitle_anim', False):
        base['anime'] = list(entry.anime)
        base['anime_start_at'] = list(entry.anime_start_at)
    else:
        base['anime'] = []
        base['anime_start_at'] = []

    # 叠加组件位置偏移
    _apply_offsets(base, offsets)

    return base


def _apply_offsets(base, offsets):
    """将已保存的组件偏移叠加到渲染数据的 position 上。

    标准模式: poster / background / tf_title / tf_message 四个组件。
    简洁模式: concise.position 对应 simple_mode 偏移键。
    直接替换 position 列表（不修改共享的样式数据）。
    """
    if not offsets:
        return

    # 简洁模式: concise.position 使用独立的 simple_mode 偏移键
    if 'concise' in base:
        c = base['concise']
        ox = offsets.get('simple_mode', {}).get('x', 0)
        oy = offsets.get('simple_mode', {}).get('y', 0)
        if ox or oy:
            c['position'] = [c['position'][0] + ox, c['position'][1] + oy]
        return

    # 标准模式: poster / background / tf_title / tf_message
    for comp_name in ('poster', 'background', 'tf_title', 'tf_message'):
        comp = base.get(comp_name)
        if not comp or not comp.get('position'):
            continue
        ox = offsets.get(comp_name, {}).get('x', 0)
        oy = offsets.get(comp_name, {}).get('y', 0)
        if ox or oy:
            # 替换为新列表，避免修改共享的样式数据
            comp['position'] = [comp['position'][0] + ox,
                                comp['position'][1] + oy]
