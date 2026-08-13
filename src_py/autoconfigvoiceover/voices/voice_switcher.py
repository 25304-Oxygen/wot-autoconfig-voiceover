# coding=utf-8
"""语音切换核心——模式名解析 + setMode + ActiveVoice 激活 + 确认音。

将切换逻辑从 voice_switch_page 提取到此模块，保持页面薄；
页面只需调 switch_voice / set_voice_volume / play_preview 即可
"""

from autoconfigvoiceover.constants import VOICE_SELECTED_EVENT
from autoconfigvoiceover.logger import Logger

logger = Logger('VoiceSwitcher')

# ── 模块级状态 ──
_default_lang = None          # 游戏原始 default 模式的 voiceLanguage
_preview_sound = None         # 当前正在播放的试听/确认音（可 stop 打断）
_current_resolved_mode = 'default'  # 当前实际生效的 soundMode 名（战斗兜底用）
_our_switch = False           # True = 正在执行我们自己的 switch_voice（跳过外部钩子）
_original_setMode = None      # 被钩的原始 SoundModes.setMode（供 fini 还原）
_original_mapping_funcs = {}  # 被钩的原始函数引用（供 fini 还原）

# ── 战斗状态标志 ──
_in_battle = False               # 当前是否在战斗中
_has_special_crew = False        # 当前战斗是否使用了特殊车长（specialVoice 非 None）
_voice_override_on = True        # 战斗期 voiceOverride 快照（热路径避免反复读配置）
_suppress_setmode_hook = False   # 抑制 setMode/mapping 钩子（original_func 执行期间）


def enter_battle():
    """进入战斗时调用（setPlayerVehicle, isPlayerVehicle=True）。

    重置 _has_special_crew——每次新战斗（或复活）后，
    由 setPlayerVehicle 根据 self.specialVoice 重新判断。
    """
    global _in_battle, _has_special_crew, _voice_override_on
    _in_battle = True
    _has_special_crew = False
    from autoconfigvoiceover.config import load_config
    _voice_override_on = load_config(log=False).get('settings', {}).get('voiceOverride', True)


def leave_battle():
    """离开战斗时调用（onBecomeNonPlayer）。

    战斗状态全部清理，下次进战斗重新判定。
    """
    global _in_battle, _has_special_crew, _voice_override_on, _suppress_setmode_hook
    _in_battle = False
    _has_special_crew = False
    _voice_override_on = True
    _suppress_setmode_hook = False


# ═════════════════════════════════════════════════════════════
# init 期
# ═════════════════════════════════════════════════════════════

def capture_default_lang():
    """记录游戏原始 default 模式的 voiceLanguage，供 override_default 用。

    必须在 sound_manager.register() 之前调用——register 会缓存 modes
    副本（含当前 default.voiceLanguage），此后 override_default 方可安全
    修改，fini 时 recover 可还原。
    """
    global _default_lang
    import SoundGroups
    _default_lang = SoundGroups.g_instance.soundModes._SoundModes__modes['default'].voiceLanguage
    logger.debug('已捕获默认 voiceLanguage: %s', _default_lang)


def prepare_resolved_mode(voice_id, type_index=0, lang_index=0):
    """仅解析并记录当前生效的模式名，不执行 setMode / 确认音 / 消息。

    供 init() 期使用——让 setMode 钩子在登录前就知道要守护哪个模式，
    避免 loading 界面播放确认音和消息推送。

    :return: True 解析成功；False 失败（调用方回退 default）
    """
    global _current_resolved_mode
    mode_name = resolve_mode(voice_id, type_index, lang_index)
    if mode_name is None:
        return False
    import SoundGroups
    if mode_name not in SoundGroups.g_instance.soundModes.modes:
        return False
    _current_resolved_mode = mode_name
    logger.info('已预备模式守护: %s (voiceID=%s)', mode_name, voice_id)
    return True


# ═════════════════════════════════════════════════════════════
# 模式名解析
# ═════════════════════════════════════════════════════════════

