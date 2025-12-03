# coding=utf-8
"""
    UI Text & UI Template
    各种模板，所有将被显示在UI上的文本都在这里。
"""
from constants import MY_LOG_PATH
MY_MODS_DISPLAY_NAME = '语音包管理插件'
COMMANDER_VO_LABEL = [{'label': '车长语音'}]
CREW_VO_LABEL = [{'label': '车长语音'}, {'label': '车组语音'}]
Full_Crew_tag = '[含车组]'
Multi_Lingual_tag = '[多语言]'
CONFIG_TEMPLATE = """{{
    // [语音包管理插件]的配置文件，如果你想要这个配置文件变回默认，请删除它
    // To generate default config, delete config file and launch a game again
    // [learn more] https://github.com/25304-Oxygen/wot-autoconfig-voiceover
    
    //
    // 表示当前插件启用/禁用，禁用插件时，将恢复为原来的语音状态
    // Everything will go back to normal when the mod is disabled
    //
    // Valid values: true/false
    //
    "enabled": {enabled},
    
    //
    // 当语音列表可选：0或1
    // 0 -> 语音选择下拉列表将展示游戏内自带的语音包
    // 1 -> 语音选择下拉列表将展示已安装语音包
    //
    // Select the list of voice packs to display
    //
    // Valid values: 0/1    (ingame-voice/3rd-part-voice)
    //
    "vo_list_option": {vo_list_option},
    
    //
    // 当前所用语音的lang名，在插件中会被解析为索引值
    // 这个lang名是指voiceover.json、gameSoundModes.json中保存的voiceID字段，它们位于jsons文件夹中
    // 当这个索引值对应的语音在两个语音列表中都不存在时，将被修改为默认语音
    // 默认语音为default
    //
    // Valid values: The string of the voice ID (default: "default")
    // you can find it in 'voiceover.json' and 'gameSoundModes.json' in the jsons folder.
    //
    // It will be parsed as an index value in the mod
    //
    "current_voice": "{current_voice}",
    
    //
    // 使用系别语音时，切换成员性别
    // 0 -> 男性
    // 1 -> 女性
    // Switch gender while using nation voice
    //
    // Valid values: 0/1    (male/female)
    //
    "nation_voice_gender" : {nation_voice_gender},
    
    //
    // 当特殊语音拥有额外的车组语音时，你可以选择切换车长语音或车组语音
    // 若额外语音不存在，则自动切换为车长语音
    // 0 -> 车长语音
    // 1 -> 车组语音
    //
    // Use special mode voice on some special commanders
    //
    // Valid values:
    // 0 -> commander voice (default option)
    // 1 -> crew voice  (if option exists)
    //
    "full_crew": {full_crew},
    
    //
    // 更换特殊语音的语言类型
    // 可能有这些分类：标准、RU、CN、EN
    // 0 -> 默认语言（可能不是中文）
    //
    // Switch the language of the special voice
    // possible categories: Standard, RU, CN, EN
    // Valid values: integer
    //
    // 0 -> default (Stander)
    // 
    "language_tag": {language_tag},
    
    //
    // 声音模式是否在设置菜单可见，开启后语音覆盖功能将暂时关闭
    // 设置游戏自带的语音包是否可见，这个列表会很长，而且是空白的，建议不要开
    // Display voice options in the settings menu and disable voice overlay
    // outside voice equals 3rd-part voice pack.
    //
    // Actually, you will see a blank list. I just kept this feature.
    //
    // Valid values (the same applies below): true/false
    //
    "ingame_voice_visible": {ingame_voice_visible},
    
    //
    // 设置你安装的语音包是否可见，开启后语音覆盖功能将暂时关闭
    //
    "outside_voice_visible": {outside_voice_visible},
    
    //
    // 通过插件切换语音包时自动应用已保存的音量方案
    // Set the volume of 'Voice Notifications' when switching voices by mod
    // the volume level is based on the saved information.
    //
    "auto_volume": {auto_volume},
    
    //
    // 使用语音包的自定义重映射方案
    // 它将替代audio_mods.xml执行语音替换的功能，以保证使用语音包的最佳体验
    // Use custom remapping information provided by a 3rd-party voice pack
    // to replace the specified sound, which functions the same as audio_mods.xml.
    //
    "auto_remapping": {auto_remapping},
    
    //
    // 进入游戏后你将收到已安装的第三方语音包统计数据
    // true -> 详细的名单列表
    // false -> 仅统计语音包的数量
    //
    // Mod will automatically notify the information of the existing 3rd-party voices.
    // true -> Show namelist
    // false -> Types and Counts
    //
    "show_details": {show_details},
    
    //
    // 切换语音时，接收来自该语音包的自定义的通知信息（如果有的话）
    // 关闭后，仍可通过点击右侧图片来获取该信息（如果有的话）
    // When switching to a voice, receive custom notification from it (if any)
    // you can do this anytime by just clicking the picture on the right.
    //
    "info_notify": {info_notify},
    
    // 
    // 版本号，不要修改
    // DO NOT edit version field
    //
    "__version__": {__version__}
}}"""
PLAY_EVENTS_TEMPLATE = [{
    "name": "战斗开始",
    "id": "vo_start_battle"}, {
    "name": "战车被毁",
    "id": "vo_vehicle_destroyed"}, {
    "name": "被点亮音效1",
    "id": "lightbulb"}, {
    "name": "火炮预警",
    "id": "artillery_lightbulb"}, {
    "name": "通讯范围内首次出现敌军",
    "id": "enemy_sighted_for_team"}, {
    "name": "溅射击伤",
    "id": "vo_damage_by_near_explosion_by_player"}, {
    "name": "点燃对手",
    "id": "vo_enemy_fire_started_by_player"}, {
    "name": "重创对手",
    "id": "vo_enemy_hp_damaged_by_projectile_and_chassis_damaged_by_player"}, {
    "name": "击穿目标",
    "id": "vo_enemy_hp_damaged_by_projectile_by_player"}, {
    "name": "击毁敌方坦克",
    "id": "vo_enemy_killed_by_player"}, {
    "name": "锁定目标",
    "id": "vo_target_captured"}, {
    "name": "目标丢失",
    "id": "vo_target_lost"}, {
    "name": "解除锁定",
    "id": "vo_target_unlocked"}, {
    "name": "击毁盟友",
    "id": "vo_ally_killed_by_player"}, {
    "name": "未击穿装甲",
    "id": "vo_armor_not_pierced_by_player"}, {
    "name": "跳弹",
    "id": "vo_armor_ricochet_by_player"}, {
    "name": "致命一击（未造成HP伤害）",
    "id": "vo_enemy_no_hp_damage_at_attempt_and_chassis_damaged_by_player"}, {
    "name": "车长受重伤",
    "id": "vo_commander_killed"}, {
    "name": "驾驶员受重伤",
    "id": "vo_driver_killed"}, {
    "name": "炮手受重伤",
    "id": "vo_gunner_killed"}, {
    "name": "装填手受重伤",
    "id": "vo_loader_killed"}, {
    "name": "通讯兵受重伤",
    "id": "vo_radioman_killed"}, {
    "name": "车组全员阵亡",
    "id": "vo_crew_deactivated"}, {
    "name": "战车起火",
    "id": "vo_fire_started"}, {
    "name": "火被扑灭了",
    "id": "vo_fire_stopped"}, {
    "name": "弹药架受损",
    "id": "vo_ammo_bay_damaged"}, {
    "name": "油箱被击中",
    "id": "vo_fuel_tank_damaged"}, {
    "name": "电台受损",
    "id": "vo_radio_damaged"}, {
    "name": "履带被击毁",
    "id": "vo_track_destroyed"}, {
    "name": "发动机受损",
    "id": "vo_engine_damaged"}, {
    "name": "发动机被击毁",
    "id": "vo_engine_destroyed"}, {
    "name": "发动机完成修复",
    "id": "vo_engine_functional"}, {
    "name": "主炮受损",
    "id": "vo_gun_damaged"}, {
    "name": "主炮被击毁",
    "id": "vo_gun_destroyed"}, {
    "name": "主炮完成修复",
    "id": "vo_gun_functional"}, {
    "name": "炮塔座圈受损",
    "id": "vo_turret_rotator_damaged"}, {
    "name": "炮塔无法转动",
    "id": "vo_turret_rotator_destroyed"}, {
    "name": "炮塔座圈修复",
    "id": "vo_turret_rotator_functional"}, {
    "name": "战斗中组队：发送协助请求",
    "id": "vo_dp_assistance_been_requested"}, {
    "name": "战斗中组队：创建小队",
    "id": "vo_dp_platoon_created"}, {
    "name": "战斗中组队：加入小队",
    "id": "vo_dp_platoon_joined"}, {
    "name": "战斗中组队：新玩家入队",
    "id": "vo_dp_player_joined_platoon"}, {
    "name": "战斗中组队：解散小队",
    "id": "vo_dp_platoon_dismissed"}, {
    "name": "战斗中组队：主动离队",
    "id": "vo_dp_left_platoon"}, {
    "name": "战斗中组队：被踢出小队",
    "id": "vo_dp_been_excluded_platoon"}, {
    "name": "前往目标地点/占领基地",
    "id": "ibc_pc_ping_action"}, {
    "name": "注意此区域/装填中",
    "id": "ibc_pc_ping_attention"}, {
    "name": "【由你】战斗中通讯：收到",
    "id": "ibc_vo_pc_reply_affirmative"}, {
    "name": "【由你】战斗中通讯：发出支援",
    "id": "ibc_vo_pc_reply_sos"}, {
    "name": "【由你】战斗中通讯：谢谢",
    "id": "ibc_vo_pc_reply_thank_you"}, {
    "name": "【由你】战斗中通讯：请求支援",
    "id": "ibc_vo_pc_request_sos"}, {
    "name": "【由你】战斗中通讯：请求撤退",
    "id": "ibc_vo_pc_request_retreat"}, {
    "name": "【队友】战斗中通讯：收到",
    "id": "ibc_vo_npc_reply_affirmative"}, {
    "name": "【队友】战斗中通讯：发出支援",
    "id": "ibc_vo_npc_reply_sos"}, {
    "name": "【队友】战斗中通讯：谢谢",
    "id": "ibc_vo_npc_reply_thank_you"}, {
    "name": "【队友】战斗中通讯：请求支援",
    "id": "ibc_vo_npc_request_sos"}, {
    "name": "【队友】战斗中通讯：请求撤退",
    "id": "ibc_vo_npc_request_retreat"
}]

