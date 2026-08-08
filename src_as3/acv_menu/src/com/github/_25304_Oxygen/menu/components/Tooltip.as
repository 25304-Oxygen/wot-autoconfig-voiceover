package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.DisplayObject;
    import flash.display.Bitmap;
    import flash.display.BitmapData;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;
    import flash.events.TimerEvent;
    import flash.utils.Timer;
    import flash.geom.Point;
    import flash.geom.Rectangle;
    import flash.utils.Dictionary;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.ui.ImageCache;

    /**
     * 自定义 Tooltip 组件——富文本 + 图片混合布局。
     *
     * HTML 格式说明:
     *   每个 <p> 标签是一个"行块"，按顺序垂直排列。
     *   - <p align="left|center|right">…</p>  文本块，支持 <font>、<b> 等标签
     *   - <p align="center"><img src="…" width="200"/></p>  图片块
     *   - 无 <p> 标签时，整个字符串作为左对齐文本块
     *
     * 图片规则:
     *   - 已缓存的图片（ImageCache）→ 立即显示真实图片
     *   - 未缓存的图片 → 显示占位矩形，异步加载完成后原地替换
     *   - 不指定 width → 使用图片原始宽度，超过 maxWidth 时等比缩小
     *   - 指定 width → 等比缩放
     *   - 指定 width+height → 拉伸到精确尺寸（可能变形）
     *   - 图片不会超出 tooltip 边框
     *
     * 用法:
     *   // 方式一: 绑定到组件（hover 显示）
     *   Tooltip.attach(mySprite, '<p align="left">提示</p>');
     *   Tooltip.attach(mySprite, html, {maxWidth: 300});
     *
     *   // 方式二: Python 端触发（指定坐标）
     *   Tooltip.showAt(html, config, stageX, stageY);
     *
     *   // 清理
     *   Tooltip.detach(mySprite);
     *   Tooltip.hide();
     *   Tooltip.disposeAll();  // View 销毁时调用
     */
    public class Tooltip extends Sprite
    {
        private static const L:Object = Log.getLogger("Tooltip");

        // ═══════════════════════════════════════════════════════
        // 默认配置
        // ═══════════════════════════════════════════════════════

        private static const DEFAULT_MAX_WIDTH:Number = 300;
        private static const DEFAULT_MAX_HEIGHT:Number = 0;   // 0 = 不限制
        private static const DEFAULT_PADDING:Number = 10;    // 边框与内容左右间距（原 8）
        private static const DEFAULT_PADDING_V:Number = 15;  // 边框与内容上下间距
        private static const DEFAULT_STROKE_WIDTH:Number = 1.5;
        private static const DEFAULT_CORNER_RADIUS:Number = 6;
        private static const DEFAULT_GAP:Number = 4;
        private static const DEFAULT_DELAY:int = 400;
        private static const HIDE_DELAY:int = 150;     // 光标移开后保留时间，供用户移到滚动条上
        private static const CURSOR_OFFSET:int = 12;
        private static const STAGE_MARGIN:int = 8;

        // 文本默认样式
        private static const TEXT_SIZE:int = 14;
        private static const TEXT_LEADING:int = 4;

        // 占位矩形默认尺寸（未缓存图片且未指定宽高时使用）
        private static const PLACEHOLDER_W:Number = 100;
        private static const PLACEHOLDER_H:Number = 60;

        // 滚动条
        private static const SB_W:Number = 5;           // 滚动条宽度
        private static const SB_MARGIN:Number = 2;      // 滚动条与边缘间距
        private static const WHEEL_STEP:int = 30;

        // ═══════════════════════════════════════════════════════
        // 静态成员
        // ═══════════════════════════════════════════════════════

        private static var _instance:Tooltip;
        private static var _bindings:Dictionary = new Dictionary();

        /**
         * 绑定 tooltip 到目标 DisplayObject。hover 时自动显示。
         * @param target  触发 tooltip 的显示对象
         * @param html    HTML 内容字符串
         * @param config  可选配置: maxWidth, padding, bgColor, strokeColor,
         *                strokeWidth, cornerRadius, gap, delay
         */
        public static function attach(target:DisplayObject, html:String, config:Object = null):void
        {
            if (_bindings[target])
                detach(target);

            var cfg:Object = _mergeConfig(config);
            _bindings[target] = {html: html, config: cfg};

            target.addEventListener(MouseEvent.MOUSE_OVER, _onTargetOver);
            target.addEventListener(MouseEvent.MOUSE_OUT, _onTargetOut);

            // 设置手型指针，标示"此处有 Tooltip"
            if (target is Sprite)
            {
                (target as Sprite).buttonMode = true;
                (target as Sprite).useHandCursor = true;
            }

            L.debug("已绑定 → " + target.name);
        }

        /** 解除目标组件的 tooltip 绑定。 */
        public static function detach(target:DisplayObject):void
        {
            if (!_bindings[target]) return;

            target.removeEventListener(MouseEvent.MOUSE_OVER, _onTargetOver);
            target.removeEventListener(MouseEvent.MOUSE_OUT, _onTargetOut);

            // 还原手型指针
            if (target is Sprite)
            {
                (target as Sprite).buttonMode = false;
                (target as Sprite).useHandCursor = false;
            }

            delete _bindings[target];

            L.debug("已解绑 → " + target.name);
        }

        /**
         * 程序化显示 tooltip（Python 端调用）。
         * @param html    HTML 内容
         * @param config  配置对象
         * @param stageX  舞台 X 坐标（可选，默认 0）
         * @param stageY  舞台 Y 坐标（可选，默认 0）
         */
        public static function showAt(html:String, config:Object = null,
                                       stageX:Number = 0, stageY:Number = 0):void
        {
            var inst:Tooltip = _getInstance();
            var cfg:Object = _mergeConfig(config);
            inst._html = html;
            inst._config = cfg;
            inst._showX = stageX;
            inst._showY = stageY;
            inst._target = null;
            inst.cancelShow();
            inst.doShow();
        }

        /** 立即隐藏当前 tooltip。 */
        public static function hide():void
        {
            if (_instance)
                _instance._doHide();
        }

        /** 清理所有绑定和实例（View 销毁时调用）。 */
        public static function disposeAll():void
        {
            for (var key:Object in _bindings)
            {
                var target:DisplayObject = key as DisplayObject;
                if (target)
                {
                    target.removeEventListener(MouseEvent.MOUSE_OVER, _onTargetOver);
                    target.removeEventListener(MouseEvent.MOUSE_OUT, _onTargetOut);
                }
            }
            _bindings = new Dictionary();

            if (_instance)
            {
                _instance.cancelShow();
                _instance._doHide();
                Theme.unregister(_instance);
                _instance = null;
            }
            L.debug("已全部清理");
        }

        // ═══════════════════════════════════════════════════════
        // 静态内部方法
        // ═══════════════════════════════════════════════════════

        private static function _getInstance():Tooltip
        {
            if (!_instance)
                _instance = new Tooltip();
            return _instance;
        }

        private static function _mergeConfig(config:Object):Object
        {
            var c:Object = {};
            c.maxWidth     = _getNum(config, "maxWidth",     DEFAULT_MAX_WIDTH);
            c.maxHeight    = _getNum(config, "maxHeight",    DEFAULT_MAX_HEIGHT);
            c.padding      = _getNum(config, "padding",      DEFAULT_PADDING);
            c.paddingV     = _getNum(config, "paddingV",     DEFAULT_PADDING_V);
            c.bgColor      = _getUint(config, "bgColor",     Theme.surface0);
            c.strokeColor  = _getUint(config, "strokeColor", Theme.stroke);
            c.strokeWidth  = _getNum(config, "strokeWidth",  DEFAULT_STROKE_WIDTH);
            c.cornerRadius = _getNum(config, "cornerRadius", DEFAULT_CORNER_RADIUS);
            c.gap          = _getNum(config, "gap",          DEFAULT_GAP);
            c.delay        = _getNum(config, "delay",        DEFAULT_DELAY);
            c.showScrollBar = _getBool(config, "showScrollBar", false);
            return c;
        }

        private static function _getNum(config:Object, key:String, fallback:Number):Number
        {
            if (config && config.hasOwnProperty(key))
            {
                var v:Number = Number(config[key]);
                return isNaN(v) ? fallback : v;
            }
            return fallback;
        }

        /**
         * 读取 uint 配置值。支持:
         *   - AS3 uint 字面量: {bgColor: 0x1E1E1E}
         *   - 十六进制字符串:  {bgColor: "0x1E1E1E"} 或 "#1E1E1E"
         *   - 十进制数字:      {bgColor: 1973790}
         */
        private static function _getUint(config:Object, key:String, fallback:uint):uint
        {
            if (!config || !config.hasOwnProperty(key))
                return fallback;

            var val:* = config[key];
            if (val is String)
            {
                var s:String = String(val);
                if (s.indexOf("0x") == 0 || s.indexOf("0X") == 0)
                    s = s.substring(2);
                if (s.indexOf("#") == 0)
                    s = s.substring(1);
                var result:uint = parseInt("0x" + s);
                return isNaN(result) ? fallback : result;
            }
            return uint(val);
        }

        /** 读取 Boolean 配置值。 */
        private static function _getBool(config:Object, key:String, fallback:Boolean):Boolean
        {
            if (config && config.hasOwnProperty(key))
                return Boolean(config[key]);
            return fallback;
        }

        // ═══════════════════════════════════════════════════════
        // 静态事件处理
        // ═══════════════════════════════════════════════════════

        private static function _onTargetOver(event:MouseEvent):void
        {
            var target:DisplayObject = event.currentTarget as DisplayObject;
            var binding:Object = _bindings[target];
            if (!binding) return;

            var inst:Tooltip = _getInstance();
            inst._html   = binding.html;
            inst._config = binding.config;
            inst._target = target;
            inst._showX  = 0;
            inst._showY  = 0;
            inst.beginShow();
        }

        private static function _onTargetOut(event:MouseEvent):void
        {
            var target:DisplayObject = event.currentTarget as DisplayObject;
            var inst:Tooltip = _getInstance();
            if (inst._target == target)
                inst.beginHide();  // 延迟隐藏，给用户时间把光标移到 Tooltip 上
        }

        // ═══════════════════════════════════════════════════════
        // 实例字段
        // ═══════════════════════════════════════════════════════

        private var _html:String;
        private var _rawHtml:String;
        private var _config:Object;
        private var _target:DisplayObject;

        private var _blocks:Array;
        private var _bg:Shape;

        private var _contentW:Number = 0;
        private var _contentH:Number = 0;

        // 滚动支持
        private var _contentContainer:Sprite;   // 包裹所有块，scrollRect 裁剪
        private var _sbTrack:Shape;             // 滚动条轨道
        private var _sbThumb:Shape;             // 滚动条拇指（仅视觉指示）
        private var _scrollPos:Number = 0;
        private var _maxScroll:Number = 0;
        private var _needsScroll:Boolean = false;
        private var _totalContentH:Number = 0;  // 内容总高度（未裁剪）

        private var _showTimer:Timer;    // 延迟显示计时器（hover 后等待 delay ms）
        private var _hideTimer:Timer;    // 延迟隐藏计时器（给用户时间把光标移到 Tooltip 上）
        private var _isShowing:Boolean = false;
        private var _isBuilt:Boolean = false;

        private var _showX:Number = 0;
        private var _showY:Number = 0;

        /** 记录进行中的异步图片加载数量，用于 debug。 */
        private var _pendingImageLoads:int = 0;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        public function Tooltip()
        {
            super();
            this.visible = false;
            this.mouseEnabled = false;
            this.mouseChildren = false;
            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 显示 / 隐藏流程
        // ═══════════════════════════════════════════════════════

        /** 启动延迟计时器，到期后显示。 */
        public function beginShow():void
        {
            // 确保自身已添加到 stage（Tooltip 默认 visible=false，不影响交互）
            if (!this.parent)
            {
                var s:* = _resolveStage();
                if (s) s.addChild(this);
            }

            if (!_showTimer)
            {
                _showTimer = new Timer(_config.delay, 1);
                _showTimer.addEventListener(TimerEvent.TIMER_COMPLETE, _onShowTimerComplete);
            }
            _showTimer.reset();
            _showTimer.start();
        }

        /** 取消显示（鼠标移出或切换目标）。 */
        public function cancelShow():void
        {
            if (_showTimer && _showTimer.running)
                _showTimer.stop();
            _doHide();
        }

        /**
         * 延迟隐藏——给用户 150ms 把光标从绑定组件移到 Tooltip 上。
         * 如果延迟期间光标进入 Tooltip，则取消隐藏，保持可见供用户操作滚动条。
         */
        public function beginHide():void
        {
            // 取消尚未触发的 show 计时器——鼠标已在延迟期间移出目标
            if (_showTimer && _showTimer.running)
                _showTimer.stop();

            // 开启鼠标检测，让 Tooltip 能接收 MOUSE_OVER/MOUSE_OUT
            this.mouseEnabled = true;

            if (!_hideTimer)
            {
                _hideTimer = new Timer(HIDE_DELAY, 1);
                _hideTimer.addEventListener(TimerEvent.TIMER_COMPLETE, _onHideTimerComplete);
            }
            _hideTimer.reset();
            _hideTimer.start();

            this.addEventListener(MouseEvent.MOUSE_OVER, _onTooltipOver);
        }

        private function _onShowTimerComplete(event:TimerEvent):void
        {
            // 到期前目标已被移除 stage → 不显示
            if (_target && !_target.stage)
                return;
            doShow();
        }

        private function _onHideTimerComplete(event:TimerEvent):void
        {
            this.removeEventListener(MouseEvent.MOUSE_OVER, _onTooltipOver);
            _doHide();
        }

        /** 光标进入 Tooltip → 取消隐藏倒计时，保持可见。 */
        private function _onTooltipOver(event:MouseEvent):void
        {
            if (_hideTimer && _hideTimer.running)
                _hideTimer.stop();
            this.removeEventListener(MouseEvent.MOUSE_OVER, _onTooltipOver);
            // 开始监听光标何时离开 Tooltip
            this.addEventListener(MouseEvent.MOUSE_OUT, _onTooltipOut);
        }

        /** 光标离开 Tooltip → 立即隐藏。 */
        private function _onTooltipOut(event:MouseEvent):void
        {
            this.removeEventListener(MouseEvent.MOUSE_OUT, _onTooltipOut);
            _doHide();
        }

        /** 实际构建并显示 tooltip。 */
        public function doShow():void
        {
            if (_isShowing) return;

            var s:* = _resolveStage();
            if (!s)
            {
                L.warn("无 stage 引用，无法显示");
                return;
            }

            _isShowing = true;

            if (!this.parent)
                s.addChild(this);

            // 每次显示前用最新主题颜色刷新配置——
            // 解决 bindings 在 Tooltip 单例创建前 attach 导致的颜色 stale 问题：
            // · 插件首次启动→换肤→首次触发 Tooltip（Theme.apply 时单例未创建，回调未执行）
            // · 重进游戏→非默认主题→Tooltip 背景色使用默认值
            _config.bgColor = Theme.surface0;
            _config.strokeColor = Theme.stroke;

            // 保存原始 HTML（后续换肤 rebuild 时重新预处理 class 标记）
            _rawHtml = _html;
            _html = _processHtmlClasses(_html);

            _build();
            _position();
            this.visible = true;

            L.debug("显示 (" + int(_contentW) + "×" + int(_contentH) + ")"
                + (_pendingImageLoads > 0 ? " 异步图片: " + _pendingImageLoads : ""));
        }

        private function _doHide():void
        {
            if (!_isShowing) return;
            _isShowing = false;
            _pendingImageLoads = 0;
            this.visible = false;
            this.mouseEnabled = false;

            // 清理隐藏倒计时相关监听器
            if (_hideTimer && _hideTimer.running)
                _hideTimer.stop();
            this.removeEventListener(MouseEvent.MOUSE_OVER, _onTooltipOver);
            this.removeEventListener(MouseEvent.MOUSE_OUT, _onTooltipOut);

            if (this.parent)
                this.parent.removeChild(this);

            L.debug("隐藏");
        }

        /** 获取可用的 stage 引用。 */
        private function _resolveStage():*
        {
            if (this.stage) return this.stage;
            if (_target && _target.stage) return _target.stage;
            return null;
        }

        /** 主题刷新回调——更新所有 binding 缓存的颜色并重绘。 */
        private function _refreshStyle():void
        {
            // —— 更新所有 binding 的缓存默认颜色 ——
            for (var key:Object in _bindings)
            {
                var binding:Object = _bindings[key];
                if (binding && binding.config)
                {
                    binding.config.bgColor = Theme.surface0;
                    binding.config.strokeColor = Theme.stroke;
                }
            }

            // —— 更新当前实例 config（防御 null：首次显示前 Theme.apply 时 _config 尚未设置）——
            if (_config)
            {
                _config.bgColor = Theme.surface0;
                _config.strokeColor = Theme.stroke;
            }

            // —— 当前可见时重建（用新主题颜色重处理 class 标记）——
            if (_isShowing)
            {
                // 有 _rawHtml 说明使用了 class 标记 → 重新预处理 + 完全重建
                if (_rawHtml)
                {
                    _html = _processHtmlClasses(_rawHtml);
                    _build();
                }
                else
                {
                    // 遗留路径：无 class 标记的纯色 tooltip → 只重绘背景+滚动条
                    _drawBackground();
                    if (_needsScroll && _config && _config.showScrollBar != false)
                    {
                        _drawScrollBar();
                        _updateScrollThumb();
                    }

                    // 更新可见文本块颜色
                    if (_blocks)
                    {
                        var newColor:uint = Theme.textPrimary;
                        for (var i:int = 0; i < _blocks.length; i++)
                        {
                            var disp:DisplayObject = _blocks[i] as DisplayObject;
                            if (disp is TextField)
                            {
                                var tf:TextField = disp as TextField;
                                tf.textColor = newColor;
                            }
                        }
                    }
                }
            }
        }

        // ═══════════════════════════════════════════════════════
        // 布局构建
        // ═══════════════════════════════════════════════════════

        private function _build():void
        {
            if (_isBuilt) _clear();

            var blocks:Array = _parseHTML(_html);
            var pad:Number   = _config.padding;
            var padV:Number  = _config.paddingV;
            var maxW:Number  = _config.maxWidth;
            var maxH:Number  = Number(_config.maxHeight) || 0;
            var availW:Number = maxW - pad * 2;
            var gap:Number   = _config.gap;

            _blocks = [];
            _pendingImageLoads = 0;

            // ═══════════════════════════════════════════
            // 第一趟：创建所有块，只测量尺寸
            // ═══════════════════════════════════════════
            var blockInfos:Array = [];
            var totalH:Number = 0;

            for each (var block:Object in blocks)
            {
                var disp:DisplayObject;
                var bw:Number = 0;
                var bh:Number = 0;

                if (block.type == "image")
                {
                    disp = _createImageBlock(block, availW);
                    bw = disp.width;
                    bh = disp.height;
                }
                else
                {
                    var textResult:Object = _createTextBlock(
                        block.html, block.align, availW);
                    disp = textResult.tf as DisplayObject;
                    bw = textResult.textWidth;
                    bh = textResult.height;
                }

                blockInfos.push({
                    disp: disp, bw: bw, bh: bh, align: block.align
                });
                totalH += bh + gap;
            }
            _totalContentH = totalH - gap + padV * 2;  // 含顶部 + 底部间距

            // ═══════════════════════════════════════════
            // 计算内容宽度（考虑对齐偏移后的右边界）
            // ═══════════════════════════════════════════
            var maxRight:Number = 0;
            for each (var info:Object in blockInfos)
            {
                var testOx:Number = pad;
                if (info.align == "center")
                    testOx = pad + (availW - info.bw) / 2;
                else if (info.align == "right")
                    testOx = pad + availW - info.bw;
                var rightEdge:Number = (testOx - pad) + info.bw;
                maxRight = Math.max(maxRight, rightEdge);
            }
            // 内容宽度 = 最右边界 + 可能的滚动条空间，但不超 maxWidth
            _contentW = Math.min(availW, Math.max(maxRight, 50));

            // ═══════════════════════════════════════════
            // 滚动判断
            // ═══════════════════════════════════════════
            _needsScroll = (maxH > 0 && _totalContentH > maxH);
            _contentH = _needsScroll ? maxH : _totalContentH;
            _scrollPos = 0;
            _maxScroll = _needsScroll ? _totalContentH - _contentH : 0;

            // ═══════════════════════════════════════════
            // 内容容器（滚动时需要 scrollRect 裁剪）
            // ═══════════════════════════════════════════
            _contentContainer = new Sprite();
            if (_needsScroll)
            {
                _contentContainer.scrollRect = new Rectangle(
                    0, 0, _contentW, _contentH);
                // 启用鼠标事件以接收滚轮
                this.mouseEnabled = true;
                this.addEventListener(MouseEvent.MOUSE_WHEEL,
                    _onWheel, false, 0, true);
            }

            // ═══════════════════════════════════════════
            // 第二趟：用实际 _contentW 重算对齐偏移，放入容器
            // ═══════════════════════════════════════════
            var curY:Number = padV;
            for each (info in blockInfos)
            {
                var ox:Number = pad;
                if (info.align == "center")
                    ox = pad + (_contentW - info.bw) / 2;
                else if (info.align == "right")
                    ox = pad + _contentW - info.bw;
                info.disp.x = int(ox);
                info.disp.y = int(curY);

                _contentContainer.addChild(info.disp);
                _blocks.push(info.disp);
                curY += info.bh + gap;
            }
            this.addChild(_contentContainer);

            // ═══════════════════════════════════════════
            // 背景
            // ═══════════════════════════════════════════
            _drawBackground();

            // ═══════════════════════════════════════════
            // 滚动条（在背景之上）
            // ═══════════════════════════════════════════
            if (_needsScroll && _config.showScrollBar != false)
            {
                _drawScrollBar();
                _updateScrollThumb();
            }

            _isBuilt = true;
        }

        private function _clear():void
        {
            this.removeEventListener(MouseEvent.MOUSE_WHEEL, _onWheel);
            while (this.numChildren > 0)
                this.removeChildAt(0);
            _bg = null;
            _sbTrack = null;
            _sbThumb = null;
            _contentContainer = null;
            _blocks = null;
            _contentW = 0;
            _contentH = 0;
            _scrollPos = 0;
            _maxScroll = 0;
            _needsScroll = false;
            _totalContentH = 0;
            _isBuilt = false;
        }

        // ═══════════════════════════════════════════════════════
        // HTML 预处理 —— 将 class 标记替换为当前主题实际颜色
        // ═══════════════════════════════════════════════════════

        /**
         * 将 HTML 中的 class 标记替换为当前主题颜色值。
         *
         * Python 端生成 HTML 时使用语义 class（如 class="secondary"），
         * 与具体颜色值解耦。Flash 端在渲染前替换为实际 Theme 颜色。
         *
         * 支持的 class:
         *   secondary  → Theme.textSecondary（次要/说明文字）
         */
        private function _processHtmlClasses(html:String):String
        {
            if (!html || html.length == 0) return html;

            // 快速检查——避免仅为了 test() 而触发 RegExp 有状态 lastIndex
            if (html.indexOf('class="secondary"') == -1
                && html.indexOf("class='secondary'") == -1)
                return html;

            var secColor:String = Theme.textSecondary.toString(16).toUpperCase();
            while (secColor.length < 6) secColor = "0" + secColor;
            secColor = "#" + secColor;

            L.debug("_processHtmlClasses: 替换 class=\"secondary\" → color=\""
                + secColor + "\" (HTML " + html.length + " 字符)");

            // 仅替换 class="secondary"/class='secondary' → color="#XXXXXX"，
            // 不动 <font 前缀和其他属性。不用 \b——Scaleform 正则引擎可能
            // 不支持单词边界，导致替换静默失败。
            // 之前用 /<font\s+class.../ 会把 <font 前缀和 class 之后的
            // 属性（如 size="11"）截断成裸文本，尖括号泄漏。
            var result:String = html.replace(
                /class\s*=\s*["']secondary["']/gi,
                'color="' + secColor + '"');
            return result;
        }

        // ═══════════════════════════════════════════════════════
        // HTML 解析
        // ═══════════════════════════════════════════════════════

        /**
         * 解析 HTML 为块描述数组。
         * 支持 <p align="...">…</p>，内部可含 <img>。
         * 无 <p> 标签时自动包裹为左对齐文本块。
         *
         * ⚠ 使用 indexOf 手动解析，不依赖正则非贪婪量词 (*?)——
         *   Scaleform 正则引擎可能不支持非贪婪。
         *
         * @return [{type: "text"|"image", html/src/width/height, align}, …]
         */
        private function _parseHTML(html:String):Array
        {
            var blocks:Array = [];
            if (!html || html.length == 0) return blocks;

            // ── 用 indexOf 找出所有 <p>…</p> 块，不用非贪婪正则 ──
            var searchFrom:int = 0;
            var len:int = html.length;

            while (searchFrom < len)
            {
                // 找下一个 "<p"
                var tagStart:int = html.indexOf("<p", searchFrom);
                if (tagStart == -1) break;

                // 确保是 <p> 标签而非 <pre>/<param>
                var afterP:String = html.charAt(tagStart + 2);
                if (afterP != " " && afterP != ">" && afterP != "\t" && afterP != "\r" && afterP != "\n")
                {
                    searchFrom = tagStart + 2;
                    continue;
                }

                // 找 <p ... > 的 >
                var gtPos:int = html.indexOf(">", tagStart + 2);
                if (gtPos == -1) { searchFrom = tagStart + 2; continue; }

                // 找对应的 </p>
                var closePos:int = html.indexOf("</p>", gtPos + 1);
                if (closePos == -1) { searchFrom = gtPos + 1; continue; }

                var fullTag:String = html.substring(tagStart, closePos + 4);
                var content:String = html.substring(gtPos + 1, closePos);

                // 提取 align 属性
                var align:String = "left";
                var alignMatch:Array = fullTag.match(
                    /<p\b[^>]*align\s*=\s*["'](\w+)["'][^>]*>/i);
                if (alignMatch)
                {
                    align = (alignMatch[1] as String).toLowerCase();
                    if (align != "left" && align != "center" && align != "right")
                        align = "left";
                }

                // ── 检查是否包含图片 ──
                var imgMatch:Array = content.match(/<img\b[^>]*\/?>/i);
                if (imgMatch)
                {
                    var imgTag:String = imgMatch[0];

                    var src:String = "";
                    var srcMatch:Array = imgTag.match(/src\s*=\s*["']([^"']*)["']/i);
                    if (srcMatch) src = srcMatch[1];

                    var w:Number = 0;
                    var wMatch:Array = imgTag.match(/width\s*=\s*["'](\d+)["']/i);
                    if (wMatch) w = Number(wMatch[1]);

                    var h:Number = 0;
                    var hMatch:Array = imgTag.match(/height\s*=\s*["'](\d+)["']/i);
                    if (hMatch) h = Number(hMatch[1]);

                    blocks.push({
                        type: "image", src: src,
                        width: w, height: h,
                        align: align
                    });
                }
                else
                {
                    blocks.push({
                        type: "text", html: content, align: align
                    });
                }

                searchFrom = closePos + 4;
            }

            // ── 回退: 无 <p> 标签 → 整串作为左对齐文本块 ──
            if (blocks.length == 0)
            {
                blocks.push({type: "text", html: html, align: "left"});
            }

            return blocks;
        }

        // ═══════════════════════════════════════════════════════
        // 文本块创建
        // ═══════════════════════════════════════════════════════

        private function _createTextBlock(html:String, align:String,
                                           maxWidth:Number):Object
        {
            // 默认 TextFormat → htmlText 中的 <font> 标签会覆盖默认值
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = TEXT_SIZE;
            fmt.color = Theme.textPrimary;
            fmt.leading = TEXT_LEADING;

            if (align == "center")
                fmt.align = "center";
            else if (align == "right")
                fmt.align = "right";
            else
                fmt.align = "left";

            // ── 测量真实文字宽度 ──
            // Scaleform 中 textWidth 对粗体 <b> 等标签测量偏小，不可靠。
            // 用独立 autoSize TextField 获取精确宽度后再创建显示用 TextField。
            var measureTF:TextField = new TextField();
            measureTF.defaultTextFormat = fmt;
            measureTF.selectable = false;
            measureTF.mouseEnabled = false;
            measureTF.wordWrap = false;
            measureTF.multiline = true;
            measureTF.autoSize = "left";
            measureTF.htmlText = html;
            var measuredW:Number = Math.min(measureTF.width + 2, maxWidth);

            // ── 创建显示用 TextField ──
            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.wordWrap = true;
            tf.multiline = true;
            tf.width = measuredW;  // 用测量宽度，防止 TextField 超出 tooltip 背景
            tf.htmlText = html;

            var actualHeight:Number = tf.textHeight + TEXT_LEADING;
            tf.height = actualHeight;

            return {tf: tf, textWidth: measuredW, height: actualHeight};
        }

        // ═══════════════════════════════════════════════════════
        // 图片块创建（ImageCache 集成）
        // ═══════════════════════════════════════════════════════

        /**
         * 创建图片显示对象。
         *   - 已缓存 → 立即显示 Bitmap（使用真实尺寸，受 maxWidth 和 width/height 约束）
         *   - 未缓存 → 显示占位矩形，异步加载后原地替换
         *
         * 容器尺寸在创建时就确定，异步加载不会导致 re-layout。
         */
        private function _createImageBlock(block:Object, maxWidth:Number):DisplayObject
        {
            var src:String = block.src || "";
            var specifiedW:Number = block.width;   // 0 = 未指定
            var specifiedH:Number = block.height;

            // ── 尝试从缓存获取 ──
            var bmd:BitmapData = (src.length > 0) ? ImageCache.getCached(src) : null;

            var displayW:Number;
            var displayH:Number;

            if (bmd)
            {
                // 已缓存 → 使用真实尺寸
                displayW = specifiedW > 0 ? specifiedW : bmd.width;
                displayH = specifiedH > 0 ? specifiedH : bmd.height;
            }
            else
            {
                // 未缓存 → 占位尺寸
                displayW = specifiedW > 0 ? specifiedW : PLACEHOLDER_W;
                displayH = specifiedH > 0 ? specifiedH : PLACEHOLDER_H;
            }

            // 等比缩放: 宽度不超过 maxWidth
            if (displayW > maxWidth)
            {
                var scale:Number = maxWidth / displayW;
                displayW = maxWidth;
                displayH = int(displayH * scale);
            }

            var container:Sprite = new Sprite();

            if (bmd)
            {
                // 已缓存 → 直接显示真实图片
                var bmp:Bitmap = new Bitmap(bmd);
                bmp.smoothing = true;
                bmp.width = displayW;
                bmp.height = displayH;
                container.addChild(bmp);
            }
            else
            {
                // 未缓存 → 占位矩形 + 异步加载
                _drawPlaceholder(container, displayW, displayH);

                if (src.length > 0)
                {
                    _pendingImageLoads++;
                    // 捕获本次 build 的容器引用和当前 tooltip 实例
                    var inst:Tooltip = this;
                    ImageCache.load(src, function(loadedBmd:BitmapData, success:Boolean):void
                    {
                        inst._onImageLoaded(container, loadedBmd, success,
                                           specifiedW, specifiedH, maxWidth);
                    });
                }
            }

            return container;
        }

        /**
         * 异步图片加载完成回调。
         * 仅当 tooltip 仍在显示且容器仍在显示列表中时才替换占位内容。
         *
         * 根据真实图片尺寸重新计算显示尺寸（与缓存命中路径一致），
         * 避免使用占位矩形尺寸拉伸图片导致比例错误。
         */
        private function _onImageLoaded(container:Sprite, bmd:BitmapData,
                                         success:Boolean, specifiedW:Number,
                                         specifiedH:Number, maxWidth:Number):void
        {
            _pendingImageLoads = Math.max(0, _pendingImageLoads - 1);

            if (!success || !bmd)
            {
                L.warn("图片加载失败");
                return;
            }

            // 安全检查: tooltip 是否仍在显示 + 容器是否仍属于当前构建
            if (!_isShowing) return;
            if (!container.parent || container.parent != _contentContainer) return;

            // 根据真实图片尺寸重新计算显示尺寸（与缓存命中路径一致）
            var displayW:Number = specifiedW > 0 ? specifiedW : bmd.width;
            var displayH:Number = specifiedH > 0 ? specifiedH : bmd.height;
            if (displayW > maxWidth)
            {
                var scale:Number = maxWidth / displayW;
                displayW = maxWidth;
                displayH = int(displayH * scale);
            }

            // 替换占位内容为真实图片
            while (container.numChildren > 0)
                container.removeChildAt(0);

            var bmp:Bitmap = new Bitmap(bmd);
            bmp.smoothing = true;
            bmp.width = displayW;
            bmp.height = displayH;
            container.addChild(bmp);

            L.debug("异步图片已替换 " + bmd.width + "×" + bmd.height
                + " → " + int(displayW) + "×" + int(displayH));
        }

        /** 绘制占位矩形（深灰背景 + 对角线，表示图片正在加载）。 */
        private function _drawPlaceholder(container:Sprite, w:Number, h:Number):void
        {
            var placeholder:Shape = new Shape();

            var bg:uint = Theme.surface2;
            var line:uint = Theme.textSecondary;
            var alpha:Number = 0.4;

            placeholder.graphics.beginFill(bg, 1.0);
            placeholder.graphics.lineStyle(1, Theme.sbBtn, 0.6);
            placeholder.graphics.drawRect(0, 0, w, h);
            placeholder.graphics.endFill();

            // 对角线标记
            placeholder.graphics.lineStyle(1, line, alpha);
            placeholder.graphics.moveTo(0, 0);
            placeholder.graphics.lineTo(w, h);
            placeholder.graphics.moveTo(w, 0);
            placeholder.graphics.lineTo(0, h);

            container.addChild(placeholder);
        }

        // ═══════════════════════════════════════════════════════
        // 背景绘制
        // ═══════════════════════════════════════════════════════

        private function _drawBackground():void
        {
            if (_bg && this.contains(_bg))
                this.removeChild(_bg);

            var bg:Shape = new Shape();
            var showSB:Boolean = _needsScroll && _config.showScrollBar != false;
            var sbSpace:Number = showSB ? SB_W + SB_MARGIN : 0;
            var w:Number = _contentW + _config.padding * 2 + sbSpace;
            var h:Number = _contentH;
            var r:Number = _config.cornerRadius;
            var sw:Number = _config.strokeWidth;

            // 填充 + 描边
            if (sw > 0)
                bg.graphics.lineStyle(sw, _config.strokeColor);
            bg.graphics.beginFill(_config.bgColor, 1.0);
            bg.graphics.drawRoundRect(0, 0, w, h, r * 2, r * 2);
            bg.graphics.endFill();

            this.addChildAt(bg, 0);
            _bg = bg;
        }

        // ═══════════════════════════════════════════════════════
        // 滚动条（仅视觉指示 + 滚轮滚动）
        // ═══════════════════════════════════════════════════════

        /** 绘制滚动条轨道和拇指。 */
        private function _drawScrollBar():void
        {
            var trackX:Number = _contentW + _config.padding + SB_MARGIN;
            var trackH:Number = _contentH;
            var trackW:Number = SB_W;

            _sbTrack = new Shape();
            _sbTrack.graphics.beginFill(Theme.surface2, 1.0);
            _sbTrack.graphics.drawRoundRect(0, 0, trackW, trackH, 2, 2);
            _sbTrack.graphics.endFill();
            _sbTrack.x = trackX;
            _sbTrack.y = 0;
            this.addChild(_sbTrack);

            _sbThumb = new Shape();
            _sbThumb.x = trackX;
            this.addChild(_sbThumb);
        }

        /** 根据 _scrollPos 更新拇指位置和高度。 */
        private function _updateScrollThumb():void
        {
            if (!_sbThumb || !_needsScroll) return;

            var trackH:Number = _contentH;
            var ratio:Number = trackH / _totalContentH;
            var thumbH:Number = Math.max(10, ratio * trackH);
            var travel:Number = trackH - thumbH;
            var thumbY:Number = (_maxScroll > 0)
                ? (_scrollPos / _maxScroll) * travel : 0;

            _sbThumb.graphics.clear();
            _sbThumb.graphics.beginFill(Theme.sbThumb, 1.0);
            _sbThumb.graphics.drawRoundRect(0, 0, SB_W, thumbH, 2, 2);
            _sbThumb.graphics.endFill();
            _sbThumb.y = thumbY;
        }

        /** 滚轮滚动（捕获阶段，阻止冒泡）。 */
        private function _onWheel(event:MouseEvent):void
        {
            if (!_needsScroll || !_contentContainer) return;

            var delta:int = event.delta > 0 ? -1 : 1;
            _scrollPos = Math.max(0, Math.min(_maxScroll,
                _scrollPos + delta * WHEEL_STEP));
            _contentContainer.y = -_scrollPos;
            _updateScrollThumb();
            event.stopImmediatePropagation();
        }

        // ═══════════════════════════════════════════════════════
        // 定位
        // ═══════════════════════════════════════════════════════

        /** 计算 tooltip 最终位置（鼠标偏移 + 边界约束）。 */
        private function _position():void
        {
            var sx:Number, sy:Number;

            if (this.stage)
            {
                if (_showX != 0 || _showY != 0)
                {
                    // 手动指定坐标（showAt）
                    sx = _showX;
                    sy = _showY;
                }
                else
                {
                    // 跟随鼠标
                    sx = this.stage.mouseX + CURSOR_OFFSET;
                    sy = this.stage.mouseY + CURSOR_OFFSET;
                }
            }
            else
            {
                sx = 0;
                sy = 0;
            }

            var pos:Point = _clampPosition(sx, sy);
            this.x = pos.x;
            this.y = pos.y;
        }

        /** 将位置限制在舞台可见区域内。 */
        private function _clampPosition(x:Number, y:Number):Point
        {
            var stageW:Number = this.stage ? this.stage.stageWidth : 1920;
            var stageH:Number = this.stage ? this.stage.stageHeight : 1080;
            var w:Number = _bg ? _bg.width : 100;
            var h:Number = _bg ? _bg.height : 40;
            var margin:int = STAGE_MARGIN;

            if (x + w > stageW - margin)
                x = stageW - w - margin;
            if (y + h > stageH - margin)
                y = stageH - h - margin;
            if (x < margin)
                x = margin;
            if (y < margin)
                y = margin;

            return new Point(int(x), int(y));
        }
    }
}
