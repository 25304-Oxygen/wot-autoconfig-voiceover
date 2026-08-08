package com.github._25304_Oxygen.menu
{
    import flash.display.Sprite;
    import flash.geom.Rectangle;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.tween.Tween;
    import com.github._25304_Oxygen.shared.tween.Easing;
    import com.github._25304_Oxygen.shared.ui.BitmapContainer;
    import com.github._25304_Oxygen.menu.pages.BasePage;

    /**
     * 面板——支持水平/垂直滑入滑出 + 垂直弹出（overshoot）。
     *
     * - 水平模式（默认）：面板从左侧滑入/滑出，用于半折叠圆角面板。
     * - 垂直模式：面板从上方滑入/滑出（无回弹），用于全展开直角面板。
     *
     * 内容层支持 setContent/switchPage 页面切换，也可直接 addChild
     * 添加固定 UI 元素。
     */
    public class PanelView extends Sprite
    {
        private static const L:Object = Log.getLogger("PanelView");

        // 尺寸
        private var _w:Number;
        private var _h:Number;

        // 外观
        private var _bgColor:uint;
        private var _bgAlpha:Number;
        private var _radius:Number;
        private var _rounded:Boolean;
        private var _strokeColor:uint;
        private var _strokeWidth:Number;
        private var _bottomStrokeWidth:Number = 0;   // 0=使用 _strokeWidth
        private var _bottomStrokeColor:uint = 0;    // 0=使用 _strokeColor
        private var _bgSprite:Sprite;
        private var _imageLayer:BitmapContainer;    // 背景图（填充之上、组件之下）

        // 内容
        private var _currentPage:BasePage;
        private var _contentLayer:Sprite;

        // 动画
        private var _animTween:Tween;
        private var _visible:Boolean = false;

        // 方向
        private var _vertical:Boolean;

        // 面板在容器内的目标坐标
        private var _targetX:Number = 0;
        private var _targetY:Number = 0;

        /**
         * @param w          面板宽度（px）
         * @param h          面板高度（px）
         * @param bgColor    背景色（默认白色）
         * @param bgAlpha    背景透明度（默认 0.92）
         * @param radius     圆角半径（默认 12，0=直角）
         * @param vertical   true=垂直动画，false=水平动画（默认）
         */
        public function PanelView(w:Number, h:Number,
                                   bgColor:uint = 0xFFFFFF,
                                   bgAlpha:Number = 0.92,
                                   radius:Number = 12,
                                   vertical:Boolean = false,
                                   strokeColor:uint = 0,
                                   strokeWidth:Number = 0)
        {
            super();

            _w        = w;
            _h        = h;
            _bgColor  = bgColor;
            _bgAlpha  = bgAlpha;
            _radius   = radius;
            _rounded  = radius > 0;
            _vertical = vertical;
            _strokeColor = strokeColor;
            _strokeWidth = strokeWidth;

            // 背景
            _drawBackground();

            // 内容层（在背景之上）
            _contentLayer = new Sprite();
            _contentLayer.scrollRect = new Rectangle(0, 0, _w, _h);
            addChild(_contentLayer);

            // 初始隐藏
            this.alpha = 0;
            L.debug("创建: " + w + "×" + h +
                        (_vertical ? " 垂直" : " 水平"));
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 面板宽度。 */
        public function get panelWidth():Number  { return _w; }
        /** 面板高度。 */
        public function get panelHeight():Number { return _h; }

        /** 内容层——直接 addChild 添加固定 UI 元素。 */
        public function get contentLayer():Sprite { return _contentLayer; }

        /**
         * 设置面板在容器内的目标坐标。
         * showIn/showOut 的动画终点/起点由此决定。
         */
        public function setTarget(x:Number, y:Number):void
        {
            _targetX = x;
            _targetY = y;
            if (!_visible)
            {
                this.x = x;
                this.y = y;
            }
        }

        /** @deprecated 兼容旧 API，等价于 setTarget(x, 0)。 */
        public function setTargetX(x:Number):void
        {
            setTarget(x, 0);
        }

        /**
         * 设置当前显示的页面。
         * 旧页面仅从显示列表中移除（保留状态），不销毁。
         * 同一页面重复设置时跳过，避免组件丢失。
         *
         * 注意: 页面实例由 MenuView._pages 管理生命周期，
         * dispose 仅在 MenuView.onDispose() 中统一调用。
         */
        public function setContent(page:BasePage):void
        {
            // 同一页面 → 无需切换
            if (_currentPage == page) return;

            if (_currentPage)
            {
                _currentPage.hide();
                if (_currentPage.parent == _contentLayer)
                    _contentLayer.removeChild(_currentPage);
            }

            _currentPage = page;
            if (page)
            {
                _contentLayer.addChild(page);
                page.init();
                page.show();
                L.info("切换到页面: " + page.pageId);
            }
        }

        /** 获取当前页面。 */
        public function get currentPage():BasePage
        {
            return _currentPage;
        }

        /**
         * 滑入——面板从折叠位置滑入到目标位置。
         * 水平: 从左侧滑入；垂直: 从上方滑入。
         * @param onComplete  动画完成回调
         */
        public function showIn(onComplete:Function = null):void
        {
            if (_visible) return;
            _visible = true;

            _killAnim();

            if (_vertical)
            {
                var fromY:Number = _targetY - _h;
                this.y = fromY;
                this.x = _targetX;
            }
            else
            {
                var fromX:Number = _targetX - _w;
                this.x = fromX;
                this.y = _targetY;
            }
            this.alpha = 0;

            var props:Object = _vertical
                ? {y: _targetY, alpha: 1.0}
                : {x: _targetX, alpha: 1.0};

            _animTween = Tween.to(this, 0.4, props, Easing.easeOutCubic,
                function():void {
                    _animTween = null;
                    if (onComplete != null) onComplete();
                });

            L.debug("showIn: " + (_vertical ? "垂直" : "水平"));
        }

        /**
         * 立即显示面板到目标位置，不走动画。
         * 用于跨会话恢复状态（上次是展开态，这次打开直接显示展开态）。
         */
        public function showInstant():void
        {
            if (_visible) return;
            _visible = true;

            _killAnim();
            this.x = _targetX;
            this.y = _targetY;
            this.alpha = 1.0;

            L.debug("showInstant");
        }

        /**
         * 滑出——面板滑出并淡出。
         * 水平: 向左滑出；垂直: 向上滑出。
         * @param onComplete  动画完成回调
         */
        public function showOut(onComplete:Function = null):void
        {
            if (!_visible) return;
            _visible = false;

            _killAnim();

            var props:Object;
            if (_vertical)
            {
                props = {y: _targetY - _h, alpha: 0};
            }
            else
            {
                props = {x: _targetX - _w, alpha: 0};
            }

            _animTween = Tween.to(this, 0.3, props, Easing.easeInCubic,
                function():void {
                    _animTween = null;
                    if (onComplete != null) onComplete();
                });

            L.debug("showOut");
        }

        /**
         * 弹出（垂直模式）——从上方滑入到目标位置，无回弹。
         * @param onComplete  完成回调
         */
        public function popIn(onComplete:Function = null):void
        {
            if (_visible) return;
            _visible = true;

            _killAnim();

            // 起始: 面板完全藏在上方
            this.y = _targetY - _h;
            this.x = _targetX;
            this.alpha = 1.0;

            _animTween = Tween.to(this, 0.3,
                {y: _targetY},
                Easing.easeOutCubic,
                function():void {
                    _animTween = null;
                    if (onComplete != null) onComplete();
                });

            L.debug("popIn: " + (_targetY - _h).toFixed(0) +
                        " → " + _targetY.toFixed(0));
        }

        /**
         * 弹回（垂直模式）——面板向上收回。
         * @param onComplete  动画完成回调
         */
        public function popOut(onComplete:Function = null):void
        {
            if (!_visible) return;
            _visible = false;

            _killAnim();

            _animTween = Tween.to(this, 0.2,
                {y: _targetY - _h},
                Easing.easeInCubic,
                function():void {
                    _animTween = null;
                    if (onComplete != null) onComplete();
                });

            L.debug("popOut");
        }

        /**
         * 页面切换动画（垂直模式用 popIn/popOut，水平模式用 showIn/showOut）。
         * @param newPage    新页面
         * @param onComplete 整体切换完成回调
         */
        public function switchPage(newPage:BasePage, onComplete:Function = null):void
        {
            // DEBUG：页面切换中间态，最终落地由 setContent 的"切换到页面"记录
            L.debug("切换页面 → " + newPage.pageId);

            var self:PanelView = this;
            var outComplete:Function = function():void {
                self.setContent(newPage);
                self.showIn(onComplete);
            };

            showOut(outComplete);
        }

        /**
         * 垂直模式下的切换：弹回 → 换页 → 弹出。
         */
        public function switchPageVertical(newPage:BasePage, onComplete:Function = null):void
        {
            // DEBUG：垂直切换中间态（与 switchPage 同理由）
            L.debug("垂直切换页面 → " + newPage.pageId);

            var self:PanelView = this;

            popOut(function():void {
                self.setContent(newPage);
                self.popIn(onComplete);
            });
        }

        /** 面板是否处于展开（可见）状态。 */
        public function get visiblePanel():Boolean
        {
            return _visible;
        }

        /**
         * 挂载背景图片——插在背景填充和组件层之间（cover 裁剪成面板形状）。
         * 可重复调用替换；加载失败保持默认填充外观。
         */
        public function setImage(path:String):void
        {
            if (!path || path.length == 0)
            {
                clearImage();
                return;
            }

            if (!_imageLayer)
            {
                _imageLayer = new BitmapContainer(_w, _h,
                    _rounded ? _radius : 0, null, "cover");
                _imageLayer.mouseEnabled = false;
                _imageLayer.mouseChildren = false;
                // z 顺序: 背景填充 → 图片 → 内容层
                addChildAt(_imageLayer, getChildIndex(_contentLayer));
            }
            _imageLayer.load(path);
            // DEBUG：与 BitmapContainer/ImageCache 的图片日志重复
            L.debug("面板背景图: " + path);
        }

        /** 清除背景图片，恢复默认填充外观。 */
        public function clearImage():void
        {
            if (_imageLayer)
                _imageLayer.clear();
        }

        /**
         * 更新描边颜色和宽度，自动重绘背景。
         * 内容层保持在背景之上。
         */
        public function setStroke(color:uint, width:Number):void
        {
            _strokeColor = color;
            _strokeWidth = width;
            _redrawBg();
        }

        /**
         * 更新背景色和描边颜色，自动重绘（换肤用）。
         * 只改传入的非零值，保留未传项。
         */
        public function setColors(bgColor:uint = 0, strokeColor:uint = 0):void
        {
            if (bgColor != 0)       _bgColor     = bgColor;
            if (strokeColor != 0)   _strokeColor = strokeColor;
            _redrawBg();
        }

        /**
         * 设置直角面板下边缘的独立描边（仅非圆角面板生效）。
         * @param width  下边缘描边宽度，0 表示使用 _strokeWidth
         * @param color  下边缘描边颜色，0 表示使用 _strokeColor
         */
        public function setBottomStroke(width:Number, color:uint = 0):void
        {
            _bottomStrokeWidth = width;
            _bottomStrokeColor = color;
            if (!_rounded) _redrawBg();
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        private function _drawBackground():void
        {
            _bgSprite = new Sprite();

            if (_rounded)
            {
                // 圆角面板 — 统一描边 + 圆角填充
                if (_strokeWidth > 0)
                    _bgSprite.graphics.lineStyle(_strokeWidth, _strokeColor);
                _bgSprite.graphics.beginFill(_bgColor, _bgAlpha);
                _bgSprite.graphics.drawRoundRect(0, 0, _w, _h, _radius * 2, _radius * 2);
                _bgSprite.graphics.endFill();
            }
            else
            {
                // 直角面板 — 先填充，再分边描边（下边可独立加粗）
                _bgSprite.graphics.beginFill(_bgColor, _bgAlpha);
                _bgSprite.graphics.drawRect(0, 0, _w, _h);
                _bgSprite.graphics.endFill();

                if (_strokeWidth > 0)
                {
                    _bgSprite.graphics.lineStyle(_strokeWidth, _strokeColor);
                    // 上边
                    _bgSprite.graphics.moveTo(0, 0);
                    _bgSprite.graphics.lineTo(_w, 0);
                    // 左边
                    _bgSprite.graphics.moveTo(0, 0);
                    _bgSprite.graphics.lineTo(0, _h);
                    // 右边
                    _bgSprite.graphics.moveTo(_w, 0);
                    _bgSprite.graphics.lineTo(_w, _h);
                }

                // 下边 — 独立描边宽度和颜色
                var bw:Number = (_bottomStrokeWidth > 0) ? _bottomStrokeWidth : _strokeWidth;
                var bc:uint  = (_bottomStrokeColor != 0) ? _bottomStrokeColor : _strokeColor;
                if (bw > 0)
                {
                    _bgSprite.graphics.lineStyle(bw, bc);
                    _bgSprite.graphics.moveTo(0, _h);
                    _bgSprite.graphics.lineTo(_w, _h);
                }
            }

            addChild(_bgSprite);
        }

        private function _redrawBg():void
        {
            if (_bgSprite && contains(_bgSprite))
                removeChild(_bgSprite);
            _drawBackground();
            // 维持层序: 背景填充 → 背景图 → 内容层
            if (_imageLayer && contains(_imageLayer))
            {
                removeChild(_imageLayer);
                addChild(_imageLayer);
            }
            if (_contentLayer && contains(_contentLayer))
            {
                removeChild(_contentLayer);
                addChild(_contentLayer);
            }
        }

        private function _killAnim():void
        {
            if (_animTween)
            {
                _animTween.stop();
                _animTween = null;
            }
        }
    }
}