EVENTS_LIST = [{'label': item['name']} for item in PLAY_EVENTS_TEMPLATE]


def column_a_ingame_voices(config, iv_list, voice_data):
    return [
        {
            'type': 'Label',
            'text': '> 游戏内语音包设置面板',
            'tooltip': '{HEADER}关于插件的介绍{/HEADER}'
                       '{BODY}通过下方单选按钮可以切换游戏内语音包设置面板与第三方语音包设置面板。'
                       '\n·带有按钮的布局元素：'
                       '\n通过点按右侧按钮保存并应用所选项（例如下拉列表）'
                       '\n·不带按钮的布局元素：'
                       '\n通过点按插件管理器下方的保存或保存并退出按钮应用改动（如复选框）'
                       '\n\n重新打开设置面板来手动刷新界面。{/BODY}'
        },
        {
            'type': 'Label',
            'text': '> 关于插件生成的文件',
            'tooltip': ('{HEADER}文件信息说明{/HEADER}'
                        '{BODY}配置文件所在路径：%s\n'
                        '\n> config.json\n保存当前的设置信息。'
                        '\n> playEvents.json\n测试声音时选择播放的事件。'
                        '\n> voiceover.json\n保存第三方语音包信息。'
                        '\n> gameSoundModes.json\n保存游戏内语音包信息。'
                        '\n> script.log\n日志文件，记录插件运行状态与异常信息。{/BODY}' % MY_LOG_PATH)
        },
        {
            'type': 'RadioButtonGroup',
            'text': '当前的语音包列表',
            'tooltip': '{BODY}点击切换后，重新打开设置面板来手动刷新界面。{/BODY}',
            'options': [
                {'label': '游戏内语音包'},
                {'label': '添加的语音包'}
            ],
            'button': {
                'width': 60,
                'height': 24,
                'text': '切换'
            },
            'value': config['vo_list_option'],
            'varName': 'vo_list_option'
        },
        {
            'type': 'Dropdown',
            'text': '游戏内语音包',
            'tooltip': '{HEADER}自动扩充的语音包列表{/HEADER}'
                       '{BODY}在版本更新或新语音包出现在游戏中时，它将自动被添加进这个列表并通报。语音包名称通过客户端获取，'
                       '你可以在gameSoundModes.json中随意修它的名字。'
                       '\n点击应用后，重新打开设置面板来手动刷新界面。\n{/BODY}'
                       '{ATTENTION}根据所在客户端/服务器的不同，部分语音包会因为实际并不存于游戏资源文件中，而无法使用。{/ATTENTION}',
            'options': iv_list,
            'button': {
                'width': 60,
                'height': 24,
                'text': '应用'
            },
            'width': 230,
            'value': config['current_voice'],
            'varName': 'current_voice'
        },
        {
            'type': 'Dropdown',
            'text': '测试声音',
            'tooltip': '{HEADER}可以用来播放任何声音{/HEADER}'
                       '{BODY}播放列表保存在playEvent.json中可供你随意更改。\n{/BODY}'
                       '{NOTE}bnk是动态加载的，若这个声音所在的bnk尚未被加载进内存，则无法播放。{/NOTE}',
            'options': EVENTS_LIST,
            'button': {
                'width': 60,
                'height': 24,
                'iconSource': '../maps/icons/buttons/sound.png',
                'iconOffsetLeft': 1
            },
            'width': 230,
            'value': config['__event__'],
            'varName': '__event__'
        },
        {
            'type': 'Slider',
            'text': '调整音量',
            'tooltip': '{HEADER}单独为该语音包调节音量{/HEADER}'
                       '{BODY}滑块作用和你在设置界面的效果是一样的，点击右侧按钮后，音量改动将立即生效。'
                       '\n切换为未设置音量的语音包时，会将音量同步为你之前设置的音量大小。'
                       '\n切换为已设定音量的语音包时，重新打开界面即可查看当前语音包音量方案。\n{/BODY}'
                       '{NOTE}音量信息将会保存进gameSoundModes.json{/NOTE}',
            'button': {
                'width': 60,
                'height': 24,
                'text': '设定'
            },
            'minimum': 0,
            'maximum': 100,
            'snapInterval': 1,
            'value': voice_data['volume'],
            'format': '{{value}}',
            'varName': 'volume'
        }
    ]


