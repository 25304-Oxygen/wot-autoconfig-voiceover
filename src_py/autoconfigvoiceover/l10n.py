# coding=utf-8
"""l10n 词典加载与查询

加载链（按键合并，任一命中即返回）:
  磁盘 mods/configs/autoConfigVoiceOver/l10n/<lang>.json    ← 用户可编辑，优先
      （文件缺失/损坏时自动用 VFS 对应文件覆盖恢复，见 _load_disk_json_or_restore）
    └─ 缺键 → VFS 同语言文件（wotmod 打包资源）
    └─ 缺键 → en.json（磁盘 → VFS）
    └─ 缺键 → UI_LABELS 中文基线（zh_cn 即代码本身，零成本）
    └─ 缺键 → 返回键名（开发期直接暴露缺失）

生效语言 = settings.uiLang（'auto' 默认 → helpers.getClientLanguage()）。
zh_sg（亚服简中）与 zh_cn 同文，auto 时归一为 zh_cn 直接落中文基线
（见 get_effective_lang）。
未收录语言（如 ru）经加载链落 en，再落中文基线。
运行时切换: 改 uiLang → reload() → 重推全部页面（populate 幂等）。
"""

import os

from .logger import Logger
from .constants import MY_CONFIG_FOLDER
from .utils import load_jsonc, load_vfs_json, to_utf8

logger = Logger('l10n')

# ═════════════════════════════════════════════════════════════
# 语言集合与显示名
# ═════════════════════════════════════════════════════════════

LANG_ZH_CN = 'zh_cn'
LANG_ZH_SG = 'zh_sg'  # 亚服简中与 zh_cn 同文
LANG_ZH_TW = 'zh_tw'
LANG_EN = 'en'
LANG_AUTO = 'auto'

BUILTIN_LANGS = (LANG_ZH_CN, LANG_ZH_TW, LANG_EN)
"""内置支持的语言代码。zh_cn 无词典文件——硬编码中文基线即词典。

zh_sg（亚服简中）不是独立语言——get_effective_lang 把 auto 时的 zh_sg
归一为 zh_cn（同文直接落中文基线），因此不进本元组、也不出现在语言下拉。"""

# 语言下拉显示名（母语名——不随界面语言变化，任何语言下自解释）。
# 仅保留“无文件语言的内置来源 + 未知语言兜底”：zh_cn 永远无词典文件
# （硬编码中文即词典），其显示名只能来自本表——对本表而言是唯一来源而非回退；
# 其余语言的显示名优先从语言文件 __meta__.displayName 读取（见
# get_lang_display_name），本表只兜底文件缺失/未写元数据的情况。
# 新增语言无需改本表——在 l10n/<lang>.json 顶部写 __meta__.displayName 即可。
LANG_DISPLAY_NAMES = {
    LANG_ZH_CN: '简体中文',
    LANG_ZH_TW: '繁體中文',
    LANG_EN:    'English',
}

_VFS_L10N_ROOT = 'mods/autoconfigvoiceover/l10n'
_DISK_L10N_ROOT = os.path.join(MY_CONFIG_FOLDER, 'l10n')

# ═════════════════════════════════════════════════════════════
# UI_LABELS —— 词典键登记表（键 → 中文默认值）
#
# 所有词典键在此集中登记（单一来源）:
#   - text(key) 缺失时回退本表的默认值（中文基线）
#   - build_ui_labels() 以此为键清单生成推送 dict
#   - AS3 页面 L.get(key, 中文默认) 的第二参数照抄本表
# 键前缀分区: settings/ voice_switch/ personal/ subtitle_settings/
#             semi_panel/ help/ detail/ ui_lang/ notify/
# settings/ 下 GB6 主题区用树形子前缀 settings/theme/，
# 其余区域保持扁平语义名（settings/nation_voice_title 等）。
# tooltip 键前缀 tooltip/（仅 Python 侧 text() 使用，不推给 AS3）。
# ═════════════════════════════════════════════════════════════