def resolve_mode(voice_id, type_index, lang_index):
    """把 (voiceID + 下拉索引) 解析为游戏 soundMode 名。

    第三方语音包：voiceID 即模式名，直接返回。
    内置语音：查 ingame_detail，按 voice_type 分情况处理——
      default / nation：voiceID 即模式名
      commander：按 type_index 选 normal/full_crew，再按 lang_index
        取对应语言的模式名

    :return: soundMode 名字符串；查不到返回 None
    """
    from .repository import g_voice_repo

    # 第三方语音：voiceID 即模式名
    for row in g_voice_repo.outside_rows:
        if row.get('voiceID') == voice_id:
            return voice_id

    # 内置语音：查明细表
    detail = _find_detail(voice_id)
    if detail is None:
        logger.warn('未找到语音明细: %s', voice_id)
        return None

    voice_type = detail.get('voice_type', '')
    if voice_type in ('default', 'nation'):
        return voice_id  # 系别语音/default：voiceID 就是 soundMode 名

    # 车长语音：按"更改类型/语言"解析
    target = detail['full_crew'] if type_index > 0 and 'full_crew' in detail else detail['normal']
    lang_keys = sorted(target.keys())
    if not lang_keys:
        logger.warn('车长语音 %s 无语言选项', voice_id)
        return None
    safe_lang = min(lang_index, len(lang_keys) - 1)
    mode_name = target[lang_keys[safe_lang]]
    logger.debug('解析模式: voiceID=%s type=%d lang=%d(%s) → %s',
                 voice_id, type_index, safe_lang, lang_keys[safe_lang], mode_name)
    return mode_name


def _find_detail(voice_id):
    """在 ingame_detail 列表中按 voiceID 查找。"""
    from .repository import g_voice_repo
    for d in g_voice_repo.ingame_detail:
        if d.get('voiceID') == voice_id:
            return d
    return None


# ═════════════════════════════════════════════════════════════
# 下拉选项
# ═════════════════════════════════════════════════════════════

def get_type_lang_options(voice_id):
    """返回 (type_items, lang_items) 两个字符串列表。

    - 第三方语音：两个空列表（右列下拉隐藏）
    - 内置 default：type=['标准语音'], lang=normal 的键（即 "默认语种" 等）
    - 内置 nation：type=['国家语音'], lang 同上
    - 内置 commander：type=['车长语音'] 或 ['车长语音','车组语音']，
      lang=normal 的键列表（已排序）
    """
    from autoconfigvoiceover import l10n
    from .repository import g_voice_repo

    # 第三方
    for row in g_voice_repo.outside_rows:
        if row.get('voiceID') == voice_id:
            return [], []

    detail = _find_detail(voice_id)
    if detail is None:
        return [], []

    voice_type = detail.get('voice_type', '')
    lang_keys = sorted(detail['normal'].keys())

    # 类型项描述游戏内置语音的类型，随客户端语言（与车长名/tag 同语言）
    if voice_type == 'default':
        return [l10n.text_for_client('voice_switch/type/default')], lang_keys
    elif voice_type == 'nation':
        return [l10n.text_for_client('voice_switch/type/nation')], lang_keys
    else:  # commander
        type_items = [l10n.text_for_client('voice_switch/type/commander')]
        if 'full_crew' in detail:
            type_items.append(l10n.text_for_client('voice_switch/type/crew'))
        return type_items, lang_keys


# ═════════════════════════════════════════════════════════════
# 切换
# ═════════════════════════════════════════════════════════════

