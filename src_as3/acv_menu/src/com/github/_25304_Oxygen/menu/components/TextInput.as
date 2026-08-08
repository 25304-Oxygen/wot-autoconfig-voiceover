package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFieldType;
    import flash.text.TextFormat;
    import flash.events.Event;
    import flash.events.FocusEvent;
    import flash.events.MouseEvent;
    import flash.events.TimerEvent;
    import flash.utils.Timer;

    /**
     * 自定义输入框——Dark+ 配色，纯 AS3 实现。
     *
     * 基于 AS3 原生 TextField(type="input")，自带键盘输入、选区、
     * 复制粘贴、光标渲染等能力。仅外加背景/描边/占位文字/焦点样式。
     *
     * 用法:
     *   var input:TextInput = new TextInput(220, 40, "请输入...");
     *   input.onChange = function(text:String):void { ... };
     *   addChild(input);
     */
    public class TextInput extends Sprite
    {
        // ═══════════════════════════════════════════════════════
        // 外观常量
        // ═══════════════════════════════════════════════════════

        private static const STROKE_WIDTH:Number = 1;
        private static const CORNER_RADIUS:int  = 6;
        private static const PADDING_H:int = 8;
        private static const PADDING_V:int = 6;

        private static const TEXT_SIZE:int     = 13;

        // ═══════════════════════════════════════════════════════

        private var _w:Number;
        private var _h:Number;
        private var _placeholder:String = "";
        private var _lastReportedText:String = "";

        private var _bg:Shape;
        private var _tf:TextField;

        private var _focused:Boolean = false;
        private var _editable:Boolean = true;

        /** 当前是否正在显示占位文字（代替 textColor 判断，Scaleform 中 textColor 不可靠）。 */
        private var _showingPlaceholder:Boolean = false;

        /** 防抖定时器（延迟毫秒），0 = 每次按键立即触发 onChange。 */
        private var _debounceTimer:Timer;
        private var _debounceDelay:Number = 0;
        private var _pendingText:String = "";

        /** 文本变更回调: function(text:String):void */
        public var onChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param w           组件宽度
         * @param h           组件高度
         * @param placeholder 占位文字（可选）
         */
        public function TextInput(w:Number, h:Number, placeholder:String = "")
        {
            super();
            _w = w;
            _h = h;
            _placeholder = placeholder;

            _build();
        }

        private function _build():void
        {
            this.buttonMode = false;  // 默认指针，由内部 TextField 处理光标

            // ── 背景 ──
            _bg = new Shape();
            _drawBackground(false);
            addChild(_bg);

            // ── 输入文本 ──
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = TEXT_SIZE;
            fmt.color = Theme.textPrimary;

            _tf = new TextField();
            _tf.defaultTextFormat = fmt;
            _tf.type = TextFieldType.INPUT;
            _tf.selectable = true;
            _tf.mouseEnabled = true;
            _tf.x = PADDING_H;
            _tf.y = int((_h - TEXT_SIZE - PADDING_V) / 2);
            _tf.width = _w - PADDING_H * 2;
            _tf.height = _h - PADDING_V;
            _tf.maxChars = 0;  // 无限制
            addChild(_tf);

            // ── 占位文字 ──
            if (_placeholder.length > 0)
            {
                _updatePlaceholder();
            }

            // ── 事件 ──
            _tf.addEventListener(Event.CHANGE, _onTextChange);
            _tf.addEventListener(FocusEvent.FOCUS_IN, _onFocusIn);
            _tf.addEventListener(FocusEvent.FOCUS_OUT, _onFocusOut);
            // 点击背景区域也聚焦到 TextField
            this.addEventListener(MouseEvent.MOUSE_DOWN, _onBgClick);

            // ── 主题 ──
            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        public function get text():String
        {
            return _tf ? _tf.text : "";
        }

        public function set text(value:String):void
        {
            if (!_tf) return;
            _showingPlaceholder = false;
            _tf.text = value;
            _lastReportedText = value;
        }

        /** 占位文字（内容为空 + 未聚焦时显示）。 */
        public function get placeholder():String { return _placeholder; }
        public function set placeholder(value:String):void
        {
            _placeholder = value;
            _updatePlaceholder();
        }

        /** 最大字符数，0 = 不限。 */
        public function get maxChars():int
        {
            return _tf ? _tf.maxChars : 0;
        }
        public function set maxChars(value:int):void
        {
            if (_tf) _tf.maxChars = value;
        }

        /** 可编辑状态。 */
        public function get editable():Boolean { return _editable; }
        public function set editable(value:Boolean):void
        {
            _editable = value;
            if (_tf)
            {
                _tf.type = value ? TextFieldType.INPUT : TextFieldType.DYNAMIC;
                _tf.selectable = value;
            }
            this.buttonMode = false;  // 不使用手型指针
            this.mouseEnabled = true;  // 不可编辑时仍可点击查看
        }

        /** 密码模式（显示为 •••）。 */
        public function get displayAsPassword():Boolean
        {
            return _tf ? _tf.displayAsPassword : false;
        }
        public function set displayAsPassword(value:Boolean):void
        {
            if (_tf) _tf.displayAsPassword = value;
        }

        /** 防抖延迟（毫秒），停止输入后等待此时间才触发 onChange。
         *  0 = 禁用防抖，每次按键立即触发。默认 0。 */
        public function get debounceDelay():Number { return _debounceDelay; }
        public function set debounceDelay(value:Number):void
        {
            _debounceDelay = Math.max(0, value);
            if (_debounceDelay == 0)
                _killDebounce();
        }

        /** 立即提交待处理的防抖文本（失焦前调用）。 */
        public function commit():void
        {
            _flushDebounce();
        }

        /** 获取原生 TextField，用于需要直接操作的场景。 */
        public function get textField():TextField { return _tf; }

        /** 销毁。 */
        public function dispose():void
        {
            Theme.unregister(this);
            _killDebounce();
            if (_tf)
            {
                _tf.removeEventListener(Event.CHANGE, _onTextChange);
                _tf.removeEventListener(FocusEvent.FOCUS_IN, _onFocusIn);
                _tf.removeEventListener(FocusEvent.FOCUS_OUT, _onFocusOut);
                if (_tf.parent) _tf.parent.removeChild(_tf);
                _tf = null;
            }
            this.removeEventListener(MouseEvent.MOUSE_DOWN, _onBgClick);
            onChange = null;
        }

        // ═══════════════════════════════════════════════════════
        // 绘制
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            _drawBackground(_focused);
            if (_tf)
            {
                var fmt:TextFormat = _tf.defaultTextFormat;
                fmt.color = Theme.textPrimary;
                _tf.defaultTextFormat = fmt;
                _tf.textColor = Theme.textPrimary;
                _tf.setTextFormat(fmt);
            }
        }

        private function _drawBackground(focused:Boolean):void
        {
            var strokeColor:uint = focused ? Theme.accent : Theme.stroke;
            _bg.graphics.clear();
            _bg.graphics.lineStyle(STROKE_WIDTH, strokeColor);
            _bg.graphics.beginFill(Theme.surface1, 1.0);
            _bg.graphics.drawRoundRect(0, 0, _w, _h,
                CORNER_RADIUS * 2, CORNER_RADIUS * 2);
            _bg.graphics.endFill();
        }

        // ═══════════════════════════════════════════════════════
        // 占位文字
        // ═══════════════════════════════════════════════════════

        /** 当内容为空且未聚焦时，显示占位文字。 */
        private function _updatePlaceholder():void
        {
            if (!_tf) return;
            if (!_focused && _tf.text.length == 0 && _placeholder.length > 0)
            {
                _showingPlaceholder = true;
                _tf.text = _placeholder;
            }
        }

        /** 清除占位文字（聚焦或程序化设置 text 时调用）。 */
        private function _clearPlaceholder():void
        {
            if (_showingPlaceholder)
            {
                _showingPlaceholder = false;
                _tf.text = "";
            }
        }

        // ═══════════════════════════════════════════════════════
        // 事件
        // ═══════════════════════════════════════════════════════

        private function _onTextChange(event:Event):void
        {
            if (_showingPlaceholder) return;

            var currentText:String = _tf.text;
            if (currentText == _lastReportedText) return;
            _lastReportedText = currentText;

            if (_debounceDelay > 0)
            {
                _startDebounce(currentText);
            }
            else
            {
                if (onChange != null)
                    onChange(currentText);
            }
        }

        private function _onFocusIn(event:FocusEvent):void
        {
            _focused = true;
            _drawBackground(true);
            _clearPlaceholder();
        }

        private function _onFocusOut(event:FocusEvent):void
        {
            _focused = false;
            _drawBackground(false);
            _flushDebounce();   // 失焦时立即提交，不等待防抖
            _updatePlaceholder();
        }

        // ═══════════════════════════════════════════════════════
        // 防抖
        // ═══════════════════════════════════════════════════════

        private function _startDebounce(text:String):void
        {
            _pendingText = text;
            if (!_debounceTimer)
            {
                _debounceTimer = new Timer(_debounceDelay, 1);
                _debounceTimer.addEventListener(TimerEvent.TIMER_COMPLETE,
                    _onDebounceTick);
            }
            else
            {
                _debounceTimer.stop();
                _debounceTimer.delay = _debounceDelay;
            }
            _debounceTimer.reset();
            _debounceTimer.start();
        }

        private function _onDebounceTick(event:TimerEvent):void
        {
            if (_pendingText.length >= 0 && onChange != null)
                onChange(_pendingText);
            _pendingText = "";
        }

        private function _flushDebounce():void
        {
            if (_debounceTimer && _debounceTimer.running)
            {
                _debounceTimer.stop();
                if (_pendingText.length >= 0 && onChange != null)
                    onChange(_pendingText);
                _pendingText = "";
            }
        }

        private function _killDebounce():void
        {
            if (_debounceTimer)
            {
                _debounceTimer.stop();
                _debounceTimer.removeEventListener(TimerEvent.TIMER_COMPLETE,
                    _onDebounceTick);
                _debounceTimer = null;
            }
            _pendingText = "";
        }

        /** 点击背景 → 聚焦到 TextField。 */
        private function _onBgClick(event:MouseEvent):void
        {
            if (_tf && _editable && stage)
                stage.focus = _tf;
        }
    }
}