UI_LABELS = {
    # ── 通用 ──
    'ui_lang/auto': '跟随客户端',

    # ── 半折叠面板 ──
    'semi_panel/btn_detail':   '详情',
    'semi_panel/btn_personal': '个性化',
    'semi_panel/btn_subtitle': '字幕',
    'semi_panel/toggle_on':    '启用中',
    'semi_panel/toggle_off':   '禁用中',

    # ── 设置页 ──
    # GB6 主题区是树形子前缀先例（settings/theme/*），其余区域保持扁平语义名。
    'settings/title':                 '设置',
    'settings/dropdown_loading':      '加载中...',

    #   GB1 系别语音
    'settings/nation_voice_title':    '系别语音设置',
    'settings/radio_male':            '糙汉子',
    'settings/radio_female':          '萌妹子',

    #   GB2 通知
    'settings/notify_title':          '通知设置',
    'settings/notify_label':          '语音包统计信息推送',
    'settings/radio_notify_none':     '不推送',
    'settings/radio_notify_count':    '仅计数',
    'settings/radio_notify_detail':   '详细',
    'settings/cb_ui_sound':           '开启界面交互音效',
    'settings/cb_switch_notify':      '接收语音切换通知',
    'settings/cb_play_on_switch':     '切换语音后播放选中语音',

    #   GB3 显示
    'settings/display_title':         '显示设置',
    'settings/cb_hotkey_enabled':     '允许通过热键打开菜单',
    'settings/hotkey_label':          '设置热键',
    'settings/log_label':             '日志输出设置',
    'settings/log_level/0':           '仅ERROR',
    'settings/log_level/1':           'WARN及以上',
    'settings/log_level/2':           'INFO及以上',
    'settings/log_level/3':           'DEBUG及以上',
    'settings/ui_lang_label':         '界面语言',
    'settings/cb_show_ingame':        '游戏内置语音包在设置菜单中显示',
    'settings/cb_show_installed':     '已安装的语音包在设置菜单中显示',

    #   GB4 语音通用
    'settings/voice_general_title':   '语音通用设置',
    'settings/cb_auto_volume':        '切换语音时自动应用预设音量',
    'settings/cb_sound_remap':        '允许使用声音重映射',
    'settings/cb_sound_bind':         '允许使用声音绑定',
    'settings/cb_voice_override':     '覆盖车长特殊语音',

    #   GB5 字幕通用
    'settings/subtitle_general_title': '字幕通用设置',
    'settings/subtitle_label':         '字幕显示',
    'settings/radio_sub_simple':       '简洁',
    'settings/radio_sub_standard':     '标准',
    'settings/radio_sub_none':         '不显示',
    'settings/speed_label':            '文字速度',
    'settings/preview_text':           '这是一个打字预览示例文本，用于展示字幕通用设置中的文字速度效果。',
    'settings/cb_sub_update':          '允许字幕更新内容',
    'settings/cb_sub_anim':            '启用字幕动画效果',
    'settings/cb_multi_sub':           '允许多条字幕同时出现',

    #   GB6 主题（树形子前缀先例）
    'settings/theme/title':                   'UI 主题自定义',
    'settings/theme/color_scheme_label':      '颜色方案',
    'settings/theme/bg_icon_label':           '背景图标',
    'settings/theme/title_text_label':        '标题文本颜色',
    'settings/theme/radio_follow_scheme':     '跟随颜色方案',
    'settings/theme/radio_custom':            '自定义',
    'settings/theme/color_input_placeholder': '#RRGGBB',
    'settings/theme/default_label':           '使用默认',
    'settings/theme/bgicon_default_label':    '默认',
    'settings/theme/follow_pack_label':       '跟随语音包',

    # ── 设置页 tooltip（Python 侧）──
    'settings/tooltip/nation_voice': (
        '<p align="center" size="15"><b>系别语音设置</b></p>'
        '<p align="left">切换系别语音包的默认性别。</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '仅在使用系别语音时生效</font>'
        '</p>'
    ),
    'settings/tooltip/sound_remap': (
        '<p align="center" size="15"><b>声音重映射</b></p>'
        '<p align="left">允许将游戏内特定声音进行替换，'
        '扩大了语音包对于战斗语音的修改范围。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '重映射方案由语音包指定，并随语音包的切换而切换。</font>'
        '</p>'
    ),
    'settings/tooltip/sound_bind': (
        '<p align="center" size="15"><b>声音绑定</b></p>'
        '<p align="left">允许在某些指定的声音播放或指令发出后，'
        '播放语音包中的指定事件，相当于人为创造一个“语音事件”。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '声音绑定方案由语音包指定，并随语音包的切换而切换。</font>'
        '</p>'
    ),
    'settings/tooltip/subtitle': (
        '<p align="center" size="15"><b>字幕通用设置</b></p>'
        '<p align="left">以下设置仅适用于字幕语音包，并非所有语音包都有字幕。'
        '在这里可以控制语音包字幕的显示方式、速度和视觉效果。'
        '</p>'
    ),
    'settings/tooltip/subtitle_simple': (
        '<p align="center" size="15"><b>简洁模式</b></p>'
        '<p align="left">仅显示说话人名称和台词文本内容。'
        '此模式下字幕不再使用动画效果，打字机效果不受影响。'
        '</p>'
    ),
    'settings/tooltip/subtitle_standard': (
        '<p align="center" size="15"><b>标准模式</b></p>'
        '<p align="left">显示头像、标题、文本和文本背景。'
        '</p>'
    ),
    'settings/tooltip/subtitle_update': (
        '<p align="center" size="15"><b>字幕内容更新</b></p>'
        '<p align="left"><font size="13">在一段对话中，若前后说话人相同（角色代码相同），'
        '则对话过渡时不进行新字幕弹出，通过更新当前字幕内容取而代之。</font>'
        '</p>'
    ),
    'settings/tooltip/subtitle_anim': (
        '<p align="center" size="15"><b>字幕动画效果</b></p>'
        '<p align="left">允许字幕淡入后按照指定方式运动，插件当前支持'
        '六个动画随意编排: "冒泡"、"惊讶"、"摇头"、"晃动"、"抱歉"、"点头"。'
        '</p><br>'
        '<p align="left">．冒泡：字幕向上跳跃最后返回原位</p>'
        '<p align="left">．惊讶：更快、移动范围更大的冒泡</p>'
        '<p align="left">．摇头：字幕进行左右摆动</p>'
        '<p align="left">．晃动：更快的左右摆动</p>'
        '<p align="left">．抱歉：反向冒泡</p>'
        '<p align="left">．点头：更快的反向冒泡</p><br>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '运动范围与字幕尺寸有关，字幕尺寸由其组件共同的外接矩形大小决定。</font>'
        '</p>'
    ),
    'settings/tooltip/multi_sub': (
        '<p align="center" size="15"><b>多字幕同时出现</b></p>'
        '<p align="left">允许多条字幕同时显示在屏幕上，'
        '新字幕不会覆盖当前正在播放的字幕。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '关闭后新字幕入场时会打断当前字幕，同一时间只显示一条。</font>'
        '</p>'
    ),
    'settings/tooltip/text_speed': (
        '<p align="center" size="15"><b>文字速度</b></p>'
        '<p align="left">控制字幕逐字出现的速度。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '可调节范围：0~0.1，步长 0.01，速度为 0 代表不使用出字效果。<br>'
        '推荐值 0.03~0.05。</font>'
        '</p>'
    ),
    'settings/tooltip/color_scheme': (
        '<p align="center" size="15"><b>颜色方案</b></p>'
        '<p align="left">切换菜单的整体配色。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '<b>使用默认</b> — 暗色主题；<br>'
        '<b>跟随语音包</b> — 自动使用当前语音包的主题方案（如果有的话）；<br>'
        '再往下为预设主题方案和读取自语音包的方案。</font>'
        '</p>'
    ),
    'settings/tooltip/bg_icon': (
        '<p align="center" size="15"><b>背景图标</b></p>'
        '<p align="left">切换菜单组件使用的自定义图片，'
        '包括左侧导航栏图标和面板背景图。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '<b>默认</b> — 使用本地磁盘中的图标；<br>'
        '<b>跟随语音包</b> — 自动使用当前语音包的图标方案（如果有的话）；<br>'
        '再往下为读取自各语音包的图标方案。</font>'
        '</p>'
    ),
    'settings/tooltip/title_text_color': (
        '<p align="center" size="15"><b>标题颜色</b></p>'
        '<p align="left">控制菜单顶部语音包名称的文字颜色。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '<b>跟随颜色方案</b> — 使用颜色方案中定义的大标题颜色；<br>'
        '<b>自定义</b> — 手动输入十六进制颜色值（如 #FF0000），'
        '仅修改大标题颜色，不影响其他组件。</font>'
        '</p>'
    ),
    'settings/tooltip/title': (
        '<p align="center" size="15"><b>插件设置面板</b></p>'
        '<p align="left">涵盖大多项功能的设置面板。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '修改即刻保存，下次启动生效。</font>'
        '</p>'
    ),

    # ── 语音切换页 ──
    'voice_switch/title':             '语音选择',
    'voice_switch/volume_label':      '音量调节',
    'voice_switch/preview_label':     '测试声音',
    'voice_switch/play_btn':          '播放',
    'voice_switch/change_type_label': '更改类型',
    'voice_switch/change_lang_label': '更改语言',
    'voice_switch/tab_ingame':        '游戏内置语音包',
    'voice_switch/tab_outside':       '已安装的语音包',
    'voice_switch/no_voice_packs':    '（无可用语音包）',
    'voice_switch/unsupported':       '所选语音包不支持',
    'voice_switch/event_prefix':      '事件 ',

    #  下拉项与名称 tag（Python 侧 text_for_client() 使用，随客户端语言）。
    #  内置语音的车长名/语言变体取自游戏本地化，类型名与 tag 描述这些游戏数据，
    #  故跟随客户端语言而非 settings.uiLang，读取时一次性烘焙、会话内固定。
    'voice_switch/type/default':      '标准语音',
    'voice_switch/type/nation':       '国家语音',
    'voice_switch/type/commander':    '车长语音',
    'voice_switch/type/crew':         '车组语音',
    'voice_switch/lang/default':      '默认语种',
    'voice_switch/lang/en':           '英语',
    'voice_switch/lang/ru':           '俄语',
    'voice_switch/lang/cn':           '普通话',
    'voice_switch/tag/full_crew':     '[含车组]',
    'voice_switch/tag/multi_lingual': '[多语言]',

    # ── 语音切换页 tooltip（Python 侧）──
    'voice_switch/tooltip/title': (
        '<p align="center" size="15"><b>语音切换与声音播放</b></p>'
        '<p align="left">'
        '<font color="#3D6B9B">．游戏内置语音包</font><br>'
        '<font size="13"> 客户端自带的特殊车长语音。</font>'
        '</p>'
        '<p align="left">'
        '<font color="#3D6B9B">．已安装的语音包</font><br>'
        '<font size="13"> 从 .wotmod 文件加载的第三方语音。</font>'
        '</p>'
        '<p align="left">'
        '<font color="#3D6B9B">．试听语音包中的声音</font><br>'
        '<font size="13"> 该播放列表可由语音包指定，可能据语音包的不同而变化。</font>'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        'bnk 是动态加载的，某些 bnk 只在战斗中加载，位于其中的事件'
        '无法在车库播放，请移步战斗场。</font><br>'
        '<font color="#FF8C00" size="13">'
        '注意，根据所在客户端/服务器的不同，部分语音包会因为实际并不'
        '存于游戏资源文件中，而无法使用。'
        '</font>'
        '</p>'
    ),
    'voice_switch/tooltip/change_type': (
        '<p align="center" size="15"><b>更改类型</b></p>'
        '<p align="left">针对部分特殊成员生效，可更换特殊语音类型'
        '为 <b>车长语音</b> 或 <b>车组语音</b>。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '对于拥有车组语音的车长，我在 ta 的名字后添加了对应标签。</font>'
        '</p>'
    ),
    'voice_switch/tooltip/change_lang': (
        '<p align="center" size="15"><b>更改语言</b></p>'
        '<p align="left">仅针对部分特殊成员生效，可更换语音语言，'
        '国服客户端语言大体分为 RU EN CN。指示的语言不一定准确，'
        '因为“CN”既可以代表国语配音，也可以代表国服特供版。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">'
        '对于拥有多语种语音的车长，我在 ta 的名字后添加了对应标签。</font>'
        '</p>'
    ),

    # ── 个性设置页 ──
    'personal/title':                '个性设置',
    'personal/declaration':          '前排提醒：点亮后发的是公屏喊话，所有人都能看到，也会被和谐。下面那个替换的客户端渲染文本，只有你可见且只替换自己的消息，不会被和谐。',
    'personal/chat_msg_title':       '局内喊话消息自定义',
    'personal/spotted_label':        '被点亮时喊话',
    'personal/preview_label':        '预览：',
    'personal/alive_label':          '附加条件：',
    'personal/alive_desc':           '当场上存活队友数低于或等于',
    'personal/replace_label':        '替换已有喊话',
    'personal/hint':                 '清空输入框可还原为游戏原始消息',
    'personal/spotted_placeholder':  '输入被点亮时要发送的队内消息...',
    'personal/replace_placeholder':  '输入替换文本...',

    # ── 个性设置页 tooltip（Python 侧）──
    'personal/tooltip/spotted_message': (
        '<p align="center"><font size="15"><b>被点亮时喊话</b></font></p>'
        '<p align="left">被点亮（第六感触发）时自动向队伍发送此消息。</p>'
        '<p align="left">'
        '使用占位符 <b>&lt;a&gt;</b> 代指你当前的小地图坐标，'
        '可放在文中任意位置（也可不加）。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="14">'
        '示例：我在&lt;a&gt;被点亮了 → 我在A1被点亮了</font>'
        '</p>'
    ),

    # ── 字幕设置页 ──
    'subtitle_settings/title':          '字幕设置',
    'subtitle_settings/position_title': '调整字幕位置',
    'subtitle_settings/btn_edit':       '编辑',
    'subtitle_settings/btn_done':       '完成',
    'subtitle_settings/btn_reset':      '重置',
    'subtitle_settings/btn_avatar':     '调整头像',
    'subtitle_settings/btn_title':      '调整标题',
    'subtitle_settings/btn_bg':         '调整背景',
    'subtitle_settings/btn_body':       '调整正文',

    # ── 字幕设置页 tooltip（Python 侧）──
    'subtitle_settings/tooltip/page_title': (
        '<p align="center" size="15"><b>调整字幕位置</b></p>'
        '<p align="left">'
        '按下“编辑”进入编辑模式，然后选择对应按钮启用组件拖拽，按下重置按钮可恢复为默认。'
        '</p>'
        '<p align="left">'
        '<font class="secondary" size="13">若字幕显示处于简洁模式，则仅可调整正文。'
        '简洁模式与标准模式的字幕坐标独立保存，离开页面将自动保存。</font>'
        '</p>'
    ),

    # ── 帮助页 / 语音包详情页 ──
    'help/title':   '帮助',
    'help/tooltip/title': (
        '<p align="center" size="15"><b>关于插件的一些说明</b></p>'
        '<p align="left">'
        '插件介绍、使用说明、常见问题等等。'
        '</p>'
    ),
    'help/load_failed': '帮助内容加载失败，请检查文件完整性。',
    'detail/title': '语音包详情',
    'detail/no_info': '当前语音包未提供详情信息（info.html / info.txt）。',

    # ── ModsList 入口（Python 侧，仅 text() 使用）──
    'modslist/name':        '语音包管理插件',
    'modslist/description': '加载 wotmod 格式的语音包，支持语音修改、替换、字幕渲染等功能。',

    # ── 通知（notifier，Python 侧）──
    'notify/switch_title':      '切换语音：{0}',
    'notify/switch_success':    '切换成功',
    'notify/switch_fail':       '切换失败',
    'notify/enabled':           '语音包管理插件已<b>启用</b>',
    'notify/disabled':          '语音包管理插件已<b>禁用</b>',
    'notify/welcome_title':     '<font color="#cc9933"><b>语音包管理插件</b></font>',
    'notify/welcome_mods_list': '已安装 ModsList, 可通过车库底部入口打开菜单',
    'notify/welcome_hotkey':    '你也可以使用快捷键 <b>{0}</b> 呼出菜单',
    'notify/welcome_no_mods':   '缺少 ModsListAPI, 请按 <b>{0}</b> 快捷键打开菜单面板',
    'notify/welcome_no_mods_no_hotkey': '缺少 ModsListAPI, 热键当前处于禁用状态',
    'notify/welcome_config_hint': '请安装 ModsList 或编辑/删除 config.json 来恢复热键功能（路径：{0}）',
    'notify/welcome_footer':    '你现在可以管理和启用特定语音包了！插件当前版本：v<b>{0}</b>',
    'notify/current_voice':     '<font color="#cc9933"><b>当前语音：</b></font><font color="#e0ffff"><b>{0}</b></font>',
    'notify/stats_installed':   '已安装的语音包：',
    'notify/stats_installed_count': '语音包：',
    'notify/stats_added':       '新增语音包：',
    'notify/stats_no_new':      '没有检测到新的语音包。',
    'notify/stats_removed':     '已移除的语音包：',
    'notify/stats_empty':       '啊嘞？你没有装语音包吗？',
}


