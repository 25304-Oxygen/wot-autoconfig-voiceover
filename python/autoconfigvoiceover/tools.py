# coding=utf-8
"""
    一些实用的函数，部分代码来自 ModsSettingsApi 中被限制导入的函数。
"""
from constants import CONFIG_JSON
from template import CONFIG_TEMPLATE
import inspect
import functools
import xml.etree.ElementTree as ET
import zipfile
import json
import re
import BigWorld


def override(obj, prop, getter=None, setter=None, deleter=None):
    """ Overrides attribute in object.
    Attribute should be property or callable.
    Getter, setter and deleter should be callable or None.
    :param obj: Object
    :param prop: Name of any attribute in object (can be not mangled)
    :param getter: Getter function
    :param setter: Setter function
    :param deleter: Deleter function"""
    if inspect.isclass(obj) and prop.startswith('__') and prop not in dir(obj) + dir(type(obj)):
        prop = obj.__name__ + prop
        if not prop.startswith('_'):
            prop = '_' + prop

    src = getattr(obj, prop)
    if type(src) is property and (getter or setter or deleter):
        assert getter is None or callable(getter), 'Getter is not callable!'
        assert setter is None or callable(setter), 'Setter is not callable!'
        assert deleter is None or callable(deleter), 'Deleter is not callable!'

        getter = functools.partial(getter, src.fget) if getter else src.fget
        setter = functools.partial(setter, src.fset) if setter else src.fset
        deleter = functools.partial(deleter, src.fdel) if deleter else src.fdel

        setattr(obj, prop, property(getter, setter, deleter))
        return getter
    elif getter:
        assert callable(src), 'Source property is not callable!'
        assert callable(getter), 'Handler is not callable!'

        if inspect.isclass(obj) and inspect.ismethod(src) \
                or isinstance(src, type(BigWorld.Entity.__getattribute__)):
            getter_new = lambda *args, **kwargs: getter(src, *args, **kwargs)
        else:
            getter_new = functools.partial(getter, src)

        setattr(obj, prop, getter_new)
        return getter
    else:
        return functools.partial(override, obj, prop)


def jsonRemoveComments(data, strip_space=True):
    tokenizer = re.compile('"|(/\*)|(\*/)|(//)|\n|\r')
    endSlashes = re.compile(r'(\\)*$')

    inString = False
    inMultiString = False
    inSingle = False

    result = []
    index = 0

    for match in re.finditer(tokenizer, data):
        if not (inMultiString or inSingle):
            tmp = data[index:match.start()]
            if not inString and strip_space:

                # replace white space as defined in standard
                tmp = re.sub('[ \t\n\r]+', '', tmp)
            result.append(tmp)

        index = match.end()
        group = match.group()

        if group == '"' and not (inMultiString or inSingle):
            escaped = endSlashes.search(data, 0, match.start())

            # start or unescaped quote character to end
            if not inString or (escaped is None or len(escaped.group()) % 2 == 0):
                inString = not inString
            index -= 1  # include quote character in next catch
        elif not (inString or inMultiString or inSingle):
            if group == '/*':
                inMultiString = True
            elif group == '//':
                inSingle = True
        elif group == '*/' and inMultiString and not (inString or inSingle):
            inMultiString = False
        elif group in '\r\n' and not (inMultiString or inString) and inSingle:
            inSingle = False
        elif not ((inMultiString or inSingle) or (group in ' \r\n\t' and strip_space)):
            result.append(group)

    result.append(data[index:])
    return ''.join(result)


# str -> dict
def jsonLoad(src):
    src = jsonRemoveComments(src)
    return json.loads(src, encoding='utf-8')


# json -> str
def jsonDump(json_data):
    return json.dumps(json_data, ensure_ascii=False, indent=4)


# 为字典添加新键
def add_new_key_only(obj, new):
    for key, value in new.iteritems():
        if key not in obj:
            obj[key] = value
    return obj


def add_new_dict_only(old_list, new_list, id_key):
    id_keys = {item[id_key] for item in old_list if id_key in item}

    for new_item in new_list:
        if id_key in new_item and new_item[id_key] not in id_keys:
            old_list.append(new_item)
    return old_list


# 使用 ElementTree 从 audio_mods.xml 中读取
def remap_from_xml(src):
    if not isinstance(src, (str, unicode)):
        src = src.read()

    xml_root = ET.fromstring(src)
    return {
        element.findtext('name'): element.findtext('mod')
        for element in xml_root.findall('events/event')
    }


# 通过检查 meta.xml 确定要寻找的 mod，暂时将用它来寻找自己
def check_from_meta(path, meta=None):
    with zipfile.ZipFile(path, 'r') as zip_ref:
        if 'meta.xml' not in zip_ref.namelist():
            return False
        if not meta:
            return True

        root = ET.fromstring(zip_ref.read('meta.xml'))
        return all(
            root.findtext(key) == value
            for key, value in meta.iteritems()
        )


def dict_value_convert(**kwargs):
    return {
        key: 'true' if isinstance(value, bool) and value else
             'false' if isinstance(value, bool) and not value else
             str(value)
        for key, value in kwargs.iteritems()
    }


# 为了得到带有注释、非标准 json 格式的字符串预写入
# 这里先将字典转为 {str: str}，再格式化模版字符串
def save_config(new_config):
    config_text = CONFIG_TEMPLATE.format(**dict_value_convert(**new_config))
    with open(CONFIG_JSON, 'w') as f:
        f.write(config_text)