def column_b_ingame_voices(config, voice_data):
    return [
        {
            'type': 'RadioButtonGroup',
            'text': '系别语音类型',
            'tooltip': '{HEADER}使用系别语音时指定成员性别{/HEADER}'
                       '{BODY}仅在使用系别语音时生效。{/BODY}',
            'options': [
                {'label': '糙汉子'},
                {'label': '萌妹子'}
            ],
            'button': {
                'width': 70,
                'height': 24,
                'text': '超级变换'
            },
            'value': config['nation_voice_gender'],
            'varName': 'nation_voice_gender'
        },
        {
            'type': 'Dropdown',
            'text': '特殊语音类型',
            'tooltip': '{HEADER}针对部分特殊成员生效{/HEADER}'
                       '{BODY}对于拥有车组语音的车长，我在ta的名字后添加了对应标签。{/BODY}',
            'options': CREW_VO_LABEL if voice_data['full_crew'] else COMMANDER_VO_LABEL,
            'button': {
                'width': 60,
                'height': 24,
                'text': '应用'
            },
            'width': 140,
            'value': config['full_crew'],
            'varName': 'full_crew'
        },
        {
            'type': 'Dropdown',
            'text': '切换语言',
            'tooltip': '{HEADER}针对部分特殊成员生效{/HEADER}'
                       '{BODY}部分语音拥有多语言选项，RU、CN、EN分别对应俄语、汉语、英语。'
                       '\n对于拥有多语言语音的车长，我在ta的名字后添加了对应标签。{/BODY}',
            'options': voice_data['language_tag_list'],
            'button': {
                'width': 60,
                'height': 24,
                'text': '应用'
            },
            'width': 140,
            'value': config['language_tag'],
            'varName': 'language_tag'
        },
        {
            'type': 'CheckBox',
            'text': '使游戏内语音包可见',
            'tooltip': '{HEADER}将语音包添加到设置菜单选项中{/HEADER}'
                       '{BODY}勾选并保存设置后，你可以在设置菜单的语音选择中，找到游戏内已有的语音，并随时更改。'
                       '\n不过因为标准语音以外的语音没有设置显示名字，你实际上会看到一片空白。\n{/BODY}'
                       '{ATTENTION}开启后将暂时关闭屏蔽特殊语音的功能。{/ATTENTION}',
            'value': config['ingame_voice_visible'],
            'varName': 'ingame_voice_visible'
        },
        {
            'type': 'CheckBox',
            'text': '使已安装的语音包可见',
            'tooltip': '{HEADER}将语音包添加到设置菜单选项中{/HEADER}'
                       '{BODY}勾选并保存设置后，你可以在设置菜单的语音选择中，找到已创建的声音模式，并随时更改。\n{/BODY}'
                       '{ATTENTION}开启后将暂时关闭屏蔽特殊语音的功能。{/ATTENTION}',
            'value': config['outside_voice_visible'],
            'varName': 'outside_voice_visible'
        },
        {
            'type': 'CheckBox',
            'text': '切换语音包时自动切换音量',
            'tooltip': '{HEADER}使用语音包已保存的音量方案{/HEADER}'
                       '{BODY}勾选并保存设置后，在切换语音包时，会替你自动修改战斗语音的音量。'
                       '\n切换语音包并重新打开界面，音量滑块将正确的显示当前语音包音量设置。\n{/BODY}'
                       '{ATTENTION}只有通过插件切换语音才能同步修改音量。{/ATTENTION}',
            'value': config['auto_volume'],
            'varName': 'auto_volume'
        },
        {
            'type': 'CheckBox',
            'text': '接收已安装语音包详情通知',
            'tooltip': '{HEADER}详细统计信息 / 简略统计信息{/HEADER}'
                       '{BODY}勾选并保存：进入游戏后通报已安装语音包详细名单。'
                       '\n取消勾选并保存：将仅通报已安装语音包的类别及其数量。{/BODY}',
            'value': config['show_details'],
            'varName': 'show_details'
        }
    ]