# ═════════════════════════════════════════════════════════════
# 缓存（懒加载；reload() 后重建）
# ═════════════════════════════════════════════════════════════

_cached_lang = None   # 当前生效语言（utf-8 字节串）
_cached_data = None   # 合并后的词典 {key: value}（utf-8 字节串）
_display_name_cache = {}  # lang -> 显示名（utf-8 字节串），reload() 清空
_client_dict = None   # 客户端语言词典（text_for_client 用，会话内固定）


# ═════════════════════════════════════════════════════════════
# 公开接口
# ═════════════════════════════════════════════════════════════


def get_effective_lang():
    """当前生效语言代码（utf-8 字节串）。

    settings.uiLang 非 'auto' → 用之；'auto' → helpers.getClientLanguage()。
    亚服客户端 auto 时返回 zh_sg（与 zh_cn 同为简中）——归一为 zh_cn，
    直接落中文基线；不归一的话 zh_sg 会经加载链先命中 en.json
    未收录语言（如 ru）原样返回——加载链会自动落 en（见 _ensure_loaded）。
    全部失败回退 zh_cn。
    """
    try:
        from .config import load_config
        ui_lang = load_config(log=False).get('settings', {}).get('uiLang', LANG_AUTO)
        if ui_lang and ui_lang != LANG_AUTO:
            return to_utf8(ui_lang)
    except Exception:
        pass
    try:
        from helpers import getClientLanguage
        lang = to_utf8(getClientLanguage())
        # zh_sg（亚服简中）与 zh_cn 同文——归一直接落中文基线
        return LANG_ZH_CN if lang == LANG_ZH_SG else lang
    except Exception:
        return LANG_ZH_CN