def switch_voice(voice_id, type_index=0, lang_index=0, silent=False):
    """执行完整的语音切换流程。

    :param silent: True = 不播确认音、不发语音包消息（登录恢复等非用户触发场景）
    :return: True 成功（已 setMode + activate + 广播）；False 失败
    """
    global _current_resolved_mode, _our_switch
    from autoconfigvoiceover.config import load_config

    mode_name = resolve_mode(voice_id, type_index, lang_index)
    if mode_name is None:
        logger.warn('无法解析声音模式: voiceID=%s', voice_id)
        return False

    import SoundGroups
    modes = SoundGroups.g_instance.soundModes._SoundModes__modes

    # 切换期校验：内置语音在当前客户端可能存在也可能不存在
    if mode_name not in SoundGroups.g_instance.soundModes.modes:
        logger.warn('声音模式 %s 在当前客户端不存在，切换失败', mode_name)
        return False

    current = SoundGroups.g_instance.soundModes.currentMode

    # ── 已是目标模式（非 default）：跳过切换，但仍播放确认音和消息 ──
    #     用户再次点击同一语音时，不执行 setMode/override_default/gender/volume，
    #     但播放确认音让用户知道操作已响应。
    if current == mode_name and mode_name != 'default':
        logger.debug('已是目标模式 %s，跳过 setMode，播放确认音', mode_name)
        _activate_if_needed(voice_id)
        _current_resolved_mode = mode_name
        if load_config().get('settings', {}).get('autoVolume', True):
            _apply_voice_volume(voice_id)
        if not silent and load_config().get('settings', {}).get('playOnSwitch', True):
            _play_confirmation()
        return True

    # ── 保存切换前的 default voiceLanguage，用于失败回退 ──
    prev_default_lang = modes['default'].voiceLanguage

    # ── 设置外部钩子忽略标志 ──
    _our_switch = True
    try:
        # "先切走再切回"技巧：__setMode 同名直接返回 True 不触发 setLanguage，
        # default→default 需先切到其他模式再切回（移植旧 mod 已验证方案）
        if current == mode_name == 'default':
            SoundGroups.g_instance.soundModes.setMode('ZH_CH')

        # override_default：篡改 default 模式的 voiceLanguage，
        # 防止游戏回退到 default 时语音又跳回原始语言（旧 mod 同样做法）
        if mode_name != 'default':
            new_lang = modes[mode_name].voiceLanguage
        else:
            new_lang = _default_lang
        modes['default'].voiceLanguage = new_lang

        # ── 执行实际切换 ──
        SoundGroups.g_instance.soundModes.setMode(mode_name)
        _current_resolved_mode = mode_name
        logger.info('语音已切换: %s → %s (voiceID=%s)', current, mode_name, voice_id)

        # 同步更新 national mapping，保持游戏状态一致，
        # 防止进战斗时游戏按旧 mapping 覆盖我们的语音
        try:
            SoundGroups.g_instance.soundModes.setNationalMappingByMode(mode_name)
        except Exception:
            pass

        # 性别开关（仅系别语音设，其他不设避免第三方包无声）
        _apply_gender(voice_id)

        # 确认音
        if not silent and load_config().get('settings', {}).get('playOnSwitch', True):
            _play_confirmation()

        # 音量跟随（仅在用户开启"切换语音自动应用音量"时生效）
        if load_config().get('settings', {}).get('autoVolume', True):
            _apply_voice_volume(voice_id)

        # ActiveVoice 激活 + 广播 onActiveVoiceChanged
        _activate_if_needed(voice_id)

        # ── 战斗中切换 → 触发外部字幕引擎(GUP)重同步 ──
        # GUP 等外部引擎在 setPlayerVehicle 链上匹配字幕，ACV 的 setMode
        # 直达底层、不触发它，故战斗中切换后字幕不跟随。这里模拟游戏
        # 设置"试听"链路（refreshNationalVoice）让字幕跟随本次切换。
        # 独立 try：重同步失败不影响本次切换成功。
        if _in_battle:
            try:
                _re_sync_external_engine(voice_id)
            except Exception:
                logger.exception('外部字幕引擎重同步失败（不影响本次切换）')

    except Exception:
        # ── 切换失败 → 回退 default voiceLanguage ──
        logger.exception('语音切换失败，回退 default voiceLanguage')
        try:
            modes['default'].voiceLanguage = prev_default_lang
        except Exception:
            pass
        return False
    finally:
        _our_switch = False

    return True


def _activate_if_needed(voice_id):
    """如果当前活跃语音不是目标则激活（构建 ActiveVoice + 广播）。"""
    from .active_voice import g_active_mgr
    if g_active_mgr.current is None or g_active_mgr.current.voice_id != voice_id:
        g_active_mgr.activate(voice_id)


def ensure_active_voice():
    """进战斗兜底：无登录流程（回放等）时补齐 ActiveVoice 激活。

    回放模式不触发 onAccountBecomePlayer → g_active_mgr.current 为 None，
    字幕 Manager 无法构建、菜单主题/图片无法跟随语音包。
    幂等补齐——已激活目标语音则跳过；被污染为 default 也自动拉回
    （voice_id != saved_id 时重新 activate）。
    """
    from autoconfigvoiceover.config import is_enabled, load_config
    if not is_enabled():
        return
    saved_id = load_config(log=False).get('voice', {}).get('currentVoiceId', 'default')
    if saved_id:
        _activate_if_needed(saved_id)


