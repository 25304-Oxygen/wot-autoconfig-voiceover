package com.github._25304_Oxygen.menu.pages
{
    import flash.display.Sprite;
    import flash.display.DisplayObject;
    import flash.display.Bitmap;
    import flash.display.BitmapData;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.TextEvent;
    import flash.events.MouseEvent;
    import flash.geom.Rectangle;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.ui.ImageCache;
    import com.github._25304_Oxygen.shared.i18n.L10n;
    import com.github._25304_Oxygen.menu.components.Theme;
    import com.github._25304_Oxygen.menu.components.Tooltip;

    /**
     * HTML 内容页基类——渲染 Python 端推送的 HTML 文本。
     *
     * ⚠ 不使用 StyleSheet——Scaleform CSS 引擎点击 <a> 后会将
     *   :hover 样式泄漏到整个 TextField，不可修复。
     *
     * 设计:
     *   - 默认链接样式 → Python 端内联 <font color="..."><u>
     *   - 手型光标       → Scaleform TextField 的 <a> 标签原生行为
     *   - 点击回调       → TextEvent.LINK → onAction → Python
     *   - hover 变色     → 无法实现（setTextFormat 不能覆盖 htmlText 内联样式）
     *
     * Python → Flash 数据格式:
     *   {title: "页面标题", html: "<p>...</p>", titleTooltipHtml: "可选"}
     *
     * 链接 HTML 格式（Python 端负责内联样式）:
     *   <a href='event:payload'><font color='#4A90D9'><u>链接</u></font></a>
     *
     * ═══════════════════════════════════════════════════════════
     * v2: 块级布局——解析 <p> 为文本/图片块，手动排列，取代直接
     *     htmlText 赋值。此举支持 <img> 标签和 <font class="secondary">
     *     语义颜色标记，与 Tooltip 对齐。
     * ═══════════════════════════════════════════════════════════
     */
    public class HtmlContentPage extends BasePage
    {
        private static const L:Object = Log.getLogger("HtmlContentPage");

        // ═══════════════════════════════════════════════════════
        // 布局常量
        // ═══════════════════════════════════════════════════════

        private static const MARGIN_H:int = 10;
        private static const MARGIN_BOTTOM:int = 20;
        private static const TITLE_Y:int = 8;
        private static const PAGE_W:int = 660;
        private static const PAGE_H:int = 440;
        private static const WHEEL_STEP:int = 40;

        /** 正文默认字号（与 Tooltip 统一为 14）。 */
        private static const TEXT_SIZE:int = 14;
        /** 行距。 */
        private static const TEXT_LEADING:int = 4;
        /** 块之间的垂直间距。 */
        private static const BLOCK_GAP:int = 4;
        /** 图片最大宽度（等于内容区宽度）。 */
        private static const IMG_MAX_W:Number = PAGE_W - MARGIN_H * 2;
        /** 一个 <br> 孤立刻度 = 一行文字高度（字号 + 行距）。 */
        private static const SPACER_HEIGHT:int = TEXT_SIZE + TEXT_LEADING;

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        protected var _titleTF:TextField;
        protected var _titleWrapper:Sprite;
        protected var _titleText:String;

        /** 标题词典键（i18n，子类构造传入；空串 = 不参与 i18n）。 */
        private var _titleKey:String = "";

        /** populate 是否推送过 data.title（推送后不再被 _applyLabels 覆盖）。 */
        private var _titleOverridden:Boolean = false;

        /** 视口——用 scrollRect 裁剪内容。 */
        private var _viewport:Sprite;

        /** 内容容器——包裹所有布局块，滚动时整体位移。 */
        private var _contentContainer:Sprite;

        /** 布局块列表（TextField / Sprite），供换肤时遍历。 */
        private var _blocks:Array;

        // ═══════════════════════════════════════════════════════
        // 滚动
        // ═══════════════════════════════════════════════════════

        private var _scrollPos:Number = 0;
        private var _maxScroll:Number = 0;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        private var _initialized:Boolean = false;

        /** 异步图片加载计数（debug 用）。 */
        private var _pendingImageLoads:int = 0;

        /**
         * 原始 HTML 内容（预处理前）。
         * 换肤时需用 _preprocessHtml 重新替换 class 颜色后重建。
         */
        private var _rawHtml:String;

        public var onAction:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param pageId       页面唯一标识
         * @param defaultTitle 默认标题（labels 未推送前的首屏回退）
         * @param titleKey     标题词典键（i18n；空串 = 标题不参与 i18n）
         */
        public function HtmlContentPage(pageId:String, defaultTitle:String = "",
                                        titleKey:String = "")
        {
            super(pageId);
            _titleText = defaultTitle;
            _titleKey = titleKey;
        }

        // ═══════════════════════════════════════════════════════
        // 初始化
        // ═══════════════════════════════════════════════════════

        override public function init():void
        {
            if (_initialized) return;
            _initialized = true;

            _createTitle();
            _createContentArea();

            L10n.register(this, _applyLabels);
        }

        protected function _createTitle():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TitleFont";
            fmt.size = 18;
            fmt.color = Theme.textPrimary;

            _titleTF = new TextField();
            _titleTF.defaultTextFormat = fmt;
            _titleTF.text = _titleText;
            _titleTF.selectable = false;
            _titleTF.mouseEnabled = false;
            _titleTF.autoSize = "left";

            _titleWrapper = new Sprite();
            _titleWrapper.buttonMode = false;
            _titleWrapper.useHandCursor = false;
            _titleWrapper.addChild(_titleTF);
            _titleWrapper.x = MARGIN_H;
            _titleWrapper.y = SAFE_TOP + TITLE_Y;
            addChild(_titleWrapper);
        }

        private function _createContentArea():void
        {
            // 视口尺寸 = 全展开面板内容区减去标题高度
            var contentY:int = SAFE_TOP + TITLE_Y + 22 + 6;
            var contentH:int = SAFE_TOP + PAGE_H - MARGIN_BOTTOM - contentY;

            _contentContainer = new Sprite();

            _viewport = new Sprite();
            _viewport.x = MARGIN_H;
            _viewport.y = contentY;
            _viewport.scrollRect = new Rectangle(0, 0, PAGE_W, contentH);

            // ⚠ Scaleform 不支持 useCapture（捕获阶段），在 this 上加
            //    捕获监听器永远不会触发。改为让 _viewport 接收鼠标事件——
            //    空白区域（spacer、块间隙）的滚轮事件冒泡到 _viewport 时被拦截；
            //    TextField 上的滚轮事件由 TextField 直接监听抢先处理
            //    （stopImmediatePropagation 阻止冒泡，不会重复触发）。
            //
            //    ⚠ 关键：必须给 _viewport 画一个透明填充作为"命中区域"。
            //    Scaleform 的 hit-test 基于图形几何——空 Sprite（无 graphics、
            //    无子对象）不会拦截鼠标事件，事件直接穿透到 Stage。
            //    透明填充（alpha=0）提供命中区域，但不影响视觉效果。
            _viewport.mouseEnabled = true;
            _viewport.mouseChildren = true;
            _viewport.graphics.beginFill(0x000000, 0);
            _viewport.graphics.drawRect(0, 0, PAGE_W, contentH);
            _viewport.graphics.endFill();
            _viewport.addEventListener(MouseEvent.MOUSE_WHEEL, _onWheel);

            _viewport.addChild(_contentContainer);
            addChild(_viewport);

            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // Python → Flash 数据接口
        // ═══════════════════════════════════════════════════════

        public function populate(data:Object):void
        {
            if (!data)
            {
                L.warn("populate: data 为空");
                return;
            }

            if (data.title != null && _titleTF)
            {
                _titleText = String(data.title);
                _titleTF.text = _titleText;
                _titleOverridden = true;  // populate 的 title 优先于词典刷新
            }

            if (data.html != null && _contentContainer)
            {
                _buildContent(String(data.html));
            }

            if (data.titleTooltipHtml != null && _titleWrapper)
            {
                var ttHtml:String = String(data.titleTooltipHtml);
                if (ttHtml.length > 0)
                    Tooltip.attach(_titleWrapper, ttHtml);
            }

            L.info("(" + pageId + ") 数据已应用");
        }

        // ═══════════════════════════════════════════════════════
        // 内容构建（v2: 块级布局）
        // ═══════════════════════════════════════════════════════

        /**
         * 解析 HTML 并构建块级布局。
         * 替代原有 _contentTF.htmlText 直接赋值。
         */
        private function _buildContent(html:String):void
        {
            _clearContent();
            _rawHtml = html;  // 保存原始 HTML，供 _refreshStyle 换肤重建

            var preprocessed:String = _preprocessHtml(html);
            var blockDescs:Array = _parseHTML(preprocessed);
            if (!blockDescs || blockDescs.length == 0)
            {
                L.debug("_buildContent: 无有效块");
                return;
            }

            var curY:Number = 0;

            for each (var desc:Object in blockDescs)
            {
                var disp:DisplayObject;
                var bw:Number = 0;
                var bh:Number = 0;
                var isSpacer:Boolean = false;

                if (desc.type == "spacer")
                {
                    // spacer 块——透明 Sprite 占位，高度 = SPACER_HEIGHT
                    disp = new Sprite();
                    bh = Number(desc.height) || SPACER_HEIGHT;
                    bw = 0;  // spacer 不参与内容宽度计算
                    isSpacer = true;
                }
                else if (desc.type == "image")
                {
                    var imgResult:Object = _createImageBlock(desc);
                    disp = imgResult.disp as DisplayObject;
                    bw = imgResult.bw;  // 显式计算值，不依赖 Sprite.width
                    bh = imgResult.bh;
                }
                else
                {
                    var textResult:Object = _createTextBlock(
                        desc.html, desc.align, PAGE_W);
                    disp = textResult.tf as DisplayObject;
                    bw = textResult.textWidth;
                    bh = textResult.height;
                }

                // 对齐偏移（spacer 无对齐概念，始终 x=0）
                var ox:Number = 0;
                if (!isSpacer)
                {
                    if (desc.align == "center")
                        ox = int((PAGE_W - bw) / 2);
                    else if (desc.align == "right")
                        ox = int(PAGE_W - bw);
                }

                disp.x = ox;
                disp.y = int(curY);

                _contentContainer.addChild(disp);
                _blocks.push(disp);
                curY += bh + BLOCK_GAP;
            }

            _updateScrollRange();
        }

        /** 清除上次构建的内容。 */
        private function _clearContent():void
        {
            while (_contentContainer.numChildren > 0)
                _contentContainer.removeChildAt(0);
            _blocks = [];
            _scrollPos = 0;
            _maxScroll = 0;
            _pendingImageLoads = 0;
        }

        // ═══════════════════════════════════════════════════════
        // HTML 预处理
        // ═══════════════════════════════════════════════════════

        /**
         * 预处理 HTML 字符串：将 class 标记替换为当前主题实际颜色值。
         * 不再做 <br> 规范化——<br> 由 _parseHTML 基于位置处理。
         */
        private function _preprocessHtml(html:String):String
        {
            if (!html || html.length == 0) return html;
            return _processHtmlClasses(html);
        }

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
        // HTML 解析（位置驱动——不在 <p> 内的 <br> → spacer 块）
        // ═══════════════════════════════════════════════════════

        /**
         * 解析 HTML 为块描述数组。
         *
         * ⚠ 使用 indexOf 手动解析，不依赖正则非贪婪量词 (*?)——
         *   Scaleform 正则引擎可能不支持非贪婪，导致 /(.*?)/ 退化为
         *   贪婪匹配，从第一个 <p> 吞到最后一个 </p>，造成尖括号泄漏
         *   和布局错乱。
         *
         * @return [{type: "text"|"image"|"spacer",
         *          html/src/height/width, align}, …]
         */
        private function _parseHTML(html:String):Array
        {
            var blocks:Array = [];
            if (!html || html.length == 0) return blocks;

            // ── 第一趟：用 indexOf 找出所有 <p>…</p> 块 ──
            // 不用 RegExp——Scaleform 可能不支持非贪婪量词
            var pMatches:Array = [];
            var searchFrom:int = 0;
            var len:int = html.length;

            while (searchFrom < len)
            {
                // 找下一个 "<p"（可能带属性）
                var tagStart:int = html.indexOf("<p", searchFrom);
                if (tagStart == -1) break;

                // 确保是 <p> 标签而不是 <pre>/<param> 等——
                // <p 后跟空格、> 或属性
                var afterP:String = html.charAt(tagStart + 2);
                if (afterP != " " && afterP != ">" && afterP != "\t" && afterP != "\r" && afterP != "\n")
                {
                    // 不是 <p> 标签（如 <pre>、<param>）→ 跳过
                    searchFrom = tagStart + 2;
                    continue;
                }

                // 找 <p ... > 的 >
                var gtPos:int = html.indexOf(">", tagStart + 2);
                if (gtPos == -1)
                {
                    // 标签没闭合——跳过
                    searchFrom = tagStart + 2;
                    continue;
                }

                // 找对应的 </p>
                var closePos:int = html.indexOf("</p>", gtPos + 1);
                if (closePos == -1)
                {
                    // 没找到闭合标签——跳过
                    searchFrom = gtPos + 1;
                    continue;
                }

                // 提取
                var fullTag:String = html.substring(tagStart, closePos + 4);  // <p...>...</p>
                var content:String = html.substring(gtPos + 1, closePos);     // 标签之间的内容

                pMatches.push({
                    fullTag: fullTag,
                    content: content,
                    start:  tagStart,
                    end:    closePos + 4
                });

                searchFrom = closePos + 4;
            }

            // 回退: 无 <p> 标签 → 整串作为左对齐文本块
            if (pMatches.length == 0)
            {
                blocks.push({type: "text", html: html, align: "left"});
                L.debug("_parseHTML: 无 <p> 标签，回退为单一文本块");
                return blocks;
            }

            L.debug("_parseHTML: 找到 " + pMatches.length + " 个 <p> 块");

            // ── 第二趟：遍历 <p> 块 + 处理块间孤儿文本 ──
            var pos:int = 0;

            for each (var pm:Object in pMatches)
            {
                // 本 <p> 块之前的孤立文本 → 从中提取 <br> 作为 spacer
                if (int(pm.start) > pos)
                {
                    var orphan:String = html.substring(pos, int(pm.start));
                    _extractSpacers(blocks, orphan);
                }

                // 解析 <p> 块
                var align:String = _extractAlign(pm.fullTag as String);
                var blockContent:String = pm.content as String;

                // 检查是否包含图片
                var imgMatch:Array = blockContent.match(/<img\b[^>]*\/?>/i);
                if (imgMatch)
                {
                    var imgTag:String = imgMatch[0] as String;

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
                        type: "text", html: blockContent, align: align
                    });
                }

                pos = int(pm.end);
            }

            // 尾巴的孤立 <br>（最后一个 </p> 之后）
            if (pos < len)
            {
                var tail:String = html.substring(pos);
                _extractSpacers(blocks, tail);
            }

            L.debug("_parseHTML: 共 " + blocks.length + " 个布局块 (" + pMatches.length + " 文本/图片 + " + (blocks.length - pMatches.length) + " spacer)");

            return blocks;
        }

        /**
         * 处理 <p> 块之间的孤立文本。
         * - 其中的 <br> → spacer 块（每个高度 = SPACER_HEIGHT）
         * - 剥离 <br> 后剩余的非空白文本 → 左对齐文本块
         *
         * 这确保类似 "#简介\n<p>...</p>" 的内容中，<p> 之外的
         * 文本不会被丢弃（v2 此前只识别 <p> 块和孤立的 <br>）。
         */
        private function _extractSpacers(blocks:Array, text:String):void
        {
            if (!text || text.length == 0) return;

            var brPattern:RegExp = /<br\s*\/?>/gi;
            var count:int = 0;
            while (brPattern.exec(text) != null) count++;

            // 连续 <br> 分别创建 spacer（每个高度 = SPACER_HEIGHT），
            // 而非合并——与原始 htmlText 渲染中每个 <br> 占一整行一致
            for (var i:int = 0; i < count; i++)
            {
                blocks.push({type: "spacer", height: SPACER_HEIGHT});
            }

            // 剥离 <br> 标签和首尾空白后，若还有实际内容 → 文本块
            var remaining:String = text.replace(/<br\s*\/?>/gi, "");
            remaining = remaining.replace(/^\s+|\s+$/g, "");
            if (remaining.length > 0)
            {
                blocks.push({type: "text", html: remaining, align: "left"});
            }
        }

        /** 从 <p> 标签中提取 align 属性，缺省 "left"。 */
        private function _extractAlign(fullTag:String):String
        {
            var alignMatch:Array = fullTag.match(
                /<p\b[^>]*align\s*=\s*["'](\w+)["'][^>]*>/i);
            if (alignMatch)
            {
                var a:String = (alignMatch[1] as String).toLowerCase();
                if (a == "center" || a == "right") return a;
            }
            return "left";
        }

        // ═══════════════════════════════════════════════════════
        // 文本块创建
        // ═══════════════════════════════════════════════════════

        /**
         * 为一个文本块创建 TextField。
         * 全部使用 PAGE_W 宽度，不再单独测量——避免 Scaleform
         * autoSize TextField 对 <br> 多行内容测量不准的问题。
         *
         * @return {tf:TextField, textWidth:Number, height:Number}
         */
        private function _createTextBlock(html:String, align:String,
                                           maxWidth:Number):Object
        {
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

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.selectable = false;
            tf.mouseEnabled = true;   // 允许接收 LINK 事件
            tf.wordWrap = true;
            tf.multiline = true;
            tf.width = maxWidth;
            tf.htmlText = html;
            tf.addEventListener(TextEvent.LINK, _onLink);

            // TextField 直接监听滚轮——ScrollRect 不会触发原生滚动，
            // 且 Scaleform 不支持捕获阶段。此监听器在 target 阶段触发，
            // _onWheel 内 stopImmediatePropagation 阻止冒泡到 _viewport，
            // 确保不会重复滚动。
            tf.addEventListener(MouseEvent.MOUSE_WHEEL, _onWheel);

            // height 取 textHeight + 行距；靠 wordWrap=true 自动折行
            var actualHeight:Number = tf.textHeight + TEXT_LEADING;
            tf.height = actualHeight;

            return {tf: tf, textWidth: maxWidth, height: actualHeight};
        }

        // ═══════════════════════════════════════════════════════
        // 图片块创建（ImageCache 集成）
        // ═══════════════════════════════════════════════════════

        /** 占位矩形默认尺寸（未缓存图片且未指定宽高时使用）。 */
        private static const PLACEHOLDER_W:Number = 100;
        private static const PLACEHOLDER_H:Number = 60;

        /**
         * 创建图片显示对象。
         *   - 已缓存 → 立即显示 Bitmap
         *   - 未缓存 → 显示占位矩形，异步加载后原地替换
         *
         * @return {disp:DisplayObject, bw:Number, bh:Number}
         *         显式返回计算宽高，不依赖 Sprite.width
         *         （Scaleform 对含缩放 Bitmap 的容器 bounds 计算可能不精确）
         */
        private function _createImageBlock(block:Object):Object
        {
            var src:String = block.src || "";
            var specifiedW:Number = block.width;
            var specifiedH:Number = block.height;

            // 尝试从缓存获取
            var bmd:BitmapData = (src.length > 0) ? ImageCache.getCached(src) : null;

            var displayW:Number;
            var displayH:Number;

            if (bmd)
            {
                displayW = specifiedW > 0 ? specifiedW : bmd.width;
                displayH = specifiedH > 0 ? specifiedH : bmd.height;
            }
            else
            {
                displayW = specifiedW > 0 ? specifiedW : PLACEHOLDER_W;
                displayH = specifiedH > 0 ? specifiedH : PLACEHOLDER_H;
            }

            // 等比缩放: 宽度不超过 IMG_MAX_W
            if (displayW > IMG_MAX_W)
            {
                var scale:Number = IMG_MAX_W / displayW;
                displayW = IMG_MAX_W;
                displayH = int(displayH * scale);
            }

            var container:Sprite = new Sprite();

            if (bmd)
            {
                var bmp:Bitmap = new Bitmap(bmd);
                bmp.smoothing = true;
                bmp.width = displayW;
                bmp.height = displayH;
                container.addChild(bmp);
            }
            else
            {
                _drawPlaceholder(container, displayW, displayH);

                if (src.length > 0)
                {
                    _pendingImageLoads++;
                    var page:HtmlContentPage = this;
                    ImageCache.load(src, function(loadedBmd:BitmapData, success:Boolean):void
                    {
                        page._onImageLoaded(container, loadedBmd, success,
                                           specifiedW, specifiedH, block.align);
                    });
                }
            }

            return {disp: container, bw: displayW, bh: displayH};
        }

        /**
         * 异步图片加载完成回调。
         * 仅当页面仍在显示时替换占位内容。
         *
         * 根据真实图片尺寸重新计算显示尺寸（与缓存命中路径一致），
         * 避免使用占位矩形尺寸拉伸图片导致比例错误。
         *
         * 加载完成后重新计算容器 x 位置，确保异步加载的图片
         * （尺寸可能与占位矩形不同）仍然正确居中/右对齐。
         */
        private function _onImageLoaded(container:Sprite, bmd:BitmapData,
                                        success:Boolean, specifiedW:Number,
                                        specifiedH:Number, align:String):void
        {
            _pendingImageLoads = Math.max(0, _pendingImageLoads - 1);

            if (!success || !bmd)
            {
                L.warn("图片加载失败");
                return;
            }

            // 安全检查: 容器是否仍属于当前内容
            if (!container.parent || container.parent != _contentContainer)
                return;

            // 根据真实图片尺寸重新计算显示尺寸（与缓存命中路径一致）
            var displayW:Number = specifiedW > 0 ? specifiedW : bmd.width;
            var displayH:Number = specifiedH > 0 ? specifiedH : bmd.height;
            if (displayW > IMG_MAX_W)
            {
                var scale:Number = IMG_MAX_W / displayW;
                displayW = IMG_MAX_W;
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

            // 重新计算居中/右对齐偏移（异步加载后图片尺寸可能与占位不同）
            if (align == "center")
                container.x = int((PAGE_W - displayW) / 2);
            else if (align == "right")
                container.x = int(PAGE_W - displayW);

            // 异步加载后图片尺寸可能与占位矩形不同，必须重排所有块。
            // _updateScrollRange() 只更新 _maxScroll，不移动后续块的 Y 坐标——
            // 图片从占位高(60px)变为实际高可能导致后续块叠在图片上。
            _relayoutBlocks();

            L.debug("异步图片已替换 " + bmd.width + "×" + bmd.height
                + " → " + int(displayW) + "×" + int(displayH));
        }

        /** 绘制图片加载中的占位矩形。 */
        private function _drawPlaceholder(container:Sprite, w:Number, h:Number):void
        {
            var placeholder:Shape = new Shape();

            placeholder.graphics.beginFill(Theme.surface2, 1.0);
            placeholder.graphics.lineStyle(1, Theme.sbBtn, 0.6);
            placeholder.graphics.drawRect(0, 0, w, h);
            placeholder.graphics.endFill();

            // 对角线标记——表示正在加载
            placeholder.graphics.lineStyle(1, Theme.textSecondary, 0.4);
            placeholder.graphics.moveTo(0, 0);
            placeholder.graphics.lineTo(w, h);
            placeholder.graphics.moveTo(w, 0);
            placeholder.graphics.lineTo(0, h);

            container.addChild(placeholder);
        }

        // ═══════════════════════════════════════════════════════
        // 滚动
        // ═══════════════════════════════════════════════════════

        private function _updateScrollRange():void
        {
            if (!_viewport || !_contentContainer) return;

            // 计算内容容器实际高度（最后一个子对象底部）
            var contentH:Number = 0;
            for (var i:int = 0; i < _contentContainer.numChildren; i++)
            {
                var child:DisplayObject = _contentContainer.getChildAt(i);
                var bottom:Number = child.y + child.height;
                if (bottom > contentH) contentH = bottom;
            }

            var viewH:Number = _viewport.scrollRect.height;
            _maxScroll = Math.max(0, contentH - viewH);
            _scrollPos = 0;
            _applyScroll();
        }

        /**
         * 用子对象当前实际高度重排 Y 坐标，然后更新滚动范围。
         *
         * 与 _updateScrollRange() 的区别：
         *   - _updateScrollRange 仅遍历子对象计算 maxScroll，不修改 Y 坐标
         *   - _relayoutBlocks 按顺序重新计算每个子对象的 Y，修复异步图片加载
         *     后占位矩形 → 实际图片高度变化导致的布局重叠
         *
         * 保留当前 _scrollPos（若内容变短则 clamp 到新的 maxScroll）。
         */
        private function _relayoutBlocks():void
        {
            if (!_contentContainer) return;

            var curY:Number = 0;
            for (var i:int = 0; i < _contentContainer.numChildren; i++)
            {
                var child:DisplayObject = _contentContainer.getChildAt(i);
                child.y = int(curY);
                curY += child.height + BLOCK_GAP;
            }

            var contentH:Number = curY > 0 ? curY - BLOCK_GAP : 0;
            var viewH:Number = _viewport ? _viewport.scrollRect.height : 0;
            _maxScroll = Math.max(0, contentH - viewH);
            _scrollPos = Math.min(_scrollPos, _maxScroll);
            _applyScroll();
        }

        private function _applyScroll():void
        {
            if (!_contentContainer) return;
            _contentContainer.y = -_scrollPos;
        }

        private function _onWheel(event:MouseEvent):void
        {
            if (_maxScroll <= 0) return;
            var delta:int = event.delta > 0 ? -1 : 1;
            _scrollPos = Math.max(0, Math.min(_maxScroll,
                _scrollPos + delta * WHEEL_STEP));
            _applyScroll();
            event.stopImmediatePropagation();
        }

        // ═══════════════════════════════════════════════════════
        // 链接点击 → Python
        // ═══════════════════════════════════════════════════════

        private function _onLink(e:TextEvent):void
        {
            var payload:String = e.text || "";
            L.info("(" + pageId + ") 链接点击 → " + payload);

            if (onAction != null)
                onAction("htmlLink," + pageId + "," + payload);
        }

        // ═══════════════════════════════════════════════════════
        // 主题刷新
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            if (_titleTF) _titleTF.textColor = Theme.textPrimary;

            // 有原始 HTML 时——用新主题颜色重新预处理 class 标记并重建内容。
            // 这确保 <font class="secondary"> 的颜色跟随主题变化。
            // 同时也让图片占位符的背景色（Theme.surface2）跟随主题更新。
            if (_rawHtml && _rawHtml.length > 0 && _contentContainer)
            {
                _buildContent(_rawHtml);
                return;
            }

            // 回退路径：无 _rawHtml → 遍历现有 TextField 块更新默认文字颜色
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
                        // 不调 setTextFormat——会破坏 htmlText 内联样式
                    }
                }
            }
        }

        // ═══════════════════════════════════════════════════════
        // 生命周期
        // ═══════════════════════════════════════════════════════

        /** i18n 刷新回调——labels 推送后刷新标题（populate 覆盖过的标题不动）。 */
        private function _applyLabels():void
        {
            if (_titleOverridden || _titleKey.length == 0) return;
            if (_titleTF)
            {
                _titleText = L10n.get(_titleKey, _titleText);
                _titleTF.text = _titleText;
            }
        }

        override public function dispose():void
        {
            L.debug("dispose (" + pageId + ")");
            _initialized = false;

            Theme.unregister(this);
            L10n.unregister(this);

            if (_viewport)
                _viewport.removeEventListener(MouseEvent.MOUSE_WHEEL, _onWheel);

            if (_titleWrapper)
                Tooltip.detach(_titleWrapper);

            _clearContent();

            if (_titleWrapper && _titleWrapper.parent == this)
                removeChild(_titleWrapper);
            if (_viewport && _viewport.parent == this)
                removeChild(_viewport);

            _titleWrapper = null;
            _titleTF = null;
            _viewport = null;
            _contentContainer = null;
            _blocks = null;

            super.dispose();
        }
    }
}
