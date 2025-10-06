## 坦克世界语音包管理插件
### 简介：
为了能使我自制的字幕语音包彼此之间可以兼容，我制作了这个插件。
<br>（字幕效果借助官方插件实现）

它可以读取指定方式打包的语音包，以及字幕语音包，并用它们覆盖掉游戏原有的成员语音。

此外，也可以将游戏内成员语音的必要信息写入指定文件，通过插件将这些声音重新添加。
> 注意：插件集成了坦克世界少女与战车字幕插件的部分文件，与炮声插件和字幕插件不兼容。
### 文件结构：
```
autoConfigVoiceOver_0.0.3/
├─res/
│   ├─audioww/
│   │   ├─audio_mods.xml
│   │   │ # 用于修改灯泡语音，它会使游戏内灯泡等部分声音丢失
│   │   ├─inbattle_communication_npc.bnk   用于补回这些丢失的声音
│   │   └─inbattle_communication_pc.bnk
│   │     # 如要使用默认语音，移除audioww及下文件
│   ├─gui/
│   │   └─flash/
│   │      └─gup_subtitles.swf     wot字幕插件中的文件
│   ├─mods/
│   │   └─gup.subtitles/
│   │      └─settings.json     wot字幕插件中的文件
│   └─scripts/
│       └─client/
│           ├─autoconfigvoiceover/
│    	    │   ├─__init__.pyc
│    	    │   ├─constants.pyc
│    	    │   ├─createTemplate.pyc
│    	    │   ├─fileSearch.pyc
│    	    │   ├─myLogger.pyc
│    	    │   ├─updateFile.pyc
│    	    │   └─tools.pyc
│    	    └─gui/
│    	        └─mods/
│    	            ├─mod_autoConfigVoiceOver.pyc
│    	            └─mod_gup_subtitles.pyc     wot字幕插件中的文件
├─template_json/    用于创建可读的第三方语音包的模板文件
│   ├─msg.txt
│   ├─sbt_.json
│   ├─sbtlist_.json
│   ├─vo_.json
│   └─volist_.json
├─default.png       用于展示的默认图片
├─meta.xml
├─remove_old_archive.bat    更新程序的一部分：写入信息后，移除旧的mod
└─update.png        在需要更新时用于展示的图片
```
自行编译并打包为.wotmod文件，并安装依赖mod：modsSettingsApi、modsListApi、openwg.gameface

或从release中下载。
### 可识别的第三方语音包：
- 以“voiceover_”开头的.wotmod文件
- 包含一个template_json文件夹中的json文件并将其重命名
<br>例如vo_test.json（可以在任意位置）
- 填入json文件的信息正确

此外，你还可以为其添加：一个图片用于切换后展示、一个wwise事件在切换时播放、一条消息在切换后发送。

图片命名为：“default.png”，推荐使用300×300像素大小的半透明图片。
<br>创建msg.txt并写入信息作为自定义消息。支持font标签的color属性、br标签、b标签
<br>将上述两个文件放入语音包同级目录即可
<br>用于播放的自定义wwsie事件名为：“vo_selected”
### 关于插件的更多信息：
作者b站账号：[下一个车站等你](https://space.bilibili.com/375281099)

视频介绍：[坦克世界语音包管理插件，一键强制切换语音，语音包之间不再有冲突](https://www.bilibili.com/video/BV1mAbhzXEZS)
### 结尾：
尚不支持国际化，插件显示的语言：简体中文。 目前插件还待进一步更新与优化。