def _apply_gender(voice_id):
    """系别语音设性别 switch；其他语音似乎不受影响。"""
    import SoundGroups
    from autoconfigvoiceover.config import load_config
    detail = _find_detail(voice_id)
    is_nation = detail is not None and detail.get('voice_type') == 'nation'
    if not is_nation:
        return
    gender_str = load_config().get('settings', {}).get('nationVoiceGender', 'male')
    if gender_str == 'female':
        gender = SoundGroups.CREW_GENDER_SWITCHES.FEMALE
    else:
        gender = SoundGroups.CREW_GENDER_SWITCHES.MALE
    SoundGroups.g_instance.setSwitch(SoundGroups.CREW_GENDER_SWITCHES.GROUP, gender)


def _apply_voice_volume(voice_id):
    """切换语音后自动应用该语音保存的音量。"""
    from .repository import g_voice_repo
    for row in g_voice_repo.ingame_rows + g_voice_repo.outside_rows:
        if row.get('voiceID') == voice_id:
            set_voice_volume(row.get('volume', 100))
            return
    set_voice_volume(100)


def _sync_user_voice_change(mode_name):
    """战斗中用户通过游戏菜单切换语音 → 临时同步（不持久化）。

    等同 switch_voice(silent=True) 但不写 config.json——
    下次战斗/复活时 _user_changed_voice_in_battle 重置，
    ACV 持久化选择恢复。
    """
    voice_id = _mode_to_voice_id(mode_name)
    if voice_id is None:
        return
    from autoconfigvoiceover.config import load_config
    _activate_if_needed(voice_id)
    if load_config().get('settings', {}).get('autoVolume', True):
        _apply_voice_volume(voice_id)
    _apply_gender(voice_id)
    logger.debug('战斗中语音临时同步: mode=%s voiceID=%s（未持久化）', mode_name, voice_id)


def ensure_voice_consistency():
    """菜单打开时检查：若当前 soundMode 与 ACV 选择不一致，切回。

    车库中用户可能通过游戏设置菜单或兵营试听修改了语音，
    此函数在 ACV 面板显示前纠正——让用户觉得"游戏菜单改不了"。
    战斗中不干预（用户有临时试听权）。
    """
    if _in_battle:
        return  # 战斗中不纠正，用户有临时试听权
    if _current_resolved_mode == 'default':
        return
    import SoundGroups
    current = SoundGroups.g_instance.soundModes.currentMode
    if current != _current_resolved_mode:
        logger.info('菜单打开时检测到语音不一致: current=%s ACV=%s → 切回',
                    current, _current_resolved_mode)
        try:
            SoundGroups.g_instance.soundModes.setMode(_current_resolved_mode)
        except Exception:
            logger.exception('菜单打开时纠正语音失败')


def _play_confirmation():
    """播放切换确认音。"""
    global _preview_sound
    if _preview_sound is not None:
        _preview_sound.stop()
        _preview_sound = None
    import SoundGroups
    _preview_sound = SoundGroups.g_instance.getSound2D(VOICE_SELECTED_EVENT)
    if _preview_sound is not None:
        _preview_sound.play()



# ═════════════════════════════════════════════════════════════
# 音量
# ═════════════════════════════════════════════════════════════

def set_voice_volume(volume):
    """设置 voice 通道音量并持久化偏好。

    :param volume: 0-100 的整数值
    """
    import SoundGroups
    SoundGroups.g_instance.setVolume('voice', float(volume) / 100.0, True)


# ═════════════════════════════════════════════════════════════
# 试听
# ═════════════════════════════════════════════════════════════

def play_preview(event_id):
    """播放试听音效（先停止上一个试听/确认音）。"""
    global _preview_sound
    if _preview_sound is not None:
        _preview_sound.stop()
        _preview_sound = None
    import SoundGroups
    _preview_sound = SoundGroups.g_instance.getSound2D(event_id)
    if _preview_sound is None:
        logger.warn('试听播放失败: %s（bnk 可能未加载）', event_id)
    else:
        _preview_sound.play()
        logger.debug('试听播放中: %s', event_id)


# ═════════════════════════════════════════════════════════════
# 语音可见性（游戏声音设置菜单）
# ═════════════════════════════════════════════════════════════

