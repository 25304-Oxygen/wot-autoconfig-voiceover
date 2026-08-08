# coding=utf-8
"""ACV mod 打包脚本。

流程:
  1. 编译 src_py/ 下所有 .py ->.pyc
  2. 收集 resources/flash/*.swf ->res/gui/flash/
  3. 收集 resources/autoconfigvoiceover/ ->res/mods/autoconfigvoiceover/（原封不动）
  4. 自动生成 meta.xml，打包为 .wotmod（ZIP_STORED 无压缩）

输出: build/autoConfigVoiceOver_<version>.wotmod
"""

import os
import io
import re
import zipfile
import compileall
import shutil
import xml.etree.ElementTree as ET
from xml.dom import minidom

# ═══════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PY_DIR = os.path.join(ROOT_DIR, 'src_py')
RESOURCES_DIR = os.path.join(ROOT_DIR, 'resources')
FLASH_DIR = os.path.join(RESOURCES_DIR, 'flash')
MOD_RES_DIR = os.path.join(RESOURCES_DIR, 'autoconfigvoiceover')
BUILD_DIR = os.path.join(ROOT_DIR, 'build')

# ═══════════════════════════════════════════════════════
# 从 _metadata.py 读取版本号等信息（文本解析，避免 import 链触发 ResMgr 依赖）
# ═══════════════════════════════════════════════════════

def _parse_metadata(key):
    """从 _metadata.py 中提取模块级字符串变量的值。"""
    meta_path = os.path.join(SRC_PY_DIR, 'autoconfigvoiceover', '_metadata.py')
    with io.open(meta_path, 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'^{}\s*=\s*[\'"](.+?)[\'"]'.format(key), content, re.MULTILINE)
    if not m:
        raise SystemExit('ERROR: %s not found in _metadata.py' % key)
    return m.group(1)


MOD_ID = _parse_metadata('MOD_ID')
MOD_VERSION = _parse_metadata('MOD_VERSION')
MOD_NAME = _parse_metadata('MOD_NAME')
MOD_DESCRIPTION = _parse_metadata('MOD_DESCRIPTION')


# ═══════════════════════════════════════════════════════
# meta.xml 生成
# ═══════════════════════════════════════════════════════

def generate_meta_xml():
    """根据上方的 MOD_* 常量自动生成 meta.xml 内容。"""
    el_root = ET.Element('root')
    ET.SubElement(el_root, 'id').text = MOD_ID
    ET.SubElement(el_root, 'version').text = MOD_VERSION
    ET.SubElement(el_root, 'name').text = MOD_NAME
    ET.SubElement(el_root, 'description').text = MOD_DESCRIPTION

    raw = ET.tostring(el_root, encoding='utf-8')
    dom = minidom.parseString(raw)
    pretty = dom.toprettyxml(encoding='utf-8').decode('utf-8')
    # 去掉 XML 声明行
    return '\n'.join(pretty.split('\n')[1:])


# ═══════════════════════════════════════════════════════
# 编译与收集
# ═══════════════════════════════════════════════════════

def compile_python():
    """编译 src_py/ 下所有 .py ->.pyc。

    切换到 src_py 目录内用相对路径编译，这样 .pyc 中嵌入的源文件路径
    是 autoconfigvoiceover/xxx.py 而非开发机的绝对路径。
    """
    print('[1/4] Compiling Python files...')
    cwd = os.getcwd()
    os.chdir(SRC_PY_DIR)
    try:
        compileall.compile_dir('.', force=True, quiet=1)
    finally:
        os.chdir(cwd)
    print('      Done')


def collect_pyc():
    """收集 src_py/ 下所有 .pyc，映射到 wotmod 内路径。

    mod_*.pyc ->res/scripts/client/gui/mods/
    其他 .pyc ->res/scripts/client/{相对路径}
    """
    files = {}
    count = 0
    for dirpath, _, filenames in os.walk(SRC_PY_DIR):
        # 跳过 Python 3 __pycache__ 目录
        if '__pycache__' in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith('.pyc'):
                continue
            local = os.path.join(dirpath, fn)
            rel = os.path.relpath(local, SRC_PY_DIR).replace('\\', '/')

            if fn.startswith('mod_'):
                zip_path = 'res/scripts/client/gui/mods/' + fn
            else:
                zip_path = 'res/scripts/client/' + rel

            files[local] = zip_path
            count += 1
            print('      %s -> %s' % (rel, zip_path))

    print('      Collected %d .pyc files' % count)
    return files


def collect_flash():
    """收集 resources/flash/*.swf ->res/gui/flash/。"""
    files = {}
    if not os.path.isdir(FLASH_DIR):
        print('      [Skip] resources/flash/ not found')
        return files

    for fn in os.listdir(FLASH_DIR):
        if fn.endswith('.swf'):
            local = os.path.join(FLASH_DIR, fn)
            zip_path = 'res/gui/flash/' + fn
            files[local] = zip_path
            print('      %s -> %s' % (fn, zip_path))

    return files


def collect_mod_resources():
    """收集 resources/autoconfigvoiceover/ 全部文件，原封不动映射到
    res/mods/autoconfigvoiceover/。"""
    files = {}
    if not os.path.isdir(MOD_RES_DIR):
        print('      [Skip] resources/autoconfigvoiceover/ not found')
        return files

    for dirpath, _, filenames in os.walk(MOD_RES_DIR):
        for fn in filenames:
            if fn == '.gitkeep':
                continue
            local = os.path.join(dirpath, fn)
            rel = os.path.relpath(local, MOD_RES_DIR).replace('\\', '/')
            zip_path = 'res/mods/autoconfigvoiceover/' + rel
            files[local] = zip_path
            print('      %s -> %s' % (rel, zip_path))

    return files


# ═══════════════════════════════════════════════════════
# 打包
# ═══════════════════════════════════════════════════════

def build():
    mod_filename = '%s_%s.wotmod' % (MOD_ID, MOD_VERSION)

    print('=' * 60)
    print('ACV Mod Build')
    print('  ID:      %s' % MOD_ID)
    print('  Version: %s' % MOD_VERSION)
    print('  Output:  %s' % mod_filename)
    print('=' * 60)

    # 清理并创建 build 目录
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)

    # 1. 编译
    compile_python()

    # 2-4. 收集
    print('[2/4] Collecting Python .pyc...')
    all_files = {}
    all_files.update(collect_pyc())

    print('[3/4] Collecting Flash SWF...')
    all_files.update(collect_flash())

    print('[4/4] Collecting mod resources...')
    all_files.update(collect_mod_resources())

    if not all_files:
        print('\n[ERROR] No files found to package!')
        return

    # 打包
    zip_path = os.path.join(BUILD_DIR, mod_filename)
    print('\nPacking to: %s' % zip_path)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
        # 自动生成 meta.xml
        meta_xml_str = generate_meta_xml()
        zf.writestr('meta.xml', meta_xml_str.encode('utf-8'))
        print('  + meta.xml (auto-generated)')

        for local, arcname in sorted(all_files.items()):
            zf.write(local, arcname)
            print('  + ' + arcname)

    # 清理 .pyc
    print('\nCleaning .pyc files...')
    for local in all_files:
        if local.endswith('.pyc'):
            try:
                os.remove(local)
            except OSError:
                pass
    print('  Done')

    print('\n' + '=' * 60)
    print('Build complete: build/%s' % mod_filename)
    print('=' * 60)


if __name__ == '__main__':
    build()
    