def get_available_langs():
    """可选语言代码列表（含内置 zh_cn；'auto' 由调用方恒加首位）。

    数据源: VFS l10n/ 目录枚举 + 内置 zh_cn + 磁盘 l10n/ 目录（用户自建）。
    显示名请用 get_lang_display_name(code)——读语言文件 __meta__.displayName，
    zh_cn 回退 LANG_DISPLAY_NAMES 内置表，未知代码原样显示。
    """
    langs = [LANG_ZH_CN]

    # VFS l10n/ 目录枚举（wotmod 打包的资源）
    try:
        import ResMgr
        sec = ResMgr.openSection(_VFS_L10N_ROOT)
        if sec is not None:
            for k in sec.keys():
                name = to_utf8(k)
                if name.endswith('.json') and name[:-5] not in langs:
                    langs.append(name[:-5])
    except Exception:
        pass

    # 磁盘 l10n/ 目录（用户自建语言）
    try:
        if os.path.isdir(_DISK_L10N_ROOT):
            for name in sorted(os.listdir(_DISK_L10N_ROOT)):
                if name.endswith('.json') and name[:-5] not in langs:
                    langs.append(name[:-5])
    except Exception:
        pass

    return langs


def get_lang_display_name(lang):
    """语言下拉显示名（母语名，utf-8 字节串）。

    数据源（磁盘优先 → VFS 兜底）: 语言文件顶部 __meta__.displayName。
    zh_cn 无词典文件 → 回退 LANG_DISPLAY_NAMES 内置表；未知语言代码
    原样显示代码。结果缓存于 _display_name_cache，reload() 清空
    （语言文件可被用户编辑，切换语言后重新读取）。
    """
    lang = to_utf8(lang)
    if lang in _display_name_cache:
        return _display_name_cache[lang]

    name = _read_display_name_from_files(lang)
    if name is None:
        name = LANG_DISPLAY_NAMES.get(lang, lang)
    _display_name_cache[lang] = name
    return name


