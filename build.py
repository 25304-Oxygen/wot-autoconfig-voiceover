# coding=utf-8
import json
import os
import zipfile
import compileall
import shutil
import xml.etree.ElementTree as ET
from xml.dom import minidom

SOURCE_DIR = "python"
BUILD_DIR = "build"
VERSIONS = {'acv': '0.0.7', 'rmp': '0.0.2'}
OPTIONAL_XML_PATH = 'res/mods/soundRemapping/'


def create_meta(**meta):
    meta_etree = ET.Element('root')
    for key, value in meta.iteritems():
        ET.SubElement(meta_etree, key).text = value

    # 将原始 XML 字符串（所有内容都在一行）转换为带有缩进的 XML 字符串
    meta_str = ET.tostring(meta_etree)
    meta_dom = minidom.parseString(meta_str)
    meta_data = meta_dom.toprettyxml(encoding='utf-8').split('\n')[1:]
    return '\n'.join(meta_data)


def build(mod, data, attach=None):

    meta = data['meta_%s' % mod]
    files = data['files_%s' % mod]
    paths = data['paths']
    meta['version'] = VERSIONS[mod]
    mod_name = '%s_%s.wotmod' % (meta['id'], VERSIONS[mod])

    zip_path = os.path.join(BUILD_DIR, mod_name)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zip_ref:
        for f, dest in files.iteritems():
            zip_ref.write(paths[f], dest)
        zip_ref.writestr('meta.xml', create_meta(**meta))
        if attach:
            zip_ref.writestr(attach, '')

    for f, _ in files.iteritems():
        if f.endswith('.pyc') and not f.startswith('mod_gup'):
            os.remove(paths[f])

    print '构建完成：', mod_name


if __name__ == '__main__':

    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)

    print '编译Python文件'
    compileall.compile_dir(SOURCE_DIR, force=True)

    with open('build.json', 'r') as jf:
        config = json.load(jf)

    build('acv', config)
    build('rmp', config, attach=OPTIONAL_XML_PATH)
