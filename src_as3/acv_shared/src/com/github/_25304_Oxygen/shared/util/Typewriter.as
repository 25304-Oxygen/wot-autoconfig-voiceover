package com.github._25304_Oxygen.shared.util
{
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.geom.Rectangle;
    import flash.utils.Timer;
    import flash.events.TimerEvent;

    /**
     * 打字机效果——用 mask 逐字露出文本。
     *
     * 策略: 全文一次性填入 TextField，通过 Shape mask 逐字露出。
     * 避免每帧截断 substring + setTextFormat 触发的 Scaleform 文本重排版，
     * 与设置页打字预览（SettingsPage._previewMask）采用相同实现方式。
     *
     * 用法:
     *   var tw:Typewriter = new Typewriter(myTextField, "要显示的文本", 2.0);
     *   tw.onComplete = function():void { Log.info("文字显示完成"); };
     *   tw.start();
     *
     *   // 点击跳过动画，立即显示全部文字
     *   tw.skip();
     *
     *   // 中途停止
     *   tw.stop();
     */
    public class Typewriter
    {
        /** 模块级日志器 */
        private static const L:Object = Log.getLogger("Typewriter");

        /** getCharBoundaries 矩形外扩余量（Scaleform 度量缺陷补偿，见 _cacheCharRects）。 */
        private static const CHAR_RECT_TOP_OVERHANG:Number = 1;
        private static const CHAR_RECT_BOTTOM_OVERHANG:Number = 4;

        private var _tf:TextField;
        private var _fullText:String;
        private var _delay:Number;          // ms/字
        private var _format:TextFormat;
        private var _timer:Timer;
        private var _mask:Shape;
        private var _charRects:Array;       // Rectangle[]，每字符像素边界（null=不可见字符）
        private var _charIndex:int = 0;
        private var _active:Boolean = false;

        /** 完成回调。 */
        public var onComplete:Function;

        /**
         * @param tf         目标 TextField（内容将被此组件接管）
         * @param text       要逐字显示的完整文本
         * @param duration   总持续时间（秒），默认 2.0
         * @param format     文本格式（可选，用于 setTextFormat）
         */
        public function Typewriter(tf:TextField, text:String, duration:Number = 2.0,
                                    format:TextFormat = null)
        {
            _tf = tf;
            _fullText = text;
            _format = format;

            // duration 秒 / text.length 字 = 秒/字 → ×1000 = ms/字
            if (text.length > 0)
                _delay = duration / text.length * 1000;
            else
                _delay = 0;

            _mask = new Shape();
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 开始逐字显示。mask 先就位（空 mask=文本不可见），再填文本。 */
        public function start():void
        {
            if (_active) return;
            _active = true;

            // mask 必须先加入显示列表并绑定到 _tf，再设置文本。
            // 此时 _charIndex=0 → _updateMask 什么也不画 → 文本完全被遮。
            if (_tf.parent)
            {
                _mask.x = _tf.x;
                _mask.y = _tf.y;
                _tf.parent.addChild(_mask);
                _tf.mask = _mask;
            }

            // mask 就位后再填文本
            _tf.text = _fullText;
            if (_format)
                _tf.setTextFormat(_format);

            // 速度为 0 或空文本 → 全文直接可见
            if (_delay <= 0 || _fullText.length == 0)
            {
                _charIndex = _fullText.length;
                _updateMask();
                _finish();
                return;
            }

            // 缓存每个字符的精确像素矩形
            _cacheCharRects();

            _charIndex = 0;
            _updateMask();

            // 定时器: 每 _delay ms 露出一个字符
            _timer = new Timer(_delay, _fullText.length);
            _timer.addEventListener(TimerEvent.TIMER, _onTick);
            _timer.addEventListener(TimerEvent.TIMER_COMPLETE, _onFinish);
            _timer.start();

            L.debug("启动: " + _fullText.length + "字 / " +
                       _delay.toFixed(0) + "ms/字");
        }

        /** 跳过动画，立即显示全部文字。 */
        public function skip():void
        {
            if (!_active) return;
            _cleanup();
            _tf.text = _fullText;
            if (_format)
                _tf.setTextFormat(_format);
            L.debug("跳过");
            _finish();
        }

        /** 中途停止（不触发 onComplete）。 */
        public function stop():void
        {
            if (!_active) return;
            _cleanup();
            _active = false;
            L.debug("已停止");
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        /** 定时器每 tick 露出一个字符。 */
        private function _onTick(e:TimerEvent):void
        {
            _charIndex++;
            _updateMask();
        }

        /** 定时器完成——全部字符已露出。 */
        private function _onFinish(e:TimerEvent = null):void
        {
            L.debug("完成");
            _cleanup();
            _finish();
        }

        /** 通知完成回调。 */
        private function _finish():void
        {
            _active = false;
            if (onComplete != null)
                onComplete();
        }

        /** 根据 _charIndex 重绘 mask——逐字精确矩形露出。 */
        private function _updateMask():void
        {
            var g:Object = _mask.graphics;
            g.clear();

            // Scaleform 会忽略"零绘制"的 Shape mask（认为 mask 无效），导致全文暴露。
            // charIndex=0 时画一个 1×1 像素种子矩形，让 mask 始终有效。
            if (_charIndex <= 0 || !_charRects)
            {
                g.beginFill(0x000000);
                g.drawRect(0, 0, 1, 1);
                g.endFill();
                return;
            }

            g.beginFill(0x000000);

            var end:int = Math.min(_charIndex, _charRects.length);
            for (var i:int = 0; i < end; i++)
            {
                var r:Rectangle = _charRects[i] as Rectangle;
                if (r)
                    g.drawRect(r.x, r.y, r.width, r.height);
            }
            g.endFill();
        }

        /** 缓存每个字符的精确像素矩形（getCharBoundaries）。
         *  不可见字符（换行等）返回 null，_updateMask 跳过。 */
        private function _cacheCharRects():void
        {
            _charRects = [];

            // Scaleform 度量缺陷补偿：getCharBoundaries 对 Latin 字形底部只到
            // baseline，不含 descender（y/g/p/q/j 等下降笔画下半截会被 mask
            // 盖住，表现为 "y" 变 "v"）。按字号比例向下补余量，保证下降笔画
            // 完整露出；顶部固定补 1px 防御 ascender 顶部切边。余量画的是
            // baseline 下方空白，不会提前露出相邻字符；行间 gap 大于余量，
            // 也不会漏到下一行。
            var fmt:TextFormat = _format ? _format : _tf.defaultTextFormat;
            var size:Number = (fmt && fmt.size) ? Number(fmt.size) : 13;
            var bottomOverhang:Number = Math.max(CHAR_RECT_BOTTOM_OVERHANG,
                                                 Math.ceil(size * 0.2));

            for (var i:int = 0; i < _fullText.length; i++)
            {
                var r:Rectangle = _tf.getCharBoundaries(i);
                if (r)
                    _charRects.push(new Rectangle(r.x, r.y - CHAR_RECT_TOP_OVERHANG,
                        r.width, r.height + CHAR_RECT_TOP_OVERHANG + bottomOverhang));
                else
                    _charRects.push(null);
            }
        }

        /** 停止定时器、移除 mask、清理 _tf.mask 引用。 */
        private function _cleanup():void
        {
            if (_timer)
            {
                _timer.stop();
                _timer.removeEventListener(TimerEvent.TIMER, _onTick);
                _timer.removeEventListener(TimerEvent.TIMER_COMPLETE, _onFinish);
                _timer = null;
            }
            if (_mask)
            {
                if (_tf && _tf.mask == _mask)
                    _tf.mask = null;
                if (_mask.parent)
                    _mask.parent.removeChild(_mask);
            }
        }
    }
}