def _read_display_name_from_files(lang):
    """从磁盘/VFS 语言文件读取 __meta__.displayName（utf-8 字节串）。

    磁盘文件缺失/损坏时自动用 VFS 对应文件覆盖恢复（_load_disk_json_or_restore）；
    磁盘解析成功但缺 displayName 时继续读 VFS。全部缺失、无 __meta__ 段
    或 displayName 为空均返回 None（回退内置表）。
    """
    for data in (_load_disk_json_or_restore(_disk_path(lang), _vfs_path(lang)),
                 load_vfs_json(_vfs_path(lang))):
        try:
            if data and isinstance(data, dict):
                meta = data.get('__meta__')
                if isinstance(meta, dict) and meta.get('displayName'):
                    return meta['displayName']
        except Exception:
            pass
    return None


def text(key, *args):
    """查询当前生效语言下 key 对应的文本（utf-8 字节串）。

    :param key:  英文语义键（如 'settings/nation_voice_title'）
    :param args: {0} {1} 数字占位符参数（可选；未传则保持原文）
    :return: 加载链命中值；全部缺失回退 UI_LABELS 中文基线，再缺失返回键名
    """
    _ensure_loaded()
    value = _cached_data.get(key)
    if value is None:
        value = UI_LABELS.get(key, key)
    if args:
        try:
            return value.format(*args)
        except (IndexError, KeyError, ValueError):
            pass  # 占位符与参数不匹配——保持原文，不抛异常
    return value


