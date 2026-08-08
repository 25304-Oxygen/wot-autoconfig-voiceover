package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    /**
     * 复选框——圆角方框 + 勾号 + 文字标签。
     *
     * 用法:
     *   var cb:CheckBox = new CheckBox("启用功能", false);
     *   cb.onChange = function(checked:Boolean):void { ... };
     *   addChild(cb);
     */
    public class CheckBox extends Sprite implements ISoundable
    {
        // ═══════════════════════════════════════════════════════
        // 尺寸 & 颜色
        // ═══════════════════════════════════════════════════════

        private static const BOX_SIZE:int = 18;
        private static const BOX_RADIUS:int = 4;
        private static const LABEL_GAP:int = 8;

        private static const STROKE_WIDTH:Number  = 1;
        private static const TEXT_SIZE:int        = 13;

        // ═══════════════════════════════════════════════════════

        private var _label:String;
        private var _checked:Boolean;
        private var _enabled:Boolean = true;
        /** 标签最大宽度（0 = 不限宽单行，旧行为；>0 = 限定列宽内自动换行）。 */
        private var _labelWidth:Number = 0;

        private var _boxShape:Shape;
        private var _labelTF:TextField;

        private var _w:Number;
        private var _h:Number;

        /** 状态变更回调: function(checked:Boolean):void */
        public var onChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param label      标签文字
         * @param checked    初始选中状态
         * @param labelWidth 标签最大宽度（0 = 不限宽单行；>0 = 限定列宽内换行）
         */
        public function CheckBox(label:String = "", checked:Boolean = false,
                                 labelWidth:Number = 0)
        {
            super();
            _label = label;
            _checked = checked;
            _labelWidth = labelWidth;
            _init();
        }

        private function _init():void
        {
            this.buttonMode = true;

            // 方框
            _boxShape = new Shape();
            addChild(_boxShape);
            _drawBox();

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
                _labelTF.x = BOX_SIZE + LABEL_GAP;
                _labelTF.y = int((BOX_SIZE - TEXT_SIZE) / 2) - 1;
                _applyLabelWrap(_labelTF);
                addChild(_labelTF);
            }

            var labelW:Number = _labelTF ? _labelTF.width : 0;
            _w = BOX_SIZE + LABEL_GAP + labelW;
            _h = Math.max(BOX_SIZE, _labelTF ? _labelTF.height : BOX_SIZE);

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

        public function get checked():Boolean { return _checked; }

        /** 程序化设置选中状态。 */
        public function setChecked(value:Boolean, dispatch:Boolean = true):void
        {
            if (_checked == value) return;
            _checked = value;
            _drawBox();

            if (dispatch && onChange != null)
                onChange(_checked);
        }

        /** 切换选中状态。 */
        public function toggle():void
        {
            setChecked(!_checked);
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
                _labelTF.x = BOX_SIZE + LABEL_GAP;
                _labelTF.y = int((BOX_SIZE - TEXT_SIZE) / 2) - 1;
                _applyLabelWrap(_labelTF);
                addChild(_labelTF);
            }
            if (_labelTF)
            {
                _labelTF.text = text;
                _labelTF.visible = text.length > 0;
            }
            var labelW:Number = _labelTF ? _labelTF.width : 0;
            _w = BOX_SIZE + LABEL_GAP + labelW;
            _h = Math.max(BOX_SIZE, _labelTF ? _labelTF.height : BOX_SIZE);
        }

        public function setEnabled(value:Boolean):void
        {
            _enabled = value;
            this.mouseEnabled = value;
            this.buttonMode = value;
            if (_labelTF) _labelTF.textColor = value ? Theme.textPrimary : Theme.textSecondary;
            this.alpha = value ? 1.0 : 0.5;
        }

        /** 销毁。 */
        public function dispose():void
        {
            SoundUtils.removeSound(this);
            removeEventListener(MouseEvent.CLICK, _onClick);
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

        private function _refreshStyle():void
        {
            _drawBox();
            if (_labelTF)
            {
                var fmt:TextFormat = _labelTF.defaultTextFormat;
                fmt.color = Theme.textPrimary;
                _labelTF.defaultTextFormat = fmt;
                _labelTF.textColor = _enabled ? Theme.textPrimary : Theme.textSecondary;
            }
        }

        private function _drawBox():void
        {
            _boxShape.graphics.clear();

            var strokeColor:uint = _checked ? Theme.accent : Theme.stroke;
            var r2:Number = BOX_RADIUS * 2;

            if (_checked)
            {
                // 填充背景
                _boxShape.graphics.beginFill(Theme.accent, 1.0);
                if (STROKE_WIDTH > 0)
                    _boxShape.graphics.lineStyle(STROKE_WIDTH, strokeColor);
                _boxShape.graphics.drawRoundRect(0, 0, BOX_SIZE, BOX_SIZE, r2, r2);
                _boxShape.graphics.endFill();

                // 勾号（简化为两条线段的 V 形）
                _boxShape.graphics.lineStyle(2, 0xFFFFFF);
                var cx:Number = BOX_SIZE / 2;
                var cy:Number = BOX_SIZE / 2;
                _boxShape.graphics.moveTo(cx - 4, cy + 0);
                _boxShape.graphics.lineTo(cx - 1, cy + 4);
                _boxShape.graphics.lineTo(cx + 5, cy - 4);
            }
            else
            {
                // 未选中: 透明填充 + 外框（Scaleform 中 lineStyle 单独用可能不闭合，加填充确保完整）
                _boxShape.graphics.lineStyle(STROKE_WIDTH, strokeColor);
                _boxShape.graphics.beginFill(Theme.surface1, 0.4);
                _boxShape.graphics.drawRoundRect(0, 0, BOX_SIZE, BOX_SIZE, r2, r2);
                _boxShape.graphics.endFill();
            }
        }

        // ═══════════════════════════════════════════════════════
        // 事件
        // ═══════════════════════════════════════════════════════

        private function _onClick(event:MouseEvent):void
        {
            if (!_enabled) return;
            toggle();
        }
    }
}
