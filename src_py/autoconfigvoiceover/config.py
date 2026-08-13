# coding=utf-8
"""配置文件读写。

写入: 基于纯文本模板 + json.dumps() 序列化每个值 →
      注释在模板中永久保留，不会被覆盖丢失。
读取: load_jsonc 过滤 // 注释行 → JSON 解析 → 与 DEFAULTS 深度合并。
"""

import json as _json_mod
import os
import re

from ._metadata import MOD_CONFIG_VERSION
from .constants import CONFIG_FILE, MY_CONFIG_FOLDER
from .utils import load_jsonc, deep_merge
from .logger import Logger


def _json_val(v):
    """将单个值 JSON 序列化，保留中文等非 ASCII 字符。

    Python 2 的 json.dumps 默认 ensure_ascii=True，会把中文转成
    \uXXXX 转义符。这里用 ensure_ascii=False 保留原始字符，
    若结果为 unicode 则编码回 utf-8 字节串（模板 .format() 需要 str）。
    """
    result = _json_mod.dumps(v, ensure_ascii=False)
    if isinstance(result, unicode):
        return result.encode('utf-8')
    return result

logger = Logger('Config')


# ═════════════════════════════════════════════════════════════
# 默认值 —— 新键在此追加，deep merge 自动补全旧配置
# ═════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════
# 全局启用/禁用标志
# ═════════════════════════════════════════════════════════════

_is_enabled = True


def is_enabled():
    """查询全局启用状态。所有钩子、语音切换、通知均应检查此标志。"""
    return _is_enabled


def set_enabled(value):
    """设置全局启用状态。返回旧值。"""
    global _is_enabled
    old = _is_enabled
    _is_enabled = bool(value)
    return old


DEFAULTS = {
    'position': {
        'normX': 0.5,
        'normY': 0.5,
    },
    'lastState': {
        'state':           'COLLAPSED',  # COLLAPSED | SEMI | EXPANDED
        'pageId':          'help',
        'smallCircles':    True,
        'semiPanel':       True,
        'fullPanel':       False,
        'circlesEnabled':  True,     # 左正方形按钮：小圆是否显示
        'panelLocked':     False,    # 右正方形按钮：面板是否锁定
        # 跨会话恢复：收起前最后非 COLLAPSED 状态 + 页面
        'lastNonCollapsedState':    'SEMI',     # SEMI | EXPANDED
        'lastNonCollapsedPageId':   'help',
    },
    'voice': {
        'currentVoiceId': 'default',   # 上次选中的语音 ID（重启恢复）
        'source':         'ingame',   # 'ingame' | 'outside'（所在面板）
        'typeIndex':      0,           # 更改类型下拉索引（仅内置有意义）
        'langIndex':      0,           # 更改语言下拉索引（仅内置有意义）
    },
    'settings': {
        'enabled':             True,
        'uiSoundEnabled':      True,
        'switchNotify':        False,
        'playOnSwitch':        True,
        'hotkeyEnabled':       True,
        'hotkey':              'F10',
        'logLevel':            2,
        'showIngameVoices':    False,
        'showInstalledVoices': False,
        'autoVolume':          True,
        'soundRemap':          True,
        'soundBind':           True,
        'voiceOverride':       True,
        'subtitleUpdate':      True,
        'subtitleAnim':        True,
        'multiSub':            False,
        'nationVoiceGender':   'male',
        'notifyPushLevel':     'count',
        'subtitleDisplay':     'standard',
        'textSpeed':           0.03,
        # colorScheme/bgIcon 存储稳定 ASCII token（第零期 token 化，2026-08）：
        #   colorScheme: 'default' / 'follow_pack' / 预设主题 name
        #                或语音包内嵌主题 pack_id（内容身份）
        #   bgIcon:      'default' / 'follow_pack' / 语音包 pack_id
        # 配置值不正确（不在选项列表）时由消费方回退本默认值
        'colorScheme':         'follow_pack',
        'bgIcon':              'follow_pack',
        'titleTextMode':       'followScheme',
        'titleTextColor':      '#D4D4D4',
        # uiLang: 'auto'（跟随客户端）或语言代码（'zh_cn' / 'zh_tw' / 'en'，
        #         或用户自建语言）。生效语言见 l10n.get_effective_lang()
        'uiLang':              'auto',
    },
}


# ═════════════════════════════════════════════════════════════
# 模板占位符 → 所在段 映射
# 由 DEFAULTS 自动推导，save_config 据此从模板占位符自动取键，
# 不再手写枚举键与兜底默认值（默认值只维护在 DEFAULTS 一处）。
# ═════════════════════════════════════════════════════════════

