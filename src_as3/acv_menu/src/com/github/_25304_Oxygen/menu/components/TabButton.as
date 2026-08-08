package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    /**
     * 选项卡按钮——圆角药片形状，选中时底部有强调色横条。
     *
     * 由 TabGroup 管理互斥选中，不要直接调用 setSelected()。
     *
     * 视觉风格:
     *   未选中 → surface1 背景 + stroke 描边 + textSecondary 文字
     *   悬停   → surface2 背景（微亮）
     *   选中   → surface0 背景（与面板融为一体）+ accent 底部横条 + textPrimary 文字
     *
     * 用法:
     *   var tab:TabButton = new TabButton("settings", "设置");
     *   group.addTab(tab);
     */
    public class TabButton extends Sprite implements ISoundable
    {
        // ═══════════════════════════════════════════════════════
        // 常量
        // ═══════════════════════════════════════════════════════

        /** 选项卡统一高度。 */
        public static const HEIGHT:int = 30;

        private static const PADDING_H:int = 14;
        private static const CORNER_RADIUS:Number = 0;
        private static const STROKE_WIDTH:Number = 1;
        private static const ACCENT_BAR_H:int = 3;
        private static const ACCENT_BAR_PAD:int = 8;
        private static const TEXT_SIZE:int = 14;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        private var _tabId:String;
        private var _label:String;
        private var _selected:Boolean = false;
        private var _hovered:Boolean = false;
        private var _enabled:Boolean = true;
        private var _group:TabGroup;

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        private var _bg:Shape;
        private var _accentBar:Shape;
        private var _labelTF:TextField;

        /** 逻辑宽度（不含 transform），供 TabGroup 布局用。 */
        private var _w:Number;

        /** 选中状态变更: function(tabId:String):void（由 TabGroup 触发）。 */
        public var onChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param tabId  唯一标识符（如 "info"、"settings"）
         * @param label  显示文字（不传则用 tabId）
         */
        public function TabButton(tabId:String, label:String = "")
        {
            super();
            _tabId = tabId;
            _label = label || tabId;
            _init();
        }

        private function _init():void
        {
            this.buttonMode = true;

            // 背景 Shape
            _bg = new Shape();
            addChild(_bg);

            // 底部强调条
            _accentBar = new Shape();
            addChild(_accentBar);

            // 标签 TextField
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = TEXT_SIZE;
            fmt.color = Theme.textSecondary;

            _labelTF = new TextField();
            _labelTF.defaultTextFormat = fmt;
            _labelTF.text = _label;
            _labelTF.selectable = false;
            _labelTF.mouseEnabled = false;
            _labelTF.autoSize = "left";
            _labelTF.x = PADDING_H;
            _labelTF.y = int((HEIGHT - TEXT_SIZE) / 2) - 1;
            addChild(_labelTF);

            // 计算逻辑宽度
            _w = _labelTF.width + PADDING_H * 2;

            _draw();

            addEventListener(MouseEvent.MOUSE_OVER, _onMouseOver);
            addEventListener(MouseEvent.MOUSE_OUT,  _onMouseOut);
            addEventListener(MouseEvent.CLICK,      _onClick);

            // 游戏 UI 音效
            SoundUtils.registerSound(this);

            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 访问器
        // ═══════════════════════════════════════════════════════

        /** 选项卡唯一标识符。 */
        public function get tabId():String { return _tabId; }

        /** 是否选中。 */
        public function get selected():Boolean { return _selected; }

        /** 逻辑宽度（供 TabGroup 水平排列用）。 */
        internal function get tabWidth():Number { return _w; }

        // ═══════════════════════════════════════════════════════
        // 内部（TabGroup 调用）
        // ═══════════════════════════════════════════════════════

        /** 程序化设置选中状态（TabGroup 内部调用）。 */
        internal function setSelected(value:Boolean, dispatch:Boolean = true):void
        {
            if (_selected == value) return;
            _selected = value;
            _draw();

            if (dispatch && onChange != null)
                onChange(_tabId);
        }

        /** 关联到 TabGroup（TabGroup.addTab 调用）。 */
        internal function _setGroup(group:TabGroup):void
        {
            _group = group;
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 启用/禁用。 */
        public function setEnabled(value:Boolean):void
        {
            _enabled = value;
            this.mouseEnabled = value;
            this.buttonMode = value;
            this.alpha = value ? 1.0 : 0.5;
        }

        /** 设置标签文字（i18n 刷新用）——重算逻辑宽度并触发组重排。 */
        public function setLabel(text:String):void
        {
            _label = text || _tabId;
            if (_labelTF)
            {
                _labelTF.text = _label;
                _w = _labelTF.width + PADDING_H * 2;
                _draw();
                if (_group)
                    _group.reflow();
            }
        }

        /** 销毁。 */
        public function dispose():void
        {
            SoundUtils.removeSound(this);
            if (_group) _group.removeTab(this);
            removeEventListener(MouseEvent.MOUSE_OVER, _onMouseOver);
            removeEventListener(MouseEvent.MOUSE_OUT,  _onMouseOut);
            removeEventListener(MouseEvent.CLICK,      _onClick);
            Theme.unregister(this);
            onChange = null;
        }

        // ═══════════════════════════════════════════════════════
        // ISoundable
        // ═══════════════════════════════════════════════════════

        public function canPlaySound(type:String):Boolean { return _enabled && !SoundUtils.muted; }

        public function getSoundType():String { return "tab"; }

        public function getSoundId():String { return ""; }

        // ═══════════════════════════════════════════════════════
        // 绘制
        // ═══════════════════════════════════════════════════════

        /** Theme 换肤回调。 */
        private function _refreshStyle():void
        {
            _draw();
        }

        /** 根据当前状态重绘背景、底部条、文字颜色。 */
        private function _draw():void
        {
            var fillColor:uint;
            var borderColor:uint;
            var textColor:uint;

            if (_selected)
            {
                // 选中态：背景与面板同色，让选项卡"融入"下方内容区
                fillColor = Theme.surface0;
                borderColor = Theme.stroke;
                textColor = Theme.textPrimary;
            }
            else if (_hovered)
            {
                // 悬停态：微亮反馈
                fillColor = Theme.surface2;
                borderColor = Theme.stroke;
                textColor = Theme.textPrimary;
            }
            else
            {
                // 默认态：中性背景，低调文字
                fillColor = Theme.surface1;
                borderColor = Theme.stroke;
                textColor = Theme.textSecondary;
            }

            // ── 背景圆角矩形 ──
            _bg.graphics.clear();
            _bg.graphics.lineStyle(STROKE_WIDTH, borderColor);
            _bg.graphics.beginFill(fillColor, 1.0);
            _bg.graphics.drawRoundRect(0, 0, _w, HEIGHT,
                CORNER_RADIUS * 2, CORNER_RADIUS * 2);
            _bg.graphics.endFill();

            // 底部强调条已移除——用户要求不要横线效果
            _accentBar.graphics.clear();

            // ── 文字颜色 ──
            if (_labelTF)
            {
                var fmt:TextFormat = _labelTF.defaultTextFormat;
                fmt.color = textColor;
                _labelTF.defaultTextFormat = fmt;
                _labelTF.textColor = textColor;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 事件
        // ═══════════════════════════════════════════════════════

        private function _onMouseOver(event:MouseEvent):void
        {
            if (!_enabled) return;
            _hovered = true;
            _draw();
        }

        private function _onMouseOut(event:MouseEvent):void
        {
            if (!_enabled) return;
            _hovered = false;
            _draw();
        }

        private function _onClick(event:MouseEvent):void
        {
            if (!_enabled) return;
            if (_group)
                _group._selectTab(this);
        }
    }
}
