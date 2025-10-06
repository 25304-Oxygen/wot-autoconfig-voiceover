# coding=utf-8
"""
    需要用到的一些常量，以及默认的文件模板。
"""
import os
import ResMgr
import SoundGroups
MY_MODS_VERSION = '0.0.3'
GAME_ROOT_PATH = os.path.normpath(ResMgr.resolveToAbsolutePath('../..'))    # F:/World_of_Tanks_CN  以坦克世界2.0.0.0版本为例。
RES_MODS_PATH = os.path.normpath(ResMgr.resolveToAbsolutePath('.'))         # F:/World_of_Tanks_CN/res_mods/2.0.0.0
MODS_PATH = RES_MODS_PATH.replace('res_', '')                    # F:/World_of_Tanks_CN/mods/2.0.0.0
RES_MODS_AUDIOWW = os.path.join(RES_MODS_PATH, 'audioww')               # F:/World_of_Tanks_CN/res_mods/2.0.0.0/audioww
MODS_ROOT_PATH = os.path.join(GAME_ROOT_PATH, 'mods')                   # F:/World_of_Tanks_CN/mods
CONFIGS_ROOT_PATH = os.path.join(MODS_ROOT_PATH, 'configs')             # F:/World_of_Tanks_CN/mods/configs
MY_LOG_PATH = os.path.join(CONFIGS_ROOT_PATH, 'autoConfigVoiceOver')    # ../configs/autoConfigVoiceOver
VOICEOVER_INFO_PATH = os.path.join(MY_LOG_PATH, 'voiceover_info')       # ../autoConfigVoiceOver/voiceover_info
TEMPLATE_JSON_PATH = os.path.join(MY_LOG_PATH, 'template_json')         # ../autoConfigVoiceOver/template_json
INFO_JSON = os.path.join(VOICEOVER_INFO_PATH, 'info.json')                      # ../voiceover_info/info.json
DEFAULT_MODES_JSON = os.path.join(VOICEOVER_INFO_PATH, 'default_modes.json')    # ../voiceover_info/default_modes.json
GAME_SOUND_MODES_JSON = os.path.join(MY_LOG_PATH, 'gameSoundModes.json')    # ../autoConfigVoiceOver/gameSoundModes.json
PLAY_EVENTS_JSON = os.path.join(MY_LOG_PATH, 'playEvents.json')         # ../autoConfigVoiceOver/playEvents.json
CONFIG_JSON = os.path.join(MY_LOG_PATH, 'config.json')                  # ../autoConfigVoiceOver/config.json
UPDATE_PNG = os.path.join(MY_LOG_PATH, 'update.png')                    # ../autoConfigVoiceOver/update.png
DEFAULT_PNG = os.path.join(MY_LOG_PATH, 'default.png')                  # ../autoConfigVoiceOver/default.png
WHERE_AM_I = ''
WHERE_ARE_PARENT = ''
REMOVE_PROCESS = 'remove_old_archive.bat'
OBJ_FILES = []
CURRENT_VOLUME = int(SoundGroups.g_instance.getVolume('voice') * 100)
for parent, dir_names, filenames in os.walk(MODS_PATH):
    mod_name = 'autoConfigVoiceOver_' + MY_MODS_VERSION + '.wotmod'
    for obj_file in filenames:
        if obj_file.endswith('.wotmod'):
            path = os.path.join(parent, obj_file)
            OBJ_FILES.append({"filename": obj_file, "path": path})
            if obj_file == mod_name:
                WHERE_AM_I = path
                WHERE_ARE_PARENT = parent
