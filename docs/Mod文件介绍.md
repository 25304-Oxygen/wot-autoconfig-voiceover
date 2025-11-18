# 坦克世界：Mod包

<div align="center">

**原文：** [English_doc_pdf](packages_doc_0.6_en.pdf) | [Russian_doc_pdf](packages_doc_0.6_ru.pdf)
（英-汉 翻译&校对：我）

</div>

注：*以下用Mod代指`.wotmod`这种包结构*

有关这个主题的讨论：[Mod packages / Пакеты модов](https://koreanrandom.com/forum/topic/36987-mod-packages-пакеты-модов/#comments)

---

**版本：0.6，2017年10月18日**

**坦克世界 9.20.1**

| 作者                   | 所属            | 联系方式              |
|----------------------|---------------|-------------------|
| Anton Bobrov         | Wargaming.net |                   |
| Mikhail Paulyshka    | XVM团队         | mixail@modxvm.com |
| Andrey Andruschyshyn | 个人            |                   |
| Koreanrandom.com社区   |               |                   |

**许可证：**

- 文档：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- 代码示例：[WTFPL](http://www.wtfpl.net/)

## 1、一般信息

---

Mod是组织模组中文件的一种方法。按照该方法，特定模组的全部内容都被打包到单个文件中。

如果使用旧的文件组织方法，模组中所有文件需一并放入`<坦克世界安装目录>/res_mods/<当前版本号文件夹>/`中。
用这种方式的话，不同模组的文件将会位于相同的文件夹中，你将很难找到特定模组的文件在哪。

将模组文件打包会使这一过程简单很多：要安装模组，玩家只需将包复制到`<坦克世界安装目录>/mods/<当前版本号文件夹>/`中；
要卸载模组，只需删除相应文件即可。

## 2、Mod的结构

---

Mod是一个具有以下特征的ZIP压缩包：

- 无压缩
- 扩展名：`.wotmod`
- 最大压缩包大小：2GB - 1字节（最大2,147,483,647字节）

**注意：** 当前版本的《坦克世界》不支持压缩的压缩包，因此在创建压缩包时请将压缩级别设置为"无压缩"。

**注意：** 当前版本的《坦克世界》不支持2GB及更大的压缩包，因此应将它们分割成小于2GB - 1字节的压缩包。

一个Mod必须包含以下内容：

- 必须项：`/res/`文件夹，这个文件夹包含模组内容，即原先需要放入
`<坦克世界安装目录>/res_mods/<当前版本号文件夹>`中的那些文件
- 可选项：辅助文件`meta.xml`（详见[**第5节**](#5元数据文件metaxml)）
- 可选项：包含许可协议的`LICENSE`文件
- 可选项：模组开发者可能需要的任何其他内容：模组网页链接、文档、更新日志等

Mod结构的示例：

```chatinput
/package.wotmod
    /meta.xml
    /README.md
    /LICENSE
    /res
        /scripts
            /client
                /gui
                    /mods
                        /mod_example.pyc
```

## 3、安装Mod

---

Mod需要安装到这个文件夹中：`<坦克世界安装目录>/mods/<当前版本号文件夹>/`。
你可以手动将它复制过去，也可以通过包含特定Mod或模组包的特殊安装程序文件来安装。

如有需要，Mod还可以分别放入其他的子文件夹中，这样开发者就能够将Mod文件分门别类：

```chatinput
mods/
    0.9.17.1/
        MultiHitLog_2.8.wotmod
        伤害面板/
            Some_common_library_3.14.5.wotmod
            DamagePanel_2.6.wotmod
            DamagePanel_2.8.wotmod
            DamagePanel_2.8_patch1.wotmod
```

## 4、Mod命名规范建议

---

我们建议在创建模组标识符（以下简称package_id）时采用以下命名方案：

```chatinput
package_id = author_id.mod_id
```

其中：

- `author_id`：开发者标识符。可以是开发者的反向域名（如`com.github`），也可以是开发者的昵称（如`匿名`）
- `mod_id`：模组标识符。由开发者自行决定。

模组标识符除了用在`meta.xml`文件的`<id>`字段（详见[**第5节**](#5元数据文件metaxml)），也是Mod文件名的组成部分。

模组标识符示例：

- `com.github.酷的mod`；
- `匿名.超级mod`。

Mod文件名按照以下方案创建：

```chatinput
<author_id>.<mod_id>_<mod_version>.wotmod
```

其中：

- `mod_version`：模组版本号，由模组开发者在`meta.xml`文件的`<version>`字段中指定（详见[**第5节**](#5元数据文件metaxml)）。

文件名示例：

- `com.github.酷的mod_0.1.wotmod`；
- `匿名.超级mod_0.2.8.wotmod`。

## 5、元数据文件`meta.xml`

---

可选文件`meta.xml`包含用于描述Mod的特殊字段。

示例：

```chatinput
<root>
    <!‐‐ 模组标识符 ‐‐>
    <id>noname.crosshair</id>

    <!‐‐ 模组版本号 ‐‐>
    <version>0.2.8</version>

    <!‐‐ 面向玩家的清晰的Mod名 ‐‐>
    <name>Crosshair</name>
    
    <!‐‐ Mod描述 ‐‐>
    <description>带有功能1的全新酷炫准星……</description>
</root>
```

`<id>`和`<version>`字段中指定的值用于确定Mod的加载顺序。
`<name>`和`<description>`字段中指定的值随后将在模组管理系统中使用。

## 6、加载Mod

---

### 6.1 加载顺序

---

位于`<坦克世界安装目录>/mods/<当前版本号文件夹>/`目录中的所有Mod，将按照`meta.xml`文件中
`<id>`字段指定的值进行排序，并依此顺序加载。若`meta.xml`文件缺失，则将使用文件名作为模组标识符。

可通过`load_order.xml`文件修改加载顺序，此文件应放入上述目录中。

若`load_order.xml`文件中已列出所有Mod，则按文件中的顺序加载。

若`load_order.xml`文件未列出全部Mod，则已列出的Mod将优先加载，其余Mod按字母顺序加载。

### 6.2 Mod与res_mods目录的协同使用

---

从游戏客户端的角度来看，游戏所分配的虚拟系统的根目录由以下路径组成：

- `/res_mods/<当前版本号文件夹>`
- `/mods/<当前版本号文件夹>/<Mod文件名>.wotmod/res`
- `/res/packages/*.pkg`
- `/res/`
- 以及在`<坦克世界安装目录>/paths.xml`文件中指定的其他路径

这些路径按优先级从高到低排列。也就是说，位于文件夹`/res_mods/<当前版本号文件夹>/`
中的文件具有最高优先级，且该优先级不受`load_order.xml`文件的影响。

### 6.3 对加载冲突的处理

---

通常，使用Mod包的方式确实可以做到在不同Mod中的`res/`文件夹下出现路径完全相同、名称完全相同的重复文件，
这种情况会被视为冲突。

一旦检测到冲突，受到牵连的Mod将不会被加载，系统会向用户显示相应的提示信息。

具体来说，如果`a.wotmod`和`b.wotmod`两个Mod都包含`res/scripts/entities.xml`文件，
那么`a.wotmod`将被成功加载，而`b.wotmod`则会引发冲突，因此不会被加载。

解决冲突可采用以下方法：

#### 1.使用`load_order.xml`文件

`load_order.xml`文件应位于以下目录中：`<坦克世界安装目录>/mods/<当前版本号文件夹>/`。

该文件的格式如下：

```chatinput
<root>
    <Collection>
        <pkg>package1_name.wotmod</pkg>
        <pkg>package2_name.wotmod</pkg>
        <!‐‐ 直到最后一个文件 ‐‐>
        <pkg>packageN_name.wotmod</pkg>
    </Collection>
</root>
```

在此文件中指定的Mod不会被视作冲突项。游戏在加载这些Mod时将不进行同名文件检查。
*排列在文件末尾的Mod拥有最高加载优先级。*

#### 2.使用`meta.xml`中的`<id>`字段和`<version>`字段

若`meta.xml`文件中已指定`<id>`字段，则此Mod的加载顺序将不再依据它的文件名称。
具有相同`<id>`值的Mod被视为同一模组的不同版本或组成部分，此类文件之间的冲突不会被判定为冲突。
游戏将按版本顺序（版本号在`<version>`字段中指定）加载这些Mod。

Mod版本顺序的排序规则是基于ASCII码表的字符逐位比对，其行为与[strcmp()](https://docs.microsoft.com/en-us/cpp/c-runtime-library/reference/strcmp-wcscmp-mbscmp)函数类似：

- 版本`9.0.0`的优先级高于版本`10.0.0`；
- 版本`b`的优先级高于版本`B`；
- 版本`c<任意字符>`的优先级高于版本`c`；
- 若版本号完全相同，Mod将按照其文件名的字母顺序加载。

若不同Mod包含同名文件，且其引发的冲突已通过`load_order.xml`或`meta.xml`文件解决，
则最后被加载的Mod中的文件具有最高优先级。

*注：以版本顺序为例，9.0.0版本先加载，10.0.0后加载，若它们是相同Mod的不同版本，则必然包含重复文件。*
*引发冲突后，在冲突处理中，后加载的10.0.0将重新获得最高优先级，9.0.0及其文件将不会被加载。*

### 6.4 执行Python代码

---

在所有Mod添加完毕且冲突解决之后，位于`/scripts/client/gui/mods/`目录下、文件名以
`mod_`开头的所有`.pyc`文件，将按字母顺序执行。

在一个Mod内部，此文件应位于以下路径：

```chatinput
<author_id>.<mod_id>_<version>.wotmod/res/scripts/client/gui/mods/mod_<anything>.pyc
```

## 7、模组文件的推荐路径

---

### 7.1 配置文件

---

模组的配置文件建议存放在以下路径：

```chatinput
<坦克世界安装目录>/mods/configs/<author_id>.<mod_id>/
```

其中：

- `author_id`与`mod_id`即为本文档[第4节](#4mod命名规范建议)所述的标识符。

### 7.2 日志文件

---

除了标准的`python.log`文件，建议使用以下路径：

```chatinput
<坦克世界安装目录>/mods/logs/<author_id>.<mod_id>/
```

其中：

- `author_id`与`mod_id`即为本文档[第4节](#4mod命名规范建议)所述的标识符。

### 7.3 临时文件

临时文件建议存放在以下路径：

```chatinput
<temp>/world_of_tanks/<author_id>.<mod_id>/
```

其中：

- `temp`：指当前用户在操作系统中的临时文件目录路径；
- `author_id`与`mod_id`即为本文档[第4节](#4mod命名规范建议)所述的标识符。

### 7.4 其他模组文件

如需存储需要在游戏客户端中访问的内容，请使用以下路径：

```chatinput
<package_name>.wotmod/res/mods/<author_id>.<mod_id>/
```

其中：

- `author_id`与`mod_id`即为本文档[第4节](#4mod命名规范建议)所述的标识符。

## 8、Mod包内的文件操作

---

请使用`ResMgr`模块处理Mod包内的文件。

### 8.1 标准操作

---

#### 8.1.1 从程序包中读取文件

```python
# coding=utf-8
# 导入
import ResMgr

# 函数
def read_file(vfs_path, read_as_binary=True):
    vfs_file = ResMgr.openSection(vfs_path)
    if vfs_file is not None and ResMgr.isFile(vfs_path):
        if read_as_binary:
            return str(vfs_file.asBinary)
        else:
            return str(vfs_file.asString)
    return None

# 示例
myscript = read_file('scripts/client/gui/mods/mod_mycoolmod.pyc')
```

#### 8.1.2 获取文件夹内的元素列表

```python
# coding=utf-8
# 导入
import ResMgr

# 函数
def list_directory(vfs_directory):
    result = []
    folder = ResMgr.openSection(vfs_directory)

    if folder is not None and ResMgr.isDir(vfs_directory):
        for name in folder.keys():
            if name not in result:
                result.append(name)
                
    return sorted(result)

# 示例
content = list_directory('scripts/client/gui/mods')
```

#### 8.1.3 将文件从Mod包复制到文件夹

```python
# coding=utf-8
# 导入
import os
import ResMgr

# 函数
def file_copy(vfs_from, realfs_to):
    realfs_directory = os.path.dirname(realfs_to)
    if not os.path.exists(realfs_directory):
        os.makedirs(realfs_directory)

    vfs_data = read_file(vfs_from)  # 详见8.1.1
    if vfs_data:
        with open(realfs_to, 'wb') as realfs_file:
            realfs_file.write(vfs_data)

# 示例
file_copy('scripts/client/gui/mods/mod_my.pyc', 'res_mods/0.9.17.1/scripts/client/gui/mods/mod_my.pyc')
```

## 9、已知问题

---

### 9.1 执行`.py`文件

---

**问题描述**

目前，位于Mod包内的`.py`文件无法直接执行。

**临时解决方案**

Mod包内应同时包含`.py`源文件及已编译为字节码的`.pyc`文件。

### 9.2 对ZIP格式的兼容性限制

---

**问题描述**

目前，游戏资源管理器无法正确处理结构不完整的ZIP归档。
如果压缩包内的空文件夹缺少对应的ZIP文件记录结构，将导致整个`.wotmod`文件加载失败。

**临时解决方案**

请使用符合ZIP格式标准的压缩工具来创建`.wotmod`文件，例如：

- 7-Zip http://7-zip.org；
- Info-ZIP http://info-zip.org。

## 附录A：修订记录

---

### v 0.6 (2017-10-18)

---

- 为代码示例添加许可证。

### v 0.5 (2017-10-12)

---

- 删除原9.2和9.3小节（相关问题已在《坦克世界》9.20.1版本中修复）
- 增加关于ZIP格式兼容性限制的问题说明

### v 0.4 (2017-05-04)

---

- 重写了关于使用`load_order.xml`文件解决程序包冲突的说明

### v 0.3 (2017-05-03)

---

- 增加对`.wotmod`文件格式限制的说明
- 补充了关于处理相同标识符程序包冲突的说明

### v 0.2 (2017-04-10)

---

- 重构文档设计：采用新版式，按文章结构划分
- 重写程序包命名规则说明
- 重写程序包加载顺序说明
- 增加关于日志和配置文件存储位置的推荐规范
- 新增程序包内文件操作的源代码示例
- 增加当前已知问题说明

### v 0.1 (2017-01-13)

- 初始版本