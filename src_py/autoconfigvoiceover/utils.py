# coding=utf-8
"""工具函数：JSON-with-comments 读写、ResMgr 辅助、颜色解析、
方法 monkeypatch 等。"""

import json
import os


# ═════════════════════════════════════════════════════════════
# JSONC —— 支持 // 注释行的 JSON
# ═════════════════════════════════════════════════════════════


def to_utf8(obj):
    """递归将 json.loads 产物中的 unicode 编码回 utf-8 字节串。

    全代码库约定：字符串一律用 utf-8 字节串（游戏和日志都能正常显示；
    unicode 在日志里会变成转义符号）。json.loads 总是产出 unicode，
    是唯一需要处理编码的地方，加载后立刻统一编码。
    """
    if isinstance(obj, unicode):
        return obj.encode('utf-8')
    if isinstance(obj, list):
        return [to_utf8(x) for x in obj]
    if isinstance(obj, dict):
        return dict((to_utf8(k), to_utf8(v)) for k, v in obj.items())
    return obj


def parse_jsonc(text, **kwargs):
    """解析带 // 注释的 JSON 文本，返回 utf-8 字节串编码的 dict。

    只过滤整行注释（允许前导空白），不在有效 JSON 行内识别注释。
    文本为空时返回 None。
    返回值中的字符串已统一编码为 utf-8 字节串（见 to_utf8）。

    额外关键字参数会透传给 json.loads（如 object_pairs_hook=OrderedDict）。

    这是 load_jsonc / load_vfs_json 的共享核心，所有 JSON 反序列化
    都应经过此函数以确保注释被正确去除。
    """
    # 过滤 // 注释行和空行
    clean_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('//') or stripped == '':
            continue
        clean_lines.append(line)

    clean_text = '\n'.join(clean_lines)
    if not clean_text.strip():
        return None

    try:
        return to_utf8(json.loads(clean_text, encoding='utf-8', **kwargs))
    except (ValueError, TypeError):
        return None


def load_jsonc(path):
    """读取带注释的 JSON 文件，过滤 // 开头的注释行。

    只过滤整行注释（允许前导空白），不在有效 JSON 行内识别注释。
    文件不存在或内容为空时返回 None。
    返回值中的字符串已统一编码为 utf-8 字节串（见 to_utf8）。
    """
    if not os.path.exists(path):
        return None

    with open(path, 'r') as fh:
        text = fh.read()

    return parse_jsonc(text)


def load_vfs_json(vfs_path):
    """读取 VFS（ResMgr 虚拟文件系统）中的 JSON 文件。

    用于读取打包在 wotmod / res_mods 内的 json（如语音包 pack.json）。
    内部经 parse_jsonc 过滤 // 注释行。
    文件不存在、读取失败或解析失败均返回 None，由调用方决定如何 warn。
    返回值中的字符串已统一编码为 utf-8 字节串（见 to_utf8）。

    注意：游戏引擎的 ResMgr/VFS 不支持含非 ASCII 字符（如中文）的路径，
    此类文件读取会失败。请使用纯英文文件名。
    """
    import ResMgr  # 延迟导入——保持本模块可脱离游戏环境使用

    # ResMgr.isFile 对编码不匹配的路径可能抛出异常，catch 住返回 None。
    try:
        if not ResMgr.isFile(vfs_path):
            return None
    except Exception:
        return None
    try:
        section = ResMgr.openSection(vfs_path)
    except Exception:
        return None
    if section is None:
        return None

    return parse_jsonc(section.asString)


def save_jsonc(path, data, header_comment=None):
    """写入带注释的 JSON 文件。

    自动确保 __version__ 键排在最后。目录不存在时自动创建。

    :param path:            文件路径
    :param data:            待写入的 dict
    :param header_comment:  文件头部注释字符串（可选），按行写入 // 前缀
    """
    # 确保目录存在
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname)

    # __version__ 强制放在 JSON 最后一行
    if '__version__' in data:
        version = data.pop('__version__')
        data['__version__'] = version

    text = json.dumps(data, ensure_ascii=False, indent=4, sort_keys=False)

    with open(path, 'w') as fh:
        if header_comment:
            for line in header_comment.strip().split('\n'):
                fh.write('// ' + line.strip() + '\n')
        fh.write(text)
        fh.write('\n')


# ═════════════════════════════════════════════════════════════
# 深度合并
# ═════════════════════════════════════════════════════════════


def deep_merge(base, override):
    """深度合并两个 dict。

    override 中的值覆盖 base 中的同名键。两个都是 dict 时递归合并，
    否则 override 直接替换 base。
    """
    result = dict(base)
    for key, value in override.items():
        if (key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ═════════════════════════════════════════════════════════════
# override —— 方法 monkeypatch（移植旧版 tools.py）
# ═════════════════════════════════════════════════════════════


def override(cls, method_name):
    """装饰器：替换类方法，原方法作为第一参数传入新函数。"""
    original = getattr(cls, method_name)

    def decorator(new_func):
        def wrapper(*args, **kwargs):
            return new_func(original, *args, **kwargs)
        setattr(cls, method_name, wrapper)
        return wrapper

    return decorator
