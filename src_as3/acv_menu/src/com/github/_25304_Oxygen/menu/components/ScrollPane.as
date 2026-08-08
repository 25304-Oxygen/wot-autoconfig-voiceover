package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.DisplayObject;
    import flash.display.Shape;
    import flash.geom.Rectangle;
    import flash.events.MouseEvent;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.menu.components.SoundableSprite;

    /**
     * 自绘滚动面板——纯 AS3 实现，不依赖 WoT 原生控件。
     *
     * 内置: 圆角背景 + 右侧滚动条（上按钮 / 拖拽拇指 / 下按钮）+ 鼠标滚轮。
     * 内容通过 setContent() 设置，自动计算滚动范围。
     *
     * 用法:
     *   var sp:ScrollPane = new ScrollPane(400, 300);
     *   sp.setContent(myLongSprite);
     *   addChild(sp);
     */
    public class ScrollPane extends Sprite
    {
        private static const L:Object = Log.getLogger("ScrollPane");

        // ═══════════════════════════════════════════════════════
        // 外观常量
        // ═══════════════════════════════════════════════════════

        private static const STROKE_WIDTH:Number = 1;
        private static const CORNER_RADIUS:int  = 0;

        // 滚动条
        private static const SB_W:int = 12;          // 滚动条总宽度
        private static const SB_MARGIN:int = 4;      // 滚动条与内容/边缘间距
        private static const BTN_H:int = 14;         // 上下按钮高度
        private static const THUMB_MIN_H:int = 20;   // 拇指最小高度

        // 滚动参数
        private static const WHEEL_STEP:int = 40;    // 滚轮每次滚动 px
        private static const BTN_STEP:int = 30;      // 按钮点击每次滚动 px

        // ═══════════════════════════════════════════════════════
        // 内部状态
        // ═══════════════════════════════════════════════════════

        private var _w:Number;
        private var _h:Number;

        // 可视区域
        private var _viewport:Sprite;
        private var _content:DisplayObject;

        // 背景
        private var _bg:Shape;

        // 滚动条
        private var _sbTrack:Shape;
        private var _sbThumb:Sprite;
        private var _btnUp:Sprite;
        private var _btnDown:Sprite;

        // 滚动状态
        private var _scrollPos:Number = 0;
        private var _maxScroll:Number = 0;
        private var _needsScroll:Boolean = false;

        // 拖拽
        private var _dragging:Boolean = false;
        private var _dragStartY:Number = 0;
        private var _dragStartPos:Number = 0;

        /** 缓存的 stage 引用。 */
        private var _stage:Object;

        /** 上次成功测量的内容高度——防止 Scaleform 临时返回 0 导致
         *  _needsScroll 意外翻为 false，滚动条消失。 */
        private var _lastContentH:Number = 0;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        public function ScrollPane(w:Number, h:Number)
        {
            super();
            _w = w;
            _h = h;

            _build();
            Theme.register(this, _refreshStyle);
        }

        private function _build():void
        {
            // 背景
            _bg = new Shape();
            _drawBackground();
            addChild(_bg);

            // 可视区域（用 scrollRect 裁剪内容）。
            // mouseEnabled=false 防止 viewport 在 Scaleform 中拦截子项点击。
            _viewport = new Sprite();
            _viewport.mouseEnabled = false;
            _viewport.x = SB_MARGIN;
            _viewport.y = SB_MARGIN;
            _viewport.scrollRect = new Rectangle(0, 0,
                _w - SB_W - SB_MARGIN * 3, _h - SB_MARGIN * 2);
            addChild(_viewport);

            // 滚动条轨道
            _sbTrack = new Shape();
            _sbTrack.x = _w - SB_W - SB_MARGIN;
            _sbTrack.y = SB_MARGIN + BTN_H;
            addChild(_sbTrack);

            // 滚动条拇指
            _sbThumb = new SoundableSprite("normal");
            _sbThumb.buttonMode = true;
            _sbThumb.addEventListener(MouseEvent.MOUSE_DOWN, _onThumbDown);
            _sbThumb.addEventListener(MouseEvent.MOUSE_OVER, _onThumbOver);
            _sbThumb.addEventListener(MouseEvent.MOUSE_OUT, _onThumbOut);
            addChild(_sbThumb);

            // 上按钮
            _btnUp = _buildArrowBtn(true);
            _btnUp.x = _sbTrack.x;
            _btnUp.y = SB_MARGIN;
            _btnUp.addEventListener(MouseEvent.MOUSE_DOWN, _onUpClick);
            addChild(_btnUp);

            // 下按钮
            _btnDown = _buildArrowBtn(false);
            _btnDown.x = _sbTrack.x;
            _btnDown.addEventListener(MouseEvent.MOUSE_DOWN, _onDownClick);
            addChild(_btnDown);

            // 滚轮
            this.addEventListener(MouseEvent.MOUSE_WHEEL, _onWheel, false, 0, true);

            _drawScrollBar();
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        public function setContent(content:DisplayObject):void
        {
            // 移除旧内容
            if (_content && _content.parent == _viewport)
                _viewport.removeChild(_content);

            _content = content;
            _content.x = 0;
            _content.y = 0;
            _viewport.addChild(_content);
            _scrollPos = 0;

            _updateScrollRange();
        }

        public function get scrollPosition():Number { return _scrollPos; }

        public function set scrollPosition(value:Number):void
        {
            _scrollPos = Math.max(0, Math.min(_maxScroll, value));
            _applyScroll();
            _updateThumb();  // 同步拇指位置，否则程序化滚动后拇指停在旧处
        }

        public function refresh():void
        {
            _updateScrollRange();
        }

        public function dispose():void
        {
            Theme.unregister(this);
            // 清理 stage 监听
            if (_stage)
            {
                _stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onStageMove);
                _stage.removeEventListener(MouseEvent.MOUSE_UP, _onStageUp);
            }

            if (_sbThumb)
            {
                _sbThumb.removeEventListener(MouseEvent.MOUSE_DOWN, _onThumbDown);
                _sbThumb.removeEventListener(MouseEvent.MOUSE_OVER, _onThumbOver);
                _sbThumb.removeEventListener(MouseEvent.MOUSE_OUT, _onThumbOut);
                SoundableSprite(_sbThumb).disposeItem();
                _sbThumb = null;
            }

            if (_btnUp)
            {
                _btnUp.removeEventListener(MouseEvent.MOUSE_DOWN, _onUpClick);
                SoundableSprite(_btnUp).disposeItem();
                _btnUp = null;
            }
            if (_btnDown)
            {
                _btnDown.removeEventListener(MouseEvent.MOUSE_DOWN, _onDownClick);
                SoundableSprite(_btnDown).disposeItem();
                _btnDown = null;
            }

            this.removeEventListener(MouseEvent.MOUSE_WHEEL, _onWheel);
            _content = null;
            _sbTrack = null;
            L.debug("已销毁");
        }

        // ═══════════════════════════════════════════════════════
        // 主题刷新
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            _drawBackground();
            _drawScrollBar();
        }

        // ═══════════════════════════════════════════════════════
        // 背景
        // ═══════════════════════════════════════════════════════

        private function _drawBackground():void
        {
            _bg.graphics.clear();
            _bg.graphics.lineStyle(STROKE_WIDTH, Theme.stroke);
            _bg.graphics.beginFill(Theme.surface0, 1.0);
            _bg.graphics.drawRoundRect(0, 0, _w, _h,
                CORNER_RADIUS * 2, CORNER_RADIUS * 2);
            _bg.graphics.endFill();
        }

        // ═══════════════════════════════════════════════════════
        // 滚动条绘制
        // ═══════════════════════════════════════════════════════

        private function _drawScrollBar():void
        {
            var trackH:Number = _h - SB_MARGIN * 2 - BTN_H * 2;
            var sbX:Number = _w - SB_W - SB_MARGIN;

            // 轨道
            _sbTrack.graphics.clear();
            _sbTrack.graphics.beginFill(Theme.surface2, 1.0);
            _sbTrack.graphics.drawRoundRect(0, 0, SB_W, trackH, 6, 6);
            _sbTrack.graphics.endFill();

            // 下按钮位置
            _btnDown.y = SB_MARGIN + BTN_H + trackH;

            // ▲▼ 按钮背景 + 箭头图形（_buildArrowBtn 一次性创建，换肤时需重绘）
            _redrawArrowBtn(_btnUp, true);
            _redrawArrowBtn(_btnDown, false);

            // 拇指
            _updateThumb();
        }

        /** 根据 _maxScroll 和 _scrollPos 更新拇指尺寸与位置。
         *
         *  内容存在时滚动条始终可见；内容不溢出时拇指占满轨道、不可拖拽。 */
        private function _updateThumb():void
        {
            var trackH:Number = _h - SB_MARGIN * 2 - BTN_H * 2;

            // 无内容 → 滚动条隐藏
            if (!_content)
            {
                _sbThumb.visible = false;
                _sbTrack.visible = false;
                _btnUp.visible = false;
                _btnDown.visible = false;
                return;
            }

            // 有内容 → 滚动条始终可见
            _sbThumb.visible = true;
            _sbTrack.visible = true;
            _btnUp.visible = true;
            _btnDown.visible = true;

            if (_maxScroll <= 0)
            {
                // 内容不溢出 → 拇指占满轨道，不可拖拽
                _sbThumb.graphics.clear();
                _sbThumb.graphics.beginFill(Theme.sbThumb, 0.4);
                _sbThumb.graphics.drawRoundRect(0, 0, SB_W, trackH, 6, 6);
                _sbThumb.graphics.endFill();
                _sbThumb.x = _sbTrack.x;
                _sbThumb.y = _sbTrack.y;
                _sbThumb.buttonMode = false;
                return;
            }

            // 内容溢出 → 拇指可拖拽
            _sbThumb.buttonMode = true;

            var totalH:Number = trackH + _maxScroll;
            var ratio:Number = trackH / totalH;
            var thumbH:Number = Math.max(THUMB_MIN_H, ratio * trackH);
            var travel:Number = trackH - thumbH;
            var thumbY:Number = (_scrollPos / _maxScroll) * travel;

            _sbThumb.graphics.clear();
            _sbThumb.graphics.beginFill(Theme.sbThumb, 1.0);
            _sbThumb.graphics.drawRoundRect(0, 0, SB_W, thumbH, 6, 6);
            _sbThumb.graphics.endFill();

            _sbThumb.x = _sbTrack.x;
            _sbThumb.y = _sbTrack.y + thumbY;
        }

        /** 拇指 hover 高亮。
         *  注意：clear() 之后 _sbThumb.width/height 归零，
         *  因此必须先将尺寸缓存到局部变量。 */
        private function _drawThumbHover(on:Boolean):void
        {
            var c:uint = on ? Theme.stroke : Theme.sbThumb;
            var tw:Number = _sbThumb.width;
            var th:Number = _sbThumb.height;
            if (tw <= 0 || th <= 0) return;  // 拇指尚未绘制，跳过
            _sbThumb.graphics.clear();
            _sbThumb.graphics.beginFill(c, 1.0);
            _sbThumb.graphics.drawRoundRect(0, 0, tw, th, 6, 6);
            _sbThumb.graphics.endFill();
        }

        // ═══════════════════════════════════════════════════════
        // 箭头按钮
        // ═══════════════════════════════════════════════════════

        private function _buildArrowBtn(up:Boolean):Sprite
        {
            var btn:SoundableSprite = new SoundableSprite("normal");
            btn.buttonMode = true;
            btn.mouseChildren = false;  // 确保内部 Shape 不会拦截鼠标事件

            // 背景
            var bg:Shape = new Shape();
            bg.graphics.beginFill(Theme.sbBtn, 1.0);
            bg.graphics.drawRoundRect(0, 0, SB_W, BTN_H, 4, 4);
            bg.graphics.endFill();
            btn.addChild(bg);

            // 箭头（三角形）
            var arrow:Shape = new Shape();
            var cx:Number = SB_W / 2;
            if (up)
            {
                // ▲
                arrow.graphics.beginFill(Theme.sbBtnArrow, 1.0);
                arrow.graphics.moveTo(cx, 3);
                arrow.graphics.lineTo(cx - 4, BTN_H - 4);
                arrow.graphics.lineTo(cx + 4, BTN_H - 4);
                arrow.graphics.endFill();
            }
            else
            {
                // ▼
                arrow.graphics.beginFill(Theme.sbBtnArrow, 1.0);
                arrow.graphics.moveTo(cx, BTN_H - 3);
                arrow.graphics.lineTo(cx - 4, 4);
                arrow.graphics.lineTo(cx + 4, 4);
                arrow.graphics.endFill();
            }
            btn.addChild(arrow);

            return btn;
        }

        /**
         * 重绘箭头按钮的背景和箭头图形——供换肤时调用。
         *
         * _buildArrowBtn 在构造时一次性绘制，换肤后 _drawScrollBar 需
         * 通过此方法重绘已有的 Shape，避免重建按钮。
         */
        private function _redrawArrowBtn(btn:Sprite, up:Boolean):void
        {
            if (!btn || btn.numChildren < 2) return;

            // 背景（子 0）
            var bg:Shape = btn.getChildAt(0) as Shape;
            if (bg)
            {
                bg.graphics.clear();
                bg.graphics.beginFill(Theme.sbBtn, 1.0);
                bg.graphics.drawRoundRect(0, 0, SB_W, BTN_H, 4, 4);
                bg.graphics.endFill();
            }

            // 箭头三角形（子 1）
            var arrow:Shape = btn.getChildAt(1) as Shape;
            if (arrow)
            {
                arrow.graphics.clear();
                var cx:Number = SB_W / 2;
                if (up)
                {
                    // ▲
                    arrow.graphics.beginFill(Theme.sbBtnArrow, 1.0);
                    arrow.graphics.moveTo(cx, 3);
                    arrow.graphics.lineTo(cx - 4, BTN_H - 4);
                    arrow.graphics.lineTo(cx + 4, BTN_H - 4);
                    arrow.graphics.endFill();
                }
                else
                {
                    // ▼
                    arrow.graphics.beginFill(Theme.sbBtnArrow, 1.0);
                    arrow.graphics.moveTo(cx, BTN_H - 3);
                    arrow.graphics.lineTo(cx - 4, 4);
                    arrow.graphics.lineTo(cx + 4, 4);
                    arrow.graphics.endFill();
                }
            }
        }

        // ═══════════════════════════════════════════════════════
        // 滚动逻辑
        // ═══════════════════════════════════════════════════════

        private function _updateScrollRange():void
        {
            if (!_content)
            {
                _needsScroll = false;
                _maxScroll = 0;
                _drawScrollBar();
                return;
            }

            var viewH:Number = _h - SB_MARGIN * 2;
            var contentH:Number = _content.height;

            // 防止 Scaleform 临时返回 0 导致滚动条意外消失：
            // 如果当前读数为 0 但之前有正常值，沿用旧值。
            if (contentH <= 0 && _lastContentH > 0)
                contentH = _lastContentH;
            else if (contentH > 0)
                _lastContentH = contentH;

            _maxScroll = Math.max(0, contentH - viewH);
            _needsScroll = _maxScroll > 0;

            // 如果内容缩小到不需滚动，回到顶部
            if (!_needsScroll)
                _scrollPos = 0;
            else
                _scrollPos = Math.max(0, Math.min(_maxScroll, _scrollPos));

            _applyScroll();
            _drawScrollBar();
        }

        private function _applyScroll():void
        {
            if (!_content) return;
            // content.y 位移实现滚动——content.y 是变换矩阵的一部分，
            // globalToLocal 会正确转换鼠标坐标。不能依赖 scrollRect
            // 原点偏移（它不是变换，会导致子对象的鼠标坐标错误）。
            var viewW:Number = _w - SB_W - SB_MARGIN * 3;
            var viewH:Number = _h - SB_MARGIN * 2;
            _content.y = -_scrollPos;
            _viewport.scrollRect = new Rectangle(0, 0, viewW, viewH);
        }

        // ═══════════════════════════════════════════════════════
        // 滚轮（捕获阶段，阻止冒泡到父级 ScrollPane）
        // ═══════════════════════════════════════════════════════

        private function _onWheel(event:MouseEvent):void
        {
            if (_maxScroll <= 0) return;

            var delta:int = event.delta > 0 ? -1 : 1;
            _scrollPos = Math.max(0, Math.min(_maxScroll,
                _scrollPos + delta * WHEEL_STEP));
            _applyScroll();
            _updateThumb();
            event.stopImmediatePropagation();
        }

        // ═══════════════════════════════════════════════════════
        // 按钮点击
        // ═══════════════════════════════════════════════════════

        private function _onUpClick(event:MouseEvent):void
        {
            if (_maxScroll <= 0) return;
            _scrollPos = Math.max(0, _scrollPos - BTN_STEP);
            _applyScroll();
            _updateThumb();
            event.stopImmediatePropagation();
        }

        private function _onDownClick(event:MouseEvent):void
        {
            if (_maxScroll <= 0) return;
            _scrollPos = Math.min(_maxScroll, _scrollPos + BTN_STEP);
            _applyScroll();
            _updateThumb();
            event.stopImmediatePropagation();
        }

        // ═══════════════════════════════════════════════════════
        // 拇指拖拽
        // ═══════════════════════════════════════════════════════

        private function _onThumbDown(event:MouseEvent):void
        {
            _dragging = true;
            _dragStartY = event.stageY;
            _dragStartPos = _scrollPos;
            _stage = this.stage;
            if (_stage)
            {
                _stage.addEventListener(MouseEvent.MOUSE_MOVE, _onStageMove);
                _stage.addEventListener(MouseEvent.MOUSE_UP, _onStageUp);
            }
            event.stopImmediatePropagation();
        }

        private function _onStageMove(event:MouseEvent):void
        {
            if (!_dragging || !_stage) return;

            var trackH:Number = _h - SB_MARGIN * 2 - BTN_H * 2;
            var thumbH:Number = _sbThumb.height;
            var travel:Number = trackH - thumbH;

            if (travel <= 0) return;

            var dy:Number = event.stageY - _dragStartY;
            var ratio:Number = dy / travel;
            _scrollPos = Math.max(0, Math.min(_maxScroll,
                _dragStartPos + ratio * _maxScroll));
            _applyScroll();
            _updateThumb();
        }

        private function _onStageUp(event:MouseEvent):void
        {
            _dragging = false;
            if (_stage)
            {
                _stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onStageMove);
                _stage.removeEventListener(MouseEvent.MOUSE_UP, _onStageUp);
            }
        }

        private function _onThumbOver(event:MouseEvent):void
        {
            _drawThumbHover(true);
        }

        private function _onThumbOut(event:MouseEvent):void
        {
            _drawThumbHover(false);
        }
    }
}
