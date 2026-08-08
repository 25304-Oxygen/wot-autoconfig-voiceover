package com.github._25304_Oxygen.menu.pages
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.utils.Timer;
    import flash.events.TimerEvent;
    import flash.geom.Rectangle;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.i18n.L10n;
    import com.github._25304_Oxygen.menu.components.RadioButton;
    import com.github._25304_Oxygen.menu.components.RadioGroup;
    import com.github._25304_Oxygen.menu.components.CheckBox;
    import com.github._25304_Oxygen.menu.components.Dropdown;
    import com.github._25304_Oxygen.menu.components.Stepper;
    import com.github._25304_Oxygen.menu.components.ScrollPane;
    import com.github._25304_Oxygen.menu.components.GroupBox;
    import com.github._25304_Oxygen.menu.components.TextInput;
    import com.github._25304_Oxygen.menu.components.Theme;
    import com.github._25304_Oxygen.menu.components.Tooltip;
    import com.github._25304_Oxygen.menu.components.SoundUtils;

    /**
     * 设置页——分组框重构版。
     *
     * 6 个 GroupBox，内含 RadioGroup / CheckBox / Dropdown / Stepper，
     * 全部内容放入 ScrollPane 滚动。左右两列对齐。
     *
     * 所有用户操作通过 onAction 回调 Python 端:
     *   nationVoiceGender,<male|female>
     *   notifyPush,<none|count|detail>
     *   checkbox,<key>,<0|1>
     *   hotkey,<F1..F10>
     *   logLevel,<index>
     *   subtitleDisplay,<simple|standard|none>
     *   textSpeed,<value>
     *   colorScheme,<token>
     *   bgIcon,<token>
     *   titleTextMode,<followScheme|custom>
     *   titleTextColor,<#RRGGBB>
     */
    public class SettingsPage extends BasePage
    {
        private static const L:Object = Log.getLogger("SettingsPage");

        // ═══════════════════════════════════════════════════════
        // 页面布局常量
        // ═══════════════════════════════════════════════════════

        private static const MARGIN_H:int = 10;
        private static const MARGIN_BOTTOM:int = 20;
        private static const TITLE_Y:int = 8;
        /** 页面总可用宽度（面板 680 - 左右边距各 10）。 */
        private static const PAGE_W:int = 660;

        /** GroupBox 宽度 = viewport 宽度 - 1（右侧留 1px，确保描边不被 scrollRect 裁剪）。 */
        private static const GB_W:int = 635;
        private static const PAGE_H:int = 440;

        // ═══════════════════════════════════════════════════════
        // 列布局（GroupBox 内容区内，左/右列 x 和宽度）
        // ═══════════════════════════════════════════════════════

        private static const COL_W:Number = 290;
        private static const COL_GAP:Number = 27;
        private static const COL_L:Number = 0;
        private static const COL_R:Number = COL_W + COL_GAP;
        private static const TOTAL_COL_W:Number = COL_R + COL_W;  // = 607 = GB_W 635 - PAD_SIDE 14*2

        // ═══════════════════════════════════════════════════════
        // 组件行高
        // ═══════════════════════════════════════════════════════

        private static const LABEL_ROW_H:int = 24;
        private static const RADIO_ROW_H:int = 24;
        private static const CHECK_ROW_H:int = 30;
        private static const DROPDOWN_ROW_H:int = 40;
        private static const STEPPER_ROW_H:int = 36;
        private static const GB_GAP:int = 8;

        /** CheckBox/RadioButton 标签可用宽度 = 列宽 - 指示器(18) - 间距(8)。
         *  传给组件 labelWidth 参数，限定列宽内自动换行（i18n 长翻译不横向溢出）。 */
        private static const COMP_LABEL_W:Number = COL_W - 26;

        // ═══════════════════════════════════════════════════════
        // GroupBox 内容内部顶边距（GroupBox.content 已在边框线下，只需微量 padding）
        // ═══════════════════════════════════════════════════════

        private static const GB_INNER_PAD:int = 2;

        // ═══════════════════════════════════════════════════════
        // GroupBox 高度（LABEL_MID_Y 8 + PAD_TOP_DRAW 22 + 内容高 + 底留白 16）
        // ═══════════════════════════════════════════════════════

        private static const GB1_H:int = 72;    // 系别语音设置——30 + 2 + 22 + 18
        private static const GB2_H:int = 148;   // 通知设置——30 + 2 + 96 + 20
        private static const GB3_H:int = 176;   // 显示设置——30 + 2 + 124 + 20（i18n 后左列含日志输出，动态增高）
        private static const GB4_H:int = 112;   // 语音通用设置——30 + 2 + 60 + 20
        private static const GB5_H:int = 260;   // 字幕通用设置——30 + 2 + 156 + 50(预览) + 22
        private static const GB6_H:int = 180;   // UI 主题自定义——30 + 2 + 136 + 12(间距) + 20
        private static const TEXT_INPUT_W:Number = 200;
        private static const TEXT_INPUT_H:Number = 32;

        // ═══════════════════════════════════════════════════════
        // max 排版（i18n 第一期，§5.5）——GroupBox 高度动态计算
        // ═══════════════════════════════════════════════════════

        /** 标签行高 = max(手调常量, 标签文本实测高度)。 */
        private static const GB_BOTTOM_PAD:Number = 12;   // 内容底部留白
        // 内容区顶 = LABEL_MID_Y(8) + PAD_TOP_DRAW(22) = 30
        private static const GB_HEADER_H:Number = 30;

        /** 每个 GB 的最终高度（max(手调常量, 30 + 内容实测 + 底留白)），_createContent 用它累加 y。 */
        private var _gbHeights:Array = [0, 0, 0, 0, 0, 0];

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        // 标题
        private var _titleTF:TextField;
        private var _titleWrapper:Sprite;

        // 滚动区域
        private var _scrollPane:ScrollPane;
        private var _content:Sprite;
        /** 底部撑开占位（切语言重排后同步位置，保证滚动范围正确）。 */
        private var _contentSpacer:Shape;

        // ── GB1: 系别语音设置 ──
        private var _gb1:GroupBox;
        private var _nationRadioGroup:RadioGroup;
        private var _nationMale:RadioButton;
        private var _nationFemale:RadioButton;

        // ── GB2: 通知设置 ──
        private var _gb2:GroupBox;
        private var _notifyRadioGroup:RadioGroup;
        private var _notifyNone:RadioButton;
        private var _notifyCount:RadioButton;
        private var _notifyDetail:RadioButton;
        private var _cbUiSound:CheckBox;
        private var _cbSwitchNotify:CheckBox;
        private var _cbPlayOnSwitch:CheckBox;

        // ── GB3: 显示设置 ──
        private var _gb3:GroupBox;
        private var _cbHotkey:CheckBox;
        private var _ddHotkey:Dropdown;
        private var _ddLogLevel:Dropdown;
        private var _cbShowIngame:CheckBox;
        private var _cbShowInstalled:CheckBox;

        // ── GB4: 语音通用设置 ──
        private var _gb4:GroupBox;
        private var _cbAutoVolume:CheckBox;
        private var _cbSoundRemap:CheckBox;
        private var _cbSoundBind:CheckBox;

        // ── GB5: 字幕通用设置 ──
        private var _gb5:GroupBox;
        private var _subtitleRadioGroup:RadioGroup;
        private var _subSimple:RadioButton;
        private var _subStandard:RadioButton;
        private var _subNone:RadioButton;
        private var _stepperTextSpeed:Stepper;
        private var _cbSubUpdate:CheckBox;
        private var _cbSubAnim:CheckBox;
        private var _cbMultiSub:CheckBox;

        // ── 打字预览 ──
        private var _previewTF:TextField;
        private var _previewMask:Shape;
        private var _previewRevealTimer:Timer;    // 逐字露出计时器
        private var _previewPauseTimer:Timer;     // 循环间隔 1.5s
        private var _previewCharIndex:int = 0;
        private var _previewDelay:Number = 50;    // ms/字，由 Stepper 值计算
        private var _charRects:Array;             // Rectangle[]，每个字符的精确像素边界
        private var _previewText:String;          // 当前预览文本（词典推送，含截断结果）

        /** 预览文本默认值——词典缺失时的硬编码中文基线（加载链末端）。 */
        private static const PREVIEW_TEXT:String = "这是一个打字预览示例文本，用于展示字幕通用设置中的文字速度效果。";
        private static const PREVIEW_FONT_SIZE:int = 16;
        private static const PREVIEW_PAUSE_MS:int = 1500;

        // 打字机 mask 矩形外扩余量（Scaleform 度量缺陷补偿，见 _cacheCharRects）
        private static const CHAR_RECT_TOP_OVERHANG:Number = 1;
        private static const CHAR_RECT_BOTTOM_OVERHANG:Number = 4;

        // ── 预览上限保护（§5.5）──
        // maxH 以中文原文 2 行为基准：2 × 当前字体行高。截断用省略号：
        // "…"(U+2026) 优先；游戏字体缺字形（豆腐块）时改为 "..."（待实测）。
        private static const PREVIEW_MAX_LINES:int = 2;
        private static const PREVIEW_ELLIPSIS:String = "…";

        // ── GB6: UI 主题自定义 ──
        private var _gb6:GroupBox;
        private var _ddColorScheme:Dropdown;
        private var _ddBgIcon:Dropdown;
        private var _titleTextRadioGroup:RadioGroup;
        private var _titleFollowScheme:RadioButton;
        private var _titleCustom:RadioButton;
        private var _customColorInput:TextInput;
        // GB6 label wrappers（供 Tooltip 绑定和解绑）
        private var _colorSchemeLabelWrapper:Sprite;
        private var _bgIconLabelWrapper:Sprite;
        private var _titleTextLabelWrapper:Sprite;

        // 分类标签引用（i18n 刷新用——_addLabel 返回的 TextField）
        private var _notifyLabelTF:TextField;
        private var _hotkeyLabelTF:TextField;
        private var _logLabelTF:TextField;
        private var _uiLangLabelTF:TextField;
        private var _subtitleLabelTF:TextField;
        private var _speedLabelTF:TextField;
        private var _colorSchemeLabelTF:TextField;
        private var _bgIconLabelTF:TextField;
        private var _titleTextLabelTF:TextField;

        // ── GB3: 显示设置 ──
        private var _ddUiLang:Dropdown;

        // 分类标签引用（_addLabel 创建的 TextField），供 _refreshStyle 刷新
        private var _labelFields:Array;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        private var _initialized:Boolean = false;
        private var _lastPopulateData:Object = null;

        /** 用户操作回调 → Python DAAPI onLog。 */
        public var onAction:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        public function SettingsPage()
        {
            super("settings");
        }

        override public function init():void
        {
            if (_initialized) return;
            _initialized = true;

            _createTitle();
            _createScrollPane();
            _createContent();

            Theme.register(this, _refreshStyle);
            L10n.register(this, _applyLabels);

            if (_lastPopulateData)
                _applyPopulateData(_lastPopulateData);
        }

        // ═══════════════════════════════════════════════════════
        // 标题（与其他页面统一规格）
        // ═══════════════════════════════════════════════════════

        private function _createTitle():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TitleFont";
            fmt.size = 18;
            fmt.color = Theme.textPrimary;

            _titleTF = new TextField();
            _titleTF.defaultTextFormat = fmt;
            _titleTF.text = L10n.get("settings/title", "设置");
            _titleTF.selectable = false;
            _titleTF.mouseEnabled = false;
            _titleTF.autoSize = "left";

            _titleWrapper = new Sprite();
            _titleWrapper.buttonMode = true;
            _titleWrapper.useHandCursor = true;
            _titleWrapper.addChild(_titleTF);
            _titleWrapper.x = MARGIN_H;
            _titleWrapper.y = SAFE_TOP + TITLE_Y;
            addChild(_titleWrapper);
        }

        // ═══════════════════════════════════════════════════════
        // 滚动区域（上边缘紧挨标题，左右 10px，下 20px）
        // ═══════════════════════════════════════════════════════

        private function _createScrollPane():void
        {
            var scrollY:int = SAFE_TOP + TITLE_Y + 22 + 6;
            var scrollH:int = SAFE_TOP + PAGE_H - MARGIN_BOTTOM - scrollY;

            _scrollPane = new ScrollPane(PAGE_W, scrollH);
            _scrollPane.x = MARGIN_H;
            _scrollPane.y = scrollY;
            addChild(_scrollPane);

            _content = new Sprite();
            _content.mouseEnabled = false;
            _scrollPane.setContent(_content);
        }

        // ═══════════════════════════════════════════════════════
        // 内容组装（6 个 GroupBox 竖排）
        // ═══════════════════════════════════════════════════════

        private function _createContent():void
        {
            var gy:Number = 0;
            var gb:GroupBox;

            // max 排版（§5.5）：GB 高度由 _createGBx 实测（_gbHeights），
            // y 按实测累加——中文下与手调常量一致（零回归），翻译超长自动增高。
            gb = _createGB1();  gb.y = gy;  _content.addChild(gb);  gy += _gbHeights[0] + GB_GAP;
            gb = _createGB2();  gb.y = gy;  _content.addChild(gb);  gy += _gbHeights[1] + GB_GAP;
            gb = _createGB3();  gb.y = gy;  _content.addChild(gb);  gy += _gbHeights[2] + GB_GAP;
            gb = _createGB4();  gb.y = gy;  _content.addChild(gb);  gy += _gbHeights[3] + GB_GAP;
            gb = _createGB5();  gb.y = gy;  _content.addChild(gb);  gy += _gbHeights[4] + GB_GAP;
            gb = _createGB6();  gb.y = gy;  _content.addChild(gb);  gy += _gbHeights[5];

            // 底部占位撑开 content 高度，确保最后一个 GB 不贴 ScrollPane 底边
            gy += 20;
            _contentSpacer = new Shape();
            _contentSpacer.graphics.beginFill(0, 0);
            _contentSpacer.graphics.drawRect(0, 0, 1, 20);
            _contentSpacer.graphics.endFill();
            _contentSpacer.alpha = 0;
            _contentSpacer.y = gy - 20;
            _content.addChild(_contentSpacer);

            _scrollPane.setContent(_content);
        }

        // ═══════════════════════════════════════════════════════
        // GroupBox 1: 系别语音设置（带 Tooltip）
        // ═══════════════════════════════════════════════════════

        private function _createGB1():GroupBox
        {
            _gb1 = new GroupBox(GB_W, GB1_H, L10n.get("settings/nation_voice_title", "系别语音设置"), 4);
            _gb1.setLabelBgColor(Theme.surface0);

            _nationRadioGroup = new RadioGroup();
            _nationRadioGroup.onSelectionChange = function(index:int):void {
                var val:String = (index == 0) ? "male" : "female";
                L.info("系别语音 → " + val);
                if (onAction != null) onAction("nationVoiceGender," + val);
            };

            // 左右两列各自左对齐（与其他 GB 的组件对齐方式一致）
            _nationMale = new RadioButton(L10n.get("settings/radio_male", "男声"), COMP_LABEL_W);
            _nationMale.x = COL_L;
            _nationMale.y = GB_INNER_PAD;
            _nationRadioGroup.add(_nationMale);
            _gb1.content.addChild(_nationMale);

            _nationFemale = new RadioButton(L10n.get("settings/radio_female", "女声"), COMP_LABEL_W);
            _nationFemale.x = COL_R;
            _nationFemale.y = GB_INNER_PAD;
            _nationRadioGroup.add(_nationFemale);
            _gb1.content.addChild(_nationFemale);

            _nationRadioGroup.setSelectedIndex(0);

            // max 排版：高度 = max(手调常量, 30 + 内容实测 + 底留白)
            // 单选标签换行后组件变高，取两列较高者实测高度
            _gbHeights[0] = Math.max(GB1_H, GB_HEADER_H + GB_INNER_PAD
                + Math.max(_nationMale.height, _nationFemale.height) + GB_BOTTOM_PAD);
            _gb1.setSize(GB_W, _gbHeights[0]);
            return _gb1;
        }

        // ═══════════════════════════════════════════════════════
        // GroupBox 2: 通知设置
        // ═══════════════════════════════════════════════════════

        private function _createGB2():GroupBox
        {
            _gb2 = new GroupBox(GB_W, GB2_H, L10n.get("settings/notify_title", "通知设置"), 4);
            _gb2.setLabelBgColor(Theme.surface0);

            // ── 左列: 标签 + 3 个竖排单选按钮 ──
            var ly:int = GB_INNER_PAD;

            // 标签行高 = max(手调常量, 实测文本行高)——max 排版（§5.5）
            _notifyLabelTF = _addLabel(_gb2.content,
                L10n.get("settings/notify_label", "语音包统计信息推送"), COL_L, ly);
            ly += _labelRowHeight(_notifyLabelTF);

            _notifyRadioGroup = new RadioGroup();
            _notifyRadioGroup.onSelectionChange = function(index:int):void {
                var vals:Array = ["none", "count", "detail"];
                var val:String = String(vals[index] || "none");
                L.info("通知推送 → " + val);
                if (onAction != null) onAction("notifyPush," + val);
            };

            _notifyNone = new RadioButton(L10n.get("settings/radio_notify_none", "不推送"), COMP_LABEL_W);
            _notifyNone.x = COL_L;
            _notifyNone.y = ly;
            _notifyRadioGroup.add(_notifyNone);
            _gb2.content.addChild(_notifyNone);
            ly += Math.max(RADIO_ROW_H, _notifyNone.height);

            _notifyCount = new RadioButton(L10n.get("settings/radio_notify_count", "仅计数"), COMP_LABEL_W);
            _notifyCount.x = COL_L;
            _notifyCount.y = ly;
            _notifyRadioGroup.add(_notifyCount);
            _gb2.content.addChild(_notifyCount);
            ly += Math.max(RADIO_ROW_H, _notifyCount.height);

            _notifyDetail = new RadioButton(L10n.get("settings/radio_notify_detail", "详细"), COMP_LABEL_W);
            _notifyDetail.x = COL_L;
            _notifyDetail.y = ly;
            _notifyRadioGroup.add(_notifyDetail);
            _gb2.content.addChild(_notifyDetail);

            _notifyRadioGroup.setSelectedIndex(0);

            // ── 右列: 3 个复选框 ──
            var ry:int = GB_INNER_PAD;

            _cbUiSound = new CheckBox(L10n.get("settings/cb_ui_sound", "开启界面交互音效"), false, COMP_LABEL_W);
            _cbUiSound.x = COL_R;
            _cbUiSound.y = ry;
            _cbUiSound.onChange = function(checked:Boolean):void {
                SoundUtils.setMuted(!checked);
                _onCheckboxChanged("uiSound", checked);
            };
            _gb2.content.addChild(_cbUiSound);
            ry += Math.max(CHECK_ROW_H, _cbUiSound.height);

            _cbSwitchNotify = new CheckBox(L10n.get("settings/cb_switch_notify", "接收语音切换通知"), false, COMP_LABEL_W);
            _cbSwitchNotify.x = COL_R;
            _cbSwitchNotify.y = ry;
            _cbSwitchNotify.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("switchNotify", checked);
            };
            _gb2.content.addChild(_cbSwitchNotify);
            ry += Math.max(CHECK_ROW_H, _cbSwitchNotify.height);

            _cbPlayOnSwitch = new CheckBox(L10n.get("settings/cb_play_on_switch", "切换语音后播放选中语音"), false, COMP_LABEL_W);
            _cbPlayOnSwitch.x = COL_R;
            _cbPlayOnSwitch.y = ry;
            _cbPlayOnSwitch.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("playOnSwitch", checked);
            };
            _gb2.content.addChild(_cbPlayOnSwitch);

            // max 排版：高度取左右两列内容的较高者
            _gbHeights[1] = Math.max(GB2_H,
                GB_HEADER_H + Math.max(ly, ry) + GB_BOTTOM_PAD);
            _gb2.setSize(GB_W, _gbHeights[1]);
            return _gb2;
        }

        // ═══════════════════════════════════════════════════════
        // GroupBox 3: 显示设置
        // ═══════════════════════════════════════════════════════

        private function _createGB3():GroupBox
        {
            _gb3 = new GroupBox(GB_W, GB3_H, L10n.get("settings/display_title", "显示设置"), 4);
            _gb3.setLabelBgColor(Theme.surface0);

            // ── 左列: cb + 标签 + dd ──
            var ly:int = GB_INNER_PAD;

            _cbHotkey = new CheckBox(L10n.get("settings/cb_hotkey_enabled", "允许通过热键打开菜单"), false, COMP_LABEL_W);
            _cbHotkey.x = COL_L;
            _cbHotkey.y = ly;
            _cbHotkey.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("hotkeyEnabled", checked);
                if (_ddHotkey) _ddHotkey.setEnabled(checked);
            };
            _gb3.content.addChild(_cbHotkey);
            ly += Math.max(CHECK_ROW_H, _cbHotkey.height);

            _hotkeyLabelTF = _addLabel(_gb3.content,
                L10n.get("settings/hotkey_label", "设置热键"), COL_L, ly);
            ly += _labelRowHeight(_hotkeyLabelTF);

            _ddHotkey = new Dropdown(COL_W, ["F1"]);
            _ddHotkey.x = COL_L;
            _ddHotkey.y = ly;
            _ddHotkey.setEnabled(false);
            _ddHotkey.onSelect = function(index:int, label:String):void {
                L.info("热键 → " + label);
                if (onAction != null) onAction("hotkey," + label);
            };
            _gb3.content.addChild(_ddHotkey);
            ly += DROPDOWN_ROW_H;

            // 日志输出设置——原在右列，uiLang 加入后右列过长，移入左列（i18n 2026-08）
            _logLabelTF = _addLabel(_gb3.content,
                L10n.get("settings/log_label", "日志输出设置"), COL_L, ly);
            ly += _labelRowHeight(_logLabelTF);

            _ddLogLevel = new Dropdown(COL_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _ddLogLevel.x = COL_L;
            _ddLogLevel.y = ly;
            _ddLogLevel.onSelect = function(index:int, label:String):void {
                L.info("日志级别 → " + label + " (#" + index + ")");
                if (onAction != null) onAction("logLevel," + index);
            };
            _gb3.content.addChild(_ddLogLevel);
            ly += DROPDOWN_ROW_H;

            // ── 右列: 界面语言标签 + dd + 2cb ──
            var ry:int = GB_INNER_PAD;

            // 界面语言下拉（i18n 第一期）——回传存储 value（语言代码），
            // Python 端 handle_ui_lang 保存 + 重解析 + 重推全部页面
            _uiLangLabelTF = _addLabel(_gb3.content,
                L10n.get("settings/ui_lang_label", "界面语言"), COL_R, ry);
            ry += _labelRowHeight(_uiLangLabelTF);

            _ddUiLang = new Dropdown(COL_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _ddUiLang.x = COL_R;
            _ddUiLang.y = ry;
            _ddUiLang.onSelect = function(index:int, label:String):void {
                L.info("界面语言 → " + _ddUiLang.selectedValue);
                if (onAction != null) onAction("uiLang," + _ddUiLang.selectedValue);
            };
            _gb3.content.addChild(_ddUiLang);
            ry += DROPDOWN_ROW_H;

            _cbShowIngame = new CheckBox(L10n.get("settings/cb_show_ingame", "游戏内置语音包在设置菜单中显示"), false, COMP_LABEL_W);
            _cbShowIngame.x = COL_R;
            _cbShowIngame.y = ry;
            _cbShowIngame.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("showIngameVoices", checked);
            };
            _gb3.content.addChild(_cbShowIngame);
            ry += Math.max(CHECK_ROW_H, _cbShowIngame.height);

            _cbShowInstalled = new CheckBox(L10n.get("settings/cb_show_installed", "已安装的语音包在设置菜单中显示"), false, COMP_LABEL_W);
            _cbShowInstalled.x = COL_R;
            _cbShowInstalled.y = ry;
            _cbShowInstalled.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("showInstalledVoices", checked);
            };
            _gb3.content.addChild(_cbShowInstalled);

            // max 排版：高度取左右两列内容的较高者
            _gbHeights[2] = Math.max(GB3_H,
                GB_HEADER_H + Math.max(ly, ry) + GB_BOTTOM_PAD);
            _gb3.setSize(GB_W, _gbHeights[2]);
            return _gb3;
        }

        // ═══════════════════════════════════════════════════════
        // GroupBox 4: 语音通用设置
        // ═══════════════════════════════════════════════════════

        private function _createGB4():GroupBox
        {
            _gb4 = new GroupBox(GB_W, GB4_H, L10n.get("settings/voice_general_title", "语音通用设置"), 4);
            _gb4.setLabelBgColor(Theme.surface0);

            var ly:int = GB_INNER_PAD;

            _cbAutoVolume = new CheckBox(L10n.get("settings/cb_auto_volume", "切换语音时自动应用预设音量"), false, COMP_LABEL_W);
            _cbAutoVolume.x = COL_L;
            _cbAutoVolume.y = ly;
            _cbAutoVolume.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("autoVolume", checked);
            };
            _gb4.content.addChild(_cbAutoVolume);
            ly += Math.max(CHECK_ROW_H, _cbAutoVolume.height);

            _cbSoundRemap = new CheckBox(L10n.get("settings/cb_sound_remap", "允许使用声音重映射"), false, COMP_LABEL_W);
            _cbSoundRemap.x = COL_L;
            _cbSoundRemap.y = ly;
            _cbSoundRemap.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("soundRemap", checked);
            };
            _gb4.content.addChild(_cbSoundRemap);

            // ── 右列: 声音绑定 ──
            _cbSoundBind = new CheckBox(L10n.get("settings/cb_sound_bind", "允许使用声音绑定"), false, COMP_LABEL_W);
            _cbSoundBind.x = COL_R;
            _cbSoundBind.y = GB_INNER_PAD;
            _cbSoundBind.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("soundBind", checked);
            };
            _gb4.content.addChild(_cbSoundBind);

            // max 排版：高度取左右两列内容的较高者（右列按实测高度）
            _gbHeights[3] = Math.max(GB4_H,
                GB_HEADER_H + Math.max(ly, GB_INNER_PAD + _cbSoundBind.height) + GB_BOTTOM_PAD);
            _gb4.setSize(GB_W, _gbHeights[3]);
            return _gb4;
        }

        // ═══════════════════════════════════════════════════════
        // GroupBox 5: 字幕通用设置（带 Tooltip）
        // ═══════════════════════════════════════════════════════

        private function _createGB5():GroupBox
        {
            _gb5 = new GroupBox(GB_W, GB5_H, L10n.get("settings/subtitle_general_title", "字幕通用设置"), 4);
            _gb5.setLabelBgColor(Theme.surface0);

            // ── 左列: 标签 + 3电台 + 标签 + 步进器 ──
            var ly:int = GB_INNER_PAD;

            _subtitleLabelTF = _addLabel(_gb5.content,
                L10n.get("settings/subtitle_label", "字幕显示"), COL_L, ly);
            ly += _labelRowHeight(_subtitleLabelTF);

            _subtitleRadioGroup = new RadioGroup();
            _subtitleRadioGroup.onSelectionChange = function(index:int):void {
                var vals:Array = ["simple", "standard", "none"];
                var val:String = String(vals[index] || "simple");
                L.info("字幕显示 → " + val);
                if (onAction != null) onAction("subtitleDisplay," + val);
            };

            _subSimple = new RadioButton(L10n.get("settings/radio_sub_simple", "简洁"), COMP_LABEL_W);
            _subSimple.x = COL_L;
            _subSimple.y = ly;
            _subtitleRadioGroup.add(_subSimple);
            _gb5.content.addChild(_subSimple);
            ly += Math.max(RADIO_ROW_H, _subSimple.height);

            _subStandard = new RadioButton(L10n.get("settings/radio_sub_standard", "标准"), COMP_LABEL_W);
            _subStandard.x = COL_L;
            _subStandard.y = ly;
            _subtitleRadioGroup.add(_subStandard);
            _gb5.content.addChild(_subStandard);
            ly += Math.max(RADIO_ROW_H, _subStandard.height);

            _subNone = new RadioButton(L10n.get("settings/radio_sub_none", "不显示"), COMP_LABEL_W);
            _subNone.x = COL_L;
            _subNone.y = ly;
            _subtitleRadioGroup.add(_subNone);
            _gb5.content.addChild(_subNone);
            ly += Math.max(RADIO_ROW_H, _subNone.height);

            _subtitleRadioGroup.setSelectedIndex(1);  // 默认「标准」

            _speedLabelTF = _addLabel(_gb5.content,
                L10n.get("settings/speed_label", "文字速度"), COL_L, ly);
            ly += _labelRowHeight(_speedLabelTF);

            _stepperTextSpeed = new Stepper(COL_W, 0, 0.1, 0.03, 0.01);
            _stepperTextSpeed.x = COL_L;
            _stepperTextSpeed.y = ly;
            _stepperTextSpeed.onChange = function(value:Number):void {
                L.info("文字速度 → " + value.toFixed(2));
                if (onAction != null) onAction("textSpeed," + value.toFixed(2));
                _onPreviewSpeedChange(value);
            };
            _gb5.content.addChild(_stepperTextSpeed);
            ly += STEPPER_ROW_H + 8;

            // ── 打字预览（全文 + mask 逐字露出） ──
            // 预览文本走词典（populate 推送 previewText）；词典缺失回退
            // PREVIEW_TEXT 硬编码中文基线。设文本后立即截断（上限保护）。
            var prevFmt:TextFormat = new TextFormat();
            prevFmt.font = "$TextFont";
            prevFmt.size = PREVIEW_FONT_SIZE;
            prevFmt.color = Theme.textPrimary;

            _previewTF = new TextField();
            _previewTF.defaultTextFormat = prevFmt;
            _previewTF.width = COL_W;
            _previewTF.wordWrap = true;
            _previewTF.multiline = true;
            _previewTF.selectable = false;
            _previewTF.mouseEnabled = false;
            _previewTF.x = COL_L;
            _previewTF.y = ly;
            _previewText = PREVIEW_TEXT;
            _previewTF.text = _previewText;
            _truncatePreviewText();      // 上限保护：超过中文原文 2 行高度则截断
            _cacheCharRects();
            _gb5.content.addChild(_previewTF);

            // mask：初始为空，每 tick 重绘以露出已显示字符
            _previewMask = new Shape();
            _previewMask.x = COL_L;
            _previewMask.y = ly;
            _gb5.content.addChild(_previewMask);
            _previewTF.mask = _previewMask;

            // 预览区行高按实测（max 排版）：文本高度 + 少量余量
            ly += _previewTF.textHeight + 6;

            // ── 右列: 2 个复选框 ──
            var ry:int = GB_INNER_PAD;

            _cbSubUpdate = new CheckBox(L10n.get("settings/cb_sub_update", "允许字幕更新内容"), false, COMP_LABEL_W);
            _cbSubUpdate.x = COL_R;
            _cbSubUpdate.y = ry;
            _cbSubUpdate.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("subtitleUpdate", checked);
            };
            _gb5.content.addChild(_cbSubUpdate);
            ry += Math.max(CHECK_ROW_H, _cbSubUpdate.height);

            _cbSubAnim = new CheckBox(L10n.get("settings/cb_sub_anim", "启用字幕动画效果"), false, COMP_LABEL_W);
            _cbSubAnim.x = COL_R;
            _cbSubAnim.y = ry;
            _cbSubAnim.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("subtitleAnim", checked);
            };
            _gb5.content.addChild(_cbSubAnim);
            ry += Math.max(CHECK_ROW_H, _cbSubAnim.height);

            _cbMultiSub = new CheckBox(L10n.get("settings/cb_multi_sub", "允许多条字幕同时出现"), false, COMP_LABEL_W);
            _cbMultiSub.x = COL_R;
            _cbMultiSub.y = ry;
            _cbMultiSub.onChange = function(checked:Boolean):void {
                _onCheckboxChanged("multiSub", checked);
            };
            _gb5.content.addChild(_cbMultiSub);

            // max 排版：高度取左右两列内容的较高者
            _gbHeights[4] = Math.max(GB5_H,
                GB_HEADER_H + Math.max(ly, ry) + GB_BOTTOM_PAD);
            _gb5.setSize(GB_W, _gbHeights[4]);
            return _gb5;
        }

        // ═══════════════════════════════════════════════════════
        // GroupBox 6: UI 主题自定义
        // ═══════════════════════════════════════════════════════

        private function _createGB6():GroupBox
        {
            _gb6 = new GroupBox(GB_W, GB6_H, L10n.get("settings/theme/title", "UI 主题自定义"), 4);
            _gb6.setLabelBgColor(Theme.surface0);

            // ── 左列: 颜色方案 + 背景图标 ──
            var ly:int = GB_INNER_PAD;

            _colorSchemeLabelWrapper = _addLabelWithTooltip(
                _gb6.content, L10n.get("settings/theme/color_scheme_label", "颜色方案"), COL_L, ly);
            _colorSchemeLabelTF = _colorSchemeLabelWrapper.getChildAt(0) as TextField;
            ly += _labelRowHeight(_colorSchemeLabelTF);

            _ddColorScheme = new Dropdown(COL_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _ddColorScheme.x = COL_L;
            _ddColorScheme.y = ly;
            // 回传存储 value（token），不是显示文本——存储/匹配全链路无中文
            _ddColorScheme.onSelect = function(index:int, label:String):void {
                L.info("颜色方案 → " + _ddColorScheme.selectedValue);
                if (onAction != null) onAction("colorScheme," + _ddColorScheme.selectedValue);
            };
            _gb6.content.addChild(_ddColorScheme);
            ly += DROPDOWN_ROW_H + 8;

            _bgIconLabelWrapper = _addLabelWithTooltip(
                _gb6.content, L10n.get("settings/theme/bg_icon_label", "背景图标"), COL_L, ly);
            _bgIconLabelTF = _bgIconLabelWrapper.getChildAt(0) as TextField;
            ly += _labelRowHeight(_bgIconLabelTF);

            _ddBgIcon = new Dropdown(COL_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _ddBgIcon.x = COL_L;
            _ddBgIcon.y = ly;
            // 回传存储 value（token），不是显示文本——存储/匹配全链路无中文
            _ddBgIcon.onSelect = function(index:int, label:String):void {
                L.info("背景图标 → " + _ddBgIcon.selectedValue);
                if (onAction != null) onAction("bgIcon," + _ddBgIcon.selectedValue);
            };
            _gb6.content.addChild(_ddBgIcon);

            // ── 右列: 大标题颜色单选 + 自定义颜色输入框 ──
            var ry:int = GB_INNER_PAD;

            _titleTextLabelWrapper = _addLabelWithTooltip(
                _gb6.content, L10n.get("settings/theme/title_text_label", "标题文本颜色"), COL_R, ry);
            _titleTextLabelTF = _titleTextLabelWrapper.getChildAt(0) as TextField;
            ry += _labelRowHeight(_titleTextLabelTF);

            _titleTextRadioGroup = new RadioGroup();
            _titleTextRadioGroup.onSelectionChange = function(index:int):void {
                var mode:String = (index == 0) ? "followScheme" : "custom";
                L.info("标题文本颜色 → " + mode);
                _customColorInput.visible = (index == 1);
                if (onAction != null) onAction("titleTextMode," + mode);
            };

            _titleFollowScheme = new RadioButton(L10n.get("settings/theme/radio_follow_scheme", "跟随颜色方案"), COMP_LABEL_W);
            _titleFollowScheme.x = COL_R;
            _titleFollowScheme.y = ry;
            _titleTextRadioGroup.add(_titleFollowScheme);
            _gb6.content.addChild(_titleFollowScheme);
            ry += Math.max(RADIO_ROW_H, _titleFollowScheme.height);

            _titleCustom = new RadioButton(L10n.get("settings/theme/radio_custom", "自定义"), COMP_LABEL_W);
            _titleCustom.x = COL_R;
            _titleCustom.y = ry;
            _titleTextRadioGroup.add(_titleCustom);
            _gb6.content.addChild(_titleCustom);
            ry += Math.max(RADIO_ROW_H, _titleCustom.height);

            _customColorInput = new TextInput(TEXT_INPUT_W, TEXT_INPUT_H,
                L10n.get("settings/theme/color_input_placeholder", "#RRGGBB"));
            _customColorInput.x = COL_R;
            _customColorInput.y = ry;
            _customColorInput.visible = false;
            // 限定最多 7 位（# + 6 位 hex），防止超长输入
            _customColorInput.maxChars = 7;
            _customColorInput.debounceDelay = 300;
            _customColorInput.onChange = function(text:String):void {
                // 输入未满 7 位（#RRGGBB）时不判断——避免边输入边回退，
                // 打断用户输完整色值
                if (text.length < 7) return;

                // 校验 #RRGGBB 格式
                var hexRe:RegExp = /^#[0-9A-Fa-f]{6}$/;
                if (hexRe.test(text))
                {
                    L.info("自定义标题文本颜色 → " + text);
                    if (onAction != null) onAction("titleTextColor," + text);
                }
                else
                {
                    // 格式非法 → 回退到当前 Theme.titleText 的 hex 值
                    var fallback:String = "#" + Theme.titleText.toString(16).toUpperCase();
                    // 补前导零到 6 位
                    while (fallback.length < 7) fallback = "#0" + fallback.substr(1);
                    L.info("自定义标题颜色格式无效: " + text + "，回退 → " + fallback);
                    _customColorInput.text = fallback;
                    // 回退值也同步 Python，保证持久化值与输入框显示一致
                    if (onAction != null) onAction("titleTextColor," + fallback);
                }
            };
            _gb6.content.addChild(_customColorInput);

            // max 排版：高度取左右两列内容的较高者（右列含输入框高度）
            _gbHeights[5] = Math.max(GB6_H,
                GB_HEADER_H + Math.max(ly, ry + TEXT_INPUT_H) + GB_BOTTOM_PAD);
            _gb6.setSize(GB_W, _gbHeights[5]);
            return _gb6;
        }

        // ═══════════════════════════════════════════════════════
        // 布局重排（i18n 切语言补执行）
        // ═══════════════════════════════════════════════════════

        /**
         * 按当前文本实测高度重排全部 6 个 GB（§5.5 max 排版在运行时的补执行）。
         *
         * 页面是单例——切语言只走 _applyLabels 换文本，组件位置/GB 高度仍按
         * 旧语言（中文基线）排好，导致英文长文本换行后下方组件不随之下移、
         * GB 高度不增高（如 GB4 的 cb_auto_volume 换行后压住 cb_sound_remap）。
         * 本方法按各组件当前实测高度重算每行 y、每 GB 高度，再纵向重排
         * 6 个 GB 并刷新滚动范围。布局数学必须与各 _createGBx 保持同步。
         */
        private function _relayout():void
        {
            // 组件未创建（populate 早于 init 的极端情况）时直接跳过
            if (!_gb1 || !_scrollPane) return;

            // ── GB1: 系别语音设置（单选始终在同一行，仅高度可能变）──
            _gbHeights[0] = Math.max(GB1_H, GB_HEADER_H + GB_INNER_PAD
                + Math.max(_nationMale.height, _nationFemale.height) + GB_BOTTOM_PAD);
            _gb1.setSize(GB_W, _gbHeights[0]);

            // ── GB2: 通知设置 ──
            var ly2:int = GB_INNER_PAD;
            ly2 += _labelRowHeight(_notifyLabelTF);
            _notifyNone.y = ly2;   ly2 += Math.max(RADIO_ROW_H, _notifyNone.height);
            _notifyCount.y = ly2;  ly2 += Math.max(RADIO_ROW_H, _notifyCount.height);
            _notifyDetail.y = ly2;
            var ry2:int = GB_INNER_PAD;
            _cbUiSound.y = ry2;       ry2 += Math.max(CHECK_ROW_H, _cbUiSound.height);
            _cbSwitchNotify.y = ry2;  ry2 += Math.max(CHECK_ROW_H, _cbSwitchNotify.height);
            _cbPlayOnSwitch.y = ry2;
            _gbHeights[1] = Math.max(GB2_H,
                GB_HEADER_H + Math.max(ly2, ry2) + GB_BOTTOM_PAD);
            _gb2.setSize(GB_W, _gbHeights[1]);

            // ── GB3: 显示设置 ──
            var ly3:int = GB_INNER_PAD;
            _cbHotkey.y = ly3;      ly3 += Math.max(CHECK_ROW_H, _cbHotkey.height);
            _hotkeyLabelTF.y = ly3; ly3 += _labelRowHeight(_hotkeyLabelTF);
            _ddHotkey.y = ly3;      ly3 += DROPDOWN_ROW_H;
            _logLabelTF.y = ly3;    ly3 += _labelRowHeight(_logLabelTF);
            _ddLogLevel.y = ly3;    ly3 += DROPDOWN_ROW_H;
            var ry3:int = GB_INNER_PAD;
            _uiLangLabelTF.y = ry3; ry3 += _labelRowHeight(_uiLangLabelTF);
            _ddUiLang.y = ry3;      ry3 += DROPDOWN_ROW_H;
            _cbShowIngame.y = ry3;  ry3 += Math.max(CHECK_ROW_H, _cbShowIngame.height);
            _cbShowInstalled.y = ry3;
            _gbHeights[2] = Math.max(GB3_H,
                GB_HEADER_H + Math.max(ly3, ry3) + GB_BOTTOM_PAD);
            _gb3.setSize(GB_W, _gbHeights[2]);

            // ── GB4: 语音通用设置（cb_auto_volume 英文换行 → 下一复选框下移）──
            var ly4:int = GB_INNER_PAD;
            _cbAutoVolume.y = ly4;  ly4 += Math.max(CHECK_ROW_H, _cbAutoVolume.height);
            _cbSoundRemap.y = ly4;
            _cbSoundBind.y = GB_INNER_PAD;
            _gbHeights[3] = Math.max(GB4_H,
                GB_HEADER_H + Math.max(ly4, GB_INNER_PAD + _cbSoundBind.height) + GB_BOTTOM_PAD);
            _gb4.setSize(GB_W, _gbHeights[3]);

            // ── GB5: 字幕通用设置（预览区高度按实测，populate 换文后再次重排）──
            var ly5:int = GB_INNER_PAD;
            _subtitleLabelTF.y = ly5; ly5 += _labelRowHeight(_subtitleLabelTF);
            _subSimple.y = ly5;    ly5 += Math.max(RADIO_ROW_H, _subSimple.height);
            _subStandard.y = ly5;  ly5 += Math.max(RADIO_ROW_H, _subStandard.height);
            _subNone.y = ly5;      ly5 += Math.max(RADIO_ROW_H, _subNone.height);
            _speedLabelTF.y = ly5; ly5 += _labelRowHeight(_speedLabelTF);
            _stepperTextSpeed.y = ly5; ly5 += STEPPER_ROW_H + 8;
            _previewTF.y = ly5;
            if (_previewMask) _previewMask.y = ly5;
            ly5 += _previewTF.textHeight + 6;
            var ry5:int = GB_INNER_PAD;
            _cbSubUpdate.y = ry5;  ry5 += Math.max(CHECK_ROW_H, _cbSubUpdate.height);
            _cbSubAnim.y = ry5;    ry5 += Math.max(CHECK_ROW_H, _cbSubAnim.height);
            _cbMultiSub.y = ry5;
            _gbHeights[4] = Math.max(GB5_H,
                GB_HEADER_H + Math.max(ly5, ry5) + GB_BOTTOM_PAD);
            _gb5.setSize(GB_W, _gbHeights[4]);

            // ── GB6: UI 主题自定义 ──
            var ly6:int = GB_INNER_PAD;
            _colorSchemeLabelWrapper.y = ly6; ly6 += _labelRowHeight(_colorSchemeLabelTF);
            _ddColorScheme.y = ly6; ly6 += DROPDOWN_ROW_H + 8;
            _bgIconLabelWrapper.y = ly6; ly6 += _labelRowHeight(_bgIconLabelTF);
            _ddBgIcon.y = ly6;
            var ry6:int = GB_INNER_PAD;
            _titleTextLabelWrapper.y = ry6; ry6 += _labelRowHeight(_titleTextLabelTF);
            _titleFollowScheme.y = ry6; ry6 += Math.max(RADIO_ROW_H, _titleFollowScheme.height);
            _titleCustom.y = ry6;     ry6 += Math.max(RADIO_ROW_H, _titleCustom.height);
            _customColorInput.y = ry6;
            _gbHeights[5] = Math.max(GB6_H,
                GB_HEADER_H + Math.max(ly6, ry6 + TEXT_INPUT_H) + GB_BOTTOM_PAD);
            _gb6.setSize(GB_W, _gbHeights[5]);

            // ── 纵向重排 6 个 GB（与 _createContent 相同累加规则，最后不加间隙）──
            var gbs:Array = [_gb1, _gb2, _gb3, _gb4, _gb5, _gb6];
            var gy:Number = 0;
            for (var i:int = 0; i < gbs.length; i++)
            {
                var gb:GroupBox = gbs[i] as GroupBox;
                if (!gb) continue;
                gb.y = gy;
                gy += _gbHeights[i] + (i < gbs.length - 1 ? GB_GAP : 0);
            }

            // 底部 20px 撑开 + 刷新滚动范围（内容高度变化后滚动条随之更新）
            gy += 20;
            if (_contentSpacer) _contentSpacer.y = gy - 20;
            if (_scrollPane) _scrollPane.refresh();
        }

        // ═══════════════════════════════════════════════════════
        // 辅助方法
        // ═══════════════════════════════════════════════════════

        /**
         * 在指定位置创建粗体分类标签。
         * @return 创建的 TextField（调用方保存引用供 _applyLabels 刷新文本）
         */
        private function _addLabel(parent:Sprite, text:String, px:Number, py:Number):TextField
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = Theme.textSecondary;
            fmt.bold = true;

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.text = text;
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.autoSize = "left";
            // 限定列宽内自动换行（i18n——长翻译不横向溢出/压到另一列）。
            // autoSize="left" + wordWrap 组合：宽度保持，高度随内容自动扩展，
            // _labelRowHeight 已用实测高度支撑 max 排版，中文本单行零回归。
            tf.width = COL_W;
            tf.wordWrap = true;
            tf.multiline = true;
            tf.x = px;
            tf.y = py;
            parent.addChild(tf);

            // 收集引用，供 _refreshStyle 在主题切换时刷新颜色
            if (!_labelFields) _labelFields = [];
            _labelFields.push(tf);

            return tf;
        }

        /**
         * 标签行高（max 排版 §5.5）——最终值 = max(手调常量, 文本实测行高)。
         * autoSize="left" 时 TextField.height 含上下内边距，+1 防除整。
         */
        private function _labelRowHeight(tf:TextField):Number
        {
            return Math.max(LABEL_ROW_H, (tf ? tf.height : 0) + 1);
        }

        /** 在指定位置创建可绑定 Tooltip 的粗体分类标签。
         *
         *  返回 Sprite wrapper（buttonMode=true），
         *  后续可传入 _bindTooltip 绑定 Tooltip。
         *  dispose 时需对返回的 wrapper 调用 Tooltip.detach。
         */
        private function _addLabelWithTooltip(parent:Sprite, text:String,
                                              px:Number, py:Number):Sprite
        {
            var wrapper:Sprite = new Sprite();
            wrapper.x = px;
            wrapper.y = py;
            wrapper.buttonMode = true;
            wrapper.useHandCursor = true;
            _addLabel(wrapper, text, 0, 0);
            parent.addChild(wrapper);
            return wrapper;
        }

        /** 复选框统一回调，转发到 Python。 */
        private function _onCheckboxChanged(key:String, checked:Boolean):void
        {
            L.info(key + " → " + (checked ? "选中" : "未选中"));
            if (onAction != null)
                onAction("checkbox," + key + "," + (checked ? "1" : "0"));
        }

        // ═══════════════════════════════════════════════════════
        // 主题刷新
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            if (_titleTF) _titleTF.textColor = Theme.textPrimary;
            if (_previewTF)
            {
                var pf:TextFormat = _previewTF.defaultTextFormat;
                pf.color = Theme.textPrimary;
                _previewTF.defaultTextFormat = pf;
                _previewTF.textColor = Theme.textPrimary;
                _previewTF.setTextFormat(pf);
            }
            // 分类标签——_addLabel 创建时用的 Theme.textSecondary，
            // 主题切换后需同步更新
            if (_labelFields)
            {
                for each (var tf:TextField in _labelFields)
                {
                    if (tf)
                    {
                        var lf:TextFormat = tf.defaultTextFormat;
                        lf.color = Theme.textSecondary;
                        tf.defaultTextFormat = lf;
                        tf.textColor = Theme.textSecondary;
                    }
                }
            }
        }

        // ═══════════════════════════════════════════════════════
        // i18n 刷新（L10n 注册回调——labels 推送后调用）
        // ═══════════════════════════════════════════════════════

        /** 全部用户可见文本按词典刷新。下拉选项由 populate 管理，不在此处理。 */
        private function _applyLabels():void
        {
            if (_titleTF) _titleTF.text = L10n.get("settings/title", "设置");
            if (_gb1) _gb1.setTitle(L10n.get("settings/nation_voice_title", "系别语音设置"));
            if (_nationMale) _nationMale.setLabel(L10n.get("settings/radio_male", "男声"));
            if (_nationFemale) _nationFemale.setLabel(L10n.get("settings/radio_female", "女声"));

            if (_gb2) _gb2.setTitle(L10n.get("settings/notify_title", "通知设置"));
            if (_notifyLabelTF) _notifyLabelTF.text = L10n.get("settings/notify_label", "语音包统计信息推送");
            if (_notifyNone) _notifyNone.setLabel(L10n.get("settings/radio_notify_none", "不推送"));
            if (_notifyCount) _notifyCount.setLabel(L10n.get("settings/radio_notify_count", "仅计数"));
            if (_notifyDetail) _notifyDetail.setLabel(L10n.get("settings/radio_notify_detail", "详细"));
            if (_cbUiSound) _cbUiSound.setLabel(L10n.get("settings/cb_ui_sound", "开启界面交互音效"));
            if (_cbSwitchNotify) _cbSwitchNotify.setLabel(L10n.get("settings/cb_switch_notify", "接收语音切换通知"));
            if (_cbPlayOnSwitch) _cbPlayOnSwitch.setLabel(L10n.get("settings/cb_play_on_switch", "切换语音后播放选中语音"));

            if (_gb3) _gb3.setTitle(L10n.get("settings/display_title", "显示设置"));
            if (_cbHotkey) _cbHotkey.setLabel(L10n.get("settings/cb_hotkey_enabled", "允许通过热键打开菜单"));
            if (_hotkeyLabelTF) _hotkeyLabelTF.text = L10n.get("settings/hotkey_label", "设置热键");
            if (_logLabelTF) _logLabelTF.text = L10n.get("settings/log_label", "日志输出设置");
            if (_uiLangLabelTF) _uiLangLabelTF.text = L10n.get("settings/ui_lang_label", "界面语言");
            if (_cbShowIngame) _cbShowIngame.setLabel(L10n.get("settings/cb_show_ingame", "游戏内置语音包在设置菜单中显示"));
            if (_cbShowInstalled) _cbShowInstalled.setLabel(L10n.get("settings/cb_show_installed", "已安装的语音包在设置菜单中显示"));

            if (_gb4) _gb4.setTitle(L10n.get("settings/voice_general_title", "语音通用设置"));
            if (_cbAutoVolume) _cbAutoVolume.setLabel(L10n.get("settings/cb_auto_volume", "切换语音时自动应用预设音量"));
            if (_cbSoundRemap) _cbSoundRemap.setLabel(L10n.get("settings/cb_sound_remap", "允许使用声音重映射"));
            if (_cbSoundBind) _cbSoundBind.setLabel(L10n.get("settings/cb_sound_bind", "允许使用声音绑定"));

            if (_gb5) _gb5.setTitle(L10n.get("settings/subtitle_general_title", "字幕通用设置"));
            if (_subtitleLabelTF) _subtitleLabelTF.text = L10n.get("settings/subtitle_label", "字幕显示");
            if (_subSimple) _subSimple.setLabel(L10n.get("settings/radio_sub_simple", "简洁"));
            if (_subStandard) _subStandard.setLabel(L10n.get("settings/radio_sub_standard", "标准"));
            if (_subNone) _subNone.setLabel(L10n.get("settings/radio_sub_none", "不显示"));
            if (_speedLabelTF) _speedLabelTF.text = L10n.get("settings/speed_label", "文字速度");
            if (_cbSubUpdate) _cbSubUpdate.setLabel(L10n.get("settings/cb_sub_update", "允许字幕更新内容"));
            if (_cbSubAnim) _cbSubAnim.setLabel(L10n.get("settings/cb_sub_anim", "启用字幕动画效果"));
            if (_cbMultiSub) _cbMultiSub.setLabel(L10n.get("settings/cb_multi_sub", "允许多条字幕同时出现"));

            if (_gb6) _gb6.setTitle(L10n.get("settings/theme/title", "UI 主题自定义"));
            if (_colorSchemeLabelTF) _colorSchemeLabelTF.text = L10n.get("settings/theme/color_scheme_label", "颜色方案");
            if (_bgIconLabelTF) _bgIconLabelTF.text = L10n.get("settings/theme/bg_icon_label", "背景图标");
            if (_titleTextLabelTF) _titleTextLabelTF.text = L10n.get("settings/theme/title_text_label", "标题文本颜色");
            if (_titleFollowScheme) _titleFollowScheme.setLabel(L10n.get("settings/theme/radio_follow_scheme", "跟随颜色方案"));
            if (_titleCustom) _titleCustom.setLabel(L10n.get("settings/theme/radio_custom", "自定义"));
            if (_customColorInput) _customColorInput.placeholder = L10n.get("settings/theme/color_input_placeholder", "#RRGGBB");

            // 换文本后全部 GB 按实测高度重排（长英文换行 → 下方组件下移、GB 增高）
            _relayout();
        }

        // ═══════════════════════════════════════════════════════
        // 打字预览动画
        // ═══════════════════════════════════════════════════════

        /** Stepper 值变更 → 换算延迟并立即反映到动画。 */
        private function _onPreviewSpeedChange(speed:Number):void
        {
            _previewDelay = _speedToDelay(speed);

            if (_previewDelay <= 0)
            {
                // 速度为 0：立即显示全部文字，停掉所有计时器
                _stopPreview();
                _previewCharIndex = _previewText.length;
                _updateMask();
                return;
            }

            // 速度 > 0：确保动画在运行
            var animating:Boolean = (_previewRevealTimer && _previewRevealTimer.running) ||
                                     (_previewPauseTimer && _previewPauseTimer.running);
            if (!animating)
            {
                _startPreview();  // 从静止（speed=0）恢复
            }
            else if (_previewRevealTimer && _previewRevealTimer.running)
            {
                // 正在逐字播放 → 重建计时器以立即应用新延迟
                _previewRevealTimer.stop();
                _startRevealTimer();
            }
            // 如果在暂停中，不打断，下次循环自然用 _previewDelay
        }

        /** 开始预览动画循环。speed=0 时直接显示全文，不启动计时器。 */
        private function _startPreview():void
        {
            if (!_previewTF || !_previewMask) return;
            _stopPreview();
            _previewCharIndex = 0;

            if (_previewDelay <= 0)
            {
                // 速度为 0：全文可见
                _previewCharIndex = _previewText.length;
                _updateMask();
                return;
            }

            _updateMask();
            _startRevealTimer();
        }

        /** 停止全部预览计时器。 */
        private function _stopPreview():void
        {
            if (_previewRevealTimer)
            {
                _previewRevealTimer.stop();
                _previewRevealTimer.removeEventListener(TimerEvent.TIMER, _onPreviewRevealTick);
                _previewRevealTimer = null;
            }
            if (_previewPauseTimer)
            {
                _previewPauseTimer.stop();
                _previewPauseTimer.removeEventListener(TimerEvent.TIMER_COMPLETE, _onPreviewPauseEnd);
                _previewPauseTimer = null;
            }
        }

        /** 启动 / 重启逐字露出计时器。 */
        private function _startRevealTimer():void
        {
            if (_previewDelay <= 0) return;  // speed=0 不启动计时器
            if (_previewRevealTimer)
            {
                _previewRevealTimer.stop();
                _previewRevealTimer.removeEventListener(TimerEvent.TIMER, _onPreviewRevealTick);
            }
            var remaining:int = _previewText.length - _previewCharIndex;
            _previewRevealTimer = new Timer(_previewDelay, remaining);
            _previewRevealTimer.addEventListener(TimerEvent.TIMER, _onPreviewRevealTick);
            _previewRevealTimer.addEventListener(TimerEvent.TIMER_COMPLETE, _onPreviewRevealComplete);
            _previewRevealTimer.start();
        }

        /** 每 tick 露出一个字符。 */
        private function _onPreviewRevealTick(e:TimerEvent):void
        {
            _previewCharIndex++;
            _updateMask();
        }

        /** 缓存每个字符的精确像素矩形（getCharBoundaries），供 _updateMask 绘图。 */
        private function _cacheCharRects():void
        {
            _charRects = [];

            // Scaleform 度量缺陷补偿：getCharBoundaries 对 Latin 字形底部只到
            // baseline，不含 descender（y/g/p/q/j 等下降笔画下半截会被 mask
            // 盖住，表现为 "y" 变 "v"）。按字号比例向下补余量，保证下降笔画
            // 完整露出；顶部固定补 1px 防御 ascender 顶部切边。余量画的是
            // baseline 下方空白，不会提前露出相邻字符；行间 gap 大于余量，
            // 也不会漏到下一行。
            var bottomOverhang:Number = Math.max(CHAR_RECT_BOTTOM_OVERHANG,
                                                 Math.ceil(PREVIEW_FONT_SIZE * 0.2));

            for (var i:int = 0; i < _previewText.length; i++)
            {
                var r:Rectangle = _previewTF.getCharBoundaries(i);
                // 不可见字符（如换行）返回 null，保存 null 供 _updateMask 跳过
                if (r)
                    _charRects.push(new Rectangle(r.x, r.y - CHAR_RECT_TOP_OVERHANG,
                        r.width, r.height + CHAR_RECT_TOP_OVERHANG + bottomOverhang));
                else
                    _charRects.push(null);
            }
        }

        /**
         * 设置预览文本（populate 推送的词典文本）并做上限截断。
         * 设文本 + setTextFormat 生效后立即截断一次，再缓存字符矩形——
         * 打字机 mask 逐字逻辑零改动，省略号作为普通字符正常逐字露出。
         */
        private function _applyPreviewText(text:String):void
        {
            if (!_previewTF) return;
            _previewText = text;
            _previewTF.text = text;
            _previewTF.setTextFormat(_previewTF.defaultTextFormat);
            _truncatePreviewText();
            _cacheCharRects();
        }

        /**
         * 预览文本上限保护（§5.5）——逐行砍至 maxH。
         *
         * maxH 以中文原文行数（PREVIEW_MAX_LINES=2）为基准：2 × 当前字体行高。
         * 中文原文不超 → 零回归；翻译超限才截断（防御玩家手改磁盘词典副本）。
         *
         * 算法: getLineLength(numLines-1) 取最后一行长度循环砍 → 尾部加省略号
         * → 再测，超限再砍（省略号可能使最后一行换行又超限）。循环次数 = 行数。
         * ★ 待实测点: Scaleform 下 getLineLength 对 wordWrap 自动换行行的准确性。
         */
        private function _truncatePreviewText():void
        {
            if (!_previewTF || _previewTF.numLines <= PREVIEW_MAX_LINES)
                return;

            var lineH:Number = _previewTF.textHeight / Math.max(1, _previewTF.numLines);
            var maxH:Number = lineH * PREVIEW_MAX_LINES + 4;

            var guard:int = 0;
            while (_previewTF.textHeight > maxH && guard++ < 50)
            {
                var lastLen:int = _previewTF.getLineLength(_previewTF.numLines - 1);
                var cut:String = _previewTF.text;
                cut = cut.substr(0, Math.max(0, cut.length - lastLen));
                _previewTF.text = cut + PREVIEW_ELLIPSIS;
                _previewTF.setTextFormat(_previewTF.defaultTextFormat);
            }
            _previewText = _previewTF.text;
        }

        /** 根据 _previewCharIndex 逐个字符画 mask 矩形，精确匹配每个字符宽度。 */
        private function _updateMask():void
        {
            var g:flash.display.Graphics = _previewMask.graphics;
            g.clear();

            if (_previewCharIndex <= 0 || !_charRects) return;

            g.beginFill(0x000000);

            var end:int = Math.min(_previewCharIndex, _charRects.length);
            for (var i:int = 0; i < end; i++)
            {
                var r:Rectangle = _charRects[i] as Rectangle;
                if (r)
                    g.drawRect(r.x, r.y, r.width, r.height);
            }
            g.endFill();
        }

        /** 全部字符露出 → 等 1.5s 后重置。 */
        private function _onPreviewRevealComplete(e:TimerEvent):void
        {
            _previewRevealTimer.removeEventListener(TimerEvent.TIMER, _onPreviewRevealTick);
            _previewRevealTimer.removeEventListener(TimerEvent.TIMER_COMPLETE, _onPreviewRevealComplete);
            _previewRevealTimer = null;

            _previewPauseTimer = new Timer(PREVIEW_PAUSE_MS, 1);
            _previewPauseTimer.addEventListener(TimerEvent.TIMER_COMPLETE, _onPreviewPauseEnd);
            _previewPauseTimer.start();
        }

        /** 暂停结束 → 重置并开始下一轮。 */
        private function _onPreviewPauseEnd(e:TimerEvent):void
        {
            _previewPauseTimer.removeEventListener(TimerEvent.TIMER_COMPLETE, _onPreviewPauseEnd);
            _previewPauseTimer = null;
            _startPreview();
        }

        /** speed 0~0.5 秒/字 → 毫秒/字。0 = 立即显示全部（关闭动画）。 */
        private function _speedToDelay(speed:Number):Number
        {
            // speed: 秒/字，0 表示不逐字
            return speed * 1000;
        }

        // ═══════════════════════════════════════════════════════
        // Python → Flash 数据接口
        // ═══════════════════════════════════════════════════════

        /**
         * 接收 Python 端推送的设置页数据。
         *
         * data 字段（全部可选，未传保留默认值）:
         *   nationVoiceGender   — "male"|"female"
         *   notifyPushLevel     — "none"|"count"|"detail"
         *   uiSoundEnabled      — 0|1
         *   switchNotify        — 0|1
         *   playOnSwitch        — 0|1
         *   hotkeyEnabled       — 0|1
         *   hotkey              — "F1"~"F10"
         *   hotkeyOptions       — ["F1","F2",...]
         *   logLevel            — int (DropDown 索引)
         *   logLevelOptions     — ["仅ERROR",...]
         *   showIngameVoices    — 0|1
         *   showInstalledVoices — 0|1
         *   autoVolume          — 0|1
         *   soundRemap          — 0|1
         *   soundBind           — 0|1
         *   subtitleDisplay     — "simple"|"standard"|"none"
         *   textSpeed           — 0~0.5
         *   subtitleUpdate      — 0|1
         *   subtitleAnim        — 0|1
         *   multiSub            — 0|1
         *   colorScheme         — 存储 value（'default'|'follow_pack'|主题名）
         *   colorSchemeOptions  — [{value,label},...]
         *   bgIcon              — 存储 value（'default'|'follow_pack'|pack_id）
         *   bgIconOptions       — [{value,label},...]
         *   titleTextMode       — "followScheme"|"custom"
         *   titleTextColor      — "#RRGGBB" 自定义标题颜色
         *   tooltips            — {key: html, ...}
         *   titleTooltipHtml    — 标题 Tooltip HTML
         *   theme               — 主题色板 Object
         */
        public function populate(data:Object):void
        {
            if (!data)
            {
                L.warn("populate: data 为空");
                return;
            }

            _lastPopulateData = data;
            _applyPopulateData(data);
        }

        private function _applyPopulateData(data:Object):void
        {
            // ── GB1: 系别语音设置 ──
            if (data.nationVoiceGender != null && _nationRadioGroup)
            {
                _nationRadioGroup.setSelectedIndex(
                    String(data.nationVoiceGender) == "female" ? 1 : 0);
            }

            // ── GB2: 通知设置 ──
            if (data.notifyPushLevel != null && _notifyRadioGroup)
            {
                var lvl:String = String(data.notifyPushLevel);
                _notifyRadioGroup.setSelectedIndex(
                    lvl == "count" ? 1 : (lvl == "detail" ? 2 : 0));
            }
            _applyCheck(data, "uiSoundEnabled",  _cbUiSound);
            SoundUtils.setMuted(!_cbUiSound.checked);
            _applyCheck(data, "switchNotify",   _cbSwitchNotify);
            _applyCheck(data, "playOnSwitch",    _cbPlayOnSwitch);

            // ── GB3: 显示设置 ──
            var hotkeyOn:Boolean = _applyCheck(data, "hotkeyEnabled", _cbHotkey);

            if (data.hotkeyOptions is Array && _ddHotkey)
            {
                _ddHotkey.setItems(data.hotkeyOptions as Array);
                _ddHotkey.setSelectedIndex(0);
            }
            if (data.hotkey != null && _ddHotkey)
                _ddHotkey.setSelectedIndex(int(data.hotkey));
            if (_ddHotkey)
                _ddHotkey.setEnabled(hotkeyOn);

            if (data.logLevelOptions is Array && _ddLogLevel)
            {
                _ddLogLevel.setItems(data.logLevelOptions as Array);
                _ddLogLevel.setSelectedIndex(0);
            }
            if (data.logLevel != null && _ddLogLevel)
                _ddLogLevel.setSelectedIndex(int(data.logLevel));

            // 界面语言下拉——选项 [{value,label}]，按存储 value 恢复（setSelectedValue）
            if (data.uiLangOptions is Array && _ddUiLang)
            {
                _ddUiLang.setItems(data.uiLangOptions as Array);
                if (data.uiLang != null)
                {
                    if (!_ddUiLang.setSelectedValue(String(data.uiLang)))
                        _ddUiLang.setSelectedIndex(0);
                }
                else
                {
                    _ddUiLang.setSelectedIndex(0);
                }
            }

            _applyCheck(data, "showIngameVoices",    _cbShowIngame);
            _applyCheck(data, "showInstalledVoices", _cbShowInstalled);

            // ── GB4: 语音通用设置 ──
            _applyCheck(data, "autoVolume", _cbAutoVolume);
            _applyCheck(data, "soundRemap",  _cbSoundRemap);
            _applyCheck(data, "soundBind",   _cbSoundBind);

            // ── GB5: 字幕通用设置 ──
            if (data.subtitleDisplay != null && _subtitleRadioGroup)
            {
                var sd:String = String(data.subtitleDisplay);
                _subtitleRadioGroup.setSelectedIndex(
                    sd == "standard" ? 1 : (sd == "none" ? 2 : 0));
            }
            if (data.textSpeed != null && _stepperTextSpeed)
            {
                _stepperTextSpeed.setValue(Number(data.textSpeed), false);
                _previewDelay = _speedToDelay(Number(data.textSpeed));
            }
            _applyCheck(data, "subtitleUpdate", _cbSubUpdate);
            _applyCheck(data, "subtitleAnim",   _cbSubAnim);
            _applyCheck(data, "multiSub",       _cbMultiSub);

            // ── 打字预览文本（词典推送，含上限截断）──
            // 换文本后重置打字机进度（mask 立即更新为新文本可见区）
            if (data.previewText != null && _previewTF)
            {
                _applyPreviewText(String(data.previewText));
                if (_previewCharIndex > _previewText.length)
                {
                    _previewCharIndex = _previewText.length;
                    _updateMask();
                }
            }

            // ── GB6: UI 主题自定义 ──
            // 选项为 [{value,label}]，选中按存储 value 恢复（setSelectedValue），
            // 找不到（选项列表变化）时回退第一项
            if (data.colorSchemeOptions is Array && _ddColorScheme)
            {
                _ddColorScheme.setItems(data.colorSchemeOptions as Array);
                if (data.colorScheme != null)
                {
                    if (!_ddColorScheme.setSelectedValue(String(data.colorScheme)))
                        _ddColorScheme.setSelectedIndex(0);
                }
                else
                {
                    _ddColorScheme.setSelectedIndex(0);
                }
            }

            if (data.bgIconOptions is Array && _ddBgIcon)
            {
                _ddBgIcon.setItems(data.bgIconOptions as Array);
                if (data.bgIcon != null)
                {
                    if (!_ddBgIcon.setSelectedValue(String(data.bgIcon)))
                        _ddBgIcon.setSelectedIndex(0);
                }
                else
                {
                    _ddBgIcon.setSelectedIndex(0);
                }
            }

            if (data.titleTextMode != null && _titleTextRadioGroup)
            {
                var isCustom:Boolean = String(data.titleTextMode) == "custom";
                _titleTextRadioGroup.setSelectedIndex(isCustom ? 1 : 0);
                if (_customColorInput)
                    _customColorInput.visible = isCustom;
            }
            if (data.titleTextColor != null && _customColorInput)
                _customColorInput.text = String(data.titleTextColor);

            // ── Tooltip ──
            if (data.tooltips)
            {
                _bindTooltip(data.tooltips, "nationVoice",    _gb1 ? _gb1.titleHitArea : null);
                _bindTooltip(data.tooltips, "soundRemap",     _cbSoundRemap);
                _bindTooltip(data.tooltips, "soundBind",     _cbSoundBind);
                _bindTooltip(data.tooltips, "subtitle",       _gb5 ? _gb5.titleHitArea : null);
                _bindTooltip(data.tooltips, "subtitleSimple", _subSimple);
                _bindTooltip(data.tooltips, "subtitleStandard",_subStandard);
                _bindTooltip(data.tooltips, "subtitleUpdate", _cbSubUpdate);
                _bindTooltip(data.tooltips, "subtitleAnim",   _cbSubAnim);
                _bindTooltip(data.tooltips, "multiSub",      _cbMultiSub);
                _bindTooltip(data.tooltips, "textSpeed",     _stepperTextSpeed);
                // GB6: 3 个标签的 Tooltip（标题本身不绑）
                _bindTooltip(data.tooltips, "colorScheme",   _colorSchemeLabelWrapper);
                _bindTooltip(data.tooltips, "bgIcon",         _bgIconLabelWrapper);
                _bindTooltip(data.tooltips, "titleTextColor", _titleTextLabelWrapper);
            }
            if (data.titleTooltipHtml && _titleWrapper)
                Tooltip.attach(_titleWrapper, String(data.titleTooltipHtml));

            // ── 主题 ──
            if (data.theme)
            {
                Theme.apply(data.theme);
                L.info("主题已应用");
            }

            // 预览文本换语言后高度变化 → 重排（GB5 及后续 GB 高度/位置跟随）
            _relayout();

            L.info("数据已应用");
        }

        /** 根据 data key 设置 CheckBox 状态（不派发 onChange）。返回设置后的状态。 */
        private function _applyCheck(data:Object, key:String, cb:CheckBox):Boolean
        {
            if (!cb || data[key] == null) return cb ? cb.checked : false;
            var val:Boolean = int(data[key]) != 0;
            cb.setChecked(val, false);
            return val;
        }

        /** 辅助: 绑定 Tooltip。 */
        private function _bindTooltip(tooltips:Object, key:String, target:Object):void
        {
            if (!tooltips || !target || !(target is Sprite)) return;
            var html:String = tooltips[key] as String;
            if (html && html.length > 0)
                Tooltip.attach(target as Sprite, html);
        }

        // ═══════════════════════════════════════════════════════
        // 生命周期
        // ═══════════════════════════════════════════════════════

        override public function show():void
        {
            super.show();
            if (_scrollPane)
                _scrollPane.refresh();
            _startPreview();
        }

        override public function dispose():void
        {
            L.debug("dispose");
            _initialized = false;

            Theme.unregister(this);
            L10n.unregister(this);

            // 停止打字预览
            _stopPreview();
            _previewTF = null;
            _previewMask = null;

            // Tooltip 解绑（GB 标题 Tooltip 绑定在 titleHitArea 上）
            Tooltip.detach(_titleWrapper);
            if (_gb1 && _gb1.titleHitArea)          Tooltip.detach(_gb1.titleHitArea);
            if (_cbSoundRemap)                      Tooltip.detach(_cbSoundRemap);
            if (_cbSoundBind)                       Tooltip.detach(_cbSoundBind);
            if (_gb5 && _gb5.titleHitArea)          Tooltip.detach(_gb5.titleHitArea);
            if (_subSimple)                         Tooltip.detach(_subSimple);
            if (_subStandard)                       Tooltip.detach(_subStandard);
            if (_cbSubUpdate)                       Tooltip.detach(_cbSubUpdate);
            if (_cbSubAnim)                         Tooltip.detach(_cbSubAnim);
            if (_cbMultiSub)                        Tooltip.detach(_cbMultiSub);
            if (_stepperTextSpeed)                  Tooltip.detach(_stepperTextSpeed);
            // GB6: 标签 wrapper 的 Tooltip（标题本身不绑）
            if (_colorSchemeLabelWrapper)           Tooltip.detach(_colorSchemeLabelWrapper);
            if (_bgIconLabelWrapper)                Tooltip.detach(_bgIconLabelWrapper);
            if (_titleTextLabelWrapper)             Tooltip.detach(_titleTextLabelWrapper);

            // 标题
            if (_titleWrapper && _titleWrapper.parent == this)
                removeChild(_titleWrapper);
            _titleWrapper = null;
            _titleTF = null;

            // 滚动面板（内含 _content + 全部 GB）
            if (_scrollPane)
            {
                _scrollPane.dispose();
                _scrollPane = null;
                _content = null;
                _contentSpacer = null;
            }

            // 引用置空
            _gb1 = null;  _nationRadioGroup = null;  _nationMale = null;  _nationFemale = null;
            _gb2 = null;  _notifyRadioGroup = null;  _notifyNone = null;  _notifyCount = null;
            _notifyDetail = null;
            _cbUiSound = null;  _cbSwitchNotify = null;  _cbPlayOnSwitch = null;
            _gb3 = null;  _cbHotkey = null;  _ddHotkey = null;  _ddLogLevel = null;
            _ddUiLang = null;
            _cbShowIngame = null;  _cbShowInstalled = null;
            _gb4 = null;  _cbAutoVolume = null;  _cbSoundRemap = null;  _cbSoundBind = null;
            _gb5 = null;  _subtitleRadioGroup = null;
            _subSimple = null;  _subStandard = null;  _subNone = null;
            _stepperTextSpeed = null;  _cbSubUpdate = null;  _cbSubAnim = null;  _cbMultiSub = null;
            _gb6 = null;  _ddColorScheme = null;  _ddBgIcon = null;
            _titleTextRadioGroup = null;  _titleFollowScheme = null;  _titleCustom = null;
            if (_customColorInput) { _customColorInput.dispose(); _customColorInput = null; }
            _colorSchemeLabelWrapper = null;  _bgIconLabelWrapper = null;
            _titleTextLabelWrapper = null;

            // 分类标签引用置空（i18n 刷新用）
            _notifyLabelTF = null;  _hotkeyLabelTF = null;  _logLabelTF = null;
            _uiLangLabelTF = null;  _subtitleLabelTF = null;  _speedLabelTF = null;
            _colorSchemeLabelTF = null;  _bgIconLabelTF = null;  _titleTextLabelTF = null;

            _labelFields = null;

            super.dispose();
        }
    }
}