def text_for_client(key):
    """查询客户端语言（游戏本地化语言）下 key 的文本（utf-8 字节串）。

    与 text() 的区别：不随 settings.uiLang 变化——车长名、语言变体等取自
    游戏客户端本地化，其上的 tag、类型名、语言名需与之一致，故固定跟随
    客户端语言，与"车长名不译"同一边界。客户端语言会话内不变，词典
    懒加载并缓存（_ensure_client_dict）。未收录语言经加载链落 en，
    再落中文基线（与 text() 一致）。
    """
    _ensure_client_dict()
    value = _client_dict.get(key)
    if value is None:
        value = UI_LABELS.get(key, key)
    return value


def build_ui_labels():
    """构建推送给 Flash 的 UI 标签 dict（键 → 当前生效语言文本）。

    AS3 L 类经 as_setLabelsS 接收；页面构造时 L.get(key, 中文默认)
    仅作 labels 未到达前的首屏回退（两者默认一致，UI_LABELS 为唯一来源）。
    """
    _ensure_loaded()
    result = {}
    for key, zh_default in UI_LABELS.items():
        value = _cached_data.get(key)
        result[key] = value if value is not None else zh_default
    return result


def reload():
    """语言变更后重新解析词典（uiLang 切换时调用，随后重推全部页面）。

    同时清空显示名缓存——语言文件可被用户编辑，重新读取 displayName。
    """
    global _cached_lang, _cached_data
    _cached_lang = None
    _cached_data = None
    _display_name_cache.clear()
    logger.info('词典已重置，等待重新加载')


