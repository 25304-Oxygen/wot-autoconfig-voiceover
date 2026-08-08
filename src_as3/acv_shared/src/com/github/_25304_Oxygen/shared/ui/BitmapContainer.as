package com.github._25304_Oxygen.shared.ui
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.display.BitmapData;
    import flash.geom.Matrix;
    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 图片容器——通过 ImageCache 加载外部图片，按形状裁剪显示。
     *
     * 裁剪不用 mask（Scaleform 中不可靠），而是位图填充：
     * 先把源图按缩放策略绘制进容器尺寸的透明 canvas，
     * 再用 canvas 作为矢量形状（圆/圆角矩形）的填充物——
     * 图片天然被形状边界裁剪。
     *
     * 缩放策略（scaleMode）:
     *   "stretch"（默认，兼容字幕渲染器）: 非等比拉伸到容器尺寸
     *   "cover": 大图等比缩小到刚好覆盖容器，超出裁掉（不变形）；
     *            小图居中不放大，空余区域透明
     *   "original": 原图 1:1 不缩放不裁剪，容器自动适配图片原始尺寸；
     *               构造时传入的 w/h 会被忽略
     *
     * 加载失败: 不绘制任何内容（保持透明），调用方通过
     * onReady(success=false) 得知并保持默认外观。
     *
     * 用法:
     *   var icon:BitmapContainer = new BitmapContainer(84, 84, 42, null, "cover");
     *   icon.onReady = function(success:Boolean):void { ... };
     *   icon.load("../../mods/autoconfigvoiceover/icon/voice.png");
     */
    public class BitmapContainer extends Sprite
    {
        /** 模块级日志器 */
        private static const L:Object = Log.getLogger("BitmapContainer");

        private var _w:Number;
        private var _h:Number;
        private var _radius:Number;
        private var _path:String;
        private var _scaleMode:String;

        private var _shape:Shape;           // 位图填充的形状载体
        private var _canvas:BitmapData;     // 预合成画布（容器尺寸，透明底）
        private var _loaded:Boolean = false;

        /** 加载完成回调: function(success:Boolean):void（成功或失败都触发）。 */
        public var onReady:Function;

        /**
         * @param w          容器宽度
         * @param h          容器高度
         * @param radius     圆角半径（px）。设为宽/高的一半可得到圆形；0=直角
         * @param path       图片路径（可选，构造后仍可用 load() 指定）
         * @param scaleMode  "stretch"（默认）| "cover"
         */
        public function BitmapContainer(w:Number, h:Number, radius:Number = 0,
                                         path:String = null,
                                         scaleMode:String = "stretch")
        {
            _w = w;
            _h = h;
            _radius = radius;
            _scaleMode = scaleMode;

            // 纯图片展示容器，不参与鼠标命中——上层字幕/图标不会拦截下层点击
            mouseEnabled = false;
            mouseChildren = false;

            _shape = new Shape();
            addChild(_shape);

            if (path)
                load(path);
        }

        // ═══════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════

        /** 加载指定路径的图片。可重复调用以替换图片。 */
        public function load(path:String):void
        {
            _path = path;
            // DEBUG：每次 load() 都调用（含缓存命中，字幕图片每次展示都会触发）。
            // 真实首载由 ImageCache 在 INFO 记录。
            L.debug("加载: " + path);

            var self:BitmapContainer = this;
            ImageCache.load(path, function(bmd:BitmapData, success:Boolean):void {
                // 期间可能又发起了新的 load —— 只处理最后一次请求
                if (path != self._path) return;
                self._onImage(bmd, success);
            });
        }

        /** 清除图片，回到透明状态。 */
        public function clear():void
        {
            _path = null;
            _loaded = false;
            _shape.graphics.clear();
            _disposeCanvas();
        }

        /** 是否已成功加载图片。 */
        public function get loaded():Boolean
        {
            return _loaded;
        }

        // ═══════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════

        private function _onImage(bmd:BitmapData, success:Boolean):void
        {
            if (!success || !bmd)
            {
                // 加载失败 → 保持透明，让调用方维持默认外观
                _loaded = false;
                _shape.graphics.clear();
                _disposeCanvas();
                // DEBUG：同一失败的首次 WARN 已在 ImageCache 记录，
                // 此处是每次展示都会重放的"保持默认"提示，避免刷屏。
                L.debug("加载失败，保持默认: " + _path);
                if (onReady != null) onReady(false);
                return;
            }

            _render(bmd);
            _loaded = true;
            if (onReady != null) onReady(true);
        }

        /** 把源图按缩放策略合成到画布，再用画布填充形状。 */
        private function _render(bmd:BitmapData):void
        {
            _disposeCanvas();

            var sx:Number;
            var sy:Number;
            var m:Matrix = new Matrix();

            if (_scaleMode == "original")
            {
                // original：原图 1:1，容器尺寸跟随图片
                _w = bmd.width;
                _h = bmd.height;
                // m 为单位矩阵，无需 scale/translate
            }
            else if (_scaleMode == "cover")
            {
                // cover：大图等比缩小到覆盖容器；小图不放大（上限 1）
                var s:Number = Math.min(1,
                    Math.max(_w / bmd.width, _h / bmd.height));
                sx = sy = s;
                m.scale(s, s);
                // 居中（大图裁掉两侧，小图四周留透明）
                m.translate((_w - bmd.width * s) / 2,
                            (_h - bmd.height * s) / 2);
            }
            else
            {
                // stretch：非等比拉伸铺满容器（旧行为，字幕渲染器依赖）
                sx = _w / bmd.width;
                sy = _h / bmd.height;
                m.scale(sx, sy);
            }

            _canvas = new BitmapData(_w, _h, true, 0x00000000);
            _canvas.draw(bmd, m, null, null, null, true);

            // 位图填充 + 形状路径 = 可靠的形状裁剪（不依赖 mask）
            _shape.graphics.clear();
            _shape.graphics.beginBitmapFill(_canvas, null, false, true);
            if (_radius > 0)
                _shape.graphics.drawRoundRect(0, 0, _w, _h,
                    _radius * 2, _radius * 2);
            else
                _shape.graphics.drawRect(0, 0, _w, _h);
            _shape.graphics.endFill();

            // DEBUG：每次展示都会重渲染（字幕表情图每帧/每次显示都会走这里）。
            // 尺寸/缩放细节交给调试时关注。
            L.debug("渲染完成: " + _path + " (" + bmd.width + "×" + bmd.height
                + " → " + _w + "×" + _h + ", " + _scaleMode + ")");
        }

        /** 释放预合成画布（源图 BitmapData 归 ImageCache 管理，不动）。 */
        private function _disposeCanvas():void
        {
            if (_canvas)
            {
                _canvas.dispose();
                _canvas = null;
            }
        }
    }
}
