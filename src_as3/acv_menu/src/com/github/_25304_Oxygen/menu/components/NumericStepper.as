package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;
    import flash.events.Event;

    /**
     * 数字步进器——直角双段式：左侧数字 + 右侧日字箭头。
     *
     * 布局:
     *   ┌───────┬───┐
     *   │              │  ▲  │
     *   │     42       │───│
     *   │              │  ▼  │
     *   └───────┴───┘
     *
     * 长按箭头自动连发（250ms 初始延迟 → 60ms 间隔）。
     * 鼠标滚轮即时增减。
     *
     * 用法:
     *   var ns:NumericStepper = new NumericStepper(0, 100, 50, 5);
     *   ns.onChange = function(value:Number):void { ... };
     *   addChild(ns);
     */
    public class NumericStepper extends Sprite
    {
        // ═══════════════════════════════════════════════════════
        // 布局常量
        // ═══════════════════════════════════════════════════════

        /** 默认整体尺寸。 */
        private static const DEFAULT_W:int = 100;
        private static const DEFAULT_H:int = 28;

        /** 右侧箭头区宽度。 */
        private static const ARROW_W:int = 24;

        /** 描边宽度。 */
        private static const STROKE:Number = 1;

        /** 箭头三角形半边长。 */
        private static const ARROW_HALF:Number = 4;

        /** 长按连发: 初始延迟 (ms)。 */
        private static const REPEAT_DELAY:int = 250;

        /** 长按连发: 间隔 (ms)。 */
        private static const REPEAT_INTERVAL:int = 60;

        // ═══════════════════════════════════════════════════════
        // 属性
        // ═══════════════════════════════════════════════════════

        private var _totalW:Number;
        private var _totalH:Number;
        private var _numberW:Number;

        private var _min:Number;
        private var _max:Number;
        private var _value:Number;
        private var _step:Number;

        // 子对象
        private var _numberBg:Shape;     // 数字区背景
        private var _numberTF:TextField;
        private var _upBtn:Sprite;
        private var _downBtn:Sprite;
        private var _divider:Shape;      // 日字中间横线
        private var _border:Shape;       // 最顶层外框

        // 连发状态
        private var _holdDirection:int = 0;   // 1 = up, -1 = down, 0 = none
        private var _holdElapsed:int = 0;
        private var _holdArmed:Boolean = false;

        // 按钮 hover 状态（用于重绘高亮）
        private var _upHovered:Boolean = false;
        private var _downHovered:Boolean = false;
        private var _upPressed:Boolean = false;
        private var _downPressed:Boolean = false;

        /** 值变更回调: function(value:Number):void */
        public var onChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param min    最小值
         * @param max    最大值
         * @param value  初始值
         * @param step   步长 (默认 1)
         * @param w      组件总宽度 (默认 100)
         * @param h      组件总高度 (默认 28)
         */
        public function NumericStepper(min:Number, max:Number, value:Number,
                                        step:Number = 1,
                                        w:Number = DEFAULT_W, h:Number = DEFAULT_H)
        {
            super();
            _min = min;
            _max = max;
            _step = step > 0 ? step : 1;
            _value = _clamp(_snap(value));
            _totalW = w;
            _totalH = h;
            _numberW = _totalW - ARROW_W;

            _build();
        }

        private function _build():void
        {
            // ── 数字区背景（最底层）──
            _numberBg = new Shape();
            addChild(_numberBg);
            _redrawNumberBg();

            // ── 数字显示文本 ──
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 13;
            fmt.color = Theme.textPrimary;
            fmt.align = "center";

            _numberTF = new TextField();
            _numberTF.defaultTextFormat = fmt;
            _numberTF.text = String(_value);
            _numberTF.selectable = false;
            _numberTF.mouseEnabled = false;
            _numberTF.width = _numberW;
            _numberTF.height = 20;
            _numberTF.x = 0;
            _numberTF.y = int((_totalH - 20) / 2);
            addChild(_numberTF);

            // ── 右侧日字箭头区 ──
            var arrowX:Number = _numberW;

            // 上下分割线（日字中间那一横）
            _divider = new Shape();
            _divider.x = arrowX;
            _divider.y = int(_totalH / 2);
            addChild(_divider);

            _upBtn = new Sprite();
            _upBtn.buttonMode = true;
            _upBtn.mouseChildren = false;
            _upBtn.x = arrowX;
            _upBtn.y = 0;
            addChild(_upBtn);

            _downBtn = new Sprite();
            _downBtn.buttonMode = true;
            _downBtn.mouseChildren = false;
            _downBtn.x = arrowX;
            _downBtn.y = int(_totalH / 2);
            addChild(_downBtn);

            _redrawDivider();
            _drawUpBtn(Theme.surface1);
            _drawDownBtn(Theme.surface1);

            // ── 最顶层边框（确保不被子对象遮挡）──
            _border = new Shape();
            addChild(_border);
            _redrawBorder();

            // ── 事件 ──
            _upBtn.addEventListener(MouseEvent.MOUSE_OVER,   _onUpOver);
            _upBtn.addEventListener(MouseEvent.MOUSE_OUT,    _onUpOut);
            _upBtn.addEventListener(MouseEvent.MOUSE_DOWN,   _onUpDown);
            _downBtn.addEventListener(MouseEvent.MOUSE_OVER, _onDownOver);
            _downBtn.addEventListener(MouseEvent.MOUSE_OUT,  _onDownOut);
            _downBtn.addEventListener(MouseEvent.MOUSE_DOWN, _onDownDown);

            // 鼠标滚轮（捕获阶段，阻止冒泡）
            this.addEventListener(MouseEvent.MOUSE_WHEEL, _onWheel,
                false, 0, true);

            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 公开 API
        // ═══════════════════════════════════════════════════════

        public function get value():Number { return _value; }

        public function setValue(val:Number, dispatch:Boolean = true):void
        {
            var newVal:Number = _clamp(_snap(val));
            if (_value == newVal) return;
            _value = newVal;
            _numberTF.text = String(_value);

            if (dispatch && onChange != null)
                onChange(_value);
        }

        /** 更新范围与步长。不改变当前值（但会 clamp）。 */
        public function setRange(min:Number, max:Number, step:Number = 0):void
        {
            _min = min;
            _max = max;
            if (step > 0) _step = step;
            setValue(_value, false);
        }

        /** 步进（正数为增，负数为减）。 */
        public function step(direction:int):void
        {
            setValue(_value + direction * _step);
        }

        /** 销毁。 */
        public function dispose():void
        {
            _stopRepeat();
            _upBtn.removeEventListener(MouseEvent.MOUSE_OVER,   _onUpOver);
            _upBtn.removeEventListener(MouseEvent.MOUSE_OUT,    _onUpOut);
            _upBtn.removeEventListener(MouseEvent.MOUSE_DOWN,   _onUpDown);
            _downBtn.removeEventListener(MouseEvent.MOUSE_OVER, _onDownOver);
            _downBtn.removeEventListener(MouseEvent.MOUSE_OUT,  _onDownOut);
            _downBtn.removeEventListener(MouseEvent.MOUSE_DOWN, _onDownDown);
            this.removeEventListener(MouseEvent.MOUSE_WHEEL, _onWheel);
            Theme.unregister(this);
            onChange = null;
        }

        // ═══════════════════════════════════════════════════════
        // 绘制
        // ═══════════════════════════════════════════════════════

        /** 绘制箭头按钮背景。 */
        private function _drawArrowBtn(target:Sprite, fillColor:uint,
                                       btnW:Number, btnH:Number):void
        {
            target.graphics.clear();
            target.graphics.beginFill(fillColor, 1.0);
            target.graphics.drawRect(0, 0, btnW, btnH);
            target.graphics.endFill();
        }

        /** 绘制 ▲ 三角形。 */
        private function _drawUpArrow(target:Sprite, color:uint):void
        {
            var cx:Number = ARROW_W / 2;
            var cy:Number = target.height / 2;
            // 让三角形稍微偏上一点
            var topY:Number = cy - ARROW_HALF;
            var botY:Number = cy + ARROW_HALF;
            target.graphics.beginFill(color, 1.0);
            target.graphics.moveTo(cx, topY);
            target.graphics.lineTo(cx - ARROW_HALF, botY);
            target.graphics.lineTo(cx + ARROW_HALF, botY);
            target.graphics.lineTo(cx, topY);
            target.graphics.endFill();
        }

        /** 绘制 ▼ 三角形。 */
        private function _drawDownArrow(target:Sprite, color:uint):void
        {
            var cx:Number = ARROW_W / 2;
            var cy:Number = target.height / 2;
            var topY:Number = cy - ARROW_HALF;
            var botY:Number = cy + ARROW_HALF;
            target.graphics.beginFill(color, 1.0);
            target.graphics.moveTo(cx, botY);
            target.graphics.lineTo(cx - ARROW_HALF, topY);
            target.graphics.lineTo(cx + ARROW_HALF, topY);
            target.graphics.lineTo(cx, botY);
            target.graphics.endFill();
        }

        /** 上按钮: 背景 + 箭头。 */
        private function _drawUpBtn(bgColor:uint):void
        {
            var h:Number = int(_totalH / 2);
            _drawArrowBtn(_upBtn, bgColor, ARROW_W, h);
            _drawUpArrow(_upBtn, Theme.textPrimary);
        }

        /** 下按钮: 背景 + 箭头。 */
        private function _drawDownBtn(bgColor:uint):void
        {
            var h:Number = _totalH - int(_totalH / 2);
            _drawArrowBtn(_downBtn, bgColor, ARROW_W, h);
            _drawDownArrow(_downBtn, Theme.textPrimary);
        }

        /** 数字区背景填充。 */
        private function _redrawNumberBg():void
        {
            _numberBg.graphics.clear();
            _numberBg.graphics.beginFill(Theme.surface1, 1.0);
            _numberBg.graphics.drawRect(0, 0, _numberW, _totalH);
            _numberBg.graphics.endFill();
        }

        /** 日字中间横线。 */
        private function _redrawDivider():void
        {
            _divider.graphics.clear();
            _divider.graphics.lineStyle(STROKE, Theme.stroke);
            _divider.graphics.moveTo(0, 0);
            _divider.graphics.lineTo(ARROW_W, 0);
        }

        /** 画整体外框（最顶层 Shape，直角矩形）。 */
        private function _redrawBorder():void
        {
            _border.graphics.clear();
            _border.graphics.lineStyle(STROKE, Theme.stroke);
            _border.graphics.drawRect(0, 0, _totalW, _totalH);
        }

        // ═══════════════════════════════════════════════════════
        // 颜色状态
        // ═══════════════════════════════════════════════════════

        private function _upFillColor():uint
        {
            if (_upPressed)   return Theme.accentPress;
            if (_upHovered)   return Theme.accentHover;
            return Theme.surface1;
        }

        private function _downFillColor():uint
        {
            if (_downPressed)   return Theme.accentPress;
            if (_downHovered)   return Theme.accentHover;
            return Theme.surface1;
        }

        // ═══════════════════════════════════════════════════════
        // 主题刷新
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            _redrawNumberBg();
            _drawUpBtn(_upFillColor());
            _drawDownBtn(_downFillColor());
            _redrawDivider();
            _redrawBorder();

            if (_numberTF)
            {
                var fmt:TextFormat = _numberTF.defaultTextFormat;
                fmt.color = Theme.textPrimary;
                _numberTF.defaultTextFormat = fmt;
                _numberTF.textColor = Theme.textPrimary;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 鼠标事件 —— 上按钮
        // ═══════════════════════════════════════════════════════

        private function _onUpOver(event:MouseEvent):void
        {
            _upHovered = true;
            _drawUpBtn(_upFillColor());
        }

        private function _onUpOut(event:MouseEvent):void
        {
            _upHovered = false;
            _upPressed = false;
            _drawUpBtn(_upFillColor());
        }

        private function _onUpDown(event:MouseEvent):void
        {
            _upPressed = true;
            _drawUpBtn(_upFillColor());
            setValue(_value + _step);
            _startRepeat(1);

            if (stage)
                stage.addEventListener(MouseEvent.MOUSE_UP, _onStageUp);
        }

        // ═══════════════════════════════════════════════════════
        // 鼠标事件 —— 下按钮
        // ═══════════════════════════════════════════════════════

        private function _onDownOver(event:MouseEvent):void
        {
            _downHovered = true;
            _drawDownBtn(_downFillColor());
        }

        private function _onDownOut(event:MouseEvent):void
        {
            _downHovered = false;
            _downPressed = false;
            _drawDownBtn(_downFillColor());
        }

        private function _onDownDown(event:MouseEvent):void
        {
            _downPressed = true;
            _drawDownBtn(_downFillColor());
            setValue(_value - _step);
            _startRepeat(-1);

            if (stage)
                stage.addEventListener(MouseEvent.MOUSE_UP, _onStageUp);
        }

        // ═══════════════════════════════════════════════════════
        // 鼠标事件 —— Stage 全局释放
        // ═══════════════════════════════════════════════════════

        private function _onStageUp(event:MouseEvent):void
        {
            if (stage)
                stage.removeEventListener(MouseEvent.MOUSE_UP, _onStageUp);

            _upPressed = false;
            _downPressed = false;
            _drawUpBtn(_upFillColor());
            _drawDownBtn(_downFillColor());
            _stopRepeat();
        }

        // ═══════════════════════════════════════════════════════
        // 鼠标事件 —— 滚轮
        // ═══════════════════════════════════════════════════════

        private function _onWheel(event:MouseEvent):void
        {
            var delta:int = event.delta > 0 ? 1 : -1;
            setValue(_value + delta * _step);
            event.stopImmediatePropagation();
        }

        // ═══════════════════════════════════════════════════════
        // 长按连发
        // ═══════════════════════════════════════════════════════

        private function _startRepeat(direction:int):void
        {
            _holdDirection = direction;
            _holdElapsed = 0;
            _holdArmed = false;
            this.addEventListener(Event.ENTER_FRAME, _onEnterFrame);
        }

        private function _stopRepeat():void
        {
            _holdDirection = 0;
            _holdArmed = false;
            this.removeEventListener(Event.ENTER_FRAME, _onEnterFrame);
        }

        private function _onEnterFrame(event:Event):void
        {
            // Scaleform ENTER_FRAME 的帧间隔约为 16ms (60fps)
            // 无法精确计时 → 基于帧计数近似
            // 实际上 Scaleform 中 event 无 delta，用帧计数
            _holdElapsed += 16;  // 近似 60fps

            if (!_holdArmed)
            {
                if (_holdElapsed >= REPEAT_DELAY)
                {
                    _holdArmed = true;
                    _holdElapsed = 0;
                }
                else
                {
                    return;
                }
            }

            if (_holdElapsed >= REPEAT_INTERVAL)
            {
                _holdElapsed -= REPEAT_INTERVAL;
                setValue(_value + _holdDirection * _step);
            }
        }

        // ═══════════════════════════════════════════════════════
        // 工具
        // ═══════════════════════════════════════════════════════

        private function _clamp(val:Number):Number
        {
            if (val < _min) return _min;
            if (val > _max) return _max;
            return val;
        }

        private function _snap(val:Number):Number
        {
            return Math.round((val - _min) / _step) * _step + _min;
        }
    }
}