def apply_voice_visibility(show_ingame=True, show_outside=True):
    """控制语音在游戏自带声音设置菜单中的显示/隐藏。

    直接设置soundMode.invisible 来隐藏游戏声音设置下拉列表中的条目。
    'default' 条目始终不会被隐藏。

    应在 init 期（sound_manager.register 之后）和用户修改
    showIngameVoices / showInstalledVoices 复选框后调用。
    """
    import SoundGroups
    from .repository import g_voice_repo

    modes = SoundGroups.g_instance.soundModes._SoundModes__modes
    key_list = modes.keys()

    # 游戏内置语音（排除 default——游戏始终需要默认语音）
    for row in g_voice_repo.ingame_rows:
        vo = row.get('voiceID', '')
        if vo and vo != 'default' and vo in key_list:
            modes[vo].invisible = not show_ingame

    # 第三方语音包
    for row in g_voice_repo.outside_rows:
        vo = row.get('voiceID', '')
        if vo and vo in key_list:
            modes[vo].invisible = not show_outside

    logger.info('语音可见性已更新: 内置=%s 第三方=%s', show_ingame, show_outside)


# ═════════════════════════════════════════════════════════════
# 当前模式（战斗兜底用）
# ═════════════════════════════════════════════════════════════

def get_current_mode_name():
    """返回当前实际生效的 soundMode 名。

    供 hooks 的 SpecialSoundCtrl.setPlayerVehicle override 读取，
    用于进战场时兜底——无论游戏把模式改成什么，最后强制拉回此值。
    """
    return _current_resolved_mode


# ═════════════════════════════════════════════════════════════
# 外部字幕引擎重同步（GUP 等）
# ═════════════════════════════════════════════════════════════

def _re_sync_external_engine(voice_id):
    """战斗中切换语音后，重新出发 GUP Mod 字幕引擎的同步点。

    推测 GUP Mod 在 SpecialSoundCtrl.setPlayerVehicle 链上读取
    当前语音模式并重新匹配字幕；游戏设置菜单的"试听"也走这条链
    （AltVoicesSetting.clearPreviewSound → Vehicle.refreshNationalVoice）。
    之前使用 setMode 直接修改语音，不触发该链，导致 GUP Mod 字幕不跟随。
    """
    import BigWorld
    import SoundGroups
    player = BigWorld.player()
    vehicle = getattr(player, 'vehicle', None)
    if vehicle is None:
        logger.debug('重同步: 当前无 vehicle，跳过')
        return
    try:
        vehicle.refreshNationalVoice()
    except Exception:
        logger.exception('refreshNationalVoice 触发外部同步失败')
    # refreshNationalVoice 会按车辆/乘组重设语音（普通成员→系别音、
    # 特殊车长→特殊语音），重置 ACV 选择恢复
    try:
        SoundGroups.g_instance.soundModes.setMode(_current_resolved_mode)
    except Exception:
        logger.exception('重置 ACV 语音模式失败')
    try:
        SoundGroups.g_instance.soundModes.setNationalMappingByMode(_current_resolved_mode)
    except Exception:
        pass
    # ensure_active_voice 可能已按旧 config 重激活，拉回本次目标
    _activate_if_needed(voice_id)


def apply_voice_override(checked):
    """局内即时应用 voiceOverride 变更（更新快照 + 触发一次语音/字幕同步）。

    仅在战斗中且使用特殊车长时才有实际切换动作：
      - 关闭 → 开启：refreshNationalVoice 按车辆/乘组自然重设后，
        再 setMode(_current_resolved_mode) 强制拉回 ACV 选择
      - 开启 → 关闭：仅 refreshNationalVoice —— 特殊车长恢复自己的语音，
        GUP 字幕随 __currentMode 改为真实语言
    非战斗 / 普通成员：只更新快照，后续逻辑自然生效。
    """
    global _voice_override_on
    _voice_override_on = bool(checked)

    if not (_in_battle and _has_special_crew):
        logger.debug('voiceOverride=%s 已更新（非特殊车长战斗，无需即时切换）', _voice_override_on)
        return

    import BigWorld
    import SoundGroups
    player = BigWorld.player()
    vehicle = getattr(player, 'vehicle', None)
    if vehicle is None:
        logger.debug('voiceOverride=%s 已更新（当前无 vehicle，跳过即时切换）', _voice_override_on)
        return

    # 游戏原生"恢复正常语音"链（游戏设置菜单试听后的标准恢复路径）：
    # refreshNationalVoice 按车辆/乘组重设语音（特殊车长→特殊语音），
    # 同时触发 GUP 字幕引擎在 setPlayerVehicle 链上的重新匹配
    try:
        vehicle.refreshNationalVoice()
    except Exception:
        logger.exception('voiceOverride 即时切换: refreshNationalVoice 失败')

    if checked:
        # 关闭 → 开启：重设后强制拉回 ACV 选择
        try:
            SoundGroups.g_instance.soundModes.setMode(_current_resolved_mode)
        except Exception:
            logger.exception('voiceOverride 即时切换: setMode 拉回失败')

    logger.info('voiceOverride 已即时应用: %s（战斗内特殊车长）', '开启' if checked else '关闭')


