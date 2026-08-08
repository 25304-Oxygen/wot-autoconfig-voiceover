package com.github._25304_Oxygen.menu
{
    import flash.display.BitmapData;
    import flash.display.Sprite;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.ui.BitmapContainer;
    import com.github._25304_Oxygen.shared.ui.ImageCache;
    import com.github._25304_Oxygen.shared.tween.Tween;
    import com.github._25304_Oxygen.shared.tween.Easing;

    import com.github._25304_Oxygen.menu.components.SoundUtils;

    /**
     * 圆形按钮——可指定描边、填充色、直径、图片。
     *
     * 击区域为圆形（hitArea），确保透明区域不响应点击。
     *
     * 图片模式:
     *   setImage(path) 在填充之上挂 PNG（cover 裁剪成圆形）；
     *   hideFillWhenImage=true 时图片就绪后隐藏填充和描边（小圆用），
     *   加载失败保持默认外观。clearImage() 恢复默认。
     *
     * 翻转效果:
     *   flip() 只让图片绕圆心竖直轴做 2D 翻转（scaleX 1→0→1），
     *   背景填充和描边保持不动。中点回调可用于翻转过程中换图。
     *
     * 用法:
     *   var btn:CircleButton = new CircleButton(180, 0xFF6699, 0xFF4477, 3);
     *   btn.setImage("../../mods/autoconfigvoiceover/icon/menu.png");
     *   btn.onClick = function():void { ... };
     */
    public class CircleButton extends Sprite implements ISoundable
    {
        private static const L:Object = Log.getLogger("CircleButton");

        private var _diameter:Number;
        private var _radius:Number;
        private var _fillColor:uint;
        private var _strokeColor:uint;
        private var _strokeWidth:Number;
        private var _hideFillWhenImage:Boolean;

        private var _flipWrap:Sprite;       // 图片翻转容器（轴点=圆心，只装图片）
        private var _fillSprite:Sprite;     // 圆形填充（含描边，不参与翻转）
        private var _imageBmp:BitmapContainer;  // 图片（可选）

        private var _flipping:Boolean = false;
        /** flipWithImage 预加载/翻转期间的目标图——拦截同路径的直接 setImage */
        private var _flipTargetPath:String = null;
        private var _breatheTween:Tween;        // 进行中的呼吸补间（图片层）
        private var _breatheFillTween:Tween;    // 进行中的呼吸补间（填充层）

        /** 点击回调。 */
        public var onClick:Function;

        /**
         * @param diameter           直径（px）
         * @param fillColor          填充颜色（默认粉色）
         * @param strokeColor        描边颜色（0 = 无描边）
         * @param strokeWidth        描边宽度（px）
         * @param hideFillWhenImage  图片就绪后是否隐藏填充+描边（小圆传 true）
         */
        public function CircleButton(diameter:Number, fillColor:uint = 0xFF6699,
                                      strokeColor:uint = 0, strokeWidth:Number = 0,
                                      hideFillWhenImage:Boolean = false)
        {
            super();

            _diameter = diameter;
            _radius   = diameter / 2;
            _fillColor   = fillColor;
            _strokeColor = strokeColor;
            _strokeWidth = strokeWidth;
            _hideFillWhenImage = hideFillWhenImage;

            // 圆形填充（原点=圆心，缩放时从中心鼓起；不参与翻转）
            _fillSprite = new Sprite();
            _fillSprite.x = _radius;
            _fillSprite.y = _radius;
            addChild(_fillSprite);
            _drawFill();

            // 图片翻转容器——放在圆心，图片反向偏移，使 scaleX 以圆心为轴
            _flipWrap = new Sprite();
            _flipWrap.x = _radius;
            _flipWrap.y = _radius;
            addChild(_flipWrap);

            // 圆形点击区（不随翻转缩放，保持稳定命中）
            var hit:Sprite = new Sprite();
            hit.graphics.beginFill(0x000000, 0);
            hit.graphics.drawCircle(_radius, _radius, _radius);
            hit.graphics.endFill();
            this.hitArea = hit;

            addEventListener(MouseEvent.CLICK, _onSelfClick);

            // 游戏 UI 音效
            SoundUtils.registerSound(this);

            L.debug("创建: d=" + diameter);
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 挂载图片（cover 裁剪成圆形）。可重复调用替换。 */
        public function setImage(path:String):void
        {
            if (!path || path.length == 0)
            {
                clearImage();
                return;
            }

            // flipWithImage 预加载/翻转期间，同路径的直接 setImage 会被拦截——
            // 换图统一交给翻转中点执行，否则图片会在翻转开始前就被抢先替换
            // （大圆图片会同时经 as_setImages 与 flip 两路设置，见 _flipTargetPath）。
            if (_flipTargetPath && path == _flipTargetPath)
            {
                L.debug("setImage 被翻转目标拦截，交给中点换图: " + path);
                return;
            }

            // DEBUG：与 BitmapContainer/ImageCache 的图片日志重复，保留最外层摘要即可
            L.debug("加载图片: " + path);
            if (!_imageBmp)
            {
                _imageBmp = new BitmapContainer(_diameter, _diameter, _radius,
                                                 null, "cover");
                _imageBmp.x = -_radius;
                _imageBmp.y = -_radius;
                _imageBmp.mouseEnabled = false;
                _imageBmp.mouseChildren = false;
                _imageBmp.onReady = _onImageReady;
                _flipWrap.addChild(_imageBmp);
            }
            _imageBmp.load(path);
        }

        /** 清除图片，恢复默认填充外观。 */
        public function clearImage():void
        {
            if (_imageBmp)
                _imageBmp.clear();
            _fillSprite.visible = true;
        }

        /**
         * 2D 翻转——只翻图片，绕圆心竖直轴压扁再展开；
         * 背景填充和描边保持不动。
         * @param onMidpoint  压扁到 0 时的回调（可在此换图，当前可不传）
         */
        public function flip(onMidpoint:Function = null):void
        {
            // 纯翻转（不带换图回调）会打断进行中的 flipWithImage——
            // 清除其目标图拦截，避免后续 setImage 被永久挡掉
            if (onMidpoint == null)
                _flipTargetPath = null;

            // 防重入：上一次翻转未完成时先复位再重新开始
            Tween.kill(_flipWrap);
            _flipWrap.scaleX = 1.0;
            _flipping = true;

            var self:CircleButton = this;
            Tween.to(_flipWrap, 0.12, { scaleX: 0 }, Easing.easeInCubic,
                function():void {
                    if (onMidpoint != null)
                        onMidpoint();
                    Tween.to(self._flipWrap, 0.12, { scaleX: 1.0 },
                        Easing.easeOutCubic,
                        function():void { self._flipping = false; });
                });
            L.debug("翻转");
        }

        /**
         * 翻转中途换图——压扁到 0 时加载新图片，再展开。
         * 用于切换语音包时替换大圆 menu.png。
         *
         * ★ 翻转前先预加载图片到 ImageCache——Scaleform 的 Loader
         * 是异步的，若等到翻转中点（~0.12s）才发起加载，回调远未触发，
         * 翻转展开时仍是旧图。预加载到缓存后，中点 setImage 触发的是
         * 同步缓存命中，图片瞬间替换，视觉上在翻转后半程看到新图。
         *
         * @param newImagePath  Flash 可加载的图片路径
         */
        public function flipWithImage(newImagePath:String):void
        {
            if (!newImagePath || newImagePath.length == 0)
            {
                flip();
                return;
            }

            var self:CircleButton = this;
            // 立即标记翻转目标图——从此刻起直到翻转中点，同路径的直接
            // setImage 会被拦截，避免图片在翻转开始前被抢先替换
            _flipTargetPath = newImagePath;
            ImageCache.load(newImagePath, function(bmd:BitmapData, success:Boolean):void {
                if (!success)
                    L.warn("翻转前预加载失败，仍翻转但保持原图: " + newImagePath);
                // 无论加载成功与否都执行翻转（失败时保持原图不换）
                self.flip(function():void {
                    // 中点：先解除目标图拦截，再换图（成功时）。
                    // 此刻图片不可见（scaleX=0），替换后随后半段翻转展开
                    self._flipTargetPath = null;
                    if (success)
                    {
                        L.info("翻转中点 → 换图 (缓存命中): " + newImagePath);
                        self.setImage(newImagePath);
                    }
                });
            });
        }

        /**
         * 旋转图片——以圆心为轴旋转指定角度（正值=顺时针）。
         * 与其他补间（flip 的 scaleX）并行运行互不干扰。
         * @param delta    旋转增量角度（度）
         * @param duration 动画时长（秒）
         * @param easing   缓动函数（如 Easing.easeOutCubic）
         */
        public function rotate(delta:Number, duration:Number,
                               easing:Function = null):void
        {
            if (easing == null) easing = Easing.easeOutCubic;
            Tween.to(_flipWrap, duration,
                { rotation: _flipWrap.rotation + delta }, easing);
        }

        /**
         * 呼吸效果——整个大圆（底色+描边+图片）以圆心为中心
         * 等比放大到 peak 再缩回 1.0。
         * 一次完整呼吸，总时长 duration（前半鼓起、后半回落）。
         * @param peak     峰值缩放（如 1.06 = 放大 6%）
         * @param duration 总时长（秒），与面板收展动画对齐
         */
        public function breathe(peak:Number = 1.06, duration:Number = 0.4):void
        {
            _stopBreathe();
            var self:CircleButton = this;
            // 填充层与图片层同步补间（填充层原点已在圆心）
            _breatheFillTween = Tween.to(_fillSprite, duration / 2,
                { scaleX: peak, scaleY: peak }, Easing.easeOutCubic);
            _breatheTween = Tween.to(_flipWrap, duration / 2,
                { scaleX: peak, scaleY: peak }, Easing.easeOutCubic,
                function():void {
                    self._breatheFillTween = Tween.to(self._fillSprite,
                        duration / 2, { scaleX: 1.0, scaleY: 1.0 },
                        Easing.easeInCubic);
                    self._breatheTween = Tween.to(self._flipWrap,
                        duration / 2, { scaleX: 1.0, scaleY: 1.0 },
                        Easing.easeInCubic,
                        function():void {
                            self._breatheTween = null;
                            self._breatheFillTween = null;
                        });
                });
        }

        /** 停止进行中的呼吸并复位缩放。 */
        private function _stopBreathe():void
        {
            if (_breatheTween)
            {
                _breatheTween.stop();
                _breatheTween = null;
            }
            if (_breatheFillTween)
            {
                _breatheFillTween.stop();
                _breatheFillTween = null;
            }
            _flipWrap.scaleX = 1.0;
            _flipWrap.scaleY = 1.0;
            _fillSprite.scaleX = 1.0;
            _fillSprite.scaleY = 1.0;
        }

        /** 直径（px）。 */
        public function get diameter():Number { return _diameter; }

        /** 半径（px）。 */
        public function get radius():Number { return _radius; }

        /** 设置颜色集中的属性。 */
        public function setColors(fillColor:uint, strokeColor:uint = 0,
                                   strokeWidth:Number = 0):void
        {
            _fillColor   = fillColor;
            _strokeColor = strokeColor;
            _strokeWidth = strokeWidth;
            _drawFill();  // 只重绘，不改 visible——换肤与挂图互不干扰
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        private function _drawFill():void
        {
            _fillSprite.graphics.clear();

            if (_strokeWidth > 0)
            {
                _fillSprite.graphics.lineStyle(_strokeWidth, _strokeColor);
            }

            _fillSprite.graphics.beginFill(_fillColor);
            _fillSprite.graphics.drawCircle(0, 0, _radius);  // 以自身原点（圆心）绘制
            _fillSprite.graphics.endFill();
        }

        /** 图片加载回调——只有成功时才隐藏默认填充。 */
        private function _onImageReady(success:Boolean):void
        {
            if (success)
            {
                L.debug("图片就绪");
                if (_hideFillWhenImage)
                    _fillSprite.visible = false;
            }
            else
            {
                // 加载失败 → 保持/恢复默认外观
                _fillSprite.visible = true;
            }
        }

        private function _onSelfClick(event:MouseEvent):void
        {
            if (onClick != null)
                onClick();
        }

        // ═══════════════════════════════════════════════════════
        // ISoundable
        // ═══════════════════════════════════════════════════════

        public function canPlaySound(type:String):Boolean { return !SoundUtils.muted; }

        public function getSoundType():String { return "normal"; }

        public function getSoundId():String { return ""; }
    }
}
