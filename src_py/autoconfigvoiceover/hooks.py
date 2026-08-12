# coding=utf-8
"""ACV 游戏生命周期钩子。

此模块被 import 时即注册回调；不需要手动调用任何函数。

当前挂载：
  - SpecialSoundCtrl.setPlayerVehicle override：精准识别特殊车长并强制拉回
    ACV 选择；普通成员放行，允许游戏菜单自由切换
  - _ReceivedCmdDecorator.getCommandText override：替换公屏快捷喊话文本
    在显示端拦截，按原始逻辑加 key 后缀后匹配用户自定义替换
  - SixthSenseMeta.as_showS override：第六感触发 → 自动发送被点亮喊话
"""

from .logger import Logger
from .utils import override

logger = Logger('Hooks')

# ═════════════════════════════════════════════════════════════
# 1. setPlayerVehicle 兜底
# ═════════════════════════════════════════════════════════════

from gui.game_control.special_sound_ctrl import SpecialSoundCtrl  # noqa: E402
from gui.battle_control import avatar_getter  # noqa: E402


@override(SpecialSoundCtrl, 'setPlayerVehicle')
def _new_setPlayerVehicle(original_func, self, vehiclePublicInfo, isPlayerVehicle):
    """进战场时只有游戏激活了特殊语音才掰回 ACV 选择。

    普通成员 → 不干预（游戏菜单可自由切换，setMode 钩子放行）。
    特殊车长 → 强制拉回 + setMode 钩子拦截后续游戏的持续 enforcement。

    延迟导入避免模块级循环依赖。
    """
    from autoconfigvoiceover.voices import voice_switcher

    # ── 战斗开始：重置标志 ──
    if isPlayerVehicle:
        voice_switcher.enter_battle()  # _in_battle=True, _has_special_crew=False
        # ── 回放模式不触发走 onAccountBecomePlayer，进战斗时补齐 ActiveVoice 激活 ──
        voice_switcher.ensure_active_voice()

    # ── 抑制钩子：original_func 内部的 setMode/mapping 调用
    #     不是用户操作，不应触发外部切换同步 ──
    voice_switcher._suppress_setmode_hook = True
    try:
        original_func(self, vehiclePublicInfo, isPlayerVehicle)
    finally:
        voice_switcher._suppress_setmode_hook = False

    # ── 旁观者 → 不干预，听被观察者的语音 ──
    if not isPlayerVehicle:
        return

    # ── 记录本场战斗是否有特殊车长（供 setMode 钩子参考）──
    voice_switcher._has_special_crew = (self.specialVoice is not None)

    from .config import is_enabled
    if not is_enabled():
        return

    arena = avatar_getter.getArena()
    if arena is None:
        logger.debug('setPlayerVehicle: arena 尚未就绪，跳过语音守护和字幕加载')
        return

    # ── 普通成员 → 放行（游戏菜单可自由切换）──
    if self.specialVoice is None:
        logger.debug('setPlayerVehicle: 普通成员，放行')
        _load_subtitle_view()
        return

    # ── 特殊车长 → 首次强制掰回，后续由 setMode 钩子持续守护 ──
    from autoconfigvoiceover.voices.voice_switcher import get_current_mode_name
    import SoundGroups

    mode_name = get_current_mode_name()
    if mode_name:
        logger.debug('setPlayerVehicle: 特殊车长 specialVoice=%s → 强制拉回 %s',
                     self.specialVoice.languageMode, mode_name)
        SoundGroups.g_instance.soundModes.setMode(mode_name)

    _load_subtitle_view()


@override(SpecialSoundCtrl, '_SpecialSoundCtrl__setSpecialVoice')
def _new_setSpecialVoice(original_func, self, params):
    """源点替换特殊车长语音的 languageMode，让 GUP 字幕跟随 ACV 选择。

    推测 GUP 字幕引擎对特殊车长按 SpecialSoundCtrl.specialVoice
    （即 __currentMode）选择字幕；普通车长 specialVoice 为 None，
    它才退而读 soundModes.currentMode。此前我们只强制 setMode 
    只改了 currentMode，改不动 __currentMode，所以特殊车长的字幕
    永远按真实车长语音显示

    这里在 __setSpecialVoice 的入口把 params.languageMode 换成 ACV
    解析出的模式，让游戏自身把特殊语音伪装成 ACV 选择。
    """
    from autoconfigvoiceover.config import is_enabled
    from autoconfigvoiceover.voices import voice_switcher
    if voice_switcher._in_battle and is_enabled():
        mode_name = voice_switcher.get_current_mode_name()
        if mode_name and mode_name != 'default':
            try:
                params = params._replace(languageMode=mode_name)
            except Exception:
                logger.exception('替换特殊语音 languageMode 失败，保持原样')
    return original_func(self, params)