# 匹配模板中 {xxx} 形式的简单占位符（本模板不含 {xxx:fmt} 规格）
_PLACEHOLDER_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')

_PLACEHOLDER_SECTION = {}
for _section, _body in DEFAULTS.items():
    for _key in _body:
        _PLACEHOLDER_SECTION[_key] = _section


# ═════════════════════════════════════════════════════════════
# 写入模板 —— 注释写在这里，永久保留
# ═════════════════════════════════════════════════════════════

_TEMPLATE = '''\
// [语音包管理插件]的配置文件，如果你想要这个配置文件变回默认，请删除它
// To generate default config, delete config file and launch a game again
// [learn more] https://github.com/25304-Oxygen/wot-autoconfig-voiceover
{{

    //
    // 记录菜单所在位置，使用归一化坐标，不建议自行编辑
    //
    "position": {{
        "normX": {normX},
        "normY": {normY}
    }},

    //
    // 记录菜单展开状态，不建议自行编辑
    //
    "lastState": {{
        "state": {state},
        "pageId": {pageId},
        "smallCircles": {smallCircles},
        "semiPanel": {semiPanel},
        "fullPanel": {fullPanel},
        "circlesEnabled": {circlesEnabled},
        "panelLocked": {panelLocked},
        "lastNonCollapsedState": {lastNonCollapsedState},
        "lastNonCollapsedPageId": {lastNonCollapsedPageId}
    }},

    //
    // 记录语音包选择结果，不建议自行编辑
    //
    "voice": {{
        "currentVoiceId": {currentVoiceId},
        "source": {source},
        "typeIndex": {typeIndex},
        "langIndex": {langIndex}
    }},

    //
    // 以下是设置页相关设置，可以自行编辑
    // You can edit these settings manually
    //
    "settings": {{

        //
        // 插件启用 / 禁用，禁用后将卸载对声音模块的编辑，关闭字幕功能，但不会主动禁用热键
        // 插件启用期间会将所有 2D 声音转为当前自身位置发出的 3D 声音，以满足字幕驱动模块需求
        // 最干净的“禁用”是直接卸载插件
        // （true / false）
        //
        "enabled": {enabled},

        //
        // UI 音效开关，控制菜单操作的音效播放
        // （true / false）
        //
        "uiSoundEnabled": {uiSoundEnabled},

        //
        // 切换语音包时是否接收切换通知
        // （true / false）
        //
        "switchNotify": {switchNotify},

        //
        // 切换语音包后是否播放选中语音 vo_selected，这个声音可以使用重映射功能替换
        // （true / false）
        //
        "playOnSwitch": {playOnSwitch},

        //
        // 是否开启热键功能，通过热键快捷打开/关闭菜单
        // 可能与其他热键冲突，建议使用 ModsList 作为入口或避开常用热键
        // （true / false）
        // 
        "hotkeyEnabled": {hotkeyEnabled},

        //
        // 热键代码，使用热键字典的键名，不建议自行编辑
        //
        "hotkey": {hotkey},

        //
        // 日志等级，0=仅错误信息，1=警告信息及以上，2=通知信息及以上，3=调试信息及以上
        // （0 / 1 / 2 / 3）
        //
        "logLevel": {logLevel},

        //
        // 声音模式是否在设置菜单可见，由于菜单实现了随时呼出，特殊语音覆盖功能将始终可用
        // 设置游戏自带的语音包是否可见，这个列表会很长
        // （true / false）
        //
        "showIngameVoices": {showIngameVoices},

        //
        // 设置安装的第三方的语音包是否可见
        // （true / false）
        //
        "showInstalledVoices": {showInstalledVoices},

        //
        // 通过插件切换语音包时自动应用已保存的音量方案
        // （true / false） 
        //
        "autoVolume": {autoVolume},

        //
        // 是否使用语音包的自定义重映射方案，这个方案会随语音包一同切换
        // 允许语音替换某些 Wwise 事件的声音，用于丰富语音包体验
        // （true / false）
        //
        "soundRemap": {soundRemap},

        //
        // 是否使用语音包的自定义声音绑定方案，这个方案会随语音包一同切换
        // 允许语音包在某些指令 / 声音触发后，播放指定语音，用于丰富语音包体验
        // （true / false）
        //
        "soundBind": {soundBind},

        //
        // 使用特殊车长时是否强制拉回插件选择的语音，关闭后特殊车长使用自己的特殊语音
        // （true / false）
        //
        "voiceOverride": {voiceOverride},

        //
        // 是否允许字幕更新内容，同一个说话人下一条字幕将以内容更新的方式出现
        // （true / false）
        //
        "subtitleUpdate": {subtitleUpdate},

        //
        // 是否允许字幕入场后使用额外动画，该效果不适用于简洁模式下的字幕
        // （true / false）
        //
        "subtitleAnim": {subtitleAnim},

        //
        // 是否允许多条语音的字幕队列同时出现在屏幕
        // 关闭后，新语音和字幕将打断上一条语音及其字幕
        // （true / false）
        //
        "multiSub": {multiSub},

        //
        // 使用系别语音时，切换成员性别
        // （"male" / "female"）
        //
        "nationVoiceGender": {nationVoiceGender},

        //
        // 语音包统计信息输出，可选择：不输出、已有的语音仅计数、展示详细列表
        // 无论 "count" 还是 "detail" 模式均会详细展示语音包增减情况
        // （"none" / "count" / "detail"）
        //
        "notifyPushLevel": {notifyPushLevel},

        //
        // 字幕显示设置：标准、简洁、不显示
        // （"standard" / "simple" / "none"）
        //
        "subtitleDisplay": {subtitleDisplay},

        //
        // 字幕文本出字速度，速度为 0 表示无出字效果
        // （0 - 0.1，步长 0.01）
        //
        "textSpeed": {textSpeed},

        //
        // 菜单颜色方案，不建议自行编辑
        // （"default" / "follow_pack" / 预设主题名称或语音包标识）
        //
        "colorScheme": {colorScheme},

        //
        // 菜单背景图标方案，不建议自行编辑
        // （"default" / "follow_pack" / 语音包标识）
        //
        "bgIcon": {bgIcon},

        //
        // 标题颜色选择跟随当前颜色方案或者自定义
        // ("followScheme" / "custom")
        //
        "titleTextMode": {titleTextMode},

        //
        // 自定义标题颜色，使用十六进制颜色代码
        // example: "#D4D4D4"
        //
        "titleTextColor": {titleTextColor},

        //
        // 界面语言，用于插件菜单的显示语言
        // （"auto" 跟随客户端 / "zh_cn" / "zh_tw" / "en"）
        //
        "uiLang": {uiLang}
    }},

    // 
    // 版本号，不要修改
    // DO NOT edit version field
    //
    "__version__": {version}
}}'''


