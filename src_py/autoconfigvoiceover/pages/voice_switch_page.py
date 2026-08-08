# coding=utf-8
"""VoiceSwitchPage —— 语音切换面板。

对应 Flash: com.github._25304_Oxygen.menu.pages.VoiceSwitchPage
入口: 左侧小圆导航按钮 #1（voiceSwitch）

功能:
  语音包选择    — 两个选项卡（游戏内置 / 已安装），点击列表项立即切换
  语音包切换    — 切换后自动保存状态到配置文件
  音量调节      — 拖动滑块实时生效
  试听声音      — 下拉选事件 → 点击播放 → Wwise playSound2D

Flash 交互 → Python 回调（通过 onLog 前缀匹配）:
  voiceSelect,<voiceID>    — 用户点击列表项
  volumeChange,<0-100>     — 用户拖动音量滑块
  preview,<eventID>        — 用户点击播放按钮
  changeType,<index>       — 用户切换"更改类型"下拉（仅游戏内置选项卡）
  changeLang,<index>       — 用户切换"更改语言"下拉（仅游戏内置选项卡）
"""

from autoconfigvoiceover.logger import Logger

logger = Logger('VoiceSwitchPage')


# ═════════════════════════════════════════════════════════════
# VoiceSwitchPage
# ═════════════════════════════════════════════════════════════