def _load_subtitle_view():
    """尝试加载字幕 View。"""
    try:
        from autoconfigvoiceover.subtitle.host import ensure_subtitle_view
        ensure_subtitle_view()
        logger.debug('字幕 View 加载流程完成')
    except Exception:
        logger.exception('字幕 View 加载失败')


logger.debug('已注册 SpecialSoundCtrl.setPlayerVehicle override（语音守护）')


# ═════════════════════════════════════════════════════════════
# _safe_format —— 格式化辅助
# ═════════════════════════════════════════════════════════════

def _safe_format(text, kw):
    """安全格式化：预处理 float→int 以兼容 %d/%i/%u 格式符。

    wulf.getTranslatedText (C++) 遇到 %(floatArg1)d 且值为 float 时自动
    截断成 int，但 Python 的 % 运算符会抛 TypeError。此函数预先将 %d/%i/%u
    格式符对应的 float 值转换为 int，避免异常。

    无占位符的纯文本（如"收到！"）直接返回。
    """
    try:
        return text % kw
    except TypeError:
        import re
        int_keys = set(re.findall(r'%\((\w+)\)[diu]', text))
        if not int_keys:
            raise
        safe_kw = dict(kw)
        for k in int_keys:
            if k in safe_kw and isinstance(safe_kw[k], float):
                safe_kw[k] = int(safe_kw[k])
        return text % safe_kw


# ═════════════════════════════════════════════════════════════
# 2. _ReceivedCmdDecorator.getCommandText override
#    在显示端拦截快捷喊话文本，替换为用户自定义内容。
#
#    为什么选显示端而非发送端：
#      - 发送端 createByName 只能阻止原生命令→另发 broadcast
#        （纯文本在战斗中显示不可靠、走屏蔽词过滤、消耗冷却）
#      - 显示端 getCommandText 直接替换渲染文本，原生命令照常
#        发送，服务器/队友不受影响，仅本地方可见替换效果
# ═════════════════════════════════════════════════════════════

try:
    from messenger.proto.bw_chat2.battle_chat_cmd import _ReceivedCmdDecorator  # noqa: E402
    from messenger_common_chat2 import MESSENGER_ACTION_IDS as _ACTIONS2  # noqa: E402
    from gui.Scaleform.locale.INGAME_GUI import INGAME_GUI as I18N_INGAME_GUI  # noqa: E402

    @override(_ReceivedCmdDecorator, 'getCommandText')
    def _new_getCommandText(original_func, self):
        """在原始 getCommandText 之前检查是否有用户自定义替换。

        关键：必须先按原始逻辑给 i18nKey 加后缀（_reloading/_empty/
        _numbered/_gridInfo），再用后缀 key 查 get_replacement()，
        否则与设置页的 key 对不上。
        """
        from .config import is_enabled
        if not is_enabled():
            return original_func(self)

        command = _ACTIONS2.battleChatCommandFromActionID(self._commandID)
        if command is None or not command.msgText:
            return original_func(self)

        i18nKey = I18N_INGAME_GUI.chat_shortcuts(command.msgText)
        if not i18nKey:
            return original_func(self)

        # 仅替换自己发出的快捷消息，队友的消息原样显示
        if not self.isSender():
            return original_func(self)

        # ── 声音绑定：玩家发送快捷指令时触发对应音效 ──
        try:
            from .sound import g_binding_engine
            g_binding_engine.on_command(i18nKey)
        except Exception:
            pass

        try:
            from autoconfigvoiceover.pages.personal_settings_page import get_replacement
            result = None

            # ── 按原始逻辑：构建参数 + key 后缀 + 查替换 ──
            if self.isOnMinimap():
                i18n_args = {}
                if self.isSPGAimCommand():
                    reloadTime = self._protoData['floatArg1']
                    if reloadTime > 0:
                        i18n_args['reloadTime'] = reloadTime
                        i18nKey += '_reloading'
                replacement = get_replacement(i18nKey)
                if replacement:
                    result = _safe_format(replacement, i18n_args)

            elif self.hasTarget():
                i18n_args = {'target': self._getTarget()}
                if self.isSPGAimCommand():
                    reloadTime = self._protoData['floatArg1']
                    if reloadTime > 0:
                        i18n_args['reloadTime'] = reloadTime
                        i18nKey += '_reloading'
                    elif reloadTime < 0:
                        i18nKey += '_empty'
                replacement = get_replacement(i18nKey)
                if replacement:
                    result = _safe_format(replacement, i18n_args)

            elif self.isBaseRelatedCommand():
                i18n_args = {}
                strArg = self._protoData['strArg1']
                if strArg != '':
                    i18n_args['strArg1'] = strArg
                    i18nKey += '_numbered'
                replacement = get_replacement(i18nKey)
                if replacement:
                    result = _safe_format(replacement, i18n_args)

            elif self.isLocationRelatedCommand():
                i18n_args = {}
                if self.isSPGAimCommand():
                    reloadTime = self._protoData['floatArg1']
                    if reloadTime > 0:
                        i18n_args['reloadTime'] = reloadTime
                        i18nKey += '_reloading'
                    elif reloadTime < 0:
                        i18nKey += '_empty'
                sessionProvider = self.sessionProvider
                if sessionProvider is not None:
                    mapsCtrl = sessionProvider.dynamic.maps
                    if mapsCtrl is not None and mapsCtrl.hasMinimapGrid():
                        cellId = mapsCtrl.getMinimapCellIdByPosition(
                            self.getMarkedPosition())
                        if cellId is not None:
                            i18n_args['gridId'] = mapsCtrl.getMinimapCellNameById(cellId)
                            i18nKey += '_gridInfo'
                replacement = get_replacement(i18nKey)
                if replacement:
                    result = _safe_format(replacement, i18n_args)

            else:
                # 简单命令（affirmative, negative, thanks 等）无后缀
                replacement = get_replacement(i18nKey)
                if replacement:
                    result = _safe_format(replacement, self._protoData)

            if replacement:
                logger.info('快捷喊话已替换: %s → "%s"', i18nKey, result)
                return result

        except Exception:
            logger.debug('getCommandText 替换失败 cmdID=%s', self._commandID, exc_info=True)

        return original_func(self)

    logger.debug('已注册 _ReceivedCmdDecorator.getCommandText override（快捷喊话替换）')