# REMOVE_PROCESS = os.path.join(WHERE_ARE_PARENT, 'remove_old_archive.bat')
CONFIG_TEMPLATE = """{
    // [语音包管理插件]的配置文件
    // 如果你想要这个配置文件变回默认，请删除它
    //
    // 当前模式可选：0或1
    // 0 -> 语音选择下拉列表将展示游戏内自带的语音包
    // 1 -> 语音选择下拉列表将展示已安装语音包
    "currentMode": {vo_type_acv},
    //
    // 当前所用语音的lang名，在插件中会被解析为索引值
    // 当这个索引值对应的语音在两个语音列表中都不存在时，将被修改为默认语音
    // 默认语音为default
    "modeName": {vo_selector_acv},
    //
    // 表示当前插件启用/禁用
    // 禁用插件时，将恢复为原来的语音状态，但是很可惜，点亮语音丢失问题无法恢复为原始状态
    // 这是为了实现更好的语音包效果做出的妥协
    // 选择启用/禁用后，点击插件管理器的保存或保存并退出按钮即可
    "enabled": {enabled},
    //
    // 切换语音包时自动应用已保存的音量方案
    // 为每一个语音包单独设置启用时的音量，此功能在使用插件切换语音包时生效
    // 注意，当一个语音包被移除后，它的音量方案也将丢失
    "autoVolume": {vo_volume_acv},
    //
    // 声音模式是否可见
    // 开启后，你可以在设置菜单随时更换声音模式，但是特殊成员语音不会被你的选择所覆盖，且特殊成员语音不存在时，原本拥有对应语音的车长将使用默认的语音
    // 你可以通过插件修改默认的语音，设置菜单中选中“标准”战斗音效即可
    "visibleAll": {vo_visible_acv},
    //
    // 接受自定义的通知信息
    // 开启后，你将在切换语音后收到一条来自语音包的自定义通知信息（如果有的话）
    // 关闭后，仍可通过点击右侧图片来获取该信息（如果有的话）
    "infoNotify": {big_button_acv},
    //
    // 
    // 版本号，不要修改
    "__version__": 2
}"""
GAME_SOUND_MODES_TEMPLATE = """{
    // 通过这个文件，你可以使用游戏内自带的语音包
    // 如果你想要这个配置文件变回默认，请删除它
    //
    // 游戏内语音包信息位于压缩文件[GameFile]/res/packages/gui-part2.pkg中soundModes下的main_sound_modes.xml
    // 提取文件后，使用WoT XML Editor等工具解压xml即可查看文件内容，你可以在github上找到这个工具
    // 语音信息对应关系如下：
    // description     ->  "name"
    // name            ->  "voiceID"
    // wwbanks         ->  "bankPath"
    //
    // 按上述规范填入信息后，即可在游戏内下拉列表中启用对应语音
    // "name"仅用于展示的名字，可以填中文
    // 每个特殊成员都有一个属于自己的"voiceID"，
    //
    // 一旦你填入正确的信息，你就能通过插件切换至该语音，同时，该特殊成员语音将不能被屏蔽
    // 一个可行方法是挂接一个函数，在进入战斗之后显式修改语音。
    // 以后再更新这个功能吧……
    // 另一种方法是自己给voiceID重新起个名字，这样特殊成员语音就因为找不到这个ID而无法切换，从而被屏蔽
    // 这样，这个语音也能用，通过插件进行切换
    //
    // 示例如下：
    //
    "modes": [
        {
            "name": "美穗",
            "voiceID": "gup_jp_commander",
            "bankPath": "gup_jp/gup_miho/voiceover.bnk"
        },
        {
            "name": "鮟鱇鱼车组",
            "voiceID": "gup_jp_crew",
            "bankPath": "gup_jp/gup_crew/voiceover.bnk"
        },
        {
            "name": "艾丽卡",
            "voiceID": "gup_erika",
            "bankPath": "gup_jp/gup_erika/voiceover.bnk"
        },
        {
            "name": "米卡",
            "voiceID": "gup_mika",
            "bankPath": "gup_jp/gup_mika/voiceover.bnk"
        },
        {
            "name": "BT-42继续高中车组",
            "voiceID": "gup_crew_24",
            "bankPath": "gup_jp/gup_crew_24/voiceover.bnk"
        },
        {
            "name": "爱里寿",
            "voiceID": "gup_alice",
            "bankPath": "gup_jp/gup_alice/voiceover.bnk"
        },
        {
            "name": "大吉岭",
            "voiceID": "gup_darjeeling",
            "bankPath": "gup_jp/gup_darjeeling/voiceover.bnk"
        },
        {
            "name": "圣·葛罗丽安娜女子学院车组",
            "voiceID": "gup_crew_25",
            "bankPath": "gup_jp/gup_crew_25/voiceover.bnk"
        },
        {
            "name": "艾尔梅琳达·冯·克里格(CN)",
            "voiceID": "ermelinda24_cn",
            "bankPath": "WT24/WT24_zh_CN_ermelinda/voiceover.bnk"
        },
        {
            "name": "那兔那年那些事",
            "voiceID": "yha_crew",
            "bankPath": "YHA_cn_CN/voiceover.bnk"
        },
        {
            "name": "三国·关羽",
            "voiceID": "tankmen_mtlb1_1",
            "bankPath": "Custom/Custom_zh_CN_Guan_Yu/voiceover.bnk"
        }
    ]
}"""
PLAY_EVENTS_TEMPLATE = """{
    // 用于播放语音包的指定语音
    // 如果你想要这个配置文件变回默认，请删除它
    //
    // id指WoT中规定的Wwise事件名，name是将要显示在下拉列表的汉字
    // 任何事件都可以被播放，并不仅限于语音包所制作的声音，你也可以用它播放自己创建的Wwise事件
    // 获取事件 - https://gitlab.com/openwg/wot.wwise/-/tree/master/wwise_project/ru/Events
    //
    // 以下事件已被更名：
    // battle_equipment_763（使用小医疗包）    ——>    battle_equipment_763_mod
    // battle_equipment_1019（使用大医疗包）   ——>    battle_equipment_1019_mod
    // expl_enemy_NPC（敌军阵亡提示）          ——>    expl_enemy_NPC_mod
    // expl_ally_NPC（友军阵亡提示）           ——>    expl_ally_NPC_mod
    // artillery_lightbulb（火炮预警）        ——>    artillery_lightbulb_mod
    // enemy_sighted_for_team（详见示例）     ——>    enemy_sighted_for_team_mod
    // lightbulb（灯泡音效1）                 ——>    lightbulb_mod
    // lightbulb_02（灯泡音效2）              ——>    lightbulb_02_mod
    // 在soundbank中保留更名后事件即可在游戏中播放
    //
    // 可以通过创建新字典来添加事件，请注意JSON语法规范。
    //
    // 示例如下：
    //
    "eventList": [
        {
            "name": "战斗开始",
            "id": "vo_start_battle"
        },
        {
            "name": "战车被毁",
            "id": "vo_vehicle_destroyed"
        },
        {
            "name": "被点亮音效1",
            "id": "lightbulb_mod"
        },
        {
            "name": "火炮预警",
            "id": "artillery_lightbulb_mod"
        },
        {
            "name": "通讯范围内首次出现敌军",
            "id": "enemy_sighted_for_team_mod"
        },
        {
            "name": "溅射击伤",
            "id": "vo_damage_by_near_explosion_by_player"
        },
        {
            "name": "点燃对手",
            "id": "vo_enemy_fire_started_by_player"
        },
        {
            "name": "重创对手",
            "id": "vo_enemy_hp_damaged_by_projectile_and_chassis_damaged_by_player"
        },
        {
            "name": "击穿目标",
            "id": "vo_enemy_hp_damaged_by_projectile_by_player"
        },
        {
            "name": "击毁敌方坦克",
            "id": "vo_enemy_killed_by_player"
        },
        {
            "name": "锁定目标",
            "id": "vo_target_captured"
        },
        {
            "name": "目标丢失",
            "id": "vo_target_lost"
        },
        {
            "name": "解除锁定",
            "id": "vo_target_unlocked"
        },
        {
            "name": "击毁盟友",
            "id": "vo_ally_killed_by_player"
        },
        {
            "name": "未击穿装甲",
            "id": "vo_armor_not_pierced_by_player"
        },
        {
            "name": "跳弹",
            "id": "vo_armor_ricochet_by_player"
        },
        {
            "name": "致命一击（未造成HP伤害）",
            "id": "vo_enemy_no_hp_damage_at_attempt_and_chassis_damaged_by_player"
        },
        {
            "name": "车长受伤",
            "id": "vo_commander_killed"
        },
        {
            "name": "驾驶员受伤",
            "id": "vo_driver_killed"
        },
        {
            "name": "炮手受伤",
            "id": "vo_gunner_killed"
        },
        {
            "name": "装填手受伤",
            "id": "vo_loader_killed"
        },
        {
            "name": "通讯兵受伤",
            "id": "vo_radioman_killed"
        },
        {
            "name": "车组全员阵亡",
            "id": "vo_crew_deactivated"
        },
        {
            "name": "战车起火",
            "id": "vo_fire_started"
        },
        {
            "name": "火被扑灭了",
            "id": "vo_fire_stopped"
        },
        {
            "name": "弹药架受损",
            "id": "vo_ammo_bay_damaged"
        },
        {
            "name": "油箱被击中",
            "id": "vo_fuel_tank_damaged"
        },
        {
            "name": "电台受损",
            "id": "vo_radio_damaged"
        },
        {
            "name": "履带被击毁",
            "id": "vo_track_destroyed"
        },
        {
            "name": "发动机受损",
            "id": "vo_engine_damaged"
        },
        {
            "name": "发动机被击毁",
            "id": "vo_engine_destroyed"
        },
        {
            "name": "发动机完成修复",
            "id": "vo_engine_functional"
        },
        {
            "name": "主炮受损",
            "id": "vo_gun_damaged"
        },
        {
            "name": "主炮被击毁",
            "id": "vo_gun_destroyed"
        },
        {
            "name": "主炮完成修复",
            "id": "vo_gun_functional"
        },
        {
            "name": "炮塔座圈受损",
            "id": "vo_turret_rotator_damaged"
        },
        {
            "name": "炮塔无法转动",
            "id": "vo_turret_rotator_destroyed"
        },
        {
            "name": "炮塔座圈修复",
            "id": "vo_turret_rotator_functional"
        },
        {
            "name": "发送协助请求",
            "id": "vo_dp_assistance_been_requested"
        },
        {
            "name": "创建小队",
            "id": "vo_dp_platoon_created"
        },
        {
            "name": "加入小队",
            "id": "vo_dp_platoon_joined"
        },
        {
            "name": "新玩家入队",
            "id": "vo_dp_player_joined_platoon"
        },
        {
            "name": "解散小队",
            "id": "vo_dp_platoon_dismissed"
        },
        {
            "name": "主动离队",
            "id": "vo_dp_left_platoon"
        },
        {
            "name": "被踢出小队",
            "id": "vo_dp_been_excluded_platoon"
        },
        {
            "name": "前往目标地点/占领基地",
            "id": "ibc_pc_ping_action"
        },
        {
            "name": "注意此区域/装填中",
            "id": "ibc_pc_ping_attention"
        },
        {
            "name": "（你）收到",
            "id": "ibc_vo_pc_reply_affirmative"
        },
        {
            "name": "（你）发出支援",
            "id": "ibc_vo_pc_reply_sos"
        },
        {
            "name": "（你）谢谢",
            "id": "ibc_vo_pc_reply_thank_you"
        },
        {
            "name": "（你）请求支援",
            "id": "ibc_vo_pc_request_sos"
        },
        {
            "name": "（你）请求撤退",
            "id": "ibc_vo_pc_request_retreat"
        },
        {
            "name": "（队友）收到",
            "id": "ibc_vo_npc_reply_affirmative"
        },
        {
            "name": "（队友）发出支援",
            "id": "ibc_vo_npc_reply_sos"
        },
        {
            "name": "（队友）谢谢",
            "id": "ibc_vo_npc_reply_thank_you"
        },
        {
            "name": "（队友）请求支援",
            "id": "ibc_vo_npc_request_sos"
        },
        {
            "name": "（队友）请求撤退",
            "id": "ibc_vo_npc_request_retreat"
        }
    ]
}"""
INFO_TEMPLATE = """[
    // 补回各个系别的语音，不要改动，但是音量方案可以动
    // 音量可设置范围：0到100
    // 若非整数或者超出范围，将自动设为初始值
    {{
        "name": "ZH_CH",
        "wwise_language": "china",
        "description": "中系",
        "volume": {ZH_CH_volume}
    }},
    {{
        "name": "RU",
        "wwise_language": "ussr",
        "description": "苏系",
        "volume": {RU_volume}
    }},
    {{
        "name": "DE",
        "wwise_language": "germany",
        "description": "德系",
        "volume": {DE_volume}
    }},
    {{
        "name": "EN",
        "wwise_language": "usa",
        "description": "美系",
        "volume": {EN_volume}
    }},
    {{
        "name": "UK",
        "wwise_language": "uk",
        "description": "英系",
        "volume": {UK_volume}
    }},
    {{
        "name": "FR",
        "wwise_language": "france",
        "description": "法系",
        "volume": {FR_volume}
    }},
    {{
        "name": "CS",
        "wwise_language": "czech",
        "description": "捷克",
        "volume": {CS_volume}
    }},
    {{
        "name": "SV",
        "wwise_language": "sweden",
        "description": "瑞典",
        "volume": {SV_volume}
    }},
    {{
        "name": "PL",
        "wwise_language": "poland",
        "description": "波兰",
        "volume": {PL_volume}
    }},
    {{
        "name": "IT",
        "wwise_language": "italy",
        "description": "意大利",
        "volume": {IT_volume}
    }},
    {{
        "name": "JA",
        "wwise_language": "japan",
        "description": "日系",
        "volume": {JA_volume}
    }}
]"""