class VoiceSwitchPage(object):
    """语音切换页的业务逻辑。

    持有两个语音包列表（游戏内置 / 已安装），当前激活的语音包 ID，
    当前音量和试听事件列表。用户操作通过 onLog 回调分发到对应方法。
    """

    def __init__(self, meta):
        """
        :param meta: ACVMenuMeta 实例，用于 DAAPI 通信
        """
        self._meta = meta

        # ── 语音包数据 ──
        self._ingame_voices = []
        self._outside_voices = []
        self._current_voice_id = ''

        # ── 音量 ──
        self._volume = 50

        # ── 试听事件 ──
        self._preview_events = []

        # ── "更改类型" / "更改语言" 当前选中索引 ──
        self._type_index = 0
        self._lang_index = 0

    # ═════════════════════════════════════════════════════════
    # 数据推送 → Flash
    # ═════════════════════════════════════════════════════════

    def push_data(self):
        """向 Flash 推送语音切换页全部初始数据。

        在 __menuReady__ 信号触发后由 MenuManager 调用。
        一次性打包: 两个语音包列表、当前激活语音、音量、试听事件、Tooltip。
        """
        # ── 从语音包仓库加载真实数据 ──
        self._load_data()

        # ── ACV 面板始终显示全部语音包，不受游戏菜单可见性设置影响 ──
        #     showIngameVoices/showInstalledVoices 仅控制游戏自带声音设置菜单
        #     中的下拉列表条目（apply_voice_visibility），与 ACV 面板无关。
        ingame_voices = self._ingame_voices
        outside_voices = self._outside_voices

        # type/lang 选项从当前活跃语音动态生成
        from autoconfigvoiceover.voices import voice_switcher
        type_items, lang_items = voice_switcher.get_type_lang_options(
            self._current_voice_id)

        # 确定当前 source（所在面板），用于 Flash 恢复选项卡状态
        source = 'ingame'
        for vo in self._outside_voices:
            if vo['voiceID'] == self._current_voice_id:
                source = 'outside'
                break

        # 字幕按钮可见性——与语音切换数据一起推送，避免独立 DAAPI 调用失败
        # 时按钮状态不确定。★ GFx 无法序列化 Python bool，传 1/0。
        available = self._get_subtitle_availability()
        data = {
            'source':         source,
            'ingameVoices':   ingame_voices,
            'outsideVoices':  outside_voices,
            'currentVoiceId': self._current_voice_id,
            'volume':         self._volume,
            'previewEvents':  self._preview_events,
            'typeItems':      type_items,
            'typeIndex':      self._type_index,
            'langItems':      lang_items,
            'langIndex':      self._lang_index,
            'tooltipHtml':    self._get_tooltip_html(),
            'tooltips':       self._get_label_tooltips(),
            'subtitleAvailable': 1 if available else 0,
        }
        self._meta.as_populateVoiceSwitchesS(data)
        logger.info('语音切换页数据已推送 (%d + %d 语音包, %d 试听事件)',
                    len(ingame_voices), len(outside_voices),
                    len(self._preview_events))

        # 同步更新半折叠面板标题为当前语音包显示名称
        display_name = self._current_voice_id
        for vo in self._ingame_voices + self._outside_voices:  # 全量查找（含被过滤的）
            if vo['voiceID'] == self._current_voice_id:
                display_name = vo.get('nickName', self._current_voice_id)
                break
        self._meta.as_setTitleTextS(display_name)

    def _get_subtitle_availability(self):
        """检查当前语音包的字幕可用性，返回 bool。"""
        from autoconfigvoiceover.voices import g_active_mgr
        from autoconfigvoiceover.subtitle.loader import is_subtitle_available

        active = g_active_mgr.current
        if active is None or active.is_builtin:
            return False
        return is_subtitle_available(active.pack.root)

    def _sync_subtitle_availability(self):
        """通过独立 DAAPI 调用通知 Flash 更新"字幕"按钮（供外部调用）。

        常规流程应走 push_data() 数据推送通道；
        此方法用于 sound.py 等外部模块在语音切换后同步状态。
        """
        available = self._get_subtitle_availability()
        self._meta.as_setSubtitleAvailableS(available)
        logger.debug('字幕可用性: %s', available)

    # ═════════════════════════════════════════════════════════
    # 回调处理（Flash → Python）
    # ═════════════════════════════════════════════════════════

    def handle_voice_select(self, voice_id):
        """用户点击列表项，执行语音切换。

        内置语音含类型/语言变体：切换至新语音时重置下拉索引为 0；
        点击已激活语音时保留当前 type/lang 索引（仅播放确认音，
        不改变类型/语言设置）。

        重复点击同一语音包：不发送通知、不触发翻转动画。
        """
        # 已激活语音 → 保留类型/语言索引，仅播放确认音
        same_voice = (voice_id == self._current_voice_id)
        if same_voice:
            type_idx = self._type_index
            lang_idx = self._lang_index
        else:
            type_idx = 0
            lang_idx = 0

        self._type_index = type_idx
        self._lang_index = lang_idx

        from autoconfigvoiceover.voices import voice_switcher

        success = voice_switcher.switch_voice(voice_id, type_idx, lang_idx)
        if not success:
            logger.warn('语音切换失败: %s', voice_id)
            # 失败通知
            from autoconfigvoiceover.notifier import notify_voice_switch
            notify_voice_switch(self._get_voice_display_name(voice_id),
                               success=False)
            return

        # ── 更新激活标记（1/0，PyGFxValue 不支持布尔值）──
        for vo in self._ingame_voices:
            vo['active'] = 1 if vo['voiceID'] == voice_id else 0
        for vo in self._outside_voices:
            vo['active'] = 1 if vo['voiceID'] == voice_id else 0
        self._current_voice_id = voice_id

        # 试听列表跟随活跃语音变化
        from autoconfigvoiceover.voices import g_active_mgr
        if g_active_mgr.current is not None:
            self._preview_events = [dict(evt) for evt in g_active_mgr.current.events]

        # ── 更新音量步进器 ──
        # autoVolume 开启：Wwise 已被 switch_voice 修改，步进条同步到预设音量
        # autoVolume 关闭：Wwise 未变，步进条保持当前实际音量
        from autoconfigvoiceover.config import load_config
        from autoconfigvoiceover.voices import g_voice_repo
        if load_config().get('settings', {}).get('autoVolume', True):
            for row in g_voice_repo.ingame_rows + g_voice_repo.outside_rows:
                if row.get('voiceID') == voice_id:
                    self._volume = row.get('volume', 50)
                    break
        else:
            import SoundGroups
            self._volume = int(SoundGroups.g_instance.getVolume('voice') * 100)

        # 持久化：记住重启后恢复的选择
        source = 'ingame'
        for vo in self._outside_voices:
            if vo['voiceID'] == voice_id:
                source = 'outside'
                break
        from autoconfigvoiceover.config import save_config
        save_config({'voice': {
            'currentVoiceId': voice_id,
            'source': source,
            'typeIndex': self._type_index,
            'langIndex': self._lang_index,
        }})

        # 刷新 Flash（含新的 typeItems/langItems、active 标记、试听列表、音量）
        self.push_data()

        # 若颜色方案设为"跟随语音包"，切语音后重切主题
        self._reapply_theme_if_following_pack()

        # ── 切换语音后的大圆翻转动画（仅切换不同语音时触发）──
        if not same_voice:
            self._trigger_big_circle_flip(voice_id)

        # ── 刷新语音包相关的全部 UI（图片 + 详情页）──
        if not same_voice:
            from autoconfigvoiceover.menu import refresh_voice_pack_ui
            refresh_voice_pack_ui()

        # ── 语音切换通知（重复点击不通知）──
        if not same_voice:
            from autoconfigvoiceover.notifier import notify_voice_switch
            notify_voice_switch(self._get_voice_display_name(voice_id),
                               success=True)

    def handle_volume_change(self, volume):
        """用户拖动音量滑块：设置 voice 通道音量 + 回写对应语音行的音量。"""
        volume = int(volume)
        self._volume = volume

        from autoconfigvoiceover.voices import voice_switcher, g_voice_repo

        voice_switcher.set_voice_volume(volume)

        # 回写到对应行（内存态，供本次会话 _apply_voice_volume 使用）
        for row in (g_voice_repo.ingame_rows + g_voice_repo.outside_rows):
            if row.get('voiceID') == self._current_voice_id:
                row['volume'] = volume
                break

        # 即时落盘到所属 JSON 文件（内置 → gameSoundModes.json，
        # 第三方 → voiceover.json）
        g_voice_repo.persist_volume(self._current_voice_id)

    def handle_preview(self, event_id):
        """用户点击播放按钮，试听某个声音事件。

        先停上一个试听/确认音再播新的（持 getSound2D 引用可 stop）。
        bnk 未加载时 getSound2D 返回 None → warn。
        """
        # 找到事件显示名用于日志（字段约定与 playEvent.json 一致: text/event）
        event_name = event_id
        for evt in self._preview_events:
            if evt.get('event') == event_id:
                event_name = evt.get('text', event_id)
                break

        # DEBUG：试听为用户可见的即时反馈，无需每次点击都留 INFO
        logger.debug('试听播放: %s (%s)', event_name, event_id)

        from autoconfigvoiceover.voices import voice_switcher
        voice_switcher.play_preview(event_id)

    def handle_change_type(self, index_str):
        """用户切换"更改类型"下拉——用新类型索引重解析模式名并重切。"""
        try:
            index = int(index_str)
        except (ValueError, TypeError):
            logger.warn('无效的类型索引: %s', index_str)
            return

        from autoconfigvoiceover.voices import voice_switcher
        type_items, lang_items = voice_switcher.get_type_lang_options(
            self._current_voice_id)
        if index < 0 or index >= len(type_items):
            # 选项数可能比上次推送时少（切换语音后 Flash 仍用旧列表）
            index = 0

        success = voice_switcher.switch_voice(self._current_voice_id, index,
                                               self._lang_index)
        if not success:
            logger.warn('更改类型后切换失败: voiceID=%s type=%d',
                        self._current_voice_id, index)
            from autoconfigvoiceover.notifier import notify_voice_switch
            notify_voice_switch(self._get_voice_display_name(
                self._current_voice_id), success=False)
            return

        self._type_index = index
        self._persist_voice_state()
        self.push_data()

        from autoconfigvoiceover.notifier import notify_voice_switch
        notify_voice_switch(self._get_voice_display_name(
            self._current_voice_id), success=True)

    def handle_change_lang(self, index_str):
        """用户切换"更改语言"下拉——用新语言索引重解析模式名并重切。"""
        try:
            index = int(index_str)
        except (ValueError, TypeError):
            logger.warn('无效的语言索引: %s', index_str)
            return

        from autoconfigvoiceover.voices import voice_switcher
        type_items, lang_items = voice_switcher.get_type_lang_options(
            self._current_voice_id)
        if index < 0 or index >= len(lang_items):
            index = 0

        success = voice_switcher.switch_voice(self._current_voice_id,
                                               self._type_index, index)
        if not success:
            logger.warn('更改语言后切换失败: voiceID=%s lang=%d',
                        self._current_voice_id, index)
            from autoconfigvoiceover.notifier import notify_voice_switch
            notify_voice_switch(self._get_voice_display_name(
                self._current_voice_id), success=False)
            return

        self._lang_index = index
        self._persist_voice_state()
        self.push_data()

        from autoconfigvoiceover.notifier import notify_voice_switch
        notify_voice_switch(self._get_voice_display_name(
            self._current_voice_id), success=True)

    def _persist_voice_state(self):
        """保存当前语音选择到配置文件（切换语音/更改类型/更改语言后调用）。"""
        source = 'ingame'
        for vo in self._outside_voices:
            if vo['voiceID'] == self._current_voice_id:
                source = 'outside'
                break
        from autoconfigvoiceover.config import save_config
        save_config({'voice': {
            'currentVoiceId': self._current_voice_id,
            'source': source,
            'typeIndex': self._type_index,
            'langIndex': self._lang_index,
        }})

    def _reapply_theme_if_following_pack(self):
        """若当前颜色方案为"跟随语音包"，重切主题。

        从配置文件读取 colorScheme（避免耦合 SettingsPage 实例），
        委托 settings_page 模块级 resolve_theme() 解析色板。
        """
        try:
            from autoconfigvoiceover.config import load_config
            from .settings_page import (
                resolve_theme, FOLLOW_PACK_TOKEN)
            color_scheme = load_config().get('settings', {}).get(
                'colorScheme', FOLLOW_PACK_TOKEN)
        except Exception:
            return
        if color_scheme != FOLLOW_PACK_TOKEN:
            return
        self._meta.as_applyThemeS(resolve_theme(FOLLOW_PACK_TOKEN))

    def _trigger_big_circle_flip(self, voice_id):
        """切换语音包后触发大圆翻转动画。

        翻转至中点（scaleX=0）时替换大圆图片：
        - 若新语音包 VFS 中有 bgimgs/menu.png → 切换到该图片
        - 否则 → 切换回默认 menu.png（磁盘优先，VFS 兜底）

        每次切换不同语音包都执行翻转+替换，保证从有自定义 menu.png
        的语音包切换到没有的语音包时也有翻转效果（换回默认图）。
        """
        try:
            import ResMgr
            from autoconfigvoiceover.voices import g_active_mgr
            from autoconfigvoiceover.config_init import get_user_resource_flash_path

            active = g_active_mgr.current
            if active is None or active.is_builtin:
                image_path = get_user_resource_flash_path('bgimgs', 'menu.png')
                logger.debug('翻转: 内置语音 → 默认图 %s', image_path)
            else:
                vfs_path = active.pack.root + 'bgimgs/menu.png'
                logger.debug('翻转: 检查语音包图片 %s', vfs_path)
                if ResMgr.isFile(vfs_path):
                    # Flash ImageCache 从 res/gui/flash/ 加载，
                    # ../../ + VFS路径 → res/mods/voiceover/.../bgimgs/menu.png
                    image_path = '../../' + vfs_path
                    logger.info('翻转: 使用语音包自定义图片 %s', image_path)
                else:
                    image_path = get_user_resource_flash_path('bgimgs', 'menu.png')
                    logger.debug('翻转: VFS 无 %s，回退默认图 %s',
                                vfs_path, image_path)

            # ★ GFx 需要 unicode 字符串
            if isinstance(image_path, str):
                image_path = image_path.decode('utf-8')
            self._meta.as_flipBigCircleS(image_path)
        except Exception:
            logger.exception('大圆翻转失败')

    def _get_voice_display_name(self, voice_id):
        """从页面持有的语音列表中查找 voiceID 对应的显示名称。"""
        for vo in self._ingame_voices + self._outside_voices:
            if vo.get('voiceID') == voice_id:
                return vo.get('nickName', voice_id)
        return voice_id

    # ═════════════════════════════════════════════════════════
    # 数据加载（来源：voices.g_voice_repo 内存数据库）
    # ═════════════════════════════════════════════════════════

    def _load_data(self):
        """从语音包仓库拉取列表数据（页面持有自己的副本并附加 active 标记）。

        首次调用时一次性拉取（页面生命周期内不再刷新原始列表）；
        试听事件取自当前活跃语音（全局 playEvent + 包内 events.json
        增量合并）；更新语音后由 handle_voice_select / handle_change_*
        驱动 push_data 重推 Flash。
        """
        # 首次加载才拉取，避免覆盖运行时状态（如用户刚点过的 active）
        if self._ingame_voices or self._outside_voices:
            return

        from autoconfigvoiceover.voices import g_voice_repo, g_active_mgr

        # 页面副本：repo 行是共享引用，active 标记只属于本页面
        # （active 必须用 1/0，PyGFxValue 无法序列化 Python 布尔值）
        self._ingame_voices = [dict(row, active=0)
                               for row in g_voice_repo.ingame_rows]
        self._outside_voices = [dict(row, active=0)
                                for row in g_voice_repo.outside_rows]

        # 类型/语言索引从持久化配置恢复（首次 init 时写入的默认值）
        from autoconfigvoiceover.config import load_config
        voice_cfg = load_config().get('voice', {})
        self._type_index = voice_cfg.get('typeIndex', 0)
        self._lang_index = voice_cfg.get('langIndex', 0)

        # 试听列表 + 激活项从活跃语音管理器取
        active_voice = g_active_mgr.current
        if active_voice is not None:
            self._preview_events = [dict(evt) for evt in active_voice.events]
            active_id = active_voice.voice_id
        else:
            self._preview_events = [dict(evt) for evt in g_voice_repo.play_events]
            active_id = ''

        # ── 纵深防御：ActiveVoice 丢失或被污染时自动修正 ──
        # 录像回放 / 场景切换期间游戏反复调 setMode('default') 可能
        # 导致 ActiveVoice 丢失（current=None）或被设为 default。
        # 上游 setMode/mapping 钩子已做重定向，此处兜底确保打开菜单
        # 时自愈，同时修正 _current_resolved_mode（战斗兜底依赖此值）。
        saved_id = voice_cfg.get('currentVoiceId', '')
        if saved_id and saved_id != 'default':
            if active_voice is None or active_voice.voice_id == 'default':
                reason = '未初始化' if active_voice is None else '被污染为 default'
                logger.warn('ActiveVoice %s（期望 %s），自动修正',
                            reason, saved_id)
                from autoconfigvoiceover.voices import voice_switcher
                if voice_switcher.switch_voice(saved_id, self._type_index,
                                               self._lang_index, silent=True):
                    # 重读修正后的数据
                    active_voice = g_active_mgr.current
                    if active_voice is not None:
                        self._preview_events = [dict(evt)
                                                for evt in active_voice.events]
                        active_id = active_voice.voice_id

        # 音量：优先取当前语音行的音量，否则用 voice 通道音量
        self._volume = g_voice_repo.current_volume
        for row in g_voice_repo.ingame_rows + g_voice_repo.outside_rows:
            if row.get('voiceID') == active_id and 'volume' in row:
                self._volume = row['volume']
                break

        # 激活标记
        self._current_voice_id = ''
        for vo in self._ingame_voices + self._outside_voices:
            if vo['voiceID'] == active_id:
                vo['active'] = 1
                self._current_voice_id = active_id
                break
        # ActiveVoice 丢失（录像回放等）→ 优先从配置恢复 saved_id
        if not self._current_voice_id and saved_id and saved_id != 'default':
            for vo in self._ingame_voices + self._outside_voices:
                if vo['voiceID'] == saved_id:
                    vo['active'] = 1
                    self._current_voice_id = saved_id
                    logger.warn('ActiveVoice 丢失，从配置恢复: %s', saved_id)
                    break
        if not self._current_voice_id and self._ingame_voices:
            self._ingame_voices[0]['active'] = 1
            self._current_voice_id = self._ingame_voices[0]['voiceID']

        logger.debug('数据已加载: %d + %d 语音包, %d 试听事件, 音量 %d, '
                     '激活=%s type=%d lang=%d',
                     len(self._ingame_voices), len(self._outside_voices),
                     len(self._preview_events), self._volume,
                     self._current_voice_id, self._type_index,
                     self._lang_index)

    # ═════════════════════════════════════════════════════════
    # Tooltip（后续可能根据页面状态动态生成）
    # ═════════════════════════════════════════════════════════

    def _get_tooltip_html(self):
        """标题 Tooltip 富文本 HTML（随生效语言）。"""
        from autoconfigvoiceover import l10n
        return l10n.text('voice_switch/tooltip/title')

    def _get_label_tooltips(self):
        """右列"更改类型"/"更改语言"标签的 Tooltip 富文本（随生效语言）。"""
        from autoconfigvoiceover import l10n
        return {
            'changeType': l10n.text('voice_switch/tooltip/change_type'),
            'changeLang': l10n.text('voice_switch/tooltip/change_lang'),
        }
    