except ImportError:
    logger.info('_ReceivedCmdDecorator 导入失败（非战斗场景），跳过 getCommandText override')
except Exception:
    logger.exception('注册 getCommandText override 失败')


# ═════════════════════════════════════════════════════════════
# 3. 第六感钩子 —— 被点亮时自动发送自定义消息
# ═════════════════════════════════════════════════════════════

# 第六感最短 12 秒触发一次，无需额外冷却

# ═════════════════════════════════════════════════════════════
# 坐标字母同形映射 —— 用 Unicode 视觉同形字替换 ASCII 字母，
# 绕过服务器屏蔽词过滤（坐标如 G8 中的英文字母可能被误杀）
# ═════════════════════════════════════════════════════════════

_HOMOGLYPH_MAP = {
    'A': 'Α',   # Greek Alpha
    'B': 'Β',   # Greek Beta
    'C': 'С',   # Cyrillic Es
    'E': 'Ε',   # Greek Epsilon
    'G': 'ɡ',   # Latin small script G (U+0261)
    'H': 'Η',   # Greek Eta
    'I': 'Ι',   # Greek Iota
    'K': 'Κ',   # Greek Kappa
}


def _replace_grid_chars(grid_name):
    """将坐标名中的 ASCII 字母替换为 Unicode 同形字以绕过屏蔽。

    例如 "A1" → "Α1", "K7" → "Κ7"。
    无映射的字母（D、F、J）保持原样。
    """
    if not grid_name:
        return grid_name
    result = grid_name
    for ascii_ch, homo in _HOMOGLYPH_MAP.items():
        result = result.replace(ascii_ch, homo)
    return result


def _get_player_grid_name():
    """返回玩家当前所在的小地图坐标名（如 "A1"），无数据时返回空字符串。"""
    try:
        vehicle = avatar_getter.getPlayerVehicle()
        if vehicle is None:
            return ''

        from helpers import dependency
        from skeletons.gui.battle_session import IBattleSessionProvider
        sessionProvider = dependency.instance(IBattleSessionProvider)
        if sessionProvider is None:
            return ''

        mapsCtrl = sessionProvider.dynamic.maps
        if mapsCtrl is None or not mapsCtrl.hasMinimapGrid():
            return ''

        cellId = mapsCtrl.getMinimapCellIdByPosition(vehicle.position)
        if cellId is None:
            return ''

        return mapsCtrl.getMinimapCellNameById(cellId)
    except Exception:
        logger.exception('获取小地图坐标失败')
        return ''


def _count_alive_teammates():
    """返回当前存活队友数（包括自己）。"""
    try:
        arena = avatar_getter.getArena()
        if arena is None:
            return 15  # 无数据时返回很大值，永不触发条件

        playerVID = avatar_getter.getPlayerVehicleID()
        playerInfo = arena.vehicles.get(playerVID, {})
        playerTeam = playerInfo.get('team', -1)
        if playerTeam == -1:
            return 15
        alive = 0
        for vInfo in arena.vehicles.values():
            if vInfo.get('isAlive') and vInfo.get('team') == playerTeam:
                alive += 1
        return alive
    except Exception:
        logger.exception('统计存活队友数失败')
        return 15


def _send_team_message(text):
    """向队内频道发送纯文本消息。

    走 arenaChat.broadcast() → 经 filterOutMessage（长度/洪水过滤）
    → 服务器端屏蔽词处理。无法绕过。
    """
    if not text:
        return
    try:
        from messenger.proto import _SUPPORTED_PROTO_PLUGINS
        from messenger.m_constants import PROTO_TYPE
        proto = _SUPPORTED_PROTO_PLUGINS.get(PROTO_TYPE.BW_CHAT2)
        if proto is None or proto.arenaChat is None:
            logger.warn('messenger proto 不可用，喊话发送失败')
            return
        proto.arenaChat.broadcast(text)
        logger.info('已发送队内消息: %s', text)
    except Exception:
        logger.exception('发送队内消息失败')


def _check_and_send_spotted_message():
    """第六感触发 → 检查条件 → 自动发送自定义被点亮喊话。"""
    try:
        # 玩家自己的车已阵亡 → 死亡观战/幽灵状态，第六感属于被观战车 → 不喊话
        if not avatar_getter.isVehicleAlive():
            return
        # 训练模式旁观者阵营（自由摄像头，车辆带 observer 标志）→ 不喊话
        if avatar_getter.isObserver():
            return

        from autoconfigvoiceover.pages.personal_settings_page import get_spotted_config
        spottedMsg, spottedAliveLe = get_spotted_config()

        # 用户未设置喊话内容 → 跳过
        if not spottedMsg or not spottedMsg.strip():
            return

        arena = avatar_getter.getArena()
        if arena is None:
            return

        # 存活队友数条件
        aliveCount = _count_alive_teammates()
        if aliveCount > spottedAliveLe:
            logger.debug('存活队友 %d > 阈值 %d，跳过喊话', aliveCount, spottedAliveLe)
            return

        # 替换坐标占位符 <a> → 实际小地图坐标（字母用同形字绕过屏蔽）
        gridName = _get_player_grid_name()
        gridName = _replace_grid_chars(gridName)
        message = spottedMsg.replace('<a>', gridName) if gridName else spottedMsg

        _send_team_message(message)
        logger.info('第六感喊话已发送: "%s" (队友=%d)', message, aliveCount)
    except Exception:
        logger.exception('第六感喊话处理失败')


try:
    from gui.Scaleform.daapi.view.meta.SixthSenseMeta import SixthSenseMeta  # noqa: E402

    @override(SixthSenseMeta, 'as_showS')
    def _new_sixth_sense_show(original_func, self):
        """第六感灯泡亮起 → 顺便检查并发送自定义喊话。"""
        from .config import is_enabled
        if is_enabled():
            _check_and_send_spotted_message()
        return original_func(self)

    logger.debug('已注册 SixthSenseMeta.as_showS override（被点亮喊话）')
except ImportError:
    logger.info('SixthSenseMeta 导入失败（非战斗场景），跳过第六感钩子')
except Exception:
    logger.exception('注册 SixthSenseMeta override 失败')


# ═════════════════════════════════════════════════════════════
# 4. PlayerAvatar.onBecomeNonPlayer —— 离开战斗时销毁字幕视图
# ═════════════════════════════════════════════════════════════

try:
    from Avatar import PlayerAvatar  # noqa: E402

    @override(PlayerAvatar, 'onBecomeNonPlayer')
    def _new_onBecomeNonPlayer(original_func, self):
        """离开战斗时销毁字幕视图 + 清理战斗标志。"""
        try:
            from autoconfigvoiceover.voices import voice_switcher
            voice_switcher.leave_battle()
        except Exception:
            pass
        try:
            from autoconfigvoiceover.subtitle.host import destroy_subtitle_view
            destroy_subtitle_view()
        except Exception:
            pass  # 字幕模块未加载或销毁失败
        original_func(self)

    logger.debug('已注册 PlayerAvatar.onBecomeNonPlayer override（字幕销毁 + 离开战斗）')
except ImportError:
    logger.debug('PlayerAvatar 不可用，跳过 onBecomeNonPlayer override')
except Exception:
    logger.exception('注册 onBecomeNonPlayer override 失败')
