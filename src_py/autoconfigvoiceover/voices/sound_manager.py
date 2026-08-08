# coding=utf-8
"""第三方语音包注册——把通过加载校验的包注入游戏声音模式表。

注册方式：
依旧沿用 ResMgr.DataSection 在内存中伪造与 main_sound_modes.xml 的
<mode> 节点同构的数据，交给游戏原生 SoundModeDesc 构造器，再 update 进
SoundModes 的私有 dict（modes 只有 getter property，必须名称改写访问）。

无需显式加载 bank：setMode 内部调用 WWISE.setLanguage(voiceLanguage)，
Wwise 按语言目录到 audioww/<language>/ 动态加载 voiceover.bnk
（同目录 inbattle_communication_*.bnk 自动带上）。

本期只在 init 注册、fini 恢复；启用/禁用开关接入 replace/recover
属切换阶段（需连同 setMode('default') 回退一起做，避免摘除注册后
当前模式仍挂在第三方语音上的悬空状态）。
"""

from autoconfigvoiceover.logger import Logger

logger = Logger('SoundManager')

# ── 模块级状态 ──
_origin_modes = None   # 注册前的原始 modes 副本（首次注册时缓存一次）
_registered = []       # 本次注入的模式名（日志/调试用）


def derive_bank_and_language(bank):
    """把 pack.json 的 path（从 res/ 出发）转为注册所需的两个路径。

    :param bank: 如 'audioww/gup_jp/voiceover.bnk'
    :return: (bank_rel, language)
        bank_rel —— 相对 audioww/ 的 bank 路径（wwbanks/bank 字段，
                    仅供游戏侧 getIsValid 存在性校验）
        language —— bank 所在目录相对 audioww/ 的路径，即 Wwise 语言名
    """
    bank_rel = bank[len('audioww/'):] if bank.startswith('audioww/') else bank
    # bank 直接放在 audioww 根下时语言名为 ''（不推荐但允许）
    language = bank_rel.rsplit('/', 1)[0] if '/' in bank_rel else ''
    return bank_rel, language


def register():
    """把 g_voice_repo 中通过加载校验的包全部注入声音模式表。

    整体防御——任何异常只记日志，不阻断 mod 初始化；
    pack_id 与现有模式重名的包跳过并 warn（不覆盖游戏/其他包的模式）。
    """
    global _origin_modes
    try:
        import SoundGroups
        from .repository import g_voice_repo

        modes = SoundGroups.g_instance.soundModes._SoundModes__modes
        # 首次注册前缓存原始副本，供 recover 整体还原
        if _origin_modes is None:
            _origin_modes = modes.copy()

        # description 用合并后的昵称（继承用户在 voiceover.json 中的改名）
        name_map = dict((row['voiceID'], row['nickName'])
                        for row in g_voice_repo.outside_rows
                        if 'voiceID' in row and 'nickName' in row)

        extra = {}
        for pack in g_voice_repo.packs:
            if pack.pack_id in modes:
                logger.warn('语音包 %s 与现有声音模式重名，跳过注册', pack.pack_id)
                continue
            nick_name = name_map.get(pack.pack_id, pack.nick_name)
            extra[pack.pack_id] = _build_mode_desc(pack, nick_name)

        modes.update(extra)
        del _registered[:]
        _registered.extend(sorted(extra.keys()))
        logger.info('已注册 %d 个第三方语音模式: %s',
                    len(_registered), '、'.join(_registered) or '（无）')
    except Exception:
        logger.exception('第三方语音模式注册失败')


def recover():
    """整体还原声音模式表到注册前状态（fini 用；未来启停开关复用）。"""
    if _origin_modes is None:
        return
    try:
        import SoundGroups
        SoundGroups.g_instance.soundModes._SoundModes__modes = _origin_modes.copy()
        logger.info('声音模式表已还原（摘除 %d 个第三方模式）', len(_registered))
        del _registered[:]
    except Exception:
        logger.exception('声音模式表还原失败')


# ═════════════════════════════════════════════════════════════
# 内部
# ═════════════════════════════════════════════════════════════

def set_builtin_display_names(ingame_rows):
    """将内置语音的本地化名称写入游戏声音模式表的 description 字段。

    游戏默认只给声音模式设了 i18n key（如 #nations:china），
    但不会主动 resolve 为人类可读文本写入 description 属性。
    此处遍历已翻译的 nickName 并直接赋值到 _SoundModes__modes[vid].description，
    让游戏自带的声音设置菜单也能显示正确名称。

    应在 register() 之后调用（modes dict 此时已稳定）。
    """
    try:
        import SoundGroups
        modes = SoundGroups.g_instance.soundModes._SoundModes__modes
        updated = 0
        for row in ingame_rows:
            vid = row.get('voiceID')
            nick = row.get('nickName')
            if vid and nick and vid in modes:
                modes[vid].description = nick
                updated += 1
        logger.info('已更新 %d 个内置声音模式的显示名称', updated)
    except Exception:
        logger.exception('设置内置声音模式显示名称失败')


def _build_mode_desc(pack, nick_name):
    """伪造 <mode> 节点构造游戏原生 SoundModeDesc。

    字段与 main_sound_modes.xml 对齐：name=模式名（voiceID）、
    wwise_language、description（makeString 对非 # 串原样返回）、
    invisible=True（不进游戏设置菜单）、wwbanks/bank。
    """
    import ResMgr
    import SoundGroups

    bank_rel, language = derive_bank_and_language(pack.bank)
    new_sec = ResMgr.DataSection('mode')
    new_sec.write('name', pack.pack_id)
    new_sec.write('wwise_language', language)
    new_sec.write('description', nick_name)
    new_sec.write('invisible', True)
    new_sec.write('wwbanks/bank', bank_rel)
    return SoundGroups.SoundModes.SoundModeDesc(new_sec)