# ═════════════════════════════════════════════════════════════
# 内部实现
# ═════════════════════════════════════════════════════════════


def _ensure_loaded():
    """懒加载：首次查询时构建合并词典。"""
    global _cached_lang, _cached_data
    if _cached_data is not None:
        return

    lang = get_effective_lang()
    data = {}

    # 加载链（按键合并，"缺键才补"= 先 merge 的赢）——按优先级从高到低 merge:
    #   <lang>(磁盘) → <lang>(VFS) → en(磁盘) → en(VFS)
    # 磁盘层传对应 VFS 路径——磁盘文件缺失/损坏时自动用 VFS 覆盖恢复
    # zh_cn 无词典文件——跳过 en 层直接落中文基线（UI_LABELS）；否则
    # en.json 全量翻译会作为基底被先 merge，把简中界面整体变英文
    # （2026-08-06 实测修复：原顺序 en 在前，切任何语言都显示英文）。
    if lang != LANG_EN:
        _merge_file(data, _disk_path(lang), _vfs_path(lang))
        _merge_file(data, _vfs_path(lang))
    if lang != LANG_ZH_CN:
        _merge_file(data, _disk_path(LANG_EN), _vfs_path(LANG_EN))
        _merge_file(data, _vfs_path(LANG_EN))

    # __meta__ 是文件级元数据（如 displayName），不是词典键——pop 掉不入词典，
    # 避免 text()/build_ui_labels() 把它当普通键处理
    data.pop('__meta__', None)

    _cached_lang = lang
    _cached_data = data
    logger.info('词典已加载 (lang=%s, %d 键)', lang, len(data))