# ═════════════════════════════════════════════════════════════
# 外部语音变化监测（游戏设置菜单被动切换）
# ═════════════════════════════════════════════════════════════

def init_monitoring():
    """安装 SoundModes 钩子，守护用户选择的语音不被游戏覆盖。

    守卫层级：
    1. setMode 钩子：
       - 'default' 重定向到 _current_resolved_mode（始终生效）
       - 战斗中：特殊车长拦截所有外部 setMode（游戏的持续 enforcement
         + 游戏菜单）；普通成员放行（用户可通过游戏菜单临时切换）
       - _our_switch / _suppress_setmode_hook 期间跳过
    2. setNationalMappingByMode / setNationalMappingByPreset 钩子——
       监测游戏设置菜单的语音保存/预览，自动同步 ActiveVoice
       （_suppress_setmode_hook 期间跳过）

    应在 sound_manager.register() 之后、首次 switch_voice 之前调用。
    """
    global _original_setMode, _original_mapping_funcs
    import SoundGroups
    cls = SoundGroups.SoundModes

    if _original_setMode is not None:
        return  # 已安装，避免重复

    # ── setMode 钩子：拦截游戏/系统对 default 的重置 ──
    _original_setMode = cls.setMode

    def _hooked_setMode(self, mode_name):
        from autoconfigvoiceover.config import is_enabled
        if not is_enabled():
            return _original_setMode(self, mode_name)
        if _our_switch:
            return _original_setMode(self, mode_name)  # 我们自己切的，放行

        # ── 1. 'default' 重定向：游戏/系统重置 → ACV 选择 ──
        if mode_name == 'default' and _current_resolved_mode != 'default':
            if _current_resolved_mode in self.modes:
                logger.debug('setMode 钩子: %s → %s（拦截游戏重置）',
                           mode_name, _current_resolved_mode)
                mode_name = _current_resolved_mode

        # ── 2. 战斗中非 default 的外部 setMode ──
        elif (not _suppress_setmode_hook and _in_battle
              and mode_name != _current_resolved_mode
              and mode_name in self.modes):
            if _has_special_crew:
                # 特殊车长：拦截所有外部 setMode
                # （游戏每次语音播放的持续 enforcement + 游戏设置菜单）
                # voiceOverride 关闭：放行游戏原始 setMode（特殊车长用自己的语音）
                if _voice_override_on:
                    logger.debug('setMode 钩子(特殊车长): 拦截 %s → %s',
                               mode_name, _current_resolved_mode)
                    mode_name = _current_resolved_mode
                else:
                    logger.debug('setMode 钩子(特殊车长): voiceOverride 关闭，放行 %s', mode_name)
            else:
                # 普通成员：用户通过游戏设置菜单切换 → 临时同步，不落盘
                logger.info('战斗中检测到用户切换语音(普通成员): %s', mode_name)
                _sync_user_voice_change(mode_name)

        return _original_setMode(self, mode_name)

    cls.setMode = _hooked_setMode

    # ── mapping 钩子：监测游戏设置菜单语音切换 ──
    _original_mapping_funcs['setNationalMappingByMode'] = cls.setNationalMappingByMode
    _original_mapping_funcs['setNationalMappingByPreset'] = cls.setNationalMappingByPreset

    def _hooked_mapping_by_mode(self, soundMode):
        result = _original_mapping_funcs['setNationalMappingByMode'](self, soundMode)
        from autoconfigvoiceover.config import is_enabled
        if not is_enabled():
            return result
        if result and not _our_switch:
            # 游戏在场景切换时会调用 setNationalMappingByMode('default')，
            # 这不是用户主动切换语音——重定向到当前守护的模式，
            # 与 setMode 钩子保持一致的"default=所选语音"语义
            if soundMode == 'default' and _current_resolved_mode != 'default':
                soundMode = _current_resolved_mode
            if not _suppress_setmode_hook:
                _on_external_voice_change(soundMode)
        return result

    def _hooked_mapping_by_preset(self, presetName):
        result = _original_mapping_funcs['setNationalMappingByPreset'](self, presetName)
        from autoconfigvoiceover.config import is_enabled
        if not is_enabled():
            return result
        if result and not _our_switch:
            # 同上：游戏重置到 default preset 时重定向到当前所选语音
            if presetName == 'default' and _current_resolved_mode != 'default':
                presetName = _current_resolved_mode
            if not _suppress_setmode_hook:
                _on_external_voice_change(presetName)
        return result

    cls.setNationalMappingByMode = _hooked_mapping_by_mode
    cls.setNationalMappingByPreset = _hooked_mapping_by_preset
    logger.info('外部语音变化监测已安装（含 setMode 重定向守护）')


