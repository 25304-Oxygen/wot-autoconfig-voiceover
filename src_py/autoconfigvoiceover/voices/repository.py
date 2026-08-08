# coding=utf-8
"""VoiceRepository —— 语音包内存数据库（单例 g_voice_repo）。

init 期编排三路读取并合并；之后各消费方（菜单页面/字幕/换肤/注册）
只从这里取数，不再触碰文件系统。进入账号后由入口的
onAccountBecomePlayer 调 save_all() 落盘（一次会话只写一次）。
"""

from autoconfigvoiceover.constants import DEFAULT_VOLUME
from autoconfigvoiceover.logger import Logger
from . import game_reader, legacy_scanner, pack_scanner, storage

logger = Logger('VoiceRepo')


class VoiceRepository(object):
    """语音包数据的唯一状态持有者。"""

    def __init__(self):
        self._ready = False
        self._saved = False
        self._packs = []           # [PackInfo] 通过加载校验的第三方语音包
        self._ingame_detail = []   # 内置语音明细行（含 normal/full_crew，仅内存）
        self._ingame_rows = []     # 内置语音 UI/持久行 {'voiceID','nickName','volume'}
        self._outside_rows = []    # 第三方语音 UI/持久行（同上）
        self._play_events = []     # 试听事件 [{'text','event'}]（回退列表；优先用语音包 events.json）
        self._current_volume = DEFAULT_VOLUME
        self._vfs_themes = []      # [{'name', ...colors}] VFS 预设主题
        self._pack_themes = []     # [{'name', 'pack_id', ...colors}] 语音包主题
        # 本次启动读到的历史数据——仅供 compute_diff 对比
        self._saved_ingame = []
        self._saved_outside = []

    # ═══════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════

    def run(self):
        """初始化期调用：scan → read → merge。

        整体防御——任何一步失败只记日志，不阻断 mod 后续初始化，
        菜单将以空数据继续运行。
        """
        try:
            self._run()
            self._ready = True
        except Exception:
            logger.exception('语音包信息读取失败——菜单将以空数据继续运行')

    def _run(self):
        # 1. 当前 voice 通道音量（作为新第三方语音包的默认音量）
        try:
            import SoundGroups
            self._current_volume = int(
                SoundGroups.g_instance.getVolume('voice') * 100)
        except Exception:
            logger.warn('读取 voice 通道音量失败，使用默认 %d', DEFAULT_VOLUME)
            self._current_volume = DEFAULT_VOLUME

        # 2. 第三方语音包：读取（VFS 扫描）→ 加载（校验 bank，
        #    不存在的直接移除，不进任何列表）
        self._packs = [pack for pack in
                       pack_scanner.scan_packs() + legacy_scanner.scan_legacy_packs()
                       if self._bank_exists(pack)]
        fresh_outside = [{'voiceID': p.pack_id, 'nickName': p.nick_name}
                         for p in self._packs]

        # 3. 游戏内语音包 + 本地化译名（系别永远排在车长语音前面）
        nation_rows, nations = game_reader.read_nation_voices()
        commander_rows = game_reader.read_commander_voices(nations)
        self._ingame_detail = nation_rows + commander_rows
        fresh_ingame = [{'voiceID': row['voiceID'], 'nickName': row['nickName']}
                        for row in self._ingame_detail]

        # 4. 与历史数据合并（保留用户改名与音量方案）
        self._saved_ingame = storage.load_saved_ingame()
        self._saved_outside = storage.load_saved_outside()
        self._ingame_rows = storage.merge_ingame(fresh_ingame,
                                                 self._saved_ingame)
        self._outside_rows = storage.merge_outside(fresh_outside,
                                                   self._saved_outside,
                                                   self._current_volume)
        self._play_events = storage.load_play_events()

        # 5. 颜色主题扫描（VFS 预设 + 各语音包内 theme.json）
        self._scan_themes()

        logger.info('语音包数据就绪: 内置 %d（系别 %d + 车长 %d）、'
                    '第三方 %d、试听事件 %d、音量 %d、'
                    'VFS主题 %d、语音包主题 %d',
                    len(self._ingame_rows), len(nation_rows),
                    len(commander_rows), len(self._outside_rows),
                    len(self._play_events), self._current_volume,
                    len(self._vfs_themes), len(self._pack_themes))

    def _scan_themes(self):
        """扫描所有颜色主题：磁盘预设 + 各语音包内 theme.json。

        预设主题磁盘优先（用户可编辑），VFS 兜底；
        语音包内主题从 VFS 直读（语音包在 wotmod 内，不存在磁盘副本）。
        读取失败的主题被跳过（warn），不阻断其他主题加载。
        """
        from autoconfigvoiceover.config_init import load_user_json
        from autoconfigvoiceover.utils import load_vfs_json
        from .model import THEME_JSON

        # ── 预设主题（磁盘优先，VFS 兜底）──
        try:
            preset_list = load_user_json('theme.json')
            if preset_list and isinstance(preset_list, list):
                for entry in preset_list:
                    if isinstance(entry, dict) and entry.get('name'):
                        self._vfs_themes.append(entry)
                    else:
                        logger.warn('预设主题条目缺少 name，已跳过: %s',
                                    repr(entry)[:80])
            else:
                logger.warn('theme.json 为空或格式错误，无预设主题可用')
        except Exception:
            logger.exception('预设主题读取失败')

        # ── 语音包内主题（VFS 直读——语音包在 wotmod 内）──
        for pack in self._packs:
            theme_path = pack.root + THEME_JSON
            try:
                theme = load_vfs_json(theme_path)
                if theme is None:
                    continue
                if not isinstance(theme, dict) or not theme.get('name'):
                    logger.warn('语音包 %s 的 theme.json 缺少 name 键，已跳过',
                                pack.pack_id)
                    continue
                entry = dict(theme)
                entry['pack_id'] = pack.pack_id
                self._pack_themes.append(entry)
            except Exception:
                logger.exception('语音包 %s 的 theme.json 读取失败', pack.pack_id)

    def get_pack_theme(self, pack_id):
        """按 pack_id 查找语音包内嵌的主题；无则返回 None。"""
        for t in self._pack_themes:
            if t.get('pack_id') == pack_id:
                return t
        return None

    @staticmethod
    def _bank_exists(pack):
        """加载校验：voiceover.bnk 不存在的包整体移除并 warn。"""
        import ResMgr
        if ResMgr.isFile(pack.bank):
            return True
        logger.warn('语音包 %s (%s) 的音频库不存在，已移除: %s',
                    pack.pack_id, pack.nick_name, pack.bank)
        return False

    def save_all(self):
        """落盘（进入账号后调用；一次会话只写一次，失败允许重试）。"""
        if not self._ready:
            logger.debug('save_all: 数据未就绪，跳过')
            return
        if self._saved:
            logger.debug('save_all: 本次会话已保存过，跳过')
            return
        self._saved = True
        try:
            storage.save_all(self._ingame_rows, self._outside_rows)
        except Exception:
            self._saved = False  # 失败回滚标记，下次 onAccountBecomePlayer 重试
            logger.exception('语音包信息保存失败')

    def persist_volume(self, voice_id):
        """把单个语音行的音量立即写盘（拖动音量滑块时调用）。

        不受 _saved 会话守卫限制——save_all 只在进入账号时写一次，
        而音量是车库中随时可调的高频改动，需要即时持久化。
        """
        if not self._ready:
            logger.debug('persist_volume: 数据未就绪，跳过')
            return
        try:
            storage.save_volume(self._ingame_rows, self._outside_rows, voice_id)
        except Exception:
            logger.exception('保存语音 %s 的音量失败', voice_id)

    # ═══════════════════════════════════════════════════════
    # 只读访问（消费方接口）
    # ═══════════════════════════════════════════════════════

    @property
    def is_ready(self):
        """三路读取是否成功完成。"""
        return self._ready

    @property
    def packs(self):
        """[PackInfo] 通过加载校验的第三方语音包。"""
        return self._packs

    @property
    def ingame_rows(self):
        """内置语音 UI/持久行 [{'voiceID','nickName','volume'}]。"""
        return self._ingame_rows

    @property
    def outside_rows(self):
        """第三方语音 UI/持久行 [{'voiceID','nickName','volume'}]。"""
        return self._outside_rows

    @property
    def ingame_detail(self):
        """内置语音明细行（含 normal/full_crew 声音模式映射，仅内存）。"""
        return self._ingame_detail

    @property
    def play_events(self):
        """试听事件 [{'text','event'}]（随 mod 打包的 VFS 只读资源）。"""
        return self._play_events

    @property
    def current_volume(self):
        """voice 通道当前音量（0-100）。"""
        return self._current_volume

    @property
    def vfs_themes(self):
        """[{'name', ...colors}] VFS 预设颜色主题。"""
        return self._vfs_themes

    @property
    def pack_themes(self):
        """[{'name', 'pack_id', ...colors}] 语音包内嵌颜色主题。"""
        return self._pack_themes

    @property
    def default_voice(self):
        """内置"默认"语音行；数据未就绪时返回 None。"""
        for row in self._ingame_rows:
            if row.get('voiceID') == 'default':
                return row
        return None

    def get_pack(self, pack_id):
        """按 voiceID 取 PackInfo；不存在返回 None。"""
        for pack in self._packs:
            if pack.pack_id == pack_id:
                return pack
        return None

    def compute_diff(self):
        """与上次保存数据的纯数据增减集合（通知层自行渲染文案）。"""
        fresh_iv = set(r['voiceID'] for r in self._ingame_rows if 'voiceID' in r)
        saved_iv = set(r['voiceID'] for r in self._saved_ingame if 'voiceID' in r)
        fresh_ov = set(r['voiceID'] for r in self._outside_rows if 'voiceID' in r)
        saved_ov = set(r['voiceID'] for r in self._saved_outside if 'voiceID' in r)
        return {
            'added_ingame': fresh_iv - saved_iv,
            'added_outside': fresh_ov - saved_ov,
            'removed_outside': saved_ov - fresh_ov,
        }


# 模块级单例——经 voices/__init__ 导出
g_voice_repo = VoiceRepository()
