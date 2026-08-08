package com.github._25304_Oxygen.menu.pages
{
    import flash.display.Sprite;
    import flash.text.TextField;
    import flash.text.TextFormat;

    import com.github._25304_Oxygen.menu.components.Theme;
    import com.github._25304_Oxygen.menu.components.GroupBox;
    import com.github._25304_Oxygen.menu.components.Tooltip;
    import com.github._25304_Oxygen.menu.components.ToggleButton;
    import com.github._25304_Oxygen.menu.components.ToggleGroup;
    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.i18n.L10n;

    /**
     * 字幕设置页——调整字幕各元素在屏幕上的位置。
     *
     * 布局:
     *   标题 "字幕设置"（绑定 Tooltip 说明编辑流程）
     *   ┌ 调整字幕位置 ──────────────────────┐
     *   │ [编辑][完成][重置]        ← 互斥三连，无间隔，
     *   │                             总宽 = 下方目标组占宽
     *   │ [调整头像]  [调整标题]    ← 4 个互斥按钮，两列
     *   │ [调整背景]  [调整正文]
     *   └────────────────────────────────────┘
     *
     * 交互状态机:
     *   初始   → 仅"编辑"可按，"完成""重置"和目标组禁用
     *   编辑中 → 按"编辑"点亮进入；"完成""重置"和目标组可用；
     *            目标组互斥选中（其余仍可按）
     *   已完成 → 按"完成"/"重置"/切页/关菜单结束，
     *            目标组清除选中并禁用；"重置"与"完成"流程
     *            完全相同，仅通知 Python 的业务不同（重置而非保存）
     *
     * Python 通知（经 onAction）:
     *   subtitleEditStart          — 进入编辑模式
     *   subtitleEditTarget,<id>    — 选择调整目标 (avatar/title/bg/body)
     *   subtitleEditSave,<reason>  — 保存 (done/pageHidden/dispose)
     *   subtitleEditReset          — 重置位置并结束编辑
     */
    public class SubtitleSettingsPage extends BasePage
    {
        private static const L:Object = Log.getLogger("SubtitleSettingsPage");

        // ═══════════════════════════════════════════════════════
        // 布局常量
        // ═══════════════════════════════════════════════════════

        private static const TITLE_X:int = 10;
        private static const TITLE_Y:int = 8;

        /** 分组框距面板左右边缘的距离。 */
        private static const MARGIN:int = 20;

        /** 分组框宽度 (= 660 可用宽 - 2*MARGIN)。 */
        private static const GB_W:int = 620;

        /** 按钮高度。 */
        private static const BTN_H:int = 30;

        /** 目标按钮组行间距。 */
        private static const ROW_GAP:int = 10;

        /** 目标按钮组列间距。 */
        private static const COL_GAP:int = 20;

        /** 模式按钮行与目标按钮组之间的间距。 */
        private static const SECTION_GAP:int = 16;

        /**
         * 分组框高度:
         *   content.y(30) + 行起点(2) + 模式行(30) + SECTION_GAP(16)
         *   + 两行目标按钮(30*2 + 10) + 底部留白(14) = 162
         */
        private static const GB_H:int = 162;

        /** 内容区内边距（GroupBox.content 的 y 起点）。 */
        private static const CONTENT_PAD:int = 2;

        /** 最小字号（ToggleButton 内部文字为 14px，满足要求）。 */
        private static const MIN_FONT_SIZE:int = 14;

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        private var _titleTF:TextField;
        private var _titleWrapper:Sprite;
        private var _gb:GroupBox;

        private var _editBtn:ToggleButton;
        private var _doneBtn:ToggleButton;
        private var _resetBtn:ToggleButton;
        private var _modeGroup:ToggleGroup;

        private var _targetBtns:Array;          // [ToggleButton, ...]
        private var _targetGroup:ToggleGroup;
        /** 目标按钮组起始 y（切语言重排用）。 */
        private var _targetsStartY:Number;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        private var _initialized:Boolean = false;

        /** populate 早于 init 到达时缓存数据，init 后重放。 */
        private var _lastPopulateData:Object = null;

        /** 是否处于编辑模式。 */
        private var _editing:Boolean = false;

        /** 当前字幕显示模式（standard / concise）。 */
        private var _displayMode:String = "standard";

        /** 用户操作回调: function(msg:String):void → Python onLog。 */
        public var onAction:Function;

        public function SubtitleSettingsPage()
        {
            super("subtitleSettings");
        }

        // ═══════════════════════════════════════════════════════
        // 生命周期
        // ═══════════════════════════════════════════════════════

        override public function init():void
        {
            if (_initialized) return;

            _createTitle();
            _createGroupBox();
            _applyIdleState();   // 初始默认态

            Theme.register(this, _refreshStyle);
            L10n.register(this, _applyLabels);

            _initialized = true;
            L.info("初始化完成");

            // populate 先于 init 到达 → 重放缓存数据
            if (_lastPopulateData != null)
            {
                _applyPopulateData(_lastPopulateData);
            }
        }

        /** 页面被隐藏（切换页面/关闭菜单）——编辑中则视为完成并保存。 */
        override public function hide():void
        {
            if (_editing)
            {
                L.info("页面隐藏时处于编辑中，自动保存");
                _finishEdit("pageHidden");
            }
        }

        // ═══════════════════════════════════════════════════════
        // UI 构建
        // ═══════════════════════════════════════════════════════

        private function _createTitle():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TitleFont";
            fmt.size = 18;
            fmt.color = Theme.textPrimary;

            _titleTF = new TextField();
            _titleTF.defaultTextFormat = fmt;
            _titleTF.text = L10n.get("subtitle_settings/title", "字幕设置");
            _titleTF.selectable = false;
            _titleTF.mouseEnabled = false;
            _titleTF.autoSize = "left";

            // Sprite 包裹——Tooltip 需要绑定到可交互对象
            _titleWrapper = new Sprite();
            _titleWrapper.mouseChildren = false;
            _titleWrapper.buttonMode = false;
            _titleWrapper.useHandCursor = false;
            _titleWrapper.addChild(_titleTF);
            _titleWrapper.x = TITLE_X;
            _titleWrapper.y = SAFE_TOP + TITLE_Y;
            addChild(_titleWrapper);
        }

        private function _createGroupBox():void
        {
            _gb = new GroupBox(GB_W, GB_H, L10n.get("subtitle_settings/position_title", "调整字幕位置"), 4);
            _gb.labelBgVisible = false;
            _gb.x = MARGIN;
            _gb.y = int(_titleWrapper.y + _titleWrapper.height) + 16;
            addChild(_gb);

            var ly:int = CONTENT_PAD;

            // ── 目标按钮组：两列四按钮（自动宽度，统一量算交给 _layoutButtons）──
            var defs:Array = [
                {id: "avatar", label: L10n.get("subtitle_settings/btn_avatar", "调整头像")},
                {id: "title",  label: L10n.get("subtitle_settings/btn_title", "调整标题")},
                {id: "bg",     label: L10n.get("subtitle_settings/btn_bg", "调整背景")},
                {id: "body",   label: L10n.get("subtitle_settings/btn_body", "调整正文")}
            ];

            _targetGroup = new ToggleGroup();
            _targetGroup.onChange = _onTargetChange;
            _targetBtns = [];

            for (var i:int = 0; i < defs.length; i++)
            {
                var btn:ToggleButton = new ToggleButton(defs[i].id, defs[i].label);
                _targetBtns.push(btn);
                _targetGroup.add(btn);
                _gb.content.addChild(btn);
            }

            // ── 第一行：编辑 | 完成 | 重置（互斥三连，无间隔）──
            // 初始宽度为占位，_layoutButtons 按目标组实测总宽三等分后 setWidth 校正
            _editBtn  = new ToggleButton("edit",  L10n.get("subtitle_settings/btn_edit", "编辑"), 80);
            _doneBtn  = new ToggleButton("done",  L10n.get("subtitle_settings/btn_done", "完成"), 80);
            _resetBtn = new ToggleButton("reset", L10n.get("subtitle_settings/btn_reset", "重置"), 80);

            _editBtn.y  = ly;
            _doneBtn.y  = ly;
            _resetBtn.y = ly;
            _gb.content.addChild(_editBtn);
            _gb.content.addChild(_doneBtn);
            _gb.content.addChild(_resetBtn);

            _modeGroup = new ToggleGroup();
            _modeGroup.add(_editBtn);
            _modeGroup.add(_doneBtn);
            _modeGroup.add(_resetBtn);
            _modeGroup.onChange = _onModeChange;

            // 目标按钮组起始 y = 模式行底 + 段间距
            _targetsStartY = ly + BTN_H + SECTION_GAP;

            // 统一量宽/定位（创建时 + 切语言后都走这里）
            _layoutButtons();
        }

        /**
         * 按钮组重排——目标组 4 个按钮统一为等宽（= 自然自动宽度最大值 colW），
         * 模式行三等分目标组总宽（余数给最后按钮），重设固定宽并重定位全部按钮。
         * 切语言后必须调用：目标按钮 setLabel 后文字变宽，模式行固定宽要跟随，
         * 否则两行右缘错位、第二列压第一列。
         */
        private function _layoutButtons():void
        {
            // 量出 4 个按钮各自的自然自动宽度（文字宽 + 留白），取最大为列宽。
            // 必须用 naturalWidth——按钮此前已被 setWidth 固定，btnWidth 是旧
            // 列宽而非当前文字真实宽（多次切语言后仍准确）。
            var colW:Number = 0;
            for (var i:int = 0; i < _targetBtns.length; i++)
            {
                var tb:ToggleButton = _targetBtns[i] as ToggleButton;
                if (tb && tb.naturalWidth > colW) colW = tb.naturalWidth;
            }
            if (colW <= 0) colW = 84;  // 兜底（中文 4 字按钮宽，PADDING_H=14 实测）

            // 目标组 4 个按钮等宽 = colW——英文各按钮文字长度不一，
            // 自动宽下两列长短不齐；统一后右缘对齐、视觉整齐
            for (i = 0; i < _targetBtns.length; i++)
            {
                var tb2:ToggleButton = _targetBtns[i] as ToggleButton;
                if (tb2) tb2.setWidth(colW);
            }

            // 模式行：总宽 = 目标组两列 + 列间距，三等分；余数给最后一个
            var totalW:int = int(colW * 2 + COL_GAP);
            var modeW:int = int(totalW / 3);
            if (_editBtn)  _editBtn.setWidth(modeW);
            if (_doneBtn)  _doneBtn.setWidth(modeW);
            if (_resetBtn) _resetBtn.setWidth(totalW - modeW * 2);

            var modeY:Number = CONTENT_PAD;
            if (_editBtn)  { _editBtn.x = 0;          _editBtn.y = modeY; }
            if (_doneBtn)  { _doneBtn.x = modeW;      _doneBtn.y = modeY; }
            if (_resetBtn) { _resetBtn.x = modeW * 2; _resetBtn.y = modeY; }

            // 目标组两列定位
            for (i = 0; i < _targetBtns.length; i++)
            {
                var btn:ToggleButton = _targetBtns[i] as ToggleButton;
                if (!btn) continue;
                btn.x = (i % 2) * (colW + COL_GAP);
                btn.y = _targetsStartY + int(i / 2) * (BTN_H + ROW_GAP);
            }
        }

        // ═══════════════════════════════════════════════════════
        // 状态机
        // ═══════════════════════════════════════════════════════

        /** 模式按钮组（编辑/完成/重置）互斥切换回调。 */
        private function _onModeChange(id:String):void
        {
            if (id == "edit")
                _enterEditMode();
            else if (id == "done")
                _finishEdit("done");
            else if (id == "reset")
                _resetEdit();
        }

        /** 目标按钮组互斥切换回调——通知 Python 当前调整目标。 */
        private function _onTargetChange(id:String):void
        {
            L.info("调整目标 → " + id);
            if (onAction != null)
                onAction("subtitleEditTarget," + id);
        }

        /** 进入编辑模式：启用"完成""重置"和目标组（简洁模式仅正文可调）。 */
        private function _enterEditMode():void
        {
            _editing = true;
            _doneBtn.setEnabled(true);
            _resetBtn.setEnabled(true);

            if (_displayMode == "concise")
            {
                // 简洁模式：先全部禁用，再仅启用 body（索引 3）
                _targetGroup.setEnabledAll(false);
                if (_targetBtns && _targetBtns.length > 3)
                {
                    var bodyBtn:ToggleButton = _targetBtns[3] as ToggleButton;
                    if (bodyBtn) bodyBtn.setEnabled(true);
                }
            }
            else
            {
                _targetGroup.setEnabledAll(true);
            }

            L.info("进入编辑模式 (displayMode=" + _displayMode + ")");
            if (onAction != null)
                onAction("subtitleEditStart");
        }

        /**
         * 结束编辑：通知 Python 保存，视觉重置回初始默认态。
         * @param reason 保存原因: done / pageHidden / dispose
         */
        private function _finishEdit(reason:String):void
        {
            if (!_editing) return;
            _editing = false;

            L.info("结束编辑，保存 (reason=" + reason + ")");
            if (onAction != null)
                onAction("subtitleEditSave," + reason);

            _applyIdleState();
        }

        /**
         * 重置字幕位置并结束编辑：流程与"完成"完全一致，
         * 只是通知 Python 的业务不同（重置为默认而非保存当前值）。
         */
        private function _resetEdit():void
        {
            if (!_editing) return;
            _editing = false;

            L.info("结束编辑，重置字幕位置");
            if (onAction != null)
                onAction("subtitleEditReset");

            _applyIdleState();
        }

        /**
         * 应用初始默认态：仅"编辑"可按，全部按钮回深色，
         * "完成""重置"和目标组清除选中并禁用。
         */
        private function _applyIdleState():void
        {
            _targetGroup.clearSelection();
            _targetGroup.setEnabledAll(false);

            _modeGroup.clearSelection();
            _doneBtn.setEnabled(false);
            _resetBtn.setEnabled(false);
            _editBtn.setEnabled(true);
        }

        // ═══════════════════════════════════════════════════════
        // Python → Flash 数据接口
        // ═══════════════════════════════════════════════════════

        /**
         * 接收 Python 推送的数据。
         * @param data 字段:
         *   tooltips:Object — {pageTitle: html} 标题 Tooltip 富文本
         */
        public function populate(data:Object):void
        {
            if (!data) return;
            _lastPopulateData = data;

            if (!_initialized)
            {
                L.info("populate 早于 init，数据已缓存");
                return;
            }
            _applyPopulateData(data);
        }

        private function _applyPopulateData(data:Object):void
        {
            // ── GroupBox 标题 Tooltip（绑定到"调整字幕位置"标签）──
            if (data.tooltips && data.tooltips.pageTitle && _gb && _gb.titleHitArea)
            {
                Tooltip.attach(_gb.titleHitArea, String(data.tooltips.pageTitle));
                L.debug("标题 Tooltip 已绑定");
            }

            // ── 显示模式 ──
            if (data.displayMode)
                _displayMode = String(data.displayMode);

            L.info("数据已应用");
        }

        // ═══════════════════════════════════════════════════════
        // i18n 刷新（L10n 注册回调）
        // ═══════════════════════════════════════════════════════

        /** 全部用户可见文本按词典刷新。 */
        private function _applyLabels():void
        {
            if (_titleTF) _titleTF.text = L10n.get("subtitle_settings/title", "字幕设置");
            if (_gb) _gb.setTitle(L10n.get("subtitle_settings/position_title", "调整字幕位置"));
            if (_editBtn)  _editBtn.setLabel(L10n.get("subtitle_settings/btn_edit", "编辑"));
            if (_doneBtn)  _doneBtn.setLabel(L10n.get("subtitle_settings/btn_done", "完成"));
            if (_resetBtn) _resetBtn.setLabel(L10n.get("subtitle_settings/btn_reset", "重置"));

            if (_targetBtns)
            {
                var labels:Array = [
                    L10n.get("subtitle_settings/btn_avatar", "调整头像"),
                    L10n.get("subtitle_settings/btn_title", "调整标题"),
                    L10n.get("subtitle_settings/btn_bg", "调整背景"),
                    L10n.get("subtitle_settings/btn_body", "调整正文")
                ];
                for (var i:int = 0; i < _targetBtns.length && i < labels.length; i++)
                {
                    var btn:ToggleButton = _targetBtns[i] as ToggleButton;
                    if (btn) btn.setLabel(labels[i] as String);
                }
            }

            // 目标按钮自动变宽后整组重排（模式行固定宽跟随、两列不压叠）
            _layoutButtons();
        }

        // ═══════════════════════════════════════════════════════
        // 主题刷新
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            if (_titleTF) _titleTF.textColor = Theme.textPrimary;
        }

        // ═══════════════════════════════════════════════════════
        // 销毁
        // ═══════════════════════════════════════════════════════

        override public function dispose():void
        {
            // 编辑中被销毁（如车库↔战斗切换）→ 先保存
            if (_editing)
                _finishEdit("dispose");

            Theme.unregister(this);
            L10n.unregister(this);

            _initialized = false;
            _lastPopulateData = null;

            // Tooltip 解绑（绑定在 GroupBox 标题点击区上）
            if (_gb && _gb.titleHitArea)
                Tooltip.detach(_gb.titleHitArea);

            if (_modeGroup)   { _modeGroup.dispose();   _modeGroup = null; }
            if (_targetGroup) { _targetGroup.dispose(); _targetGroup = null; }

            if (_editBtn)  { _editBtn.dispose();  _editBtn = null; }
            if (_doneBtn)  { _doneBtn.dispose();  _doneBtn = null; }
            if (_resetBtn) { _resetBtn.dispose(); _resetBtn = null; }

            if (_targetBtns)
            {
                for (var i:int = 0; i < _targetBtns.length; i++)
                {
                    var btn:ToggleButton = _targetBtns[i] as ToggleButton;
                    if (btn) btn.dispose();
                }
                _targetBtns = null;
            }

            if (_gb) { _gb.dispose(); _gb = null; }

            _titleTF = null;
            _titleWrapper = null;
            onAction = null;

            super.dispose();
        }
    }
}
