# coding=utf-8
"""字幕状态机：接收 Wwise marker → 加载句子 → 管理 renderer 队列 → 产出 Flash 命令。

═══════════════════════════════════════════════════════════════════════════════
架构
  SubtitleManager 是纯状态机，不直接触碰 Flash。
  通过 dispatcher(cmd_dict) 产出命令，由外部（battle view）负责 DAAPI 发送。
  Flash 回调（report_height / fade_out_done）通过 manager 方法喂回状态机。

队列层级
  一轮音频触发 = 一个 SubtitleSession，包含一个 SubtitleData（多条 timeline 条目）。
  条目按 start_at 时序依次出现 → 由 BigWorld.callback 调度。
  跨音频并发由 allow_concurrent 开关控制。

动画时序（Flash renderer 侧）
  入场动画（内置）→ 额外动画序列 → 静止
  入场动画结束后等 anime_start_at[0] 秒 → 播 anime[0] → 等 anime_start_at[1] → ...
  指令语义:
    create       — 创建 renderer，播入场动画，然后逐字出字
    update_content — 替换内容，跳过入场，重置逐字出字；有额外动画则播
    shift_up     — 以入场同款缓动上移 N px
    shift_down   — 下移 N px
    fade_out     — 等约 1s → 淡出 → 销毁自身 → 回调 onFadeOutDone
═══════════════════════════════════════════════════════════════════════════════
"""

import BigWorld

from autoconfigvoiceover.logger import Logger
from .loader import load_sentence, load_offsets

logger = Logger('SubtitleManager')

# ═════════════════════════════════════════════════════════════
# 常量
# ═════════════════════════════════════════════════════════════

DEFAULT_SLOT_HEIGHT = 80
"""默认占位高度（px）：新建 renderer 时旧 renderer 上移的预估值。
实际高度由 renderer 上报后替换。"""

SHIFT_EXTRA_MARGIN = 20
"""移位额外边距（px）：在旧 renderer 上移距离基础上额外增加的间隙，
给下方字幕的淡出/入场动画留出呼吸空间，避免重叠。"""

# ═════════════════════════════════════════════════════════════
# 数据结构
# ═════════════════════════════════════════════════════════════


class RendererState(object):
    """追踪一个 Flash renderer 的状态。"""

    __slots__ = ('id', 'audio_key', 'character', 'height', 'state')

    def __init__(self, rid, audio_key, character, height=0, state='entering'):
        """
        :param rid:       唯一 ID（递增整数）
        :param audio_key: 所属音频标识（marker 名）
        :param character: 当前显示的角色代号（用于 allow_update 匹配）
        :param height:    实际像素高度（Flash 上报，0=未知）
        :param state:     'entering' | 'active' | 'shifting' | 'fading' | 'dead'
        """
        self.id = rid
        self.audio_key = audio_key
        self.character = character
        self.height = height
        self.state = state


class SubtitleSession(object):
    """一轮音频触发的字幕生命周期。"""

    __slots__ = ('audio_key', 'renderer_ids', 'duration', 'entries',
                 'current_index', '_dead')

    def __init__(self, audio_key, data):
        """
        :param audio_key: 音频标识（marker 名）
        :param data:      SubtitleData 实例
        """
        self.audio_key = audio_key
        self.renderer_ids = []   # [int] 按创建顺序排列
        self.duration = data.duration
        self.entries = list(data.timeline)  # [SubtitleEntry]
        self.current_index = 0
        self._dead = False

    @property
    def dead(self):
        return self._dead

    def kill(self):
        """标记 session 为已终止，阻止后续条目显示。"""
        self._dead = True


# ═════════════════════════════════════════════════════════════
# SubtitleManager
# ═════════════════════════════════════════════════════════════