def _ensure_client_dict():
    """懒加载客户端语言词典（会话内固定，text_for_client 专用）。

    加载链与 _ensure_loaded 一致，但语言取 helpers.getClientLanguage()
    （游戏本地化语言）而非 settings.uiLang。客户端语言会话内不变，
    uiLang 切换无需重建。
    """
    global _client_dict
    if _client_dict is not None:
        return
    try:
        from helpers import getClientLanguage
        lang = to_utf8(getClientLanguage())
        # 亚服简中与 zh_cn 同文——归一直接落中文基线
        if lang == LANG_ZH_SG:
            lang = LANG_ZH_CN
    except Exception:
        lang = LANG_ZH_CN

    data = {}
    if lang != LANG_EN:
        _merge_file(data, _disk_path(lang), _vfs_path(lang))
        _merge_file(data, _vfs_path(lang))
    if lang != LANG_ZH_CN:
        _merge_file(data, _disk_path(LANG_EN), _vfs_path(LANG_EN))
        _merge_file(data, _vfs_path(LANG_EN))
    data.pop('__meta__', None)

    _client_dict = data
    logger.info('客户端语言词典已构建 (client_lang=%s)', lang)


def _load_disk_json_or_restore(disk_path, vfs_path):
    """读取磁盘词典；缺失/解析失败（损坏）时用 VFS 对应文件覆盖恢复。

    返回解析后的词典 dict；磁盘与 VFS 均不可用时返回 None。
    """
    data = load_jsonc(disk_path)
    if data is not None:
        return data
    return _restore_disk_json(vfs_path, disk_path)


def _restore_disk_json(vfs_path, disk_path):
    """磁盘词典缺失/损坏时，用 VFS 对应文件覆盖磁盘并返回解析结果。

    先解析 VFS 文件确认可用（VFS 亦损坏时返回 None，不覆盖磁盘原文件、
    继续回退加载链），再用 VFS 原始字节覆盖磁盘（保留注释等原样格式）。
    """
    loaded = load_vfs_json(vfs_path)
    if loaded is None:
        return None
    try:
        import os
        import ResMgr
        section = ResMgr.openSection(vfs_path)
        if section is None:
            return None
        disk_dir = os.path.dirname(disk_path)
        if disk_dir and not os.path.isdir(disk_dir):
            os.makedirs(disk_dir)
        with open(disk_path, 'wb') as fh:
            fh.write(section.asBinary)
        logger.info('已从 VFS 恢复磁盘词典: %s', disk_path)
        return loaded
    except Exception:
        return None


def _merge_file(data, path, vfs_path=None):
    """将单个词典文件按"缺键才补"语义并入 data（load_jsonc 自动过滤注释）。

    path 为磁盘层（加载链第一优先）时传 vfs_path 对应 VFS 路径：
    磁盘文件缺失或解析失败（损坏）时，自动用 VFS 对应文件覆盖磁盘
    （自愈，见 _load_disk_json_or_restore），再读磁盘副本。
    """
    try:
        if path.startswith('mods/'):
            loaded = load_vfs_json(path)
        else:
            loaded = _load_disk_json_or_restore(path, vfs_path)
        if loaded:
            for k, v in loaded.items():
                if k not in data:
                    data[k] = v
    except Exception:
        pass  # 文件缺失/损坏——跳过该层，继续回退


def _vfs_path(lang):
    """VFS 词典文件路径。"""
    return '%s/%s.json' % (_VFS_L10N_ROOT, lang)


def _disk_path(lang):
    """磁盘词典文件路径（用户可编辑副本）。"""
    return os.path.join(_DISK_L10N_ROOT, lang + '.json')