def column_a_outside_voices(config, ov_list, voice_data):
    return [
        {
            'type': 'Label',
            'text': '> 已安装语音包设置面板',
            'tooltip': '{HEADER}添加并管理第三方语音包{/HEADER}'
                       '{BODY}按指定方式打包的语音包将会被收录在此处。'
                       '\n这些酷炫的语音包可能包含：'
                       '\n一张图片用于展示，一个用于切换语音后播放的Wwise事件，切换后弹出的自定义文本，'
                       '\n可获取的、自定义的语音重映射列表用于替换任意声音，以及字幕效果。\n{/BODY}'
                       '{NOTE}相关教程由作者：bilibili@“下一个车站等你”发布。{/NOTE}'
        },
        {
            'type': 'RadioButtonGroup',
            'text': '当前语音包列表',
            'tooltip': '{BODY}点击切换后，重新打开设置面板来手动刷新界面。{/BODY}',
            'options': [
                {'label': '游戏内语音包'},
                {'label': '添加的语音包'}
            ],
            'button': {
                'width': 60,
                'height': 24,
                'text': '切换'
            },
            'value': config['vo_list_option'],
            'varName': 'vo_list_option'
        },
        {
            'type': 'Dropdown',
            'text': '已安装的语音包',
            'tooltip': '{HEADER}已安装了语音包但是找不到？{/HEADER}'
                       '{BODY}找不到对应的语音包：'
                       '\n1.安装的语音包没有打包成正确的wotmod文件，插件只能识别指定方式打包的语音包。'
                       '\n2.打包的方式不正确或者读取语音包信息时出现了错误，请检查日志。'
                       '\n\n点击应用后，重新打开设置面板来手动刷新界面。{/BODY}',
            'options': ov_list,
            'button': {
                'width': 60,
                'height': 24,
                'text': '应用'
            },
            'width': 230,
            'value': config['current_voice'],
            'varName': 'current_voice'
        },
        {
            'type': 'Dropdown',
            'text': '测试声音',
            'tooltip': '{HEADER}可以用来播放任何声音{/HEADER}'
                       '{BODY}播放列表保存在playEvent.json中可供你随意更改。\n{/BODY}'
                       '{NOTE}bnk是动态加载的，若这个声音所在的bnk尚未被加载进内存，则无法播放。{/NOTE}',
            'options': EVENTS_LIST,
            'button': {
                'width': 60,
                'height': 24,
                'iconSource': '../maps/icons/buttons/sound.png',
                'iconOffsetLeft': 1
            },
            'width': 230,
            'value': config['__event__'],
            'varName': '__event__'
        },
        {
            'type': 'Slider',
            'text': '调整音量',
            'tooltip': '{HEADER}单独为该语音包调节音量{/HEADER}'
                       '{BODY}滑块作用和你在设置界面的效果是一样的，点击右侧按钮后，音量改动将立即生效。'
                       '\n切换为未设置音量的语音包时，会将音量同步为你之前设置的音量大小。'
                       '\n切换为已设定音量的语音包时，重新打开界面即可查看当前语音包音量方案。\n{/BODY}'
                       '{NOTE}音量信息将会保存进voiceover.json{/NOTE}',
            'button': {
                'width': 60,
                'height': 24,
                'text': '设定'
            },
            'minimum': 0,
            'maximum': 100,
            'snapInterval': 1,
            'value': voice_data['volume'],
            'format': '{{value}}',
            'varName': 'volume'
        },
        {
            'type': 'CheckBox',
            'text': '启用语音重映射',
            'tooltip': '{HEADER}使用动态重映射{/HEADER}'
                       '{BODY}此功能可以使语音包替换战斗语音之外的声音，与audio_mods.xml功能相同。'
                       '\n切换语音包的同时，将切换语音重映射方案，若不存在重映射方案，将不会替换声音。{/BODY}'
                       '{ATTENTION}开启后需要通过插件切换重映射。{/ATTENTION}',
            'button': {
                'width': 70,
                'height': 24,
                'offsetLeft': 100,
                'text': '查看映射'
            },
            'value': config['auto_remapping'],
            'varName': 'auto_remapping'
        }
    ]


def column_b_outside_voices(config, voice_data):
    return [
        {
            'type': 'CheckBox',
            'text': '切换语音后展示语音包信息',
            'tooltip': '{HEADER}接受自定义的通知信息{/HEADER}'
                       '{BODY}切换语音包后，你还将收到一条来自语音包的自定义通知信息，并播放选中语音vo_selected。'
                       '\n你可以随时点击图片获取这条通知信息。\n{/BODY}'
                       '{NOTE}PS：下面的图片其实是一个巨大的按钮。{/NOTE}',
            'button': {
                'width': 300,
                'height': 300,
                'offsetTop': 30,
                'offsetLeft': -200,
                'iconSource': voice_data['icon'],
                'iconOffsetTop': 0,
                'iconOffsetLeft': 1
            },
            'value': config['info_notify'],
            'varName': 'info_notify'
        }
    ]