def fini_monitoring():
    """卸载 SoundModes 钩子，还原原始方法。"""
    global _original_setMode, _original_mapping_funcs
    import SoundGroups
    cls = SoundGroups.SoundModes

    if _original_setMode is not None:
        cls.setMode = _original_setMode
        _original_setMode = None

    if _original_mapping_funcs:
        if 'setNationalMappingByMode' in _original_mapping_funcs:
            cls.setNationalMappingByMode = _original_mapping_funcs['setNationalMappingByMode']
        if 'setNationalMappingByPreset' in _original_mapping_funcs:
            cls.setNationalMappingByPreset = _original_mapping_funcs['setNationalMappingByPreset']
        _original_mapping_funcs = {}

    logger.info('外部语音变化监测已卸载')


def _mode_to_voice_id(mode_name):
    """将 soundMode 名或 nationalPreset 名映射为 voice_id。

    优先级：第三方语音包 > 内置语音。都匹配不到返回 None
    （此时游戏操作的是我们不知道的声音模式，静默忽略）。
    """
    from .repository import g_voice_repo

    # 第三方语音包：pack_id 即 mode 名
    for row in g_voice_repo.outside_rows:
        if row.get('voiceID') == mode_name:
            return mode_name

    # 内置语音：voiceID 即 mode 名
    for row in g_voice_repo.ingame_rows:
        if row.get('voiceID') == mode_name:
            return mode_name

    # 检查是否是游戏当前 modes dict 中存在的模式名
    # （可能是未收录的内置模式或 nationalPreset 名）
    import SoundGroups
    if mode_name in SoundGroups.g_instance.soundModes.modes:
        return mode_name

    return None


def _on_external_voice_change(name):
    """游戏设置菜单被动改变了语音 → 同步 ActiveVoice。

    只在 g_active_mgr 已激活过（current 非 None）时才响应，
    避免游戏启动期的初始化调用被误判为外部切换。

    注意：不再更新 _current_resolved_mode——该值只能通过 ACV 面板
    切换（switch_voice）修改。外部语音变化仅同步 ActiveVoice，
    下次 ACV 面板打开 / 下次进战斗时会被纠正回 _current_resolved_mode。
    """
    from .active_voice import g_active_mgr

    if g_active_mgr.current is None:
        return  # 尚未完成首次激活，忽略启动期的 mapping 调用

    # 游戏场景切换会触发 default mapping，不是用户主动切语音
    if name == 'default':
        return

    voice_id = _mode_to_voice_id(name)
    if voice_id is None:
        return  # 无法映射的 mode/preset，静默忽略

    if g_active_mgr.current.voice_id == voice_id:
        return  # 已经是最新

    logger.info('检测到外部语音切换: %s → voiceID=%s，同步 ActiveVoice'
                '（不更新 _current_resolved_mode）',
                name, voice_id)

    # 构建 ActiveVoice 并广播（声音子系统自动联动）
    g_active_mgr.activate(voice_id)
