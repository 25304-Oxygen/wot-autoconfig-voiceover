# coding=utf-8
"""
    用于替代 audio_mods.xml 实现语音重映射。支持动态修改重映射方案。可以独立使用。
"""
import ResMgr
import WWISE
import functools
MY_MODS_VERSION = '0.0.2'
DEFAULT_XML = 'mods/soundRemapping/audio_mods.xml'
# 你可以将 audio_mods.xml 直接转移至 soundRemapping 文件夹中作为它的初始重映射方案


def _get_remap(path=DEFAULT_XML):
    if not ResMgr.isFile(path):
        return {}
    root_sec = ResMgr.openSection(path)
    if not root_sec.has_key('events'):
        return {}
    return {
        item.readString('name'): item.readString('mod')
        for item in root_sec['events'].values()
    }


class RemappingControl(object):
    def __init__(self):
        self.__remapping = _get_remap()
        if self.__remapping is None:
            self.__remapping = {}

    def replace(self, event):
        return self.__remapping.get(event, event)

    def reset_remapping(self, new_dict=None):
        if not isinstance(new_dict, dict):
            new_dict = {}
        self.__remapping = new_dict

    @property
    def remapping(self):
        return self.__remapping


g_remap_ctrl = RemappingControl()


def _override_func(cls, method):
    def decorator(handler_func):
        orig_func = getattr(cls, method)

        @functools.wraps(orig_func)
        def wrapper(*args, **kwargs):
            return handler_func(orig_func, *args, **kwargs)

        if isinstance(orig_func, property):
            setattr(cls, method, property(wrapper))
        else:
            setattr(cls, method, wrapper)

        return handler_func
    return decorator


# 通常情况下，也可以用 *args **kwargs 替换 event、object 以外的参数作为参数列表
@_override_func(WWISE, 'WW_eventGlobal')
def _WWISE_WW_eventGlobal(orig_func, event, checkSoundBankName=''):
    return orig_func(g_remap_ctrl.replace(event), checkSoundBankName)


@_override_func(WWISE, 'WW_eventGlobalPos')
def _WWISE_WW_eventGlobalPos(orig_func, event, pos):
    return orig_func(g_remap_ctrl.replace(event), pos)


# 某次更新添加了这个新参数 local
@_override_func(WWISE, 'WW_getSound')
def _WWISE_WW_getSound(orig_func, eventName, objectName, matrix, local=(0.0, 0.0, 0.0)):
    return orig_func(g_remap_ctrl.replace(eventName), objectName, matrix, local)


@_override_func(WWISE, 'WW_getSoundPos')
def _WWISE_WW_getSoundPos(orig_func, eventName, objectName, position):
    return orig_func(g_remap_ctrl.replace(eventName), objectName, position)


@_override_func(WWISE, 'WW_getSoundCallback')
def _WWISE_WW_getSoundCallback(orig_func, eventName, objectName, matrix, callback):
    return orig_func(g_remap_ctrl.replace(eventName), objectName, matrix, callback)
