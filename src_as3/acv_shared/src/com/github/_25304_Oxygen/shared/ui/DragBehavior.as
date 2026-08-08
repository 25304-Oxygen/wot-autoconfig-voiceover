package com.github._25304_Oxygen.shared.ui
{
    import flash.display.Sprite;
    import flash.display.Stage;
    import flash.events.MouseEvent;
    import flash.events.Event;
    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.tween.Tween;
    import com.github._25304_Oxygen.shared.tween.Easing;

    /**
     * 可复用的窗口拖拽行为 + 屏幕缩放回弹。
     *
     * 碰撞体积: 窗口的矩形边界即碰撞区，通过 margins 控制至少保留
     * 多少像素在屏幕内。窗口不缩放，所以碰撞区大小固定。
     *
     * 拖拽手柄: 可以是任意形状的 Sprite——画圆即圆手柄，画三角即三角手柄。
     * handle 上设置 buttonMode=true + mouseChildren=false 即可。
     *
     * 屏幕缩放: stage resize 时自动重新 clamp 位置并以 Tween 平滑回弹。
     *
     * 用法:
     *   var drag: DragBehavior = new DragBehavior(_windowContainer, _titleBar, onMoved);
     *   drag.setMargins(40, 40, 28, 40);    // left, right, top, bottom
     *   drag.enabled = false;                // 禁用拖拽（字幕调试开关）
     *
     * 销毁时调用 dispose() 移除包括 resize 在内的所有事件监听。
     */
    public class DragBehavior
    {
        /** 模块级日志器 */
        private static const L:Object = Log.getLogger("DragBehavior");

        // ── 拖拽目标 & 手柄 ──────────────────────────
        private var _target:Sprite;
        private var _handle:Sprite;

        // ── 拖拽状态 ────────────────────────────────
        private var _dragging:Boolean = false;
        private var _didMove:Boolean = false;    // 是否真正发生过位移
        private var _offsetX:Number = 0;
        private var _offsetY:Number = 0;

        // ── 把手尺寸（用于计算 minX/minY，确保把手始终可操作） ──
        private var _handleW:Number = 0;   // 0 = 使用 _target.width
        private var _handleH:Number = 0;   // 0 = 使用 _target.height

        // ── 屏幕边界留白（px） ──────────────────────
        private var _marginLeft:Number   = 40;
        private var _marginRight:Number  = 40;
        private var _marginTop:Number    = 0;
        private var _marginBottom:Number = 40;

        // ── 回调 ────────────────────────────────────
        private var _onMove:Function;     // function(x:Number, y:Number):void
        private var _enabled:Boolean = true;

        // ── 缓存的 stage 引用 ─────────────────────
        private var _stage:Stage;
        private var _hasResizeListener:Boolean = false;

        // ═══════════════════════════════════════════════════
        // 构造函数
        // ═══════════════════════════════════════════════════

        /**
         * @param target  被拖拽移动的显示对象（通常是窗口容器）。
         *                这个 Sprite 的矩形边界 = 碰撞体积。
         * @param handle  响应鼠标按下的事件源（通常是标题栏）。
         *                可以是任意 Sprite——画圆即圆手柄，画三角即三角手柄。
         * @param onMove  拖拽结束回调，参数 (x:Number, y:Number)
         */
        public function DragBehavior(target:Sprite, handle:Sprite, onMove:Function = null)
        {
            _target = target;
            _handle = handle;
            _onMove = onMove;

            if (_target.stage)
                _stage = _target.stage;

            _handle.addEventListener(MouseEvent.MOUSE_DOWN, _onDragStart);
            L.info("已绑定");
        }

        // ═══════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════

        /**
         * 设置屏幕边界留白——拖拽时窗口至少保留这些像素在屏幕内。
         * @param left   左侧最少可见 px（典型值 40）
         * @param right  右侧最少可见 px（典型值 40）
         * @param top    顶部最少可见 px（典型值 = 标题栏高度，如 28）
         * @param bottom 底部最少可见 px（典型值 40）
         */
        public function setMargins(left:Number, right:Number, top:Number, bottom:Number):void
        {
            _marginLeft   = left;
            _marginRight  = right;
            _marginTop    = top;
            _marginBottom = bottom;
        }

        /**
         * 设置拖拽把手在 target 内的尺寸。
         * 用于计算 minX/minY——确保把手至少有 margin 像素保留在屏幕内。
         * 不设置时默认使用 _target.width / _target.height。
         *
         * @param w  把手宽度（相对于 target 坐标系的 x=0）
         * @param h  把手高度（相对于 target 坐标系的 y=0）
         */
        public function setHandleBounds(w:Number, h:Number):void
        {
            _handleW = w;
            _handleH = h;
        }

        /** 启用/禁用拖拽。字幕调试时设为 false。 */
        public function set enabled(value:Boolean):void
        {
            if (_enabled != value)
                L.info("拖拽 " + (value ? "启用" : "禁用"));
            _enabled = value;
        }

        public function get enabled():Boolean
        {
            return _enabled;
        }

        /** 立即执行一次边界约束（供外部 resize 处理调用）。 */
        public function clamp():void
        {
            _clampNow();
        }

        /** 销毁——移除所有事件监听（含 stage resize）。 */
        public function dispose():void
        {
            _handle.removeEventListener(MouseEvent.MOUSE_DOWN, _onDragStart);
            if (_dragging && _stage)
            {
                _stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onDragMove);
                _stage.removeEventListener(MouseEvent.MOUSE_UP,   _onDragEnd);
            }
            _removeResizeListener();
            _dragging = false;
            _onMove = null;
            L.info("已销毁");
        }

        // ═══════════════════════════════════════════════════
        // 拖拽事件
        // ═══════════════════════════════════════════════════

        private function _onDragStart(event:MouseEvent):void
        {
            if (!_enabled) return;

            if (!_stage)
                _stage = _target.stage;

            _dragging = true;
            _didMove = false;
            _offsetX = _stage.mouseX - _target.x;
            _offsetY = _stage.mouseY - _target.y;

            _stage.addEventListener(MouseEvent.MOUSE_MOVE, _onDragMove);
            _stage.addEventListener(MouseEvent.MOUSE_UP,   _onDragEnd);
            _ensureResizeListener();
            L.info("拖拽开始: offset=(" + _offsetX.toFixed(1) + "," + _offsetY.toFixed(1) + ")");
        }

        private function _onDragMove(event:MouseEvent):void
        {
            if (!_dragging || !_stage) return;

            _didMove = true;
            _target.x = _stage.mouseX - _offsetX;
            _target.y = _stage.mouseY - _offsetY;

            _clampNow();
        }

        private function _onDragEnd(event:MouseEvent):void
        {
            _dragging = false;

            if (_stage)
            {
                _stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onDragMove);
                _stage.removeEventListener(MouseEvent.MOUSE_UP,   _onDragEnd);
            }

            if (_didMove)
            {
                if (_onMove != null)
                    _onMove(_target.x, _target.y);
                L.info("拖拽结束: (" + _target.x.toFixed(1) + "," + _target.y.toFixed(1) + ")");
            }
            else
            {
                L.debug("拖拽取消（无位移，判定为点击）");
            }
        }

        // ═══════════════════════════════════════════════════
        // 边界约束
        // ═══════════════════════════════════════════════════

        /** 立即 clamp 到合法区域（拖拽时每帧调用）。
         *
         * 约束逻辑:
         *   minX / minY — 基于把手尺寸计算，确保把手至少有 margin 像素在屏幕内
         *   maxX / maxY — 基于把手左/上边缘，不让把手完全移出屏幕右侧/底部
         */
        private function _clampNow():void
        {
            if (!_stage) return;

            var maxW:int = _stage.stageWidth;
            var maxH:int = _stage.stageHeight;

            var hw:Number = _handleW > 0 ? _handleW : _target.width;
            var hh:Number = _handleH > 0 ? _handleH : _target.height;

            // 把手右边缘 >= marginLeft，即 target.x >= marginLeft - hw
            var minX:Number = _marginLeft - hw;
            // 把手下边缘 >= marginTop
            var minY:Number = _marginTop - hh;
            // 把手左边缘 <= maxW - marginRight
            var maxX:Number =  maxW - _marginRight;
            // 把手上边缘 <= maxH - marginBottom
            var maxY:Number =  maxH - _marginBottom;

            if (_target.x < minX) _target.x = minX;
            if (_target.y < minY) _target.y = minY;
            if (_target.x > maxX) _target.x = maxX;
            if (_target.y > maxY) _target.y = maxY;
        }

        /** 计算合法位置但不修改 target，返回 {x, y}。 */
        private function _computeClamped():Object
        {
            if (!_stage) return {x: _target.x, y: _target.y};

            var maxW:int = _stage.stageWidth;
            var maxH:int = _stage.stageHeight;

            var hw:Number = _handleW > 0 ? _handleW : _target.width;
            var hh:Number = _handleH > 0 ? _handleH : _target.height;

            var cx:Number = _target.x;
            var cy:Number = _target.y;

            var minX:Number = _marginLeft - hw;
            var minY:Number = _marginTop - hh;
            var maxX:Number =  maxW - _marginRight;
            var maxY:Number =  maxH - _marginBottom;

            if (cx < minX) cx = minX;
            if (cy < minY) cy = minY;
            if (cx > maxX) cx = maxX;
            if (cy > maxY) cy = maxY;

            return {x: cx, y: cy};
        }

        // ═══════════════════════════════════════════════════
        // 屏幕缩放回弹
        // ═══════════════════════════════════════════════════

        private function _ensureResizeListener():void
        {
            if (_stage && !_hasResizeListener)
            {
                _stage.addEventListener(Event.RESIZE, _onStageResize);
                _hasResizeListener = true;
            }
        }

        private function _removeResizeListener():void
        {
            if (_stage && _hasResizeListener)
            {
                _stage.removeEventListener(Event.RESIZE, _onStageResize);
                _hasResizeListener = false;
            }
        }

        private function _onStageResize(event:Event):void
        {
            if (!_stage || _dragging) return;

            var clamped:Object = _computeClamped();
            var changed:Boolean = (Math.abs(clamped.x - _target.x) > 0.5 ||
                                    Math.abs(clamped.y - _target.y) > 0.5);

            if (changed)
            {
                L.debug("resize 回弹: (" +
                    _target.x.toFixed(0) + "," + _target.y.toFixed(0) + ") → (" +
                    clamped.x.toFixed(0) + "," + clamped.y.toFixed(0) + ")");
                Tween.to(_target, 0.25,
                    {x: clamped.x, y: clamped.y},
                    Easing.easeOutCubic);
            }
        }
    }
}