# ═════════════════════════════════════════════════════════════
# 公开接口
# ═════════════════════════════════════════════════════════════


def load_config(log=True):
    """读取配置文件，与 DEFAULTS 深度合并。

    文件不存在 → 返回 DEFAULTS 副本。
    文件缺少某键 → DEFAULTS 中的值自动补全。
    """
    data = load_jsonc(CONFIG_FILE)
    if data is None:
        logger.debug('配置文件不存在，使用默认值')
        return dict(DEFAULTS)  # 浅拷贝即可，值都是简单不可变类型

    merged = deep_merge(DEFAULTS, data)
    if log:
        logger.debug('配置已加载（%d 个顶层键）', len(merged))
    return merged


def save_config(changes):
    """合并变更并以带注释的模板格式写入文件。

    内部流程:
      1. 读磁盘当前配置（不存在则从空 dict 开始）
      2. 将 changes 深度合并进去
      3. 用 json.dumps() 序列化每个值，填入模板，写回磁盘

    每个配置值单独序列化，确保类型正确:
      True → true,  "settings" → "settings",  0.65 → 0.65

    :param changes: 待更新的键值对，只传有变更的键
    """
    if not os.path.exists(MY_CONFIG_FOLDER):
        os.makedirs(MY_CONFIG_FOLDER)

    current = load_jsonc(CONFIG_FILE)
    if current is None:
        current = {}

    # DEFAULTS 兜底 → 磁盘现状 → 本次变更，保证每个占位符都有真实默认值可写
    merged = deep_merge(DEFAULTS, current)
    merged = deep_merge(merged, changes)

    # 从模板占位符自动构造 format 参数（避免手写枚举）。
    # DEFAULTS 已合并进 merged，故 section 与键必然存在，直接下标取值。
    fmt_args = {}
    for placeholder in _PLACEHOLDER_RE.findall(_TEMPLATE):
        if placeholder == 'version':
            fmt_args[placeholder] = MOD_CONFIG_VERSION
            continue
        section = _PLACEHOLDER_SECTION.get(placeholder)
        if section is None:
            raise ValueError(
                '模板占位符 {%s} 在 DEFAULTS 中无对应键，请补全 DEFAULTS' % placeholder)
        fmt_args[placeholder] = _json_val(merged[section][placeholder])

    text = _TEMPLATE.format(**fmt_args)

    with open(CONFIG_FILE, 'w') as fh:
        fh.write(text)

    logger.debug('配置已保存')
