package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    /**
     * 单选按钮——圆形外框 + 选中内点 + 文字标签。
     *
     * 通过 RadioGroup 管理互斥选中。
     *
     * 用法:
     *   var group:RadioGroup = new RadioGroup();
     *   var rb1:RadioButton = new RadioButton("选项 A");
     *   var rb2:RadioButton = new RadioButton("选项 B");
     *   group.add(rb1);
     *   group.add(rb2);
     *   group.onSelectionChange = function(index:int):void { ... };
     *   addChild(rb1); addChild(rb2);
     */
    public class RadioButton extends Sprite implements ISoundable
    {
        // ═══════════════════════════════════════════════════════
        // 尺寸 & 颜色
        // ═══════════════════════════════════════════════════════

        private static const DOT_SIZE:int = 18;       // 外圆直径
        private static const DOT_INNER:int = 10;      // 内点直径
        private static const LABEL_GAP:int = 8;       // 圆与文字间距

        private static const STROKE_WIDTH:Number  = 1;
        private static const TEXT_SIZE:int        = 13;

        // ═══════════════════════════════════════════════════════

        private var _label:String;
        private var _selected:Boolean = false;
        private var _enabled:Boolean = true;
        private var _group:RadioGroup;
        /** 标签最大宽度（0 = 不限宽单行，旧行为；>0 = 限定列宽内自动换行）。 */
        private var _labelWidth:Number = 0;

        private var _dotShape:Shape;
        private var _labelTF:TextField;

        private var _w:Number;
        private var _h:Number;

        /** 选中状态变更: function(selected:Boolean):void */
        public var onChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        public function RadioButton(label:String = "", labelWidth:Number = 0)
        {
            super();
            _label = label;
            _labelWidth = labelWidth;
            _init();
        }

        private function _init():void
        {
            this.buttonMode = true;

            // 圆形指示器
            _dotShape = new Shape();
            addChild(_dotShape);
            _drawDot();

            // 标签
            if (_label.length > 0)
            {
                var fmt:TextFormat = new TextFormat();
                fmt.font = "$TextFont";
                fmt.size = TEXT_SIZE;
                fmt.color = Theme.textPrimary;

                _labelTF = new TextField();
                _labelTF.defaultTextFormat = fmt;
                _labelTF.text = _label;
                _labelTF.selectable = false;
                _labelTF.mouseEnabled = false;
                _labelTF.autoSize = "left";
                _labelTF.x = DOT_SIZE + LABEL_GAP;
                _labelTF.y = int((DOT_SIZE - TEXT_SIZE) / 2) - 1;
                _applyLabelWrap(_labelTF);
                addChild(_labelTF);
            }

            // 计算整体尺寸
            var labelW:Number = _labelTF ? _labelTF.width : 0;
            _w = DOT_SIZE + LABEL_GAP + labelW;
            _h = Math.max(DOT_SIZE, _labelTF ? _labelTF.height : DOT_SIZE);

            addEventListener(MouseEvent.CLICK, _onClick);

            // 游戏 UI 音效
            SoundUtils.registerSound(this);

            Theme.register(this, _refreshStyle);
        }

        /** 应用标签换行配置（labelWidth > 0 时限定列宽内自动换行，不横向溢出）。 */
        private function _applyLabelWrap(tf:TextField):void
        {
            if (_labelWidth > 0)
            {
                tf.width = _labelWidth;
                tf.wordWrap = true;
                tf.multiline = true;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        public function get selected():Boolean { return _selected; }

        /** 程序化设置选中状态（RadioGroup 内部调用）。 */
        public function setSelected(value:Boolean, dispatch:Boolean = true):void
        {
            if (_selected == value) return;
            _selected = value;
            _drawDot();

            if (dispatch && onChange != null)
                onChange(_selected);
        }

        public function setEnabled(value:Boolean):void
        {
            _enabled = value;
            this.mouseEnabled = value;
            this.buttonMode = value;
            if (_labelTF) _labelTF.textColor = value ? Theme.textPrimary : Theme.textSecondary;
            if (!value)
            {
                this.alpha = 0.5;
            }
            else
            {
                this.alpha = 1.0;
            }
        }

        /** 设置标签文字（i18n 刷新用，与构造逻辑一致）。 */
        public function setLabel(text:String):void
        {
            _label = text;
            if (!_labelTF && text.length > 0)
            {
                var fmt:TextFormat = new TextFormat();
                fmt.font = "$TextFont";
                fmt.size = TEXT_SIZE;
                fmt.color = Theme.textPrimary;

                _labelTF = new TextField();
                _labelTF.defaultTextFormat = fmt;
                _labelTF.selectable = false;
                _labelTF.mouseEnabled = false;
                _labelTF.autoSize = "left";
                _labelTF.x = DOT_SIZE + LABEL_GAP;
                _labelTF.y = int((DOT_SIZE - TEXT_SIZE) / 2) - 1;
                _applyLabelWrap(_labelTF);
                addChild(_labelTF);
            }
            if (_labelTF)
            {
                _labelTF.text = text;
                _labelTF.visible = text.length > 0;
            }
            var labelW:Number = _labelTF ? _labelTF.width : 0;
            _w = DOT_SIZE + LABEL_GAP + labelW;
            _h = Math.max(DOT_SIZE, _labelTF ? _labelTF.height : DOT_SIZE);
        }

        /** 由 RadioGroup 调用，不直接调用。 */
        internal function _setGroup(group:RadioGroup):void
        {
            _group = group;
        }

        /** 销毁。 */
        public function dispose():void
        {
            SoundUtils.removeSound(this);
            if (_group) _group.remove(this);
            removeEventListener(MouseEvent.CLICK, _onClick);
            Theme.unregister(this);
            onChange = null;
        }

        // ═══════════════════════════════════════════════════════
        // ISoundable
        // ═══════════════════════════════════════════════════════

        public function canPlaySound(type:String):Boolean { return _enabled && !SoundUtils.muted; }

        public function getSoundType():String { return "radioButton"; }

        public function getSoundId():String { return ""; }

        // ═══════════════════════════════════════════════════════
        // 绘制
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            _drawDot();
            if (_labelTF)
            {
                var fmt:TextFormat = _labelTF.defaultTextFormat;
                fmt.color = Theme.textPrimary;
                _labelTF.defaultTextFormat = fmt;
                _labelTF.textColor = _enabled ? Theme.textPrimary : Theme.textSecondary;
            }
        }

        private function _drawDot():void
        {
            _dotShape.graphics.clear();
            var r:Number = DOT_SIZE / 2;

            // 外圆——透明填充确保圆内部可以响应鼠标点击
            //       仅描边时 hit area 是一条 1px 细线，圆内空白区域点击落空
            var strokeColor:uint = _selected ? Theme.accent : Theme.stroke;
            _dotShape.graphics.lineStyle(STROKE_WIDTH, strokeColor);
            _dotShape.graphics.beginFill(0, 0);          // alpha=0，不可见但撑开 hit area
            _dotShape.graphics.drawCircle(r, r, r - 1);
            _dotShape.graphics.endFill();

            // 内点（选中时填充）
            if (_selected)
            {
                _dotShape.graphics.beginFill(Theme.accent, 1.0);
                _dotShape.graphics.drawCircle(r, r, DOT_INNER / 2);
                _dotShape.graphics.endFill();
            }
        }

        // ═══════════════════════════════════════════════════════
        // 事件
        // ═══════════════════════════════════════════════════════

        private function _onClick(event:MouseEvent):void
        {
            if (!_enabled) return;
            if (_group)
                _group._selectButton(this);
        }
    }
}
