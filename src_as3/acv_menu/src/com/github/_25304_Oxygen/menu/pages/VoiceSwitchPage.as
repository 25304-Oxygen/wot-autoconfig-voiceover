package com.github._25304_Oxygen.menu.pages
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.i18n.L10n;
    import com.github._25304_Oxygen.menu.components.BaseButton;
    import com.github._25304_Oxygen.menu.components.Stepper;
    import com.github._25304_Oxygen.menu.components.Dropdown;
    import com.github._25304_Oxygen.menu.components.ScrollPane;
    import com.github._25304_Oxygen.menu.components.TabButton;
    import com.github._25304_Oxygen.menu.components.TabGroup;
    import com.github._25304_Oxygen.menu.components.Theme;
    import com.github._25304_Oxygen.menu.components.Tooltip;
    import com.github._25304_Oxygen.menu.components.SoundableSprite;

    /**
     * 语音切换页——语音包选择、切换、音量调节、试听。
     *
     * 布局（自上而下）:
     *   标题 "语音选择"（带 Tooltip）
     *   左列: "音量调节" Stepper；下方 "测试声音" Dropdown + 播放按钮
     *   右列: "更改类型" / "更改语言" Dropdown（标签带 Tooltip，
     *         仅"游戏内置语音包"选项卡下显示）
     *   选项卡（游戏内置语音包 / 已安装的语音包）
     *   语音列表（ScrollPane 可滚动，激活项自动滚到首行）
     *
     * 交互全部通过 onLog 回调 Python 端:
     *   voiceSelect,<voiceID>    — 点击列表项
     *   volumeChange,<0-100>     — 拖动音量滑块
     *   preview,<eventID>        — 点击播放按钮
     *   changeType,<index>       — "更改类型"下拉选中
     *   changeLang,<index>       — "更改语言"下拉选中
     *
     * Python 端处理完后重新 push 数据，触发 populate() 刷新。
     */
    public class VoiceSwitchPage extends BasePage
    {
        private static const L:Object = Log.getLogger("VoiceSwitchPage");

        // ═══════════════════════════════════════════════════════
        // 布局常量
        // ═══════════════════════════════════════════════════════

        /** 左右边距。 */
        private static const MARGIN_H:int = 10;

        /** 底部边距。 */
        private static const MARGIN_BOTTOM:int = 20;

        /** 标题 y（相对于页面，SAFE_TOP 下方 8px）。 */
        private static const TITLE_Y:int = 8;

        /** 标签行1 y（"音量调节" / "更改类型"）。 */
        private static const LABEL_ROW1_Y:int = 32;

        /** 组件行1 y（Stepper / 类型 Dropdown）。 */
        private static const COMP_ROW1_Y:int = 50;

        /** 标签行2 y（"测试声音" / "更改语言"）。 */
        private static const LABEL_ROW2_Y:int = 92;

        /** 组件行2 y（试听 Dropdown + 播放按钮 / 语言 Dropdown）。 */
        private static const COMP_ROW2_Y:int = 110;

        /** 选项卡 y（组件行2下方）。 */
        private static const TAB_Y:int = 152;

        // ── 组件宽度 ──

        /** 步进器宽度 = 下拉+按钮+间距（各占半行）。 */
        private static const STEPPER_W:int = 327;

        /** Dropdown 宽度。 */
        private static const DROPDOWN_W:int = 263;

        /** 播放按钮宽度。 */
        private static const PLAY_BTN_W:int = 78;

        /** 组件间水平间距。 */
        private static const COMP_GAP:int = 6;

        /** Stepper x 起点（左列）。 */
        private static const STEPPER_X:int = MARGIN_H;

        /** 试听 Dropdown x 起点（左列，Stepper 下方；243+6+78=327 与 Stepper 同宽）。 */
        private static const DROPDOWN_X:int = MARGIN_H;

        /** 播放按钮 x 起点（试听 Dropdown 右侧）。 */
        private static const PLAY_BTN_X:int = DROPDOWN_X + DROPDOWN_W + COMP_GAP;

        /** 右列与左列组件的水平间距（原右缘对齐时空隙 90 的一半）。 */
        private static const RIGHT_COL_GAP:int = 45;

        /** 右列 x 起点（"更改类型"/"更改语言"）。 */
        private static const RIGHT_COL_X:int = MARGIN_H + STEPPER_W + RIGHT_COL_GAP;

        /** 播放按钮高度。 */
        private static const PLAY_BTN_H:int = 34;

        // ── 列表 ──

        /** 单个列表项高度（为两行内容准备：名称 + 备注）。 */
        private static const LIST_ITEM_H:int = 44;

        /** 列表项内边距（文字左侧）。 */
        private static const ITEM_PAD_X:int = 12;

        /** 列表项文字大小（最小字号 14）。 */
        private static const ITEM_TEXT_SIZE:int = 16;

        // ═══════════════════════════════════════════════════════
        // 面板尺寸（从 MenuView 传入 / 计算）
        // ═══════════════════════════════════════════════════════

        /** 页面总可用宽度（面板宽 680 - 左右边距各 10 = 660）。 */
        private static const PAGE_W:int = 660;

        /** 页面总可用高度（面板 FULL_H=500 - SAFE_TOP 60 = 440）。 */
        private static const PAGE_H:int = 440;

        // ═══════════════════════════════════════════════════════
        // 数据（Python 推送）
        // ═══════════════════════════════════════════════════════

        /** 游戏内置语音包列表: [{voiceID, nickName, active}, ...] */
        private var _ingameVoices:Array;

        /** 已安装语音包列表: [{voiceID, nickName, active}, ...] */
        private var _outsideVoices:Array;

        /** 当前激活语音包 ID。 */
        private var _currentVoiceId:String = "";

        /** 当前音量 (0~100)。 */
        private var _volume:int = 50;

        /** 试听事件列表: [{text, event}, ...] */
        private var _previewEvents:Array;

        /** 试听事件 ID 平行数组（与 Dropdown 的 labels 对应）。 */
        private var _previewEventIds:Array;

        /** 当前选中的选项卡索引: 0=游戏内置, 1=已安装。 */
        private var _currentTabIndex:int = 0;

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        // 标题
        private var _titleTF:TextField;
        private var _titleWrapper:Sprite;

        // 组件标签
        private var _volumeLabel:TextField;
        private var _previewLabel:TextField;

        // 组件
        private var _stepper:Stepper;
        private var _dropdown:Dropdown;
        private var _playBtn:BaseButton;

        // 右列（仅"游戏内置语音包"选项卡下显示）
        private var _ingameExtras:Sprite;
        private var _typeLabelWrapper:Sprite;
        private var _langLabelWrapper:Sprite;
        private var _typeDropdown:Dropdown;
        private var _langDropdown:Dropdown;

        // 选项卡
        private var _tabGroup:TabGroup;
        private var _tabIngame:TabButton;
        private var _tabOutside:TabButton;

        // 列表
        private var _scrollPane:ScrollPane;
        private var _listContent:Sprite;
        private var _listItems:Array;       // 当前滚动列表中的 item Sprite 数组

        // ═══════════════════════════════════════════════════════
        // 回调
        // ═══════════════════════════════════════════════════════

        /**
         * 用户操作回调 → Python DAAPI onLog。
         * 由 MenuView 在创建页面时设置：
         *   (_pages["voiceSwitch"] as VoiceSwitchPage).onAction = this.onLog;
         *
         * 消息格式:
         *   voiceSelect,<voiceID>     — 点击列表项
         *   volumeChange,<0-100>      — 拖动音量滑块
         *   preview,<eventID>         — 点击播放按钮
         */
        public var onAction:Function;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        /** init() 是否已执行。 */
        private var _initialized:Boolean = false;

        /** 是否已接收过 Python 数据。 */
        private var _populated:Boolean = false;

        /** 缓存最后一次 populate 数据，供 dispose→init 重建。 */
        private var _lastPopulateData:Object = null;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        public function VoiceSwitchPage()
        {
            super("voiceSwitch");
        }

        override public function init():void
        {
            if (_initialized) return;
            _initialized = true;

            _listItems = [];

            _createTitle();
            _createLabels();
            _createStepper();
            _createDropdown();
            _createPlayButton();
            _createIngameExtras();
            _createTabs();
            _createScrollPane();

            // 如果 dispose→init 重建，重新应用缓存数据
            if (_lastPopulateData)
                _applyPopulateData(_lastPopulateData);

            Theme.register(this, _refreshStyle);
            L10n.register(this, _applyLabels);
        }

        // ═══════════════════════════════════════════════════════
        // 标题
        // ═══════════════════════════════════════════════════════

        private function _createTitle():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TitleFont";
            fmt.size = 18;
            fmt.color = Theme.textPrimary;

            _titleTF = new TextField();
            _titleTF.defaultTextFormat = fmt;
            _titleTF.text = L10n.get("voice_switch/title", "语音选择");
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
        // 标签行
        // ═══════════════════════════════════════════════════════

        private function _createLabels():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = Theme.textSecondary;

            _volumeLabel = new TextField();
            _volumeLabel.defaultTextFormat = fmt;
            _volumeLabel.text = L10n.get("voice_switch/volume_label", "音量调节");
            _volumeLabel.selectable = false;
            _volumeLabel.mouseEnabled = false;
            _volumeLabel.autoSize = "left";
            _volumeLabel.x = STEPPER_X;
            _volumeLabel.y = SAFE_TOP + LABEL_ROW1_Y;
            addChild(_volumeLabel);

            _previewLabel = new TextField();
            _previewLabel.defaultTextFormat = fmt;
            _previewLabel.text = L10n.get("voice_switch/preview_label", "测试声音");
            _previewLabel.selectable = false;
            _previewLabel.mouseEnabled = false;
            _previewLabel.autoSize = "left";
            _previewLabel.x = DROPDOWN_X;
            _previewLabel.y = SAFE_TOP + LABEL_ROW2_Y;
            addChild(_previewLabel);
        }

        // ═══════════════════════════════════════════════════════
        // Stepper（音量调节）
        // ═══════════════════════════════════════════════════════

        private function _createStepper():void
        {
            _stepper = new Stepper(STEPPER_W, 0, 100, _volume, 1);
            _stepper.x = STEPPER_X;
            _stepper.y = SAFE_TOP + COMP_ROW1_Y;
            _stepper.onChange = function(value:Number):void {
                _volume = int(value);
                L.info("音量 → " + _volume);
                if (onAction != null) onAction("volumeChange," + _volume);
            };
            addChild(_stepper);
        }

        // ═══════════════════════════════════════════════════════
        // Dropdown（试听事件选择）
        // ═══════════════════════════════════════════════════════

        private function _createDropdown():void
        {
            _previewEventIds = [];
            _dropdown = new Dropdown(DROPDOWN_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _dropdown.x = DROPDOWN_X;
            _dropdown.y = SAFE_TOP + COMP_ROW2_Y + 1;  // 微调与按钮视觉对齐
            _dropdown.onSelect = function(index:int, label:String):void {
                // DEBUG：下拉选择中间态，实际播放由"试听播放"（Python 端）记录
                L.debug("试听事件 #" + index + " → " + label);
                // 仅记录选中项，实际播放由按钮触发
            };
            addChild(_dropdown);
        }

        // ═══════════════════════════════════════════════════════
        // 播放按钮
        // ═══════════════════════════════════════════════════════

        private function _createPlayButton():void
        {
            _playBtn = new BaseButton(PLAY_BTN_W, PLAY_BTN_H,
                L10n.get("voice_switch/play_btn", "播放"), 0, 0);
            _playBtn.x = PLAY_BTN_X;
            _playBtn.y = SAFE_TOP + COMP_ROW2_Y;
            _playBtn.onClick = function():void {
                var idx:int = _dropdown ? int(_dropdown.selectedIndex) : -1;
                if (idx < 0 || idx >= _previewEventIds.length)
                {
                    L.warn("未选中试听事件");
                    return;
                }
                var eventId:String = String(_previewEventIds[idx]);
                // DEBUG：试听播放由 Python 端记录（含事件显示名），此处避免重复
                L.debug("试听播放 → " + eventId);
                if (onAction != null) onAction("preview," + eventId);
            };
            addChild(_playBtn);
        }

        // ═══════════════════════════════════════════════════════
        // 右列：更改类型 / 更改语言（仅"游戏内置语音包"选项卡下显示）
        // ═══════════════════════════════════════════════════════

        private function _createIngameExtras():void
        {
            _ingameExtras = new Sprite();
            _ingameExtras.mouseEnabled = false;  // 容器不拦截点击，事件直达子组件
            _ingameExtras.x = RIGHT_COL_X;
            _ingameExtras.y = SAFE_TOP;
            addChild(_ingameExtras);

            // ── 标签（包一层 Sprite 供 Tooltip 绑定）──
            _typeLabelWrapper = _buildExtraLabel(
                L10n.get("voice_switch/change_type_label", "更改类型"), LABEL_ROW1_Y);
            _langLabelWrapper = _buildExtraLabel(
                L10n.get("voice_switch/change_lang_label", "更改语言"), LABEL_ROW2_Y);

            // ── 下拉列表（宽度与"测试声音"下拉一致）──
            _typeDropdown = new Dropdown(DROPDOWN_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _typeDropdown.x = 0;
            _typeDropdown.y = COMP_ROW1_Y + 1;  // 微调与左列组件视觉对齐
            _typeDropdown.onSelect = function(index:int, label:String):void {
                L.info("更改类型 #" + index + " → " + label);
                if (onAction != null) onAction("changeType," + index);
            };
            _ingameExtras.addChild(_typeDropdown);

            _langDropdown = new Dropdown(DROPDOWN_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _langDropdown.x = 0;
            _langDropdown.y = COMP_ROW2_Y + 1;
            _langDropdown.onSelect = function(index:int, label:String):void {
                L.info("更改语言 #" + index + " → " + label);
                if (onAction != null) onAction("changeLang," + index);
            };
            _ingameExtras.addChild(_langDropdown);

            // 初始可见性与当前选项卡一致（dispose→init 重建时沿用选项卡状态）
            _ingameExtras.visible = (_currentTabIndex == 0);
        }

        /** 创建右列标签——TextField 包 Sprite，供 Tooltip 绑定。
         *  标签左缘与下拉列表左缘对齐。 */
        private function _buildExtraLabel(text:String, rowY:int):Sprite
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = Theme.textSecondary;

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.text = text;
            tf.selectable = false;
            tf.mouseEnabled = false;

            // 用 textWidth 显式收紧宽度——Tooltip 悬停区域贴合文字，
            // 不带右侧空白。读数异常时按字数估算。
            _fitLabelWidth(tf);

            var wrapper:Sprite = new Sprite();
            wrapper.buttonMode = true;
            wrapper.useHandCursor = true;
            wrapper.mouseChildren = false;
            wrapper.addChild(tf);
            wrapper.x = 0;  // 左缘与下拉左缘对齐
            wrapper.y = rowY;
            _ingameExtras.addChild(wrapper);
            return wrapper;
        }

        /** 测量并收紧标签宽度，贴合文字、不截断。
         *  换文（i18n 刷新）后必须重调：宽度若停留在旧文本的测量值，
         *  英文翻译比中文宽时右缘会被 TextField 裁掉。 */
        private function _fitLabelWidth(tf:TextField):void
        {
            if (!tf) return;
            var textW:Number = Math.ceil(tf.textWidth);
            if (isNaN(textW) || textW <= 0 || textW > DROPDOWN_W)
                textW = tf.text.length * 14;
            textW += 4;  // 少量余量，防止末字被裁
            tf.width = textW;
            tf.height = 20;
        }

        /** 右列组件显隐与禁用态由当前语音和选项卡共同决定：
         *   - 内置语音（有 type/lang 选项）→ 始终可见 + 可用
         *   - 第三方语音 + "已安装" tab   → 隐藏
         *   - 第三方语音 + "游戏内置" tab → 可见但禁用 + 占位文案
         */
        private function _updateExtrasVisible():void
        {
            if (!_ingameExtras || !_typeDropdown || !_langDropdown) return;

            // 判断当前语音是否有 type/lang 选项（内置语音才有）
            var hasOptions:Boolean = _lastPopulateData
                && _lastPopulateData.typeItems
                && _lastPopulateData.typeItems is Array
                && (_lastPopulateData.typeItems as Array).length > 0;

            if (hasOptions)
            {
                // ── 内置语音：始终显示启用态 + 实选项 ──
                _ingameExtras.visible = true;
                _typeDropdown.setEnabled(true);
                _langDropdown.setEnabled(true);

                _typeDropdown.setItems(_lastPopulateData.typeItems as Array);
                _typeDropdown.setSelectedIndex(
                    _lastPopulateData.typeIndex != null ? int(_lastPopulateData.typeIndex) : 0);
                _langDropdown.setItems(_lastPopulateData.langItems as Array);
                _langDropdown.setSelectedIndex(
                    _lastPopulateData.langIndex != null ? int(_lastPopulateData.langIndex) : 0);
            }
            else if (_currentTabIndex == 1)
            {
                // ── 第三方语音 + "已安装" tab：完全隐藏 ──
                _ingameExtras.visible = false;
            }
            else
            {
                // ── 第三方语音 + "游戏内置" tab：可见但禁用 + 占位 ──
                _ingameExtras.visible = true;
                _typeDropdown.setEnabled(false);
                _langDropdown.setEnabled(false);
                _typeDropdown.setItems([L10n.get("voice_switch/unsupported", "所选语音包不支持")]);
                _langDropdown.setItems([L10n.get("voice_switch/unsupported", "所选语音包不支持")]);
            }
        }

        // ═══════════════════════════════════════════════════════
        // 选项卡
        // ═══════════════════════════════════════════════════════

        private function _createTabs():void
        {
            _tabGroup = new TabGroup();
            _tabGroup.x = MARGIN_H;
            _tabGroup.y = SAFE_TOP + TAB_Y;

            _tabIngame  = new TabButton("ingame",  L10n.get("voice_switch/tab_ingame", "游戏内置语音包"));
            _tabOutside = new TabButton("outside", L10n.get("voice_switch/tab_outside", "已安装的语音包"));
            _tabGroup.addTab(_tabIngame);
            _tabGroup.addTab(_tabOutside);

            _tabGroup.onTabChange = function(tabId:String):void {
                _currentTabIndex = (tabId == "outside") ? 1 : 0;
                L.info("选项卡切换 → " + tabId);
                _updateExtrasVisible();
                _renderList();
            };

            addChild(_tabGroup);
        }

        // ═══════════════════════════════════════════════════════
        // 滚动列表
        // ═══════════════════════════════════════════════════════

        private function _createScrollPane():void
        {
            var scrollY:int = SAFE_TOP + TAB_Y + TabButton.HEIGHT + 1;
            var scrollH:int = SAFE_TOP + PAGE_H - MARGIN_BOTTOM - scrollY;

            _scrollPane = new ScrollPane(PAGE_W, scrollH);
            _scrollPane.x = MARGIN_H;
            _scrollPane.y = scrollY;
            addChild(_scrollPane);

            // 空内容占位
            _listContent = new Sprite();
            _scrollPane.setContent(_listContent);
        }

        // ═══════════════════════════════════════════════════════
        // 列表渲染
        // ═══════════════════════════════════════════════════════

        /**
         * 根据当前选项卡 + 数据重建滚动列表。
         *
         * 滚动列表显示当前选项卡的全部语音（含激活项，方便用户看到它在列表中的位置）。
         */
        private function _renderList():void
        {
            try
            {
                _renderListImpl();
            }
            catch (e:Error)
            {
                L.error("_renderList 异常: " + e.message
                    + "\n" + e.getStackTrace());
            }
        }

        private function _renderListImpl():void
        {
            if (!_ingameVoices && !_outsideVoices) return;

            // ── 确定当前列表 ──
            var currentList:Array = (_currentTabIndex == 0) ? _ingameVoices : _outsideVoices;
            if (!currentList) currentList = [];

            // ── 清空旧列表 ──
            _clearListItems();

            // ── 重建列表内容 ──
            _listContent = new Sprite();
            _listContent.mouseEnabled = false;  // 容器不拦截点击，事件直达 item
            var itemY:Number = 0;

            for (var i:int = 0; i < currentList.length; i++)
            {
                var vo:Object = currentList[i];
                var voiceID:String = String(vo.voiceID || "");
                var nickName:String = String(vo.nickName || voiceID);
                var isActive:Boolean = (voiceID == _currentVoiceId);

                var item:Sprite = _createListItem(voiceID, nickName, isActive);
                item.y = itemY;
                _listContent.addChild(item);
                _listItems.push(item);

                itemY += LIST_ITEM_H;
            }

            // 空列表占位
            if (currentList.length == 0)
            {
                var emptyItem:Sprite = _createListItem("",
                    L10n.get("voice_switch/no_voice_packs", "（无可用语音包）"), false);
                emptyItem.mouseEnabled = false;
                emptyItem.buttonMode = false;
                _listContent.addChild(emptyItem);
                _listItems.push(emptyItem);
            }

            _scrollPane.setContent(_listContent);

            // ── 初始滚动：激活项滚到可视区第一行 ──
            // scrollPosition setter 内部钳制到最大滚动值，激活项靠近列表
            // 底部时停在最后一屏（不再继续下滑，激活项不一定在第一行）。
            var activeIdx:int = -1;
            for (i = 0; i < currentList.length; i++)
            {
                if (String(currentList[i].voiceID || "") == _currentVoiceId)
                {
                    activeIdx = i;
                    break;
                }
            }
            if (activeIdx > 0)
                _scrollPane.scrollPosition = activeIdx * LIST_ITEM_H;
        }

        /** 创建单个列表项 Sprite（Shape 背景 + TextField）。
         *
         *  选中项仅更换背景色（Theme.accent），不用竖线或文字换色。 */
        private function _createListItem(voiceID:String, nickName:String,
                                         isActive:Boolean):Sprite
        {
            var item:SoundableSprite = new SoundableSprite("itemRenderer");
            item.name = voiceID;  // 供点击处理取用

            // 背景 —— bg 始终是 index 0（getChildAt(0) 获取）
            var bg:Shape = new Shape();
            _drawListItemBg(bg, isActive ? Theme.accent : Theme.surface1);
            item.addChild(bg);

            // 文字（颜色不区分选中/非选中，始终用 textPrimary）
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = ITEM_TEXT_SIZE;
            fmt.color = Theme.textPrimary;

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.text = nickName;
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.autoSize = "left";
            tf.x = ITEM_PAD_X;
            tf.y = int((LIST_ITEM_H - ITEM_TEXT_SIZE) / 2) - 1;
            item.addChild(tf);

            // 交互
            if (voiceID.length > 0)
            {
                item.buttonMode = true;
                item.addEventListener(MouseEvent.CLICK,       _onItemClick);
                item.addEventListener(MouseEvent.MOUSE_OVER,  _onItemOver);
                item.addEventListener(MouseEvent.MOUSE_OUT,   _onItemOut);
            }

            return item;
        }

        /** 绘制列表项背景（无描边/分隔线）。 */
        private function _drawListItemBg(bg:Shape, fillColor:uint):void
        {
            bg.graphics.clear();
            bg.graphics.beginFill(fillColor, 1.0);
            bg.graphics.drawRect(0, 0, PAGE_W, LIST_ITEM_H);
            bg.graphics.endFill();
        }

        /** 清空当前列表项（移除监听、注销音效、清空数组）。 */
        private function _clearListItems():void
        {
            for (var i:int = 0; i < _listItems.length; i++)
            {
                var item:Sprite = _listItems[i] as Sprite;
                if (item)
                {
                    item.removeEventListener(MouseEvent.CLICK,       _onItemClick);
                    item.removeEventListener(MouseEvent.MOUSE_OVER,  _onItemOver);
                    item.removeEventListener(MouseEvent.MOUSE_OUT,   _onItemOut);
                    // 注销音效监听
                    if (item is SoundableSprite)
                        SoundableSprite(item).disposeItem();
                }
            }
            _listItems = [];
        }

        // ═══════════════════════════════════════════════════════
        // 列表项交互事件
        // ═══════════════════════════════════════════════════════

        private function _onItemClick(event:MouseEvent):void
        {
            var item:Sprite = event.currentTarget as Sprite;
            if (!item) return;

            var voiceID:String = item.name;
            if (!voiceID || voiceID.length == 0) return;

            // 始终转发给 Python——即使是已激活语音也允许重新播放确认音。
            // Python 端 switch_voice 对同语音调用跳过 setMode 仅播放声音。
            L.info("选择语音 → " + voiceID);
            if (onAction != null) onAction("voiceSelect," + voiceID);
        }

        private function _onItemOver(event:MouseEvent):void
        {
            var item:Sprite = event.currentTarget as Sprite;
            if (!item) return;

            // 选中项不响应 hover 变色
            if (item.name == _currentVoiceId) return;

            var bg:Shape = item.getChildAt(0) as Shape;
            if (bg) _drawListItemBg(bg, Theme.surface2);
        }

        private function _onItemOut(event:MouseEvent):void
        {
            var item:Sprite = event.currentTarget as Sprite;
            if (!item) return;

            var bg:Shape = item.getChildAt(0) as Shape;
            if (!bg) return;

            // 选中项恢复 accent 背景，非选中项恢复 surface1
            var isActive:Boolean = (item.name == _currentVoiceId);
            _drawListItemBg(bg, isActive ? Theme.accent : Theme.surface1);
        }

        // ═══════════════════════════════════════════════════════
        // Python → Flash 数据接口
        // ═══════════════════════════════════════════════════════

        /**
         * 接收 Python 端推送的语音切换页数据。
         *
         * data 对象字段:
         *   - ingameVoices:    Array  游戏内置语音包 [{voiceID, nickName, active}, ...]
         *   - outsideVoices:   Array  已安装语音包
         *   - currentVoiceId:  String 当前激活语音包 ID
         *   - volume:          int    当前音量 (0~100)
         *   - previewEvents:   Array  试听事件 [{text, event}, ...]
         *   - typeItems:       Array  "更改类型"选项文本
         *   - typeIndex:       int    "更改类型"当前选中索引
         *   - langItems:       Array  "更改语言"选项文本
         *   - langIndex:       int    "更改语言"当前选中索引
         *   - tooltipHtml:     String 标题 Tooltip 富文本
         *   - tooltips:        Object {changeType, changeLang} 右列标签 Tooltip
         */
        public function populate(data:Object):void
        {
            if (!data)
            {
                L.warn("populate: data 为空");
                return;
            }

            // 始终缓存，供 dispose→init 重建后重新应用
            _lastPopulateData = data;
            _applyPopulateData(data);
        }

        /** 将 populate 数据实际应用到 UI。 */
        private function _applyPopulateData(data:Object):void
        {
            // ── 语音包列表 ──
            if (data.ingameVoices && data.ingameVoices is Array)
                _ingameVoices = data.ingameVoices as Array;

            if (data.outsideVoices && data.outsideVoices is Array)
                _outsideVoices = data.outsideVoices as Array;

            // ── 当前激活语音 ──
            if (data.currentVoiceId != null)
                _currentVoiceId = String(data.currentVoiceId);

            // ── 音量 ──
            if (data.volume != null)
            {
                _volume = int(data.volume);
                if (_stepper)
                    _stepper.setValue(_volume);
            }

            // ── 试听事件 ──
            if (data.previewEvents && data.previewEvents is Array)
            {
                _previewEvents = data.previewEvents as Array;
                _previewEventIds = [];
                var eventLabels:Array = [];
                for (var i:int = 0; i < _previewEvents.length; i++)
                {
                    // 字段约定与 playEvent.json 一致: text=显示名, event=Wwise 事件名
                    var evt:Object = _previewEvents[i];
                    var label:String = String(evt.text || evt.event
                        || L10n.get("voice_switch/event_prefix", "事件 ") + i);
                    var eid:String = String(evt.event || "");
                    eventLabels.push(label);
                    _previewEventIds.push(eid);
                }
                if (_dropdown)
                {
                    // setItems 内部会重置 selectedIndex=-1，先记住旧索引
                    var oldIdx:int = _dropdown.selectedIndex;
                    _dropdown.setItems(eventLabels);
                    // 旧索引仍有效则保留；否则回退到第一项
                    if (oldIdx >= 0 && oldIdx < eventLabels.length)
                        _dropdown.setSelectedIndex(oldIdx);
                    else
                        _dropdown.setSelectedIndex(0);
                }
            }

            // ── 更改类型 / 更改语言（右列）──
            if (data.typeItems && data.typeItems is Array && _typeDropdown)
            {
                _typeDropdown.setItems(data.typeItems as Array);
                _typeDropdown.setSelectedIndex(
                    data.typeIndex != null ? int(data.typeIndex) : 0);
            }
            if (data.langItems && data.langItems is Array && _langDropdown)
            {
                _langDropdown.setItems(data.langItems as Array);
                _langDropdown.setSelectedIndex(
                    data.langIndex != null ? int(data.langIndex) : 0);
            }

            // ── Tooltip ──
            if (data.tooltipHtml && _titleWrapper)
            {
                Tooltip.attach(_titleWrapper, String(data.tooltipHtml));
            }
            if (data.tooltips)
            {
                if (data.tooltips.changeType && _typeLabelWrapper)
                    Tooltip.attach(_typeLabelWrapper,
                        String(data.tooltips.changeType));
                if (data.tooltips.changeLang && _langLabelWrapper)
                    Tooltip.attach(_langLabelWrapper,
                        String(data.tooltips.changeLang));
            }

            // ── 恢复选项卡状态（根据 source 字段）──
            if (data.source != null && _tabGroup)
                _tabGroup.selectTabById(String(data.source));
            // selectTabById 内部已通过 onTabChange 调用 _updateExtrasVisible + _renderList；
            // 但当 data.source 与当前选中相同时不会触发回调，下面显式调用保证正确刷新：
            _updateExtrasVisible();

            // ── 重建列表 ──
            _renderList();

            _populated = true;
            L.info("数据已应用 "
                + (_ingameVoices ? _ingameVoices.length : 0) + "+"
                + (_outsideVoices ? _outsideVoices.length : 0) + " 语音包");
        }

        // ═══════════════════════════════════════════════════════
        // 主题刷新
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            if (_titleTF) _titleTF.textColor = Theme.textPrimary;
            if (_volumeLabel) _volumeLabel.textColor = Theme.textSecondary;
            if (_previewLabel) _previewLabel.textColor = Theme.textSecondary;

            // 右列标签（"更改类型" / "更改语言"）
            if (_typeLabelWrapper && _typeLabelWrapper.numChildren > 0)
            {
                var typeTF:TextField = _typeLabelWrapper.getChildAt(0) as TextField;
                if (typeTF) typeTF.textColor = Theme.textSecondary;
            }
            if (_langLabelWrapper && _langLabelWrapper.numChildren > 0)
            {
                var langTF:TextField = _langLabelWrapper.getChildAt(0) as TextField;
                if (langTF) langTF.textColor = Theme.textSecondary;
            }

            // 列表项——重绘背景 + 更新文字颜色
            // （之前只更新文字颜色，背景要到 hover 才刷新，表现为"慢半拍"）
            if (_listItems)
            {
                for (var i:int = 0; i < _listItems.length; i++)
                {
                    var item:Sprite = _listItems[i] as Sprite;
                    if (item && item.numChildren > 0)
                    {
                        var bg:Shape = item.getChildAt(0) as Shape;
                        if (bg)
                        {
                            var isActive:Boolean = (item.name == _currentVoiceId);
                            _drawListItemBg(bg, isActive ? Theme.accent : Theme.surface1);
                        }
                        if (item.numChildren > 1)
                        {
                            var tf:TextField = item.getChildAt(1) as TextField;
                            if (tf) tf.textColor = Theme.textPrimary;
                        }
                    }
                }
            }
        }

        override public function dispose():void
        {
            Theme.unregister(this);
            L10n.unregister(this);
            super.dispose();
        }

        // ═══════════════════════════════════════════════════════
        // i18n 刷新（L10n 注册回调）
        // ═══════════════════════════════════════════════════════

        /** 全部用户可见文本按词典刷新（下拉选项由 populate 管理）。 */
        private function _applyLabels():void
        {
            if (_titleTF) _titleTF.text = L10n.get("voice_switch/title", "语音选择");
            if (_volumeLabel) _volumeLabel.text = L10n.get("voice_switch/volume_label", "音量调节");
            if (_previewLabel) _previewLabel.text = L10n.get("voice_switch/preview_label", "测试声音");
            if (_playBtn) _playBtn.setLabel(L10n.get("voice_switch/play_btn", "播放"));
            if (_tabIngame) _tabIngame.setLabel(L10n.get("voice_switch/tab_ingame", "游戏内置语音包"));
            if (_tabOutside) _tabOutside.setLabel(L10n.get("voice_switch/tab_outside", "已安装的语音包"));

            // 右列标签（wrapper 内 TextField）——换文后必须重测宽度，
            // 否则宽度停留在中文测量值，英文翻译更宽时右缘被裁。
            if (_typeLabelWrapper && _typeLabelWrapper.numChildren > 0)
            {
                var typeTF:TextField = _typeLabelWrapper.getChildAt(0) as TextField;
                if (typeTF)
                {
                    typeTF.text = L10n.get("voice_switch/change_type_label", "更改类型");
                    _fitLabelWidth(typeTF);
                }
            }
            if (_langLabelWrapper && _langLabelWrapper.numChildren > 0)
            {
                var langTF:TextField = _langLabelWrapper.getChildAt(0) as TextField;
                if (langTF)
                {
                    langTF.text = L10n.get("voice_switch/change_lang_label", "更改语言");
                    _fitLabelWidth(langTF);
                }
            }

            // 占位文案（第三方语音 + 游戏内置 tab 的禁用占位）
            _updateExtrasVisible();
        }

    }
}
