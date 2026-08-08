package com.github._25304_Oxygen.menu.pages
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.i18n.L10n;
    import com.github._25304_Oxygen.menu.components.GroupBox;
    import com.github._25304_Oxygen.menu.components.Dropdown;
    import com.github._25304_Oxygen.menu.components.NumericStepper;
    import com.github._25304_Oxygen.menu.components.TextInput;
    import com.github._25304_Oxygen.menu.components.Theme;
    import com.github._25304_Oxygen.menu.components.Tooltip;

    /**
     * 个性设置页——被点亮喊话与快捷消息替换。
     *
     * 布局:
     *   标题 "个性设置" → 空一行 → 居中声明 → 空一行 → GroupBox
     *     ├ 被点亮时喊话 [?]
     *     ├ [输入框________________]  附加条件：存活队友≤ [▲3▼]
     *     ├ 替换已有喊话
     *     ├ [▼ 下拉选择________]  [替换文本输入________]
     *     ├ 预览： 攻击目标，装填还需15秒
     *     └ (GroupBox 外) 清空输入框可还原为游戏原始消息
     *
     * 用户操作 → onAction 回调:
     *   spottedMsg,<text>
     *   spottedAliveLe,<value>
     *   replaceSelect,<index>
     *   replaceText,<text>
     */
    public class PersonalSettingsPage extends BasePage
    {
        private static const L:Object = Log.getLogger("PersonalSettingsPage");

        // ═══════════════════════════════════════════════════════
        // 布局常量
        // ═══════════════════════════════════════════════════════

        /** 标题左边距（与其他页面统一）。 */
        private static const TITLE_X:int = 10;
        private static const TITLE_Y:int = 8;

        /** GroupBox 左右边距。 */
        private static const MARGIN:int = 20;
        private static const PAGE_W:int = 660;
        private static const PAGE_H:int = 440;

        /** GroupBox 宽度 = PAGE_W - MARGIN*2。 */
        private static const GB_W:int = 620;
        private static const GB_H:int = 284;

        /** GroupBox 内容区内边距（GroupBox 自带 PAD_SIDE=14, PAD_TOP_DRAW=22, PAD_BOTTOM=14）。 */
        private static const CONTENT_W:int = GB_W - 28;  // = 592

        /** 列布局（Dropdown + Input 行）。 */
        private static const COL_W:Number = 280;
        private static const COL_GAP:Number = 20;
        private static const COL_L:Number = 0;
        private static const COL_R:Number = COL_W + COL_GAP;  // = 300

        /** 行高。 */
        private static const LABEL_ROW_H:int = 24;
        private static const INPUT_H:int = 32;
        private static const ROW_GAP:int = 10;
        private static const SECTION_GAP:int = 8;

        /** 最小字号。 */
        private static const MIN_FONT_SIZE:int = 14;

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        // 标题
        private var _titleTF:TextField;

        // 声明文本
        private var _declarationTF:TextField;

        // GroupBox
        private var _gb:GroupBox;

        // ── 被点亮喊话 ──
        private var _spottedLabel:TextField;
        /** "被点亮时喊话" 标签的 Tooltip 目标（wrapper 包裹可交互）。 */
        private var _spottedLabelWrapper:Sprite;
        private var _spottedInput:TextInput;
        private var _spottedPreviewLabel:TextField;
        private var _spottedPreviewTF:TextField;

        // ── 存活队友数 ──
        private var _aliveTitleLabel:TextField;
        private var _aliveLabel:TextField;
        private var _aliveStepper:NumericStepper;
        /** 附加条件第二行 y（切语言重排步进器用）。 */
        private var _aliveLine2Y:Number;

        // ── 分隔线 ──
        private var _separator:Shape;

        // ── 替换已有喊话 ──
        private var _replaceHeader:TextField;

        // ── 下拉 + 输入 ──
        private var _replaceDropdown:Dropdown;
        private var _replaceInput:TextInput;

        // ── 预览 ──
        private var _previewLabel:TextField;
        private var _previewTF:TextField;

        // ── 提示（GroupBox 外）──
        private var _hintTF:TextField;

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

        public function PersonalSettingsPage()
        {
            super("personalSettings");
        }

        override public function init():void
        {
            if (_initialized) return;
            _initialized = true;

            _createTitle();
            _createDeclaration();
            _createGroupBox();
            _createHint();

            if (_lastPopulateData)
                _applyPopulateData(_lastPopulateData);

            L10n.register(this, _applyLabels);
        }

        // ═══════════════════════════════════════════════════════
        // 标题 "个性设置"（与其他页面一致的固定位置）
        // ═══════════════════════════════════════════════════════

        private function _createTitle():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TitleFont";
            fmt.size = 18;
            fmt.color = Theme.textPrimary;

            _titleTF = new TextField();
            _titleTF.defaultTextFormat = fmt;
            _titleTF.text = L10n.get("personal/title", "个性设置");
            _titleTF.selectable = false;
            _titleTF.mouseEnabled = false;
            _titleTF.autoSize = "left";
            _titleTF.x = TITLE_X;
            _titleTF.y = SAFE_TOP + TITLE_Y;
            addChild(_titleTF);
        }

        // ═══════════════════════════════════════════════════════
        // 左对齐声明文本
        // ═══════════════════════════════════════════════════════

        private function _createDeclaration():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = MIN_FONT_SIZE;
            fmt.color = Theme.textPrimary;
            fmt.bold = true;
            fmt.align = "left";

            // 标题底部 = SAFE_TOP + TITLE_Y + 22（标题行高） + 24（空行）
            var declY:int = SAFE_TOP + TITLE_Y + 22 + 24;

            _declarationTF = new TextField();
            _declarationTF.defaultTextFormat = fmt;
            _declarationTF.wordWrap = true;    // 按宽度自动折行
            _declarationTF.multiline = true;
            _declarationTF.width = GB_W;       // 与分组框同宽
            _declarationTF.autoSize = "left";  // wordWrap 下宽度不变，高度随内容增长
            _declarationTF.text = L10n.get("personal/declaration",
                "前排提醒：点亮后发的是公屏喊话，所有人都能看到，也会被和谐。下面那个替换的客户端渲染文本，只有你可见且只替换自己的消息，不会被和谐。");
            _declarationTF.selectable = false;
            _declarationTF.mouseEnabled = false;
            _declarationTF.x = MARGIN;
            _declarationTF.y = declY;
            addChild(_declarationTF);
        }

        // ═══════════════════════════════════════════════════════
        // GroupBox 及内容
        // ═══════════════════════════════════════════════════════

        private function _createGroupBox():void
        {
            // 声明文本底部空一行（用实际高度，声明折行后自动下移）
            var gbY:int = int(_declarationTF.y + _declarationTF.height) + 24;

            _gb = new GroupBox(GB_W, GB_H, L10n.get("personal/chat_msg_title", "局内喊话消息自定义"), 4);
            _gb.labelBgVisible = false;  // 去掉标签背景色
            _gb.x = MARGIN;
            _gb.y = gbY;
            addChild(_gb);

            var ly:int = 2;  // GB_INNER_PAD

            // ── Row 1: "被点亮时喊话" 标签（次要色，Tooltip 绑定目标）──
            // Tooltip 需要可交互对象，TextField mouseEnabled=false 收不到鼠标事件，
            // 用 Sprite wrapper 包裹标签作为 Tooltip target（同 SettingsPage 做法）。
            _spottedLabelWrapper = new Sprite();
            _spottedLabelWrapper.x = COL_L;
            _spottedLabelWrapper.y = ly;
            _spottedLabelWrapper.buttonMode = true;
            _spottedLabelWrapper.useHandCursor = true;
            _spottedLabel = _addLabel(_spottedLabelWrapper,
                L10n.get("personal/spotted_label", "被点亮时喊话"), 0, 0);
            _spottedLabel.textColor = Theme.textSecondary;
            _gb.content.addChild(_spottedLabelWrapper);
            ly += LABEL_ROW_H;

            // ── Row 2: 输入框（左，与下拉列表同宽） + 被点亮喊话预览（右）──
            _spottedInput = new TextInput(COL_W, INPUT_H, "");
            _spottedInput.x = COL_L;
            _spottedInput.y = ly;
            _spottedInput.debounceDelay = 300;
            _spottedInput.onChange = function(text:String):void {
                if (onAction != null) onAction("spottedMsg," + text);
            };
            _gb.content.addChild(_spottedInput);

            // "预览：" 标签 + 预览文本（与底部替换预览行布局一致）
            var spFmt:TextFormat = new TextFormat();
            spFmt.font = "$TextFont";
            spFmt.size = MIN_FONT_SIZE;
            spFmt.color = Theme.textPrimary;

            var spRowY:int = ly + int((INPUT_H - 20) / 2);  // 垂直居中于输入框

            _spottedPreviewLabel = new TextField();
            _spottedPreviewLabel.defaultTextFormat = spFmt;
            _spottedPreviewLabel.text = L10n.get("personal/preview_label", "预览：");
            _spottedPreviewLabel.selectable = false;
            _spottedPreviewLabel.mouseEnabled = false;
            _spottedPreviewLabel.autoSize = "left";
            _spottedPreviewLabel.textColor = Theme.textSecondary;  // 次要色
            _spottedPreviewLabel.x = COL_R;
            _spottedPreviewLabel.y = spRowY;
            _gb.content.addChild(_spottedPreviewLabel);

            var spTextX:int = COL_R + _spottedPreviewLabel.width + 2;  // 紧跟标签，间距 2px
            _spottedPreviewTF = new TextField();
            _spottedPreviewTF.defaultTextFormat = spFmt;
            _spottedPreviewTF.selectable = false;
            _spottedPreviewTF.mouseEnabled = false;
            _spottedPreviewTF.wordWrap = true;
            _spottedPreviewTF.multiline = true;
            _spottedPreviewTF.width = CONTENT_W - spTextX;
            _spottedPreviewTF.height = INPUT_H;
            _spottedPreviewTF.x = spTextX;
            _spottedPreviewTF.y = spRowY;
            _spottedPreviewTF.text = "";
            _gb.content.addChild(_spottedPreviewTF);
            ly += INPUT_H + ROW_GAP;

            // ── Row 3: 附加条件（两个标签上下排列） + 紧凑步进器 ──
            // 第一行"附加条件："用次要色弱化，第二行保持主色
            _aliveTitleLabel = _addLabel(_gb.content,
                L10n.get("personal/alive_label", "附加条件："), COL_L, ly);
            _aliveTitleLabel.textColor = Theme.textSecondary;

            // 第二行位置补偿：两个 TextField 叠放比单个多行框多出
            // 上下边衬（各2px），扣 4px 保持原来的行距
            _aliveLine2Y = ly + int(_aliveTitleLabel.height) - 4;
            _aliveLabel = _addLabel(_gb.content,
                L10n.get("personal/alive_desc", "当场上存活队友数低于或等于"), COL_L, _aliveLine2Y);

            // 紧凑 NumericStepper（宽56 = 24箭头 + 32数字区）
            _aliveStepper = new NumericStepper(0, 15, 5, 1, 56, 28);
            _aliveStepper.onChange = function(value:Number):void {
                if (onAction != null) onAction("spottedAliveLe," + value);
            };
            _gb.content.addChild(_aliveStepper);
            _layoutAliveRow();   // 步进器跟随第二行文字末尾（英文长文本时右移）
            ly = _aliveLine2Y + int(_aliveLabel.height) + ROW_GAP;

            // ── 分隔线（不触碰分组框左右边框，content 区已内缩 14px）──
            _separator = new Shape();
            _separator.x = COL_L;
            _separator.y = ly;
            _gb.content.addChild(_separator);
            _redrawSeparator();
            ly += SECTION_GAP;

            // ── Row 4: "替换已有喊话" 普通标签（次要色）──
            _replaceHeader = _addLabel(_gb.content,
                L10n.get("personal/replace_label", "替换已有喊话"), COL_L, ly);
            _replaceHeader.textColor = Theme.textSecondary;
            ly += LABEL_ROW_H + SECTION_GAP;

            // ── Row 4: 下拉列表 + 替换输入框 ──
            _replaceDropdown = new Dropdown(COL_W, [L10n.get("settings/dropdown_loading", "加载中...")]);
            _replaceDropdown.x = COL_L;
            _replaceDropdown.y = ly;
            _replaceDropdown.onSelect = function(index:int, label:String):void {
                if (onAction != null) onAction("replaceSelect," + index);
            };
            _gb.content.addChild(_replaceDropdown);

            _replaceInput = new TextInput(COL_W, INPUT_H, "");
            _replaceInput.x = COL_R;
            _replaceInput.y = ly;
            _replaceInput.debounceDelay = 300;
            _replaceInput.onChange = function(text:String):void {
                if (onAction != null) onAction("replaceText," + text);
            };
            _gb.content.addChild(_replaceInput);
            ly += INPUT_H + ROW_GAP;

            // ── Row 5: 预览标签 + 预览文本（同行，白色字体）──
            var previewFmt:TextFormat = new TextFormat();
            previewFmt.font = "$TextFont";
            previewFmt.size = MIN_FONT_SIZE;
            previewFmt.color = Theme.textPrimary;  // 白色字体

            _previewLabel = new TextField();
            _previewLabel.defaultTextFormat = previewFmt;
            _previewLabel.text = L10n.get("personal/preview_label", "预览：");
            _previewLabel.selectable = false;
            _previewLabel.mouseEnabled = false;
            _previewLabel.autoSize = "left";
            _previewLabel.textColor = Theme.textSecondary;  // 次要色
            _previewLabel.x = COL_L;
            _previewLabel.y = ly;
            _gb.content.addChild(_previewLabel);

            var previewTextX:int = COL_L + _previewLabel.width + 2;  // 紧跟标签，间距 2px
            _previewTF = new TextField();
            _previewTF.defaultTextFormat = previewFmt;
            _previewTF.selectable = false;
            _previewTF.mouseEnabled = false;
            _previewTF.wordWrap = true;
            _previewTF.multiline = true;
            _previewTF.width = CONTENT_W - _previewLabel.width - 2;
            _previewTF.height = 32;
            _previewTF.x = previewTextX;
            _previewTF.y = ly;
            _previewTF.text = "";
            _gb.content.addChild(_previewTF);

            // ── 主题 ──
            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 提示文字（GroupBox 外，下方空一行，左对齐 GB 边界）
        // ═══════════════════════════════════════════════════════

        private function _createHint():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = MIN_FONT_SIZE;   // 14px，不再使用 12px
            fmt.color = Theme.textSecondary;  // 次要色

            // GroupBox 底部
            var hintY:int = _gb.y + GB_H;

            _hintTF = new TextField();
            _hintTF.defaultTextFormat = fmt;
            _hintTF.text = L10n.get("personal/hint", "清空输入框可还原为游戏原始消息");
            _hintTF.selectable = false;
            _hintTF.mouseEnabled = false;
            _hintTF.autoSize = "left";
            _hintTF.x = MARGIN;  // 左对齐 GroupBox 边界
            _hintTF.y = hintY;
            addChild(_hintTF);
        }

        // ═══════════════════════════════════════════════════════
        // 辅助：创建标签 / 附加条件行重排
        // ═══════════════════════════════════════════════════════

        /**
         * 附加条件行重排——步进器紧跟第二行文字末尾（右侧无组件，允许向右延伸）。
         * 切语言后文字变长时必须重调 x，否则步进器压住文字。
         */
        private function _layoutAliveRow():void
        {
            if (!_aliveLabel || !_aliveStepper) return;
            _aliveStepper.x = COL_L + _aliveLabel.width + 4;
            // 步进器底边对齐第二行文字底部（TextField 自带 2px 下边衬需扣除）
            _aliveStepper.y = _aliveLine2Y + int(_aliveLabel.height) - 2 - 28;
        }

        /**
         * 预览行重排——两处预览标签换文后，重定位各自预览文本框（x 紧跟标签
         * 右缘 + 2px，宽度随 x 联动）。英文 "Preview: " 比中文"预览："宽，
         * 不重排则文本框压在标签上，看起来冒号后没有空格直接接预览文本。
         */
        private function _relayoutPreviewRows():void
        {
            if (_spottedPreviewLabel && _spottedPreviewTF)
            {
                _spottedPreviewTF.x = COL_R + _spottedPreviewLabel.width + 2;
                _spottedPreviewTF.width = CONTENT_W - _spottedPreviewTF.x;
            }
            if (_previewLabel && _previewTF)
            {
                _previewTF.x = COL_L + _previewLabel.width + 2;
                _previewTF.width = CONTENT_W - _previewTF.x;
            }
        }

        private function _addLabel(parent:Sprite, text:String,
                                   px:Number, py:Number):TextField
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = MIN_FONT_SIZE;
            fmt.color = Theme.textPrimary;

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.text = text;
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.autoSize = "left";
            tf.x = px;
            tf.y = py;
            parent.addChild(tf);
            return tf;
        }

        // ═══════════════════════════════════════════════════════
        // Python → Flash 数据接口
        // ═══════════════════════════════════════════════════════

        /**
         * data 字段（全部可选，未传保留默认值）:
         *   spottedMessage:String        — 被点亮喊话内容（"" = 空）
         *   spottedMsgPlaceholder:String — 输入框占位提示
         *   spottedAliveLe:int           — 存活队友阈值（1-15）
         *   replaceDropdownItems:Array   — 下拉列表选项文本
         *   replaceSelectedIndex:int     — 当前选中项索引
         *   replaceText:String           — 当前选中项的替换文本（预填充简化串，非空）
         *   replacePlaceholder:String    — 替换输入框占位提示
         *   previewText:String           — 预览文本
         *   tooltips:Object              — {key: html, ...}
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
            // ── 被点亮喊话 ──
            if (_spottedInput)
            {
                if (data.spottedMessage != null)
                    _spottedInput.text = String(data.spottedMessage);
                if (data.spottedMsgPlaceholder != null)
                    _spottedInput.placeholder = String(data.spottedMsgPlaceholder);
                else
                    _spottedInput.placeholder = L10n.get("personal/spotted_placeholder", "输入被点亮时要发送的队内消息...");
            }

            // ── 被点亮喊话预览（<a> 替换为示例坐标）──
            if (data.spottedPreview != null && _spottedPreviewTF)
                _spottedPreviewTF.text = String(data.spottedPreview);

            // ── 存活队友阈值 ──
            if (data.spottedAliveLe != null && _aliveStepper)
                _aliveStepper.setValue(int(data.spottedAliveLe), false);

            // ── 下拉列表 ──
            if (data.replaceDropdownItems is Array && _replaceDropdown)
            {
                _replaceDropdown.setItems(data.replaceDropdownItems as Array);
                _replaceDropdown.setSelectedIndex(0);
            }
            if (data.replaceSelectedIndex != null && _replaceDropdown)
                _replaceDropdown.setSelectedIndex(int(data.replaceSelectedIndex), false);

            // ── 替换输入框（预填充简化格式串）──
            if (_replaceInput)
            {
                if (data.replaceText != null)
                    _replaceInput.text = String(data.replaceText);
                if (data.replacePlaceholder != null)
                    _replaceInput.placeholder = String(data.replacePlaceholder);
            }

            // ── 预览文本 ──
            if (data.previewText != null && _previewTF)
                _previewTF.text = String(data.previewText);

            // ── Tooltip（绑到"被点亮时喊话"标签的 wrapper 上）──
            if (data.tooltips)
            {
                var ttHtml:String = data.tooltips["spottedMessage"] as String;
                if (ttHtml && ttHtml.length > 0 && _spottedLabelWrapper)
                    Tooltip.attach(_spottedLabelWrapper, ttHtml);
            }

            L.info("数据已应用");
        }

        // ═══════════════════════════════════════════════════════
        // i18n 刷新（L10n 注册回调）
        // ═══════════════════════════════════════════════════════

        /** 全部用户可见文本按词典刷新（placeholder 由 populate 管理）。 */
        private function _applyLabels():void
        {
            if (_titleTF) _titleTF.text = L10n.get("personal/title", "个性设置");
            if (_gb) _gb.setTitle(L10n.get("personal/chat_msg_title", "局内喊话消息自定义"));
            if (_spottedLabel) _spottedLabel.text = L10n.get("personal/spotted_label", "被点亮时喊话");
            if (_spottedPreviewLabel) _spottedPreviewLabel.text = L10n.get("personal/preview_label", "预览：");
            if (_aliveTitleLabel) _aliveTitleLabel.text = L10n.get("personal/alive_label", "附加条件：");
            if (_aliveLabel) _aliveLabel.text = L10n.get("personal/alive_desc", "当场上存活队友数低于或等于");
            _layoutAliveRow();   // 文本宽度变化 → 步进器跟随右移/回落
            if (_replaceHeader) _replaceHeader.text = L10n.get("personal/replace_label", "替换已有喊话");
            if (_previewLabel) _previewLabel.text = L10n.get("personal/preview_label", "预览：");
            // 预览标签换文后重定位预览文本框（英文标签变宽 → 文本框右移不压标签）
            _relayoutPreviewRows();
            if (_hintTF) _hintTF.text = L10n.get("personal/hint", "清空输入框可还原为游戏原始消息");

            // 声明文本折行后高度变化 → 重新定位 GroupBox 与提示文字
            if (_declarationTF)
                _declarationTF.text = L10n.get("personal/declaration",
                    "前排提醒：点亮后发的是公屏喊话，所有人都能看到，也会被和谐。下面那个替换的客户端渲染文本，只有你可见且只替换自己的消息，不会被和谐。");
            if (_declarationTF && _gb)
            {
                var gbY:int = int(_declarationTF.y + _declarationTF.height) + 24;
                _gb.y = gbY;
                if (_hintTF)
                    _hintTF.y = gbY + GB_H;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 主题刷新
        // ═══════════════════════════════════════════════════════

        /** 重绘分隔线（主题换肤时同步描边色）。 */
        private function _redrawSeparator():void
        {
            if (!_separator) return;
            _separator.graphics.clear();
            _separator.graphics.lineStyle(1, Theme.stroke);
            _separator.graphics.moveTo(0, 0);
            _separator.graphics.lineTo(CONTENT_W, 0);
        }

        private function _refreshStyle():void
        {
            _redrawSeparator();

            if (_titleTF)
                _titleTF.textColor = Theme.textPrimary;

            if (_declarationTF)
                _declarationTF.textColor = Theme.textPrimary;

            if (_spottedLabel)
                _spottedLabel.textColor = Theme.textSecondary;

            if (_spottedPreviewLabel)
                _spottedPreviewLabel.textColor = Theme.textSecondary;

            if (_spottedPreviewTF)
            {
                var spf:TextFormat = _spottedPreviewTF.defaultTextFormat;
                spf.color = Theme.textPrimary;
                _spottedPreviewTF.defaultTextFormat = spf;
                _spottedPreviewTF.textColor = Theme.textPrimary;
            }

            if (_aliveTitleLabel)
                _aliveTitleLabel.textColor = Theme.textSecondary;

            if (_aliveLabel)
                _aliveLabel.textColor = Theme.textPrimary;

            if (_replaceHeader)
                _replaceHeader.textColor = Theme.textSecondary;

            if (_previewLabel)
                _previewLabel.textColor = Theme.textSecondary;

            if (_previewTF)
            {
                var pf:TextFormat = _previewTF.defaultTextFormat;
                pf.color = Theme.textPrimary;
                _previewTF.defaultTextFormat = pf;
                _previewTF.textColor = Theme.textPrimary;
            }

            if (_hintTF)
            {
                var hf:TextFormat = _hintTF.defaultTextFormat;
                hf.color = Theme.textSecondary;
                _hintTF.defaultTextFormat = hf;
                _hintTF.textColor = Theme.textSecondary;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 生命周期
        // ═══════════════════════════════════════════════════════

        override public function dispose():void
        {
            L.debug("dispose");
            _initialized = false;

            Theme.unregister(this);
            L10n.unregister(this);

            // Tooltip 解绑（绑定在"被点亮时喊话"标签的 wrapper 上）
            if (_spottedLabelWrapper)
                Tooltip.detach(_spottedLabelWrapper);

            // 组件销毁
            if (_spottedInput)   { _spottedInput.dispose();   _spottedInput = null;   }
            if (_aliveStepper)   { _aliveStepper.dispose();   _aliveStepper = null;   }
            if (_replaceDropdown){ _replaceDropdown.dispose();_replaceDropdown = null;}
            if (_replaceInput)   { _replaceInput.dispose();   _replaceInput = null;   }

            // GroupBox
            if (_gb && _gb.parent == this)
                removeChild(_gb);
            _gb = null;

            // 标题
            if (_titleTF && _titleTF.parent == this)
                removeChild(_titleTF);
            _titleTF = null;

            // 声明文本
            if (_declarationTF && _declarationTF.parent == this)
                removeChild(_declarationTF);
            _declarationTF = null;

            // 提示文字
            if (_hintTF && _hintTF.parent == this)
                removeChild(_hintTF);
            _hintTF = null;

            // 置空引用
            _spottedLabel = null;
            _spottedLabelWrapper = null;
            _spottedPreviewLabel = null;
            _spottedPreviewTF = null;
            _separator = null;
            _aliveTitleLabel = null;
            _aliveLabel = null;
            _replaceHeader = null;
            _previewLabel = null;
            _previewTF = null;

            super.dispose();
        }
    }
}