class SubtitleManager(object):
    """字幕状态机。

    使用方式:
      mgr = SubtitleManager(pack_root, style, settings, dispatcher)
      sound.add_marker_listener(mgr.on_marker)
      # Flash 回调:
      mgr.on_report_height(rid, height)
      mgr.on_fade_out_done(rid)
      # 清理:
      mgr.clear()
    """

    def __init__(self, pack_root, style, settings, dispatcher,
                 on_interrupt=None):
        """
        :param pack_root:  语音包 VFS 根目录，如 'mods/voiceover/my_pack/'
        :param style:      SubtitleStyle 实例（可为 None → 字幕功能不启用）
        :param settings:   dict，键:
            display_mode     — 'concise' | 'standard' | 'none'
            allow_update     — bool，同角色代号时是否更新内容而非新建
            allow_concurrent — bool，是否允许多条字幕同屏排队
            text_speed       — float，逐字出字速度（秒/字），0=瞬间
            subtitle_anim    — bool，是否允许播放额外动画（bubble/surprise/shake）
        :param dispatcher: callable(cmd_dict)，将命令发往 Flash
                           cmd_dict 格式见 _emit() 方法
        :param on_interrupt: callable(audio_key) | None
                            allow_concurrent=false 时新 session 打断旧 session
                            的回调。参数为被中断的 audio_key（marker 名），
                            供外部处理被中断的语音。
        """
        self._pack_root = pack_root
        self._style = style
        self._settings = settings
        self._dispatch = dispatcher
        self._on_interrupt = on_interrupt

        self._next_id = 1
        self._renderers = {}   # {id: RendererState}
        self._sessions = []    # [SubtitleSession]

        self._lang = style.lang if style else 'zh_cn'
        self._enabled = (style is not None
                         and settings.get('display_mode', 'standard') != 'none')

        # 加载组件位置偏移
        self._offsets = load_offsets(pack_root) if pack_root else {}

    # ═════════════════════════════════════════════════════════
    # 公开 API
    # ═════════════════════════════════════════════════════════

    def on_marker(self, marker_str):
        """Wwise marker 回调。加载句子文件，创建 session 并调度条目。

        :param marker_str: 音频内嵌名（UTF-8 字节串），用作句子文件名
        """
        if not self._enabled:
            logger.debug('字幕已禁用，忽略 marker: "%s"', marker_str)
            return
        if not marker_str:
            return

        logger.debug('收到 marker: "%s"', marker_str)
        data = load_sentence(self._pack_root, marker_str, self._lang)
        if data is None:
            logger.debug('句子文件未找到: "%s" (lang=%s)', marker_str, self._lang)
            return
        if not data.timeline:
            logger.debug('句子 %s timeline 为空，跳过', marker_str)
            return

        self._start_session(marker_str, data)

    def on_report_height(self, renderer_id, height):
        """Flash renderer 上报实际高度。

        若实际高度与预估不同，调整上下方 renderer 的位置以避免重叠或间隙。
        上方（ID 更小）同方向移动，下方（ID 更大）反方向移动。

        :param renderer_id: renderer 的 ID
        :param height:      像素高度（int/float）
        """
        state = self._renderers.get(renderer_id)
        if state is None:
            return
        try:
            height = float(height)
        except (ValueError, TypeError):
            return

        old_height = state.height if state.height > 0 else DEFAULT_SLOT_HEIGHT
        state.height = height

        # 若实际高度与预估不同，调整上方 renderer 的位置
        delta = height - old_height
        if abs(delta) < 1:
            return

        logger.debug('renderer %d 高度上报: %.0f (delta=%+.0f)',
                     renderer_id, state.height, delta)

        # 按 delta 调整上下方 renderer 的位置：
        #   - 上方（ID 更小）：同方向（实际更高→继续上移让位）
        #   - 下方（ID 更大）：反方向（实际更高→下移避免被覆盖）
        for other in self._renderers.values():
            if other.id == renderer_id:
                continue
            if other.state in ('dead', 'fading'):
                continue
            if other.id < renderer_id:
                # 上方 renderer：同方向
                if delta > 0:
                    self._emit('shift_up', other.id, distance=abs(delta))
                else:
                    self._emit('shift_down', other.id, distance=abs(delta))
            else:
                # 下方 renderer：反方向
                if delta > 0:
                    self._emit('shift_down', other.id, distance=abs(delta))
                else:
                    self._emit('shift_up', other.id, distance=abs(delta))
            other.state = 'shifting'

    def on_fade_out_done(self, renderer_id):
        """Flash renderer 淡出完成，从追踪中移除并触发下移。

        :param renderer_id: 已完成淡出的 renderer ID
        """
        state = self._renderers.pop(renderer_id, None)
        if state is None:
            return
        logger.debug('renderer %d 淡出完成', renderer_id)

        # 若允许多条字幕同屏，渲染器上方存活者下移补位
        if not self._settings.get('allow_concurrent', False):
            return

        gap = state.height if state.height > 0 else DEFAULT_SLOT_HEIGHT
        for other in self._renderers.values():
            if other.state not in ('dead', 'fading'):
                self._emit('shift_down', other.id, distance=gap)
                other.state = 'shifting'

    def clear(self):
        """清空所有字幕（切换语音包 / 离开战斗 / 禁用时调用）。"""
        self._emit('clear_all')
        for s in self._sessions:
            s.kill()
        self._sessions = []
        self._renderers.clear()
        self._next_id = 1
        logger.debug('字幕已全部清除')

    def update_settings(self, settings):
        """运行时更新设置（设置页改动后调用）。

        :param settings: 部分或全部 settings dict，会合并到现有设置中
        """
        old_enabled = self._enabled
        # 合并而非替换——设置页可能只传部分键（如 {'allow_update': True}），
        # 替换会导致 text_speed 等其余键丢失
        self._settings.update(settings)
        self._enabled = (self._style is not None
                         and self._settings.get('display_mode', 'standard') != 'none')

        if old_enabled and not self._enabled:
            self.clear()

    def update_style(self, pack_root, style):
        """切换语音包时更新样式和数据源。

        :param pack_root: 新语音包 VFS 根目录
        :param style:     新 SubtitleStyle 实例
        """
        self.clear()
        self._pack_root = pack_root
        self._style = style
        self._lang = style.lang if style else 'zh_cn'
        self._enabled = (style is not None
                         and self._settings.get('display_mode', 'standard') != 'none')
        self._offsets = load_offsets(pack_root) if pack_root else {}

    def reload_offsets(self):
        """重新加载偏移文件（字幕位置编辑保存后调用）。"""
        if self._pack_root:
            self._offsets = load_offsets(self._pack_root)
            logger.debug('偏移已重载: %d 组件', len(self._offsets))

    # ═════════════════════════════════════════════════════════
    # 内部：会话生命周期
    # ═════════════════════════════════════════════════════════

    def _start_session(self, audio_key, data):
        """创建新 session，调度其全部 timeline 条目。

        若不允许并发 → 先清空所有现有 session，并通过 on_interrupt
        回调通知外部停止旧音频。

        特殊: 若 allow_update 启用，保留现有 renderer 不清除，
        供 _show_entry 匹配角色后直接更新内容（跳过入场动画）。
        """
        if not self._settings.get('allow_concurrent', False):
            old_sessions = [s for s in self._sessions if not s.dead]

            if self._settings.get('allow_update', False):
                # allow_update 启用: 保留现有 renderer 供 _show_entry 匹配
                # 仅杀死旧 session 阻止 _end_session 触发 fade_out
                for s in old_sessions:
                    s.kill()
                self._sessions = [s for s in self._sessions if not s.dead]
            else:
                self._clear_all()

            # 通知外部中断旧音频
            if self._on_interrupt is not None:
                for old in old_sessions:
                    try:
                        self._on_interrupt(old.audio_key)
                    except Exception:
                        logger.exception('on_interrupt 回调异常')

        session = SubtitleSession(audio_key, data)
        self._sessions.append(session)

        logger.info('字幕 session 开始: %s (%d 条, %.1fs)',
                    audio_key, len(data.timeline), data.duration)

        # 调度各条目
        for i, entry in enumerate(data.timeline):
            session.current_index = i
            delay = entry.start_at
            if delay <= 0:
                self._show_entry(session, entry, i)
            else:
                BigWorld.callback(
                    delay,
                    lambda s=session, e=entry, idx=i: self._show_entry(s, e, idx)
                )

        # 调度 session 结束
        BigWorld.callback(
            data.duration,
            lambda s=session: self._end_session(s)
        )

    def _end_session(self, session):
        """Session 生命周期结束——通知所有关联 renderer 淡出。"""
        if session.dead:
            return
        session.kill()
        logger.debug('字幕 session 结束: %s', session.audio_key)

        for rid in session.renderer_ids:
            state = self._renderers.get(rid)
            if state and state.state not in ('dead', 'fading'):
                self._emit('fade_out', rid)
                state.state = 'fading'

        try:
            self._sessions.remove(session)
        except ValueError:
            pass

    def _clear_all(self):
        """立即清空所有 session 和 renderer。"""
        for rid in list(self._renderers.keys()):
            self._emit('fade_out', rid)
        self._renderers.clear()
        for s in self._sessions:
            s.kill()
        self._sessions = []
        self._next_id = 1

    # ═════════════════════════════════════════════════════════
    # 内部：条目展示
    # ═════════════════════════════════════════════════════════

    def _show_entry(self, session, entry, index):
        """展示一条 timeline 条目。

        决策树:
          1. session 已 dead → 跳过
          2. allow_update 且角色相同 → update_content（跳过入场）
          3. 否则 → shift 旧 renderer → create 新 renderer
        """
        if session.dead:
            return

        logger.debug('条目 %s[%d]: character=%s text=%s...',
                     session.audio_key, index,
                     entry.character, entry.text[:30] if entry.text else '(空)')

        # —— allow_update: 同角色 → 更新内容 ——
        if self._settings.get('allow_update', False):
            last = self._get_newest_renderer()
            if last is not None and last.character == entry.character:
                self._update_renderer(last.id, entry, session)
                return

            # 角色不同且不允许并发 → 先淡出旧 renderer 再创建新的
            if last is not None and not self._settings.get('allow_concurrent', False):
                self._emit('fade_out', last.id)
                last.state = 'fading'

        # —— 上移已有 renderer ——
        # 使用最下方 renderer 的已知高度作为上移距离，
        # 避免固定 DEFAULT_SLOT_HEIGHT 导致高 renderer 底部
        # 与新建 renderer 重叠。
        bottommost = None
        for state in self._renderers.values():
            if state.state in ('active', 'shifting', 'entering'):
                if bottommost is None or state.id > bottommost.id:
                    bottommost = state

        gap = (bottommost.height if (bottommost and bottommost.height > 0)
               else DEFAULT_SLOT_HEIGHT)
        gap += SHIFT_EXTRA_MARGIN  # 额外间隙，给淡出/入场动画留呼吸空间

        for state in self._renderers.values():
            if state.state in ('active', 'shifting', 'entering'):
                self._emit('shift_up', state.id, distance=gap)
                state.state = 'shifting'

        # —— 创建 renderer ——
        rid = self._next_id
        self._next_id += 1

        data = self._assemble_data(entry)
        self._emit('create', rid, data=data)
        self._renderers[rid] = RendererState(
            rid=rid,
            audio_key=session.audio_key,
            character=entry.character,
        )
        session.renderer_ids.append(rid)

    def _update_renderer(self, rid, entry, session):
        """更新已有 renderer 的内容。

        发送 update_content 命令 → Flash 替换文本/样式/动画，
        跳过入场动画，但额外动画照常播放（concise 模式除外）。

        同时将 renderer 从旧 session 转移到新 session，
        确保字幕的生命周期由新 session 的 duration 控制，
        而非被旧 session 在原定时间淡出（allow_concurrent=True）
        或因旧 session 已 kill 而永不淡出（allow_concurrent=False）。
        """
        data = self._assemble_data(entry)
        self._emit('update_content', rid, data=data)
        state = self._renderers.get(rid)
        if state:
            state.character = entry.character
            state.audio_key = session.audio_key

        # 将 renderer 从旧 session 转移到新 session
        for s in self._sessions:
            if rid in s.renderer_ids and s is not session:
                s.renderer_ids.remove(rid)
        if rid not in session.renderer_ids:
            session.renderer_ids.append(rid)

    # ═════════════════════════════════════════════════════════
    # 内部：数据组装
    # ═════════════════════════════════════════════════════════

    def _assemble_data(self, entry):
        """将 SubtitleEntry + SubtitleStyle → Flash 可消费的 dict。

        根据 display_mode 组装不同结构:
          - standard: poster / background / tf_title / tf_message 四层完整数据
          - concise:  单行拼接（角色名 + 冒号 + 正文），无额外动画
        """
        mode = self._settings.get('display_mode', 'standard')
        text_speed = self._settings.get('text_speed', 0.0)

        base = {
            'mode': mode,
            'text_speed': text_speed,
        }

        if mode == 'concise':
            return self._assemble_concise(entry, base)
        else:
            return self._assemble_standard(entry, base)

    def _assemble_concise(self, entry, base):
        """简洁模式：角色名 + 正文拼接，无额外动画。

        [角色名：][正文正文...]
         ←右对齐→|间隙|← 左对齐自动换行 →

        位置/宽度/间距取自 simple_mode 配置（缺省回退到 tf_messages），
        名称颜色取自 tf_titles 样式，其余（字号/字体/颜色）取自 tf_messages 样式。
        """
        name_code = entry.tf_title
        msg_style = self._style.get_tf_message(entry.tf_message)
        title_style = self._style.get_tf_title(name_code if name_code else '')
        sm = self._style.get_simple_mode()

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
        self._apply_offsets(base)

        return base

    def _assemble_standard(self, entry, base):
        """标准模式：四层完整渲染数据。

        poster / background / tf_title / tf_message 各自独立样式。
        tf_title 的文本 = 样式代号（除非样式含 img 路径→则为图片标题，文本留空）。
        """
        poster = self._style.get_poster(entry.poster)
        background = self._style.get_background(entry.background)
        tf_title = self._style.get_tf_title(entry.tf_title)
        tf_message = self._style.get_tf_message(entry.tf_message)

        # 规范化 tf_title：图片类型 → size 为 [w,h] 数组；文本类型 → 去 img
        tf_title = dict(tf_title)
        if tf_title.get('img', ''):
            if not isinstance(tf_title.get('size'), list):
                tf_title['size'] = [200, 40]
        else:
            tf_title.pop('img', None)

        # 标题文本: 样式代号即文本内容。
        # 跳过条件: ①无代号 ②图片标题 ③空字典 {}（不显示）
        title_text = ''
        if entry.tf_title and not tf_title.get('img', '') and len(tf_title) > 0:
            title_text = entry.tf_title

        base['poster'] = dict(poster)
        base['background'] = dict(background)
        base['tf_title'] = tf_title
        base['tf_title']['text'] = title_text
        base['tf_message'] = dict(tf_message)
        base['tf_message']['text'] = entry.text

        # 额外动画序列（受"字幕动画"设置控制，关闭时清空）
        # 拷贝列表而非引用：与 assembler.py 保持一致，防止复用补偿
        # 原地改写 anime_start_at 时污染 entry 原始数据。
        if self._settings.get('subtitle_anim', False):
            base['anime'] = list(entry.anime)
            base['anime_start_at'] = list(entry.anime_start_at)
        else:
            base['anime'] = []
            base['anime_start_at'] = []

        # 叠加组件位置偏移
        self._apply_offsets(base)

        return base

    # ═════════════════════════════════════════════════════════
    # 内部：辅助
    # ═════════════════════════════════════════════════════════

    def _get_newest_renderer(self):
        """获取当前激活的 renderer（ID 最大者）；无则 None。

        仅返回 state 为 entering/active/shifting 的 renderer，
        已淡出或已标记 dead 的不考虑。
        """
        best = None
        for state in self._renderers.values():
            if state.state in ('dead', 'fading'):
                continue
            if best is None or state.id > best.id:
                best = state
        return best

    def _apply_offsets(self, base):
        """将已保存的组件偏移叠加到渲染数据的 position 上。

        标准模式: poster / background / tf_title / tf_message 四个组件。
        简洁模式: concise.position 对应 simple_mode 偏移键。
        直接替换 position 列表（不修改共享的样式数据）。
        """
        off = self._offsets
        if not off:
            return

        # 简洁模式: concise.position 使用独立的 simple_mode 偏移键
        if 'concise' in base:
            c = base['concise']
            ox = off.get('simple_mode', {}).get('x', 0)
            oy = off.get('simple_mode', {}).get('y', 0)
            if ox or oy:
                c['position'] = [c['position'][0] + ox, c['position'][1] + oy]
            return

        # 标准模式: poster / background / tf_title / tf_message
        for comp_name in ('poster', 'background', 'tf_title', 'tf_message'):
            comp = base.get(comp_name)
            if not comp or not comp.get('position'):
                continue
            ox = off.get(comp_name, {}).get('x', 0)
            oy = off.get(comp_name, {}).get('y', 0)
            if ox or oy:
                # 替换为新列表，避免修改共享的样式数据
                comp['position'] = [comp['position'][0] + ox,
                                    comp['position'][1] + oy]

    def _emit(self, cmd, renderer_id=0, data=None, distance=0):
        """产出命令到 dispatcher。

        :param cmd:         命令名: 'create'|'update_content'|'shift_up'|
                                    'shift_down'|'fade_out'|'clear_all'
        :param renderer_id: 目标 renderer ID（clear_all 时忽略）
        :param data:        create/update_content 的渲染数据 dict
        :param distance:    shift_up/shift_down 的像素距离
        """
        cmd_dict = {'cmd': cmd, 'id': renderer_id}
        if data is not None:
            cmd_dict['data'] = data
        if cmd in ('shift_up', 'shift_down'):
            cmd_dict['distance'] = float(distance)

        try:
            self._dispatch(cmd_dict)
        except Exception:
            logger.exception('dispatcher 调用失败: %s id=%d', cmd, renderer_id)
