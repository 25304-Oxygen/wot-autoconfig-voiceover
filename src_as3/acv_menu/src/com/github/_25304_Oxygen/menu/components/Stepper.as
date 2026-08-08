package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 带滑块的步进器——卡通风格，Dark+ 配色。
     *
     * 水平滑块 + 值标签。支持拖拽拇指、点击轨道跳转、步进吸附。
     *
     * 用法:
     *   var stepper:Stepper = new Stepper(240, 0, 100, 50, 5);
     *   stepper.onChange = function(value:Number):void { ... };
     *   addChild(stepper);
     */
    public class Stepper extends Sprite implements ISoundable
    {
        // ═══════════════════════════════════════════════════════
        // 尺寸 & 颜色
        // ═══════════════════════════════════════════════════════

        private static const TRACK_H:int = 8;
        private static const TRACK_RADIUS:int = 4;

        private static const THUMB_D:int = 22;       // 矩形滑块高度
        private static const THUMB_W:int = 8;        // 矩形滑块宽度
        private static const THUMB_R:int = 11;       // 兼容旧计算（=THUMB_D/2）

        private static const LABEL_W:int = 30;
        private static const LABEL_GAP:int = 2;

        private static const STROKE_W:Number    = 1;

        // 布局
        private static const TRACK_Y:int = 12;   // 轨道中心 Y（THUMB_D/2）
        private static const TRACK_LEFT:int = 0;
        private static const OVERALL_H:int = 28;

        // ═══════════════════════════════════════════════════════

        private var _trackW:Number;   // 轨道实际可用宽度（总宽 - 标签宽 - 间距）
        private var _min:Number;
        private var _max:Number;
        private var _value:Number;
        private var _step:Number;

        private var _track:Shape;
        private var _progress:Shape;
        private var _trackHit:Sprite;  // 轨道点击区域（仅轨道，不含标签）
        private var _thumb:Sprite;
        private var _labelTF:TextField;

        private var _dragging:Boolean = false;
        private var _dragOffsetX:Number = 0;
        private var _dragStartValue:Number = 0;  // 拖拽开始时的值，用于判断结束时是否变化

        /** 缓存的 stage 引用，用于全局坐标转换。 */
        private var _stage:*;

        /** 值变更回调: function(value:Number):void */
        public var onChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param totalW   组件总宽度
         * @param min      最小值
         * @param max      最大值
         * @param value    初始值
         * @param step     步长
         */
        public function Stepper(totalW:Number, min:Number, max:Number,
                                 value:Number, step:Number = 1)
        {
            super();
            _min = min;
            _max = max;
            _value = _clamp(value);
            _step = step;
            _trackW = totalW - LABEL_W - LABEL_GAP;

            _build();
        }

        private function _build():void
        {
            // 轨道背景
            _track = new Shape();
            _drawTrack();
            addChild(_track);

            // 进度填充
            _progress = new Shape();
            _drawProgress();
            addChild(_progress);

            // 拇指
            _thumb = new Sprite();
            _thumb.buttonMode = true;      // 显示手型光标
            _thumb.mouseChildren = false;  // 无子对象，防止将来意外
            _drawThumb();
            _thumb.addEventListener(MouseEvent.MOUSE_DOWN, _onThumbDown);
            addChild(_thumb);

            // 值标签
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = Theme.textPrimary;
            fmt.align = "center";

            _labelTF = new TextField();
            _labelTF.defaultTextFormat = fmt;
            _labelTF.text = String(_value);
            _labelTF.selectable = false;
            _labelTF.mouseEnabled = false;
            _labelTF.x = _trackW + LABEL_GAP;
            _labelTF.y = int((OVERALL_H - 18) / 2);
            _labelTF.width = LABEL_W;
            _labelTF.height = 18;
            addChild(_labelTF);

            // 不响应鼠标滚轮——防止滚动面板时误触改变值

            // 轨道点击区域——仅轨道显示手型光标，标签区域不显示
            _trackHit = new Sprite();
            _trackHit.buttonMode = true;
            _trackHit.mouseChildren = false;
            // 用透明 Shape 定义点击区域（覆盖轨道，与拇指同高）
            var hitBg:Shape = new Shape();
            hitBg.graphics.beginFill(0x000000, 0);  // 完全透明
            hitBg.graphics.drawRect(TRACK_LEFT, TRACK_Y - THUMB_R,
                _trackW, THUMB_D);
            hitBg.graphics.endFill();
            _trackHit.addChild(hitBg);
            _trackHit.addEventListener(MouseEvent.MOUSE_DOWN, _onTrackDown);
            addChild(_trackHit);

            _updateThumbPosition();

            // 游戏 UI 音效
            SoundUtils.registerSound(this);

            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        public function get value():Number { return _value; }

        /** 程序化设置值。 */
        public function setValue(val:Number, dispatch:Boolean = true):void
        {
            var newVal:Number = _clamp(_snap(val));
            if (_value == newVal) return;
            _value = newVal;
            _labelTF.text = String(_value);
            _drawProgress();
            _updateThumbPosition();

            if (dispatch && onChange != null)
                onChange(_value);
        }

        /** 更新 min/max/step。 */
        public function setRange(min:Number, max:Number, step:Number = 0):void
        {
            _min = min;
            _max = max;
            if (step > 0) _step = step;
            setValue(_value, false);
        }

        /** 销毁。 */
        public function dispose():void
        {
            SoundUtils.removeSound(this);
            if (_stage)
            {
                _stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onStageMove);
                _stage.removeEventListener(MouseEvent.MOUSE_UP, _onStageUp);
            }
            _thumb.removeEventListener(MouseEvent.MOUSE_DOWN, _onThumbDown);
            if (_trackHit)
                _trackHit.removeEventListener(MouseEvent.MOUSE_DOWN, _onTrackDown);
            Theme.unregister(this);
            onChange = null;
        }

        // ═══════════════════════════════════════════════════════
        // ISoundable
        // ═══════════════════════════════════════════════════════

        public function canPlaySound(type:String):Boolean { return !SoundUtils.muted; }

        public function getSoundType():String { return "normal"; }

        public function getSoundId():String { return ""; }

        // ═══════════════════════════════════════════════════════
        // 绘制
        // ═══════════════════════════════════════════════════════

        private function _drawTrack():void
        {
            _track.graphics.clear();
            _track.graphics.lineStyle(STROKE_W, Theme.stroke);
            _track.graphics.beginFill(Theme.surface2, 1.0);
            _track.graphics.drawRoundRect(TRACK_LEFT, TRACK_Y - TRACK_H / 2,
                _trackW, TRACK_H, TRACK_RADIUS * 2, TRACK_RADIUS * 2);
            _track.graphics.endFill();
        }

        private function _drawProgress():void
        {
            _progress.graphics.clear();
            var ratio:Number = (_value - _min) / (_max - _min);
            var progressW:Number = ratio * _trackW;
            if (progressW > 0)
            {
                _progress.graphics.beginFill(Theme.accent, 1.0);
                _progress.graphics.drawRoundRect(TRACK_LEFT, TRACK_Y - TRACK_H / 2,
                    progressW, TRACK_H, TRACK_RADIUS * 2, TRACK_RADIUS * 2);
                _progress.graphics.endFill();
            }
        }

        private function _drawThumb():void
        {
            _thumb.graphics.clear();
            _thumb.graphics.lineStyle(STROKE_W, Theme.stroke);
            _thumb.graphics.beginFill(Theme.accentHover, 1.0);
            _thumb.graphics.drawRoundRect(0, 0, THUMB_W, THUMB_D, 4, 4);
            _thumb.graphics.endFill();

            // 内高光
            _thumb.graphics.lineStyle(1, 0xFFFFFF, 0.25);
            _thumb.graphics.drawRoundRect(2, 2, THUMB_W - 4, THUMB_D - 4, 2, 2);
        }

        /** 根据 value 更新拇指位置。矩形滑块以左边缘居中于值位置。 */
        private function _updateThumbPosition():void
        {
            var ratio:Number = (_value - _min) / (_max - _min);
            _thumb.x = TRACK_LEFT + ratio * _trackW - THUMB_W / 2;
            _thumb.y = TRACK_Y - THUMB_R;  // 高度仍为 THUMB_D=22，垂直居中不变
        }

        /** 主题刷新回调——重建所有颜色相关的绘制。 */
        private function _refreshStyle():void
        {
            _drawTrack();
            _drawProgress();
            _drawThumb();
            _updateThumbPosition();
            if (_labelTF)
            {
                var fmt:TextFormat = _labelTF.defaultTextFormat;
                fmt.color = Theme.textPrimary;
                _labelTF.defaultTextFormat = fmt;
                _labelTF.textColor = Theme.textPrimary;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 交互
        // ═══════════════════════════════════════════════════════

        private function _onThumbDown(event:MouseEvent):void
        {
            _dragging = true;
            _dragStartValue = _value;  // 记录起始值，用于 mouseUp 时判断是否变化
            _stage = stage;
            // this.mouseX 自动穿越所有父级变换（含 content.y 滚动偏移），
            // 比 globalToLocal 更可靠，尤其在 Scaleform 的 scrollRect 嵌套中。
            _dragOffsetX = this.mouseX - TRACK_LEFT - _thumb.x;
            if (_stage)
            {
                _stage.addEventListener(MouseEvent.MOUSE_MOVE, _onStageMove);
                _stage.addEventListener(MouseEvent.MOUSE_UP, _onStageUp);
            }
            // 不阻止冒泡——_onTrackDown 通过 _dragging 检查正确处理
        }

        /** 鼠标滚轮——每次滚动改变一个步长的值，阻止冒泡防止外层 ScrollPane 同时滚动。 */
        private function _onMouseWheel(event:MouseEvent):void
        {
            var delta:int = event.delta > 0 ? 1 : -1;
            var newVal:Number = _value + delta * _step;
            setValue(newVal);
            event.stopImmediatePropagation();
        }

        /** 点击轨道：值跳到点击位置，并进入拖拽模式——
         *  按住不松手直接拖动，跟拖拽拇指体验一致。 */
        private function _onTrackDown(event:MouseEvent):void
        {
            if (_dragging) return;
            _dragging = true;
            _dragStartValue = _value;  // 记录起始值
            _stage = stage;
            _dragOffsetX = 0;  // 点击轨道，值直接从鼠标位置计算
            if (_stage)
            {
                _stage.addEventListener(MouseEvent.MOUSE_MOVE, _onStageMove);
                _stage.addEventListener(MouseEvent.MOUSE_UP, _onStageUp);
            }
            // 立刻更新值到点击位置，但不派发 onChange（等 mouseUp）
            var localX:Number = this.mouseX - TRACK_LEFT;
            var ratio:Number = Math.max(0, Math.min(1, localX / _trackW));
            setValue(_min + ratio * (_max - _min), false);
        }

        private function _onStageMove(event:MouseEvent):void
        {
            if (!_dragging || !_stage) return;
            // 与 _onThumbDown 一致：用 this.mouseX 代替 globalToLocal
            var localX:Number = this.mouseX - TRACK_LEFT - _dragOffsetX;
            var ratio:Number = Math.max(0, Math.min(1, localX / _trackW));
            var rawVal:Number = _min + ratio * (_max - _min);
            setValue(rawVal, false);  // 拖拽过程中不派发 onChange，等 mouseUp
        }

        private function _onStageUp(event:MouseEvent):void
        {
            if (!_dragging) return;
            _dragging = false;
            if (_stage)
            {
                _stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onStageMove);
                _stage.removeEventListener(MouseEvent.MOUSE_UP, _onStageUp);
            }
            // 拖拽/点击结束时才派发 onChange，避免拖拽过程中日志刷屏
            if (_value != _dragStartValue && onChange != null)
                onChange(_value);
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
            if (_step <= 0) return val;
            return Math.round((val - _min) / _step) * _step + _min;
        }
    }
}
