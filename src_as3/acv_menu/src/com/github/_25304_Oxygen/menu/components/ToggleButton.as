package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    /**
     * 互斥切换按钮——未选中深色、选中变强调色，配合 ToggleGroup 使用。
     *
     * 视觉风格:
     *   未选中 → surface1 背景 + stroke 描边 + textSecondary 文字
     *   悬停   → surface2 背景（微亮）
     *   选中   → accent 背景 + textPrimary 文字
     *   禁用   → alpha 0.5 + 不响应鼠标
     *
     * 点击已选中的按钮 = no-op（由 ToggleGroup 处理），
     * 取消选中只能通过组的互斥切换或 clearSelection()。
     *
     * 用法:
     *   var btn:ToggleButton = new ToggleButton("edit", "编辑");
     *   group.add(btn);          // 互斥由 ToggleGroup 管理
     *   addChild(btn);
     */
    public class ToggleButton extends Sprite implements ISoundable
    {
        // ═══════════════════════════════════════════════════════
        // 常量
        // ═══════════════════════════════════════════════════════

        /**
         * 自动宽度时文字两侧的留白。
         * 原 26 是为短中文标签（2~4 字）留足宽度；英文长标签整体长，
         * 固定大留白会让按钮过宽、两侧空白过大（2026-08-06 调为 14）。
         */
        private static const PADDING_H:int = 14;

        private static const STROKE_WIDTH:Number = 1;
        private static const TEXT_SIZE:int = 14;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        private var _id:String;
        private var _label:String;
        private var _selected:Boolean = false;
        private var _hovered:Boolean = false;
        private var _enabled:Boolean = true;
        private var _group:ToggleGroup;

        private var _w:Number;
        private var _h:Number;

        /** 是否为自动宽度（构造 w=-1）——setLabel 时需按文字重算宽度。 */
        private var _autoWidth:Boolean = false;

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        private var _bg:Shape;
        private var _labelTF:TextField;

        /** 选中状态变更: function(id:String):void（由 ToggleGroup 触发）。 */
        public var onChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param id     唯一标识符（如 "edit"、"avatar"）
         * @param label  显示文字（不传则用 id）
         * @param w      按钮宽度（-1 = 自动：文字宽 + 两侧留白）
         * @param h      按钮高度
         */
        public function ToggleButton(id:String, label:String = "",
                                     w:Number = -1, h:Number = 30)
        {
            super();
            _id = id;
            _label = label || id;
            _h = h;
            _init(w);
        }

        private function _init(w:Number):void
        {
            this.buttonMode = true;
            this.mouseChildren = false;

            // 背景 Shape
            _bg = new Shape();
            addChild(_bg);

            // 标签 TextField
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = TEXT_SIZE;
            fmt.color = Theme.textSecondary;
            fmt.align = "center";

            _labelTF = new TextField();
            _labelTF.defaultTextFormat = fmt;
            _labelTF.text = _label;
            _labelTF.selectable = false;
            _labelTF.mouseEnabled = false;
            _labelTF.autoSize = "left";

            // 宽度：显式指定或按文字自动
            _autoWidth = (w <= 0);
            _w = _autoWidth ? _labelTF.width + PADDING_H * 2 : w;

            // 文字居中
            _labelTF.x = int((_w - _labelTF.width) / 2);
            _labelTF.y = int((_h - _labelTF.height) / 2);
            addChild(_labelTF);

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

        /** 唯一标识符。 */
        public function get id():String { return _id; }

        /** 是否选中。 */
        public function get selected():Boolean { return _selected; }

        /** 是否可用。 */
        public function get enabled():Boolean { return _enabled; }

        /** 逻辑宽度（不受 transform 影响，供布局用）。 */
        public function get btnWidth():Number { return _w; }

        /**
         * 按当前文字的自然自动宽度（文字宽 + 两侧留白）——不受已设固定宽影响。
         * 组内等宽测量用：按钮被 setWidth 固定后，btnWidth 是旧固定宽，
         * 需用本方法量出当前文字的真实自动宽（多次切语言后仍准确）。
         */
        public function get naturalWidth():Number
        {
            if (_labelTF) return _labelTF.width + PADDING_H * 2;
            return _w;
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /**
         * 程序化设置选中状态（通常由 ToggleGroup 调用）。
         * @param dispatch 是否触发 onChange 回调
         */
        public function setSelected(value:Boolean, dispatch:Boolean = true):void
        {
            if (_selected == value) return;
            _selected = value;
            _draw();

            if (dispatch && onChange != null)
                onChange(_id);
        }

        /** 启用/禁用。禁用时半透明且不响应鼠标。 */
        public function setEnabled(value:Boolean):void
        {
            _enabled = value;
            this.mouseEnabled = value;
            this.buttonMode = value;
            this.alpha = value ? 1.0 : 0.5;
            if (!value) _hovered = false;
            _draw();
        }

        /** 设置标签文字（i18n 刷新用）——文字重新居中；自动宽度时重算按钮宽。 */
        public function setLabel(text:String):void
        {
            _label = text || _id;
            if (_labelTF)
            {
                _labelTF.text = _label;
                if (_autoWidth)
                    _w = _labelTF.width + PADDING_H * 2;
                _labelTF.x = int((_w - _labelTF.width) / 2);
                _draw();
            }
        }

        /**
         * 设置固定按钮宽度（i18n 切语言后整组重排用）——重绘背景并重新居中文字。
         * 只对显式宽度按钮有效；自动宽度按钮改用它后即转为固定宽度。
         */
        public function setWidth(w:Number):void
        {
            if (w <= 0) return;
            _autoWidth = false;
            _w = w;
            if (_labelTF)
                _labelTF.x = int((_w - _labelTF.width) / 2);
            _draw();
        }

        /** 关联到 ToggleGroup（ToggleGroup.add 调用）。 */
        internal function _setGroup(group:ToggleGroup):void
        {
            _group = group;
        }

        /** 销毁。 */
        public function dispose():void
        {
            SoundUtils.removeSound(this);
            if (_group) _group.remove(this);
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

        public function getSoundType():String { return "checkBox"; }

        public function getSoundId():String { return ""; }

        // ═══════════════════════════════════════════════════════
        // 绘制
        // ═══════════════════════════════════════════════════════

        /** Theme 换肤回调。 */
        private function _refreshStyle():void
        {
            _draw();
        }

        /** 根据当前状态重绘背景和文字颜色。 */
        private function _draw():void
        {
            var fillColor:uint;
            var textColor:uint;

            if (_selected)
            {
                // 选中态：强调色点亮
                fillColor = Theme.accent;
                textColor = Theme.textPrimary;
            }
            else if (_hovered && _enabled)
            {
                // 悬停态：微亮反馈
                fillColor = Theme.surface2;
                textColor = Theme.textPrimary;
            }
            else
            {
                // 默认态：深色背景，低调文字
                fillColor = Theme.surface1;
                textColor = Theme.textSecondary;
            }

            _bg.graphics.clear();
            _bg.graphics.lineStyle(STROKE_WIDTH, Theme.stroke);
            _bg.graphics.beginFill(fillColor, 1.0);
            _bg.graphics.drawRect(0, 0, _w, _h);
            _bg.graphics.endFill();

            _labelTF.textColor = textColor;
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
                _group._selectButton(this);
            else
                setSelected(true);   // 无组时退化为单独点亮
        }
    }
}
