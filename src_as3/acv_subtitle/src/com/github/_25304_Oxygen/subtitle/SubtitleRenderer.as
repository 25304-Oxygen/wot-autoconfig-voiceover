package com.github._25304_Oxygen.subtitle
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.events.Event;
    import flash.events.TimerEvent;
    import flash.geom.Rectangle;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.text.AntiAliasType;
    import flash.utils.Timer;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.util.ColorUtil;
    import com.github._25304_Oxygen.shared.util.Typewriter;
    import com.github._25304_Oxygen.shared.ui.BitmapContainer;
    import com.github._25304_Oxygen.shared.tween.Tween;
    import com.github._25304_Oxygen.shared.tween.Easing;

    /**
     * 单条字幕渲染器。
     *
     * 两种模式:
     *   standard — 海报 + 背景 + 标题行 + 正文（四层）
     *   concise  — 角色名 + 正文并排（两个 TextField），无额外动画
     *
     * 生命周期状态:
     *   CREATED → ENTERING → ACTIVE → FADING → DEAD
     *
     * 动画时序:
     *   1. 入场动画（内置 fade+slide）→ reportHeight
     *   2. 打字机开始（text_speed > 0 时）
     *   3. 额外动画序列（anime_start_at[i] 延迟 → anime[i] → 循环）
     *
     * 注意: 这不是文档类，是 SubtitleView 内部创建的 Sprite。
     * 回调通过构造注入的 SubtitleView 引用转发到 Python。
     */
    public class SubtitleRenderer extends Sprite
    {
        /** 模块级日志器 */
        private static const L:Object = Log.getLogger("SubtitleRenderer");

        // ═══════════════════════════════════════════════════════
        // 动画常量
        // ═══════════════════════════════════════════════════════

        /** 入场动画时长（秒）。 */
        private static const ENTRY_DURATION:Number = 0.3;

        /** 入场动画起始偏移（px）——从目标下方多少像素开始滑入。 */
        private static const ENTRY_OFFSET:Number = 40;

        /** 淡出动画时长（秒）。 */
        private static const FADE_OUT_DURATION:Number = 0.3;

        /** 淡出时向上移动的距离（px）。 */
        private static const FADE_OUT_OFFSET:Number = 20;

        // ═══════════════════════════════════════════════════════
        // 额外动画参数
        // ═══════════════════════════════════════════════════════

        /** 额外动画振幅比例——相对于字幕渲染器尺寸。 */
        private static const BUBBLE_HEIGHT_RATIO:Number = 0.05;
        private static const SURPRISE_HEIGHT_RATIO:Number = 0.08;
        private static const SHAKE_WIDTH_RATIO:Number = 0.015;
        private static const DROP_HEIGHT_RATIO:Number = 0.05;

        /** 额外动画时长（秒）。 */
        private static const BUBBLE_DURATION:Number = 0.6;
        private static const SURPRISE_DURATION:Number = 0.2;
        private static const SHAKE_DURATION:Number = 0.5;
        private static const DROP_DURATION:Number = 0.5;
        private static const SWAY_DURATION:Number = 0.8;
        private static const SORRY_DURATION:Number = 0.8;

        /** shake/sway 分段数（等幅振荡，无衰减）。 */
        private static const SHAKE_SEGMENTS:int = 4;
        private static const SHAKE_SEG_TIME:Number = SHAKE_DURATION / SHAKE_SEGMENTS;

        // ═══════════════════════════════════════════════════════
        // 标识
        // ═══════════════════════════════════════════════════════

        /** 由 SubtitleView 分配的唯一 ID。 */
        private var _id:int;

        /** 当前数据。 */
        private var _data:Object;

        /**
         * 父容器 SubtitleView 引用——回调转发用。
         * 替代不可靠的 `parent as SubtitleView`（renderer 挂在普通 Sprite
         * 容器下，cast 永远为 null，导致淡出后无法通知 View 移除自己）。
         */
        private var _view:SubtitleView;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        private static const ST_CREATED:int   = 0;
        private static const ST_ENTERING:int  = 1;
        private static const ST_ACTIVE:int    = 2;
        private static const ST_FADING:int    = 3;
        private static const ST_DEAD:int      = 4;

        private var _state:int = ST_CREATED;

        // ═══════════════════════════════════════════════════════
        // 标准模式：四层
        // ═══════════════════════════════════════════════════════

        /** 海报层（BitmapContainer 或 null）。 */
        private var _posterBmp:BitmapContainer;

        /** 背景层（Shape 绘制纯色圆角矩形，或 BitmapContainer 图片背景）。 */
        private var _bgSprite:Sprite;
        private var _bgBmp:BitmapContainer;

        /** 标题 TextField（文本标题）。 */
        private var _titleTF:TextField;

        /** 标题 BitmapContainer（图片标题，tf_title.img 有值时使用）。 */
        private var _titleBmp:BitmapContainer;

        /** 正文 TextField。 */
        private var _messageTF:TextField;

        // ═══════════════════════════════════════════════════════
        // 简洁模式
        // ═══════════════════════════════════════════════════════

        /** 角色名 TextField（右对齐）。 */
        private var _nameTF:TextField;

        // ═══════════════════════════════════════════════════════
        // 动画控制
        // ═══════════════════════════════════════════════════════

        /** 当前打字机实例。 */
        private var _typewriter:Typewriter;

        /** 额外动画序列的当前索引。 */
        private var _animeIndex:int = 0;

        /** 额外动画序列副本（anime 代号列表）。 */
        private var _animeList:Array;

        /** 额外动画间隔副本（秒）。 */
        private var _animeStartAt:Array;

        /** 动画序列中当前延迟/动画用的 Tween。 */
        private var _animeTween:Tween;

        /** 额外动画延迟用的 Timer（替代延迟 Tween，不受 ENTER_FRAME 驱动器启停影响）。 */
        private var _animeTimer:Timer;

        /** 当前位移 Tween（shift / 入场 / 淡出）。 */
        private var _moveTween:Tween;

        // ═══════════════════════════════════════════════════════
        // 分层架构：_proxy 承载所有缓动，_layout 承载 shift 位移
        // ═══════════════════════════════════════════════════════

        /** 动画代理对象 {y, x, alpha}——所有 Tween 写入此对象，不直接操作 Sprite。 */
        private var _proxy:Object;

        /** 布局位移代理——所有 shift 通过 Tween 缓动到此对象，不再瞬间跳变。 */
        private var _layoutProxy:Object;

        /** 布局目标 Y 坐标（shift 累积值）。 */
        private var _layoutTargetY:Number = 0;
        private var _layoutTargetX:Number = 0;

        /** 当前布局缓动（null = 无活跃缓动）。 */
        private var _layoutTween:Tween;

        /** ENTER_FRAME 监听器是否已注册。 */
        private var _proxyListening:Boolean = false;

        /** 渲染器实际高度缓存（用于额外动画振幅计算）。 */
        private var _cachedHeight:Number = 80;

        /** 渲染器实际宽度缓存（用于 shake 振幅计算）。 */
        private var _cachedWidth:Number = 300;

        // ═══════════════════════════════════════════════════════
        // 预览编辑模式
        // ═══════════════════════════════════════════════════════

        /** 是否为位置编辑预览模式（data.preview == true）。 */
        private var _isPreview:Boolean = false;

        /**
         * 边框层字典: {targetName: {border:Shape, component:DisplayObject}}
         * border    — Shape 子对象（绘制矩形边框，叠加在组件上方）
         * component — 原始组件引用（未被 reparent，保持在原始位置）
         */
        private var _borderLayers:Object = null;

        /** 当前编辑选中的组件名（poster/background/tf_title/tf_message）。 */
        private var _editTarget:String = null;

        /**
         * 简洁模式预览：基准位置（data.concise.position 叠加偏移后的值）。
         * 拖拽时移动整个简洁块（nameTF + messageTF），getComponentX/Y
         * 返回此基准值，确保偏移计算 = 样式原始位置 + 累积拖拽偏移。
         */
        private var _conciseBaseX:Number = 0;
        private var _conciseBaseY:Number = 0;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param id    由 SubtitleView 分配的唯一 ID
         * @param data  Flash 命令中携带的渲染数据（见 manager._assemble_data）
         * @param view  父容器 SubtitleView（用于回调转发）
         */
        public function SubtitleRenderer(id:int, data:Object, view:SubtitleView = null)
        {
            super();
            _id = id;
            _data = data;
            _view = view;
            _proxy = {y: 0, x: 0, alpha: 1};
            _layoutProxy = {y: 0, x: 0};
            _layoutTargetY = 0;
            _layoutTargetX = 0;
            _isPreview = (data.preview == true);

            mouseChildren = false;
            mouseEnabled = false;

            if (data.mode == "concise")
                _buildConcise(data);
            else
                _buildStandard(data);

            // 预览模式：边框与生俱来，不在 showStatic 里事后修补。
            // 构建完成后立即填入文本并创建边框，避免后续 addChild 触发
            // Scaleform 重绘时波及已渲染的 TextField。
            if (_isPreview)
            {
                _prepareText(data);
                _createBorders();
            }
        }

        // ═══════════════════════════════════════════════════════
        // 构建：标准模式
        // ═══════════════════════════════════════════════════════

        private function _buildStandard(data:Object):void
        {
            // z-order (先 addChild 的在底层):
            //   background(底) → message(正文) → poster(头像/海报) → title(标题/顶)

            // —— 背景（底层）——
            // 空字典 {} 的 position 为 undefined → 不创建背景
            if (data.background && data.background.position != undefined)
            {
                _bgSprite = new Sprite();
                // 纯显示容器，不参与鼠标命中——防止 Scaleform 中拦截下层点击
                _bgSprite.mouseEnabled = false;
                _bgSprite.mouseChildren = false;
                addChild(_bgSprite);
                _drawBackground(data);
            }

            // —— 正文 ——
            // 空字典 {} 的 position 为 undefined → 不创建正文
            if (data.tf_message && data.tf_message.position != undefined)
            {
                _messageTF = _makeTextField(data.tf_message);
                _messageTF.wordWrap = true;
                _messageTF.multiline = true;
                addChild(_messageTF);
            }

            // —— 海报/头像 ——
            if (data.poster && data.poster.img)
            {
                var pSize:Array = data.poster.size || [64, 64];
                _posterBmp = new BitmapContainer(
                    Number(pSize[0]), Number(pSize[1]),
                    0, data.poster.img, "original");
                if (data.poster.position)
                {
                    _posterBmp.x = Number(data.poster.position[0]);
                    _posterBmp.y = Number(data.poster.position[1]);
                }
                addChild(_posterBmp);
            }

            // —— 标题（顶层）——
            // 图片标题: img 有值 → BitmapContainer（头像式）
            // 文本标题: img 无值 → TextField（样式代号即文本，简洁模式走 _buildConcise）
            if (data.tf_title && data.tf_title.img)
            {
                var tSize:Array = data.tf_title.size || [200, 40];
                _titleBmp = new BitmapContainer(
                    Number(tSize[0]), Number(tSize[1]),
                    0, data.tf_title.img, "original");
                if (data.tf_title.position)
                {
                    _titleBmp.x = Number(data.tf_title.position[0]);
                    _titleBmp.y = Number(data.tf_title.position[1]);
                }
                addChild(_titleBmp);
            }
            else if (data.tf_title && data.tf_title.text)
            {
                _titleTF = _makeTextField(data.tf_title);
                _titleTF.text = data.tf_title.text || "";
                _titleTF.setTextFormat(_titleTF.defaultTextFormat);
                addChild(_titleTF);
            }
        }

        // ═══════════════════════════════════════════════════════
        // 构建：简洁模式
        // ═══════════════════════════════════════════════════════

        private function _buildConcise(data:Object):void
        {
            var c:Object = data.concise;
            if (!c) return;

            var posX:Number = Number(c.position[0]);
            var posY:Number = Number(c.position[1]);
            var fontSize:Number = Number(c.size) || 14;
            var fontName:String = c.font || "$FieldFont";
            var gap:Number = Number(c.gap) || 8;
            var maxWidth:Number = Number(c.width) || 300;

            // —— 角色名 TextField（右对齐）——
            // 仅当 name 非空时创建；空字典 {} 隐藏标题 → name 为空字符串
            var nameText:String = c.name || "";
            var nameW:Number = 0;

            if (nameText.length > 0)
            {
                // 预估宽度: 中文约 fontSize*1.2px/字，加少量边距
                var nameEstW:Number = fontSize * 1.2 * Math.max(1, nameText.length) + 4;

                _nameTF = new TextField();
                _nameTF.selectable = false;
                _nameTF.mouseEnabled = false;
                _nameTF.antiAliasType = AntiAliasType.ADVANCED;
                _nameTF.embedFonts = true;
                _nameTF.width = nameEstW;
                _nameTF.text = nameText;
                _nameTF.x = posX;
                _nameTF.y = posY;

                var nameFmt:TextFormat = new TextFormat();
                nameFmt.font = fontName;
                nameFmt.size = fontSize;
                nameFmt.color = ColorUtil.parse(c.name_color, 0xFFFFFF);
                nameFmt.align = "right";
                _nameTF.defaultTextFormat = nameFmt;
                _nameTF.setTextFormat(nameFmt);
                addChild(_nameTF);

                // 角色名宽度。
                // Scaleform 中 textWidth 可能不会在当前帧立即可用（返回 0），
                // 此时回退为预估值，避免正文与角色名重叠。
                var measuredW:Number = _nameTF.textWidth;
                if (measuredW <= 0)
                    measuredW = nameEstW;
                nameW = measuredW + gap;
            }

            // —— 正文 TextField（左对齐）——
            _messageTF = new TextField();
            _messageTF.selectable = false;
            _messageTF.mouseEnabled = false;
            _messageTF.antiAliasType = AntiAliasType.ADVANCED;
            _messageTF.embedFonts = true;
            _messageTF.wordWrap = true;
            _messageTF.multiline = true;
            _messageTF.width = maxWidth - nameW;
            _messageTF.x = posX + nameW;
            _messageTF.y = posY;

            var textFmt:TextFormat = new TextFormat();
            textFmt.font = fontName;
            textFmt.size = fontSize;
            textFmt.color = ColorUtil.parse(c.text_color, 0xFFFFFF);
            textFmt.align = "left";
            _messageTF.defaultTextFormat = textFmt;
            addChild(_messageTF);
        }

        // ═══════════════════════════════════════════════════════
        // 背景绘制
        // ═══════════════════════════════════════════════════════

        private function _drawBackground(data:Object):void
        {
            var bg:Object = data.background;
            if (!bg) return;

            // 空字典 {} → 无内容可绘制
            if (bg.img == undefined && bg.color == undefined) return;

            // 图片背景优先
            if (bg.img)
            {
                var bgSize:Array = bg.size || [300, 80];
                _bgBmp = new BitmapContainer(
                    Number(bgSize[0]), Number(bgSize[1]),
                    Number(bg.radius) || 0, bg.img, "original");
                if (bg.position)
                {
                    _bgBmp.x = Number(bg.position[0]);
                    _bgBmp.y = Number(bg.position[1]);
                }
                _bgSprite.addChild(_bgBmp);
                return;
            }

            // 纯色圆角矩形
            if (bg.position)
            {
                _bgSprite.x = Number(bg.position[0]);
                _bgSprite.y = Number(bg.position[1]);
            }

            var w:Number = Number(bg.size ? bg.size[0] : 300);
            var h:Number = Number(bg.size ? bg.size[1] : 80);
            var color:uint = ColorUtil.parse(bg.color, 0x000000);
            var alpha:Number = _num(bg.alpha, 0.7);
            var radius:Number = _num(bg.radius, 0);

            var sh:Shape = new Shape();
            sh.graphics.beginFill(color, alpha);
            if (radius > 0)
                sh.graphics.drawRoundRect(0, 0, w, h, radius * 2, radius * 2);
            else
                sh.graphics.drawRect(0, 0, w, h);
            sh.graphics.endFill();
            _bgSprite.addChild(sh);
        }

        // ═══════════════════════════════════════════════════════
        // TextField 工厂
        // ═══════════════════════════════════════════════════════

        private function _makeTextField(cfg:Object):TextField
        {
            var tf:TextField = new TextField();
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.antiAliasType = AntiAliasType.ADVANCED;
            tf.embedFonts = true;

            if (cfg.position)
            {
                tf.x = Number(cfg.position[0]);
                tf.y = Number(cfg.position[1]);
            }
            if (cfg.width)
                tf.width = Number(cfg.width);

            var fmt:TextFormat = new TextFormat();
            fmt.font = cfg.font || "$FieldFont";
            fmt.size = Number(cfg.size) || 14;
            fmt.color = ColorUtil.parse(cfg.color, 0xFFFFFF);
            fmt.align = cfg.align || "left";
            tf.defaultTextFormat = fmt;

            return tf;
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /**
         * 将 _proxy 值合成到 Sprite 的 x/y/alpha 上。
         * this.y = _layoutProxy.y + _proxy.y
         * this.x = _layoutProxy.x + _proxy.x
         * this.alpha = _proxy.alpha
         */
        private function _composePosition():void
        {
            this.y = _layoutProxy.y + _proxy.y;
            this.x = _layoutProxy.x + _proxy.x;
            this.alpha = _proxy.alpha;
        }

        /**
         * 确保 ENTER_FRAME 监听器已注册。
         * 只在有活跃缓动时调用，闲置 renderer 不消耗帧回调。
         */
        private function _ensureProxyListener():void
        {
            if (!_proxyListening)
            {
                addEventListener(Event.ENTER_FRAME, _onProxyEnterFrame, false, 0, true);
                _proxyListening = true;
            }
        }

        /** ENTER_FRAME: 每帧将 _proxy 合成到 Sprite 位置和透明度。 */
        private function _onProxyEnterFrame(e:Event):void
        {
            _composePosition();
        }

        /**
         * 开始入场动画。
         *
         * 入场动画（fade+slide）与打字机并行启动，
         * 文本从第 0 秒开始逐字显示，不再等待入场动画结束。
         * 高度在打字机清空文本前测量并上报。
         */
        public function show():void
        {
            if (_state != ST_CREATED) return;
            _state = ST_ENTERING;

            // 保存布局位置（as_create 总是设为 (0,0)）
            _layoutProxy.y = this.y;
            _layoutProxy.x = this.x;
            _layoutTargetY = this.y;
            _layoutTargetX = this.x;

            // 起始: _proxy 从下方偏移 + 透明开始
            _proxy.y = ENTRY_OFFSET;
            _proxy.alpha = 0;
            // 立即生效，避免首帧闪现（_composePosition 在 ENTER_FRAME 之前不执行）
            _composePosition();

            _moveTween = Tween.to(_proxy, ENTRY_DURATION, {
                alpha: 1,
                y: 0
            }, Easing.easeOutCubic, _onEntryDone);

            _ensureProxyListener();

            // 先填入完整文本并测量高度（在打字机清空文本之前）
            _prepareText(_data);
            _reportHeight();

            // 缓存尺寸供额外动画振幅计算
            _cachedHeight = _measureHeight();
            _cachedWidth = _measureWidth();

            // 额外动画序列：延迟到入场动画完成后启动。
            // 若与入场动画并行，两个 Tween 同时写 _proxy.y 会冲突——
            // 额外动画的 baseY 捕获到 ENTRY_OFFSET(40) 而非目标值 0，
            // 动画结束后 _proxy.y 停留在 40，导致 renderer 异常下移。
            _animeList = _data.anime || [];
            _animeStartAt = _data.anime_start_at || [];
            _animeIndex = 0;

            // 打字机与入场动画并行启动（打字机只操作 mask，不与 _proxy 冲突）
            _startTypewriter(_data);

            L.debug("入场开始: id=" + _id);
        }

        /**
         * 更新内容（同角色 update_content）。
         *
         * 跳过入场动画，直接替换文本/样式，重置打字机 + 额外动画。
         * Typewriter.start() 的 mask 使用全新 Shape 实例 + 种子矩形，
         * 确保 Scaleform 从头就正确遮罩，无需淡入淡出过渡。
         */
        public function updateContent(data:Object):void
        {
            if (_state == ST_DEAD || _state == ST_FADING) return;

            _data = data;
            _killAnimeSequence();
            if (_typewriter) { _typewriter.stop(); _typewriter = null; }
            _applyContentUpdate(data);
        }

        /** 更新内容、样式、重建打字机。 */
        private function _applyContentUpdate(data:Object):void
        {
            // 清空旧文本
            if (_messageTF)
                _messageTF.text = "";

            // 更新文本内容和样式
            var mode:String = data.mode || "standard";
            if (mode == "concise")
                _updateConciseContent(data);
            else
                _updateStandardContent(data);

            // 重置额外动画序列
            _animeList = data.anime || [];
            _animeStartAt = data.anime_start_at || [];
            _animeIndex = 0;

            // 打字机 / 直接填文本
            var speed:Number = Number(data.text_speed) || 0;
            if (speed > 0 && _messageTF)
            {
                _startTypewriter(data);
            }
            else
            {
                if (_typewriter) { _typewriter.stop(); _typewriter = null; }
                _prepareText(data);
            }

            // 测量高度
            _reportHeight();

            // 缓存尺寸供额外动画振幅计算
            _cachedHeight = _measureHeight();
            _cachedWidth = _measureWidth();

            // 启动额外动画
            _playAnimeSequence(0);

            L.debug("update_content: id=" + _id);
        }

        /**
         * 垂直位移（shift_up / shift_down）。
         *
         * 状态分派:
         *   ST_DEAD     → 无操作
         *   ST_FADING   → 终止淡出动画，瞬间位移，从当前透明度重新淡出
         *                  （Tween.start() 快照当前 alpha 作为起始值，视觉无缝）
         *   ST_ENTERING → 终止入场动画，瞬间位移，直接设为 ACTIVE
         *                  （入场仅 0.3s，打断代价极小）
         *   其他         → 0.25s 缓动 shift 动画（原有行为）
         *
         * @param dy  正=下移，负=上移
         */
        /**
         * 垂直位移（shift_up / shift_down）。
         *
         * 分层架构 + 缓动：修改 _layoutTargetY，通过 Tween 驱动 _layoutProxy.y
         * 平滑过渡到目标位置。连续多次 shift 会 kill 旧缓动并从当前位置重新出发，
         * 不会累积跳变。
         *
         * @param dy  正=下移，负=上移
         */
        public function shift(dy:Number):void
        {
            if (_state == ST_DEAD) return;
            if (dy == 0) return;

            _layoutTargetY += dy;

            // kill 旧布局缓动，从 _layoutProxy 当前位置重新出发
            if (_layoutTween)
            {
                _layoutTween.stop();
                _layoutTween = null;
            }

            _layoutTween = Tween.to(_layoutProxy, 0.25, {
                y: _layoutTargetY
            }, Easing.easeOutCubic, _onLayoutTweenDone);

            _ensureProxyListener();

            L.debug("shift: id=" + _id + " dy=" + dy.toFixed(0)
                    + " target=" + _layoutTargetY.toFixed(0));
        }

        /**
         * 淡出 → 销毁 → 回调。
         *
         * 收到 fade_out 指令后立即执行淡出动画（无停留延迟），
         * 同时向上移动 FADE_OUT_OFFSET px，动画完成后回调 onFadeOutDone。
         */
        public function fadeOut():void
        {
            if (_state == ST_DEAD || _state == ST_FADING) return;
            _state = ST_FADING;

            // 终止打字机和额外动画（不再需要 kill _moveTween——shift 不再创建它）
            if (_typewriter) { _typewriter.stop(); _typewriter = null; }
            _killAnimeSequence();
            if (_moveTween) { _moveTween.stop(); _moveTween = null; }

            // 淡出 + 向上移动（从 _proxy 当前 y 出发，不做瞬间复位）
            _moveTween = Tween.to(_proxy, FADE_OUT_DURATION, {
                alpha: 0,
                y: _proxy.y - FADE_OUT_OFFSET
            }, Easing.easeInCubic, _onFadeOutDone);

            _ensureProxyListener();

            L.debug("fade_out: id=" + _id);
        }

        /**
         * 立即销毁（clear_all）。
         * 不播动画，不触发回调。
         */
        public function disposeRenderer():void
        {
            if (_state == ST_DEAD) return;
            _state = ST_DEAD;

            _killAnimeSequence();
            if (_typewriter) { _typewriter.stop(); _typewriter = null; }
            Tween.kill(_proxy);
            if (_moveTween) { _moveTween.stop(); _moveTween = null; }
            if (_layoutTween) { _layoutTween.stop(); _layoutTween = null; }

            // 移除 ENTER_FRAME 监听器
            if (_proxyListening)
            {
                removeEventListener(Event.ENTER_FRAME, _onProxyEnterFrame);
                _proxyListening = false;
            }

            if (parent)
                parent.removeChild(this);

            L.debug("dispose: id=" + _id);
        }

        // ═══════════════════════════════════════════════════════
        // 预览编辑模式
        // ═══════════════════════════════════════════════════════

        /**
         * 静态显示（预览模式）——跳过入场动画、打字机、额外动画。
         * 边框已在构造函数中创建，此处仅设为可见并报告高度。
         */
        public function showStatic():void
        {
            if (_state != ST_CREATED) return;
            _state = ST_ACTIVE;

            // 边框 + 文本已在构造函数中完成，直接可见
            this.alpha = 1;

            // 报告高度
            _reportHeight();

            L.debug("静态预览显示: id=" + _id);
        }

        /**
         * 设置编辑目标组件——更新边框颜色和鼠标交互。
         * @param target 组件名: poster / background / tf_title / tf_message
         */
        public function setEditTarget(target:String):void
        {
            _editTarget = target;

            if (!_borderLayers) return;

            for (var key:String in _borderLayers)
            {
                var layer:Object = _borderLayers[key];
                if (!layer) continue;

                var isTarget:Boolean = (key == target);
                var border:Shape = layer.border as Shape;

                if (isTarget)
                {
                    // 金黄色 + 加粗边框
                    _redrawBorder(border,
                        _getComponentWidth(key), _getComponentHeight(key),
                        0xC0A060, 2.0);
                }
                else
                {
                    // 白色 + 细边框
                    _redrawBorder(border,
                        _getComponentWidth(key), _getComponentHeight(key),
                        0xFFFFFF, 1.0);
                }
            }

            L.debug("编辑目标: " + target);
        }

        /**
         * 获取组件当前 X 坐标。
         *
         * 简洁模式: 返回 _conciseBaseX（基准位置），不含 nameW 偏移，
         *          确保与 _previewStylePos 原始样式位置的差值 = 纯累积偏移。
         * 标准模式: 返回组件在 renderer 内的实际 x。
         *
         * @param target poster / background / tf_title / tf_message
         */
        public function getComponentX(target:String):Number
        {
            // 简洁模式：返回基准位置（不含 nameW），与 _previewStylePos 对齐
            if (_data.mode == "concise" && target == "tf_message")
                return _conciseBaseX;

            if (_borderLayers && _borderLayers[target]
                && _borderLayers[target].component)
                return _borderLayers[target].component.x;
            return 0;
        }

        /**
         * 获取组件当前 Y 坐标。
         *
         * 简洁模式: 返回 _conciseBaseY（基准位置）。
         * 标准模式: 返回组件在 renderer 内的实际 y。
         */
        public function getComponentY(target:String):Number
        {
            if (_data.mode == "concise" && target == "tf_message")
                return _conciseBaseY;

            if (_borderLayers && _borderLayers[target]
                && _borderLayers[target].component)
                return _borderLayers[target].component.y;
            return 0;
        }

        /**
         * 判断 stage 坐标是否命中指定组件（编辑模式拖拽门槛）。
         * 只有点击激活组件自身的包围盒才允许开始拖拽，
         * 避免点击空白区域也误拖拽组件。
         *
         * @param target 组件名（poster/background/tf_title/tf_message）
         * @param stageX stage 坐标系 X
         * @param stageY stage 坐标系 Y
         */
        public function componentHitTest(target:String, stageX:Number,
                                         stageY:Number):Boolean
        {
            var layer:Object = _borderLayers ? _borderLayers[target] : null;
            if (!layer || !layer.component) return false;

            var rect:Rectangle = layer.component.getBounds(stage);
            return rect.contains(stageX, stageY);
        }

        /**
         * 设置组件位置（拖拽时实时更新组件及其边框）。
         *
         * 简洁模式: 移动整个简洁块（nameTF + messageTF + 边框），
         *          同时更新 _conciseBaseX/Y 基准值。
         * 标准模式: 移动单个组件及其边框。
         *
         * @param target 组件名
         * @param x      新 X 坐标
         * @param y      新 Y 坐标
         */
        public function setComponentPosition(target:String, x:Number, y:Number):void
        {
            // —— 简洁模式：移动整个简洁块 ——
            if (_data.mode == "concise" && target == "tf_message")
            {
                var dx:Number = int(x) - _conciseBaseX;
                var dy:Number = int(y) - _conciseBaseY;
                _conciseBaseX = int(x);
                _conciseBaseY = int(y);

                if (_nameTF)
                {
                    _nameTF.x += dx;
                    _nameTF.y += dy;
                }
                if (_messageTF)
                {
                    _messageTF.x += dx;
                    _messageTF.y += dy;
                }
                // 边框跟随正文
                if (_borderLayers && _borderLayers["tf_message"]
                    && _borderLayers["tf_message"].border)
                {
                    var b:Shape = _borderLayers["tf_message"].border as Shape;
                    b.x = _messageTF ? _messageTF.x : int(x);
                    b.y = _messageTF ? _messageTF.y : int(y);
                }
                return;
            }

            // —— 标准模式：移动单个组件 ——
            if (_borderLayers && _borderLayers[target])
            {
                var layer:Object = _borderLayers[target];
                if (layer.component)
                {
                    layer.component.x = int(x);
                    layer.component.y = int(y);
                }
                if (layer.border)
                {
                    layer.border.x = int(x);
                    layer.border.y = int(y);
                }
            }
        }

        // ═══════════════════════════════════════════════════════
        // 内部：边框绘制
        // ═══════════════════════════════════════════════════════

        /**
         * 为可编辑组件创建编辑边框。
         *
         * 边框 Shape 作为独立同级对象叠加在组件上方，不包裹、不 reparent
         * 组件。避免 Scaleform 中 removeChild→addChild 导致 TextField
         * 丢失渲染状态（width、wordWrap、embedFonts 等）。
         *
         * 标准模式: 4 个组件（background / tf_message / poster / tf_title）。
         * 简洁模式: 仅正文区域（tf_message），同时记录基准位置供拖拽偏移计算。
         */
        private function _createBorders():void
        {
            _borderLayers = {};

            // —— 简洁模式：仅正文区域可编辑 ——
            if (_data.mode == "concise")
            {
                if (!_messageTF || !_data.concise) return;

                // 记录基准位置（叠加偏移后的 concise.position），
                // 拖拽偏移计算中 getComponentX/Y 返回此值。
                var cPos:Array = _data.concise.position;
                _conciseBaseX = Number(cPos[0]);
                _conciseBaseY = Number(cPos[1]);

                var borderC:Shape = new Shape();
                _redrawBorder(borderC,
                    _getComponentWidth("tf_message"),
                    _getComponentHeight("tf_message"),
                    0xFFFFFF, 1.0);
                borderC.x = _messageTF.x;
                borderC.y = _messageTF.y;
                addChild(borderC);

                _borderLayers["tf_message"] = {
                    border:    borderC,
                    component: _messageTF
                };

                L.debug("边框已创建: 1 组件 (简洁模式)");
                return;
            }

            // —— 标准模式：四个组件 ——
            // 按 z-order 排列的组件列表（底→顶）
            var targets:Array = [
                {key: "background", obj: _bgSprite},
                {key: "tf_message", obj: _messageTF},
                {key: "poster",     obj: _posterBmp},
                {key: "tf_title",   obj: _titleBmp ? _titleBmp : _titleTF}
            ];

            for each (var t:Object in targets)
            {
                if (!t.obj) continue;
                if (!_data || !_data[t.key]) continue;

                var obj:* = t.obj;

                // 创建边框 Shape 直接加在 renderer 上，不包裹组件
                var border:Shape = new Shape();
                _redrawBorder(border,
                    _getComponentWidth(t.key), _getComponentHeight(t.key),
                    0xFFFFFF, 1.0);
                border.x = obj.x;
                border.y = obj.y;
                addChild(border);

                // 注册 {border, component}
                _borderLayers[t.key] = {
                    border:    border,
                    component: obj
                };

                // 图片组件异步加载（首次冷缓存）：构造时边框按 0 尺寸绘制
                // 不可见，图片就绪后需按实际尺寸重绘边框
                if (obj is BitmapContainer)
                    _registerBorderRefresh(t.key, obj as BitmapContainer);
                else if (t.key == "background" && _bgBmp)
                    _registerBorderRefresh(t.key, _bgBmp);
            }

            L.debug("边框已创建: " + _countBorders() + " 组件");
        }

        /** 重绘单个边框。 */
        private function _redrawBorder(border:Shape, w:Number, h:Number,
                                        color:uint, thickness:Number):void
        {
            border.graphics.clear();
            border.graphics.lineStyle(thickness, color, 1.0);
            border.graphics.drawRect(0, 0, w, h);
        }

        /**
         * 为图片组件注册"加载完成→重绘边框"回调。
         *
         * BitmapContainer 在 "original" 模式下图片异步加载后才获得实际尺寸，
         * 构造时绘制的边框尺寸为 0（不可见）。缓存命中（同步加载）时此回调
         * 不会触发——边框本就按实际尺寸绘制。
         */
        private function _registerBorderRefresh(key:String, bc:BitmapContainer):void
        {
            if (!bc) return;
            var refreshKey:String = key;
            bc.onReady = function(success:Boolean):void
            {
                _refreshBorder(refreshKey);
            };
        }

        /** 按组件当前实际尺寸重绘其边框（颜色/粗细跟随当前选中状态）。 */
        private function _refreshBorder(key:String):void
        {
            if (!_borderLayers || !_borderLayers[key]) return;
            var layer:Object = _borderLayers[key];
            if (!layer || !layer.border) return;

            var isTarget:Boolean = (key == _editTarget);
            _redrawBorder(layer.border as Shape,
                _getComponentWidth(key), _getComponentHeight(key),
                isTarget ? 0xC0A060 : 0xFFFFFF,
                isTarget ? 2.0 : 1.0);
        }

        /** 获取组件宽度（用于边框绘制）。 */
        private function _getComponentWidth(key:String):Number
        {
            switch (key)
            {
                case "poster":     return _posterBmp ? _posterBmp.width : 64;
                case "background": return _bgSprite ? _bgSprite.width : 300;
                case "tf_title":
                    if (_titleBmp) return _titleBmp.width;
                    return _titleTF ? _titleTF.width : 200;
                case "tf_message": return _messageTF ? _messageTF.width : 300;
            }
            return 100;
        }

        /** 获取组件高度（用于边框绘制）。 */
        private function _getComponentHeight(key:String):Number
        {
            switch (key)
            {
                case "poster":     return _posterBmp ? _posterBmp.height : 64;
                case "background": return _bgSprite ? _bgSprite.height : 80;
                case "tf_title":
                    if (_titleBmp) return _titleBmp.height;
                    return (_titleTF && _titleTF.textHeight > 0)
                           ? _titleTF.textHeight : 20;
                case "tf_message":
                    return (_messageTF && _messageTF.textHeight > 0)
                           ? _messageTF.textHeight : 20;
            }
            return 40;
        }

        /** 统计已创建的边框数量（调试用）。 */
        private function _countBorders():int
        {
            var count:int = 0;
            for (var key:String in _borderLayers)
            { if (_borderLayers[key]) count++; }
            return count;
        }

        /** 此渲染器的 ID。 */
        public function get rendererId():int { return _id; }

        /** 当前状态。 */
        public function get state():int { return _state; }

        // ═══════════════════════════════════════════════════════
        // 内部：入场完成
        // ═══════════════════════════════════════════════════════

        private function _onLayoutTweenDone():void
        {
            _layoutTween = null;
        }

        private function _onEntryDone():void
        {
            _moveTween = null;
            _state = ST_ACTIVE;

            // 额外动画序列在入场完成后启动，此时 _proxy.y 已归零，
            // 额外动画的 baseY 捕获到正确的 0，不会再与入场 Tween 冲突。
            _playAnimeSequence(0);

            L.debug("入场完成: id=" + _id);
        }

        // ═══════════════════════════════════════════════════════
        // 内部：打字机
        // ═══════════════════════════════════════════════════════

        /**
         * 启动打字机效果。
         * 前提: _prepareText() 已将完整文本填入 TextField。
         * text_speed=0 时文本保持完整显示（无打字机）。
         * text_speed>0 时清空文本再逐字显示。
         */
        private function _startTypewriter(data:Object):void
        {
            var speed:Number = Number(data.text_speed) || 0;
            if (speed <= 0 || !_messageTF) return;

            var mode:String = data.mode || "standard";
            var text:String;

            if (mode == "concise")
                text = (data.concise && data.concise.text) ? data.concise.text : "";
            else
                text = (data.tf_message && data.tf_message.text) ? data.tf_message.text : "";

            if (text.length > 0)
            {
                var duration:Number = text.length * speed;
                _typewriter = new Typewriter(_messageTF, text, duration,
                    _messageTF.defaultTextFormat);
                _typewriter.start();
            }
        }

        /**
         * 将完整文本填入 TextField（用于高度测量）。
         * 在 _startTypewriter 之前调用，确保 textHeight 准确。
         */
        private function _prepareText(data:Object):void
        {
            var mode:String = data.mode || "standard";

            if (mode == "concise")
            {
                if (_messageTF && data.concise)
                {
                    _messageTF.text = data.concise.text || "";
                    _messageTF.setTextFormat(_messageTF.defaultTextFormat);
                }
            }
            else
            {
                if (_messageTF && data.tf_message)
                {
                    _messageTF.text = data.tf_message.text || "";
                    _messageTF.setTextFormat(_messageTF.defaultTextFormat);
                }
            }
        }

        // ═══════════════════════════════════════════════════════
        // 内部：额外动画序列
        // ═══════════════════════════════════════════════════════

        /**
         * 递归播放额外动画序列。
         * @param index 当前动画在 animeList 中的索引
         *
         * 延迟用 flash.utils.Timer 而非 Tween.delay。
         * Timer 独立于 Tween 引擎的 ENTER_FRAME 驱动器，
         * 不受"无活跃 Tween 时自动移除 stage 监听器"的影响，
         * 避免长延迟场景（如 anime_start_at=1.73s）回调丢失。
         */
        private function _playAnimeSequence(index:int):void
        {
            if (!_animeList || index >= _animeList.length) return;
            if (_state == ST_DEAD || _state == ST_FADING) return;

            var wait:Number = 0;
            if (_animeStartAt && index < _animeStartAt.length)
                wait = Number(_animeStartAt[index]);

            var animeName:String = _animeList[index];

            if (wait > 0)
            {
                _animeTimer = new Timer(wait * 1000, 1);
                var timerCallback:Function = function(e:TimerEvent):void {
                    _animeTimer.removeEventListener(TimerEvent.TIMER, timerCallback);
                    _animeTimer.stop();
                    _animeTimer = null;
                    _playOneAnime(animeName, index);
                };
                _animeTimer.addEventListener(TimerEvent.TIMER, timerCallback, false, 0, true);
                _animeTimer.start();
            }
            else
            {
                _playOneAnime(animeName, index);
            }
        }

        /** 播放单个额外动画，完成后递归播下一个。 */
        private function _playOneAnime(name:String, index:int):void
        {
            if (_state == ST_DEAD || _state == ST_FADING) return;

            var onDone:Function = function():void {
                _playAnimeSequence(index + 1);
            };

            switch (name)
            {
                case "bubble":    _animeBubble(onDone);    break;
                case "surprise":  _animeSurprise(onDone);  break;
                case "shake":     _animeShake(onDone);     break;
                case "drop":      _animeDrop(onDone);      break;
                case "sway":      _animeSway(onDone);      break;
                case "sorry":     _animeSorry(onDone);     break;
                default:
                    L.warn("未知动画代号: " + name + " id=" + _id);
                    onDone();
            }
        }

        /** bubble: 向上弹起 → 缓动回落（无弹跳）。振幅 = _cachedHeight × 0.05，总时长 0.3s。 */
        private function _animeBubble(onDone:Function):void
        {
            var amp:Number = _cachedHeight * BUBBLE_HEIGHT_RATIO;
            var halfTime:Number = BUBBLE_DURATION / 2;
            var baseY:Number = _proxy.y;

            _animeTween = Tween.to(_proxy, halfTime, {
                y: baseY - amp
            }, Easing.easeOutCubic, function():void {
                _animeTween = Tween.to(_proxy, halfTime, {
                    y: baseY
                }, Easing.easeOutCubic, function():void {
                    _animeTween = null;
                    if (onDone != null) onDone();
                });
            });
            _ensureProxyListener();

            L.debug("bubble: id=" + _id);
        }

        /** surprise: 快速上弹 → 加速回落（先快后慢再快）。振幅 = _cachedHeight × 0.08，总时长 0.2s。 */
        private function _animeSurprise(onDone:Function):void
        {
            var amp:Number = _cachedHeight * SURPRISE_HEIGHT_RATIO;
            var upTime:Number = SURPRISE_DURATION * 0.5;
            var downTime:Number = SURPRISE_DURATION * 0.5;
            var baseY:Number = _proxy.y;

            _animeTween = Tween.to(_proxy, upTime, {
                y: baseY - amp
            }, Easing.easeOutCubic, function():void {
                _animeTween = Tween.to(_proxy, downTime, {
                    y: baseY
                }, Easing.easeInCubic, function():void {
                    _animeTween = null;
                    if (onDone != null) onDone();
                });
            });
            _ensureProxyListener();

            L.debug("surprise: id=" + _id);
        }

        /** shake: 等幅左右振荡，4 段。振幅 = _cachedWidth × 0.015，总时长 0.5s。 */
        private function _animeShake(onDone:Function):void
        {
            var amp:Number = _cachedWidth * SHAKE_WIDTH_RATIO;
            var segTime:Number = SHAKE_SEG_TIME;
            var baseX:Number = _proxy.x;

            // 4 段等幅振荡: [右, 左, 右, 归位]
            _shakeStep(0, amp, segTime, baseX, onDone);
        }

        /** shake/sway 递归分步：等分时长 linear 振荡，末段归位。 */
        private function _shakeStep(step:int, amp:Number, segTime:Number,
                                    baseX:Number, onDone:Function):void
        {
            if (step >= SHAKE_SEGMENTS)
            {
                _animeTween = null;
                if (onDone != null) onDone();
                return;
            }

            var targetX:Number;
            if (step == SHAKE_SEGMENTS - 1)
                targetX = baseX;          // 最后一段归位
            else if (step % 2 == 0)
                targetX = baseX + amp;    // 偶数段: 向右
            else
                targetX = baseX - amp;    // 奇数段: 向左

            _animeTween = Tween.to(_proxy, segTime, {
                x: targetX
            }, Easing.linear, function():void {
                _shakeStep(step + 1, amp, segTime, baseX, onDone);
            });
            _ensureProxyListener();

            L.debug("shake: step=" + step + " id=" + _id);
        }

        /** sway: 慢速摇头——同 shake 的 4 段等幅 linear 振荡，总时长 0.8s。 */
        private function _animeSway(onDone:Function):void
        {
            var amp:Number = _cachedWidth * SHAKE_WIDTH_RATIO;
            var segTime:Number = SWAY_DURATION / SHAKE_SEGMENTS;
            var baseX:Number = _proxy.x;

            _shakeStep(0, amp, segTime, baseX, onDone);
        }

        /** drop: 向下沉落 → 缓动回位。振幅 = _cachedHeight × 0.05，总时长 0.5s。 */
        private function _animeDrop(onDone:Function):void
        {
            var amp:Number = _cachedHeight * DROP_HEIGHT_RATIO;
            var halfTime:Number = DROP_DURATION / 2;
            var baseY:Number = _proxy.y;

            _animeTween = Tween.to(_proxy, halfTime, {
                y: baseY + amp
            }, Easing.easeOutCubic, function():void {
                _animeTween = Tween.to(_proxy, halfTime, {
                    y: baseY
                }, Easing.easeOutCubic, function():void {
                    _animeTween = null;
                    if (onDone != null) onDone();
                });
            });
            _ensureProxyListener();

            L.debug("drop: id=" + _id);
        }

        /** sorry: 慢低头致歉——下潜 easeOutCubic + 回位 easeInCubic，总时长 0.8s。
         *  速度轮廓：开局快 → 沉底附近慢（全程连续，无悬停）→ 末段快。 */
        private function _animeSorry(onDone:Function):void
        {
            var amp:Number = _cachedHeight * DROP_HEIGHT_RATIO;
            var halfTime:Number = SORRY_DURATION / 2;
            var baseY:Number = _proxy.y;

            _animeTween = Tween.to(_proxy, halfTime, {
                y: baseY + amp
            }, Easing.easeOutCubic, function():void {
                _animeTween = Tween.to(_proxy, halfTime, {
                    y: baseY
                }, Easing.easeInCubic, function():void {
                    _animeTween = null;
                    if (onDone != null) onDone();
                });
            });
            _ensureProxyListener();

            L.debug("sorry: id=" + _id);
        }

        /** 终止额外动画序列（停止延迟 Timer 和/或运行中的 Tween）。 */
        private function _killAnimeSequence():void
        {
            if (_animeTimer)
            {
                _animeTimer.stop();
                _animeTimer = null;
            }
            if (_animeTween)
            {
                _animeTween.stop();
                _animeTween = null;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 内部：淡出完成
        // ═══════════════════════════════════════════════════════

        private function _onFadeOutDone():void
        {
            _moveTween = null;
            _state = ST_DEAD;

            // 淡出完成立即不可见——Scaleform 中 alpha=0 但 visible=true 的
            // 对象仍参与命中测试，只有 visible=false 才保证鼠标穿透，
            // 直到 View 将其移出显示列表。
            visible = false;

            var view:SubtitleView = _getView();
            if (view)
                view.onRendererFadeOutDone(_id);
        }

        // ═══════════════════════════════════════════════════════
        // 内部：View 回调转发
        // ═══════════════════════════════════════════════════════

        /**
         * 获取父 View 引用。
         * 优先使用构造时注入的 _view；兜底尝试 parent cast
         * （renderer 通常挂在普通 Sprite 容器下，cast 会失败，因此必须显式传入）。
         */
        private function _getView():SubtitleView
        {
            if (_view) return _view;
            return parent as SubtitleView;
        }

        /** 测量并上报渲染器的总像素高度。 */
        private function _reportHeight():void
        {
            var h:Number = _measureHeight();
            var view:SubtitleView = _getView();
            if (view)
                view.onRendererHeight(_id, h);
        }

        /**
         * 计算渲染器总高度（组件最上方到最下方的完整跨度）。
         *
         * 注意：不能只取 max(bottom)，因为 poster/title 等组件可能起始于
         * 负 Y 坐标（探出背景上方）。只取 max(bottom) 会漏掉这些"探头"
         * 高度，导致 report_height 偏小 → shift_up 距离不足 → 重叠。
         * 正确算法：max(bottom) - min(top) 覆盖全部子元素的完整垂直范围。
         */
        private function _measureHeight():Number
        {
            var mode:String = (_data && _data.mode) ? _data.mode : "standard";

            if (mode == "concise")
            {
                // 简洁模式：正文高度（角色名通常单行，正文可能折行）
                var msgH:Number = _messageTF ? _messageTF.textHeight : 0;
                return msgH + 10; // 少量底部留白
            }

            // 标准模式：计算所有子元素的完整垂直范围 [minY, maxBottom]
            var minY:Number = Number.MAX_VALUE;
            var maxY:Number = 0;
            var hasContent:Boolean = false;

            // —— poster / 头像 ——
            if (_posterBmp)
            {
                var pt:Number = _posterBmp.y;
                var pb:Number = _posterBmp.y + _posterBmp.height;
                if (pt < minY) minY = pt;
                if (pb > maxY) maxY = pb;
                hasContent = true;
            }
            // —— background / 背景 ——
            if (_bgSprite && _bgSprite.numChildren > 0)
            {
                var bt:Number = _bgSprite.y;
                var bb:Number = _bgSprite.y + _bgSprite.height;
                if (bt < minY) minY = bt;
                if (bb > maxY) maxY = bb;
                hasContent = true;
            }
            // —— title / 标题 ——
            if (_titleBmp)
            {
                var tyBt:Number = _titleBmp.y;
                var tyBb:Number = _titleBmp.y + _titleBmp.height;
                if (tyBt < minY) minY = tyBt;
                if (tyBb > maxY) maxY = tyBb;
                hasContent = true;
            }
            else if (_titleTF)
            {
                var tyt:Number = _titleTF.y;
                var tyb:Number = _titleTF.y + _titleTF.textHeight;
                if (tyt < minY) minY = tyt;
                if (tyb > maxY) maxY = tyb;
                hasContent = true;
            }
            // —— message / 正文 ——
            if (_messageTF)
            {
                var mt:Number = _messageTF.y;
                var mb:Number = _messageTF.y + _messageTF.textHeight;
                if (mt < minY) minY = mt;
                if (mb > maxY) maxY = mb;
                hasContent = true;
            }

            if (!hasContent)
                return 80; // fallback = 默认槽位高度

            // 完整垂直跨度 + 少量底部留白
            var totalH:Number = maxY - minY + 4;
            return totalH > 0 ? totalH : 80;
        }

        /**
         * 计算渲染器总宽度（所有子元素最左到最右的完整水平跨度）。
         *
         * 标准模式: max(right) - min(left) 覆盖全部子元素的完整水平范围。
         * 简洁模式: nameW + gap + messageW。
         */
        private function _measureWidth():Number
        {
            var mode:String = (_data && _data.mode) ? _data.mode : "standard";

            if (mode == "concise")
            {
                var nameW:Number = 0;
                if (_nameTF)
                {
                    var ntw:Number = _nameTF.textWidth;
                    nameW = (ntw > 0) ? ntw : _nameTF.width;
                }
                var gap:Number = (_data.concise && _data.concise.gap != undefined)
                    ? Number(_data.concise.gap) : 8;
                var msgW:Number = _messageTF ? _messageTF.width : 0;
                return nameW + gap + msgW;
            }

            // 标准模式: 计算所有子元素的完整水平范围
            var minX:Number = Number.MAX_VALUE;
            var maxX:Number = 0;
            var wHasContent:Boolean = false;

            // poster
            if (_posterBmp)
            {
                var pl:Number = _posterBmp.x;
                var pr:Number = _posterBmp.x + _posterBmp.width;
                if (pl < minX) minX = pl;
                if (pr > maxX) maxX = pr;
                wHasContent = true;
            }
            // background
            if (_bgSprite && _bgSprite.numChildren > 0)
            {
                var bl:Number = _bgSprite.x;
                var br:Number = _bgSprite.x + _bgSprite.width;
                if (bl < minX) minX = bl;
                if (br > maxX) maxX = br;
                wHasContent = true;
            }
            // title
            if (_titleBmp)
            {
                var tlB:Number = _titleBmp.x;
                var trB:Number = _titleBmp.x + _titleBmp.width;
                if (tlB < minX) minX = tlB;
                if (trB > maxX) maxX = trB;
                wHasContent = true;
            }
            else if (_titleTF)
            {
                var tlT:Number = _titleTF.x;
                var trT:Number = _titleTF.x + _titleTF.width;
                if (tlT < minX) minX = tlT;
                if (trT > maxX) maxX = trT;
                wHasContent = true;
            }
            // message
            if (_messageTF)
            {
                var ml:Number = _messageTF.x;
                var mr:Number = _messageTF.x + _messageTF.width;
                if (ml < minX) minX = ml;
                if (mr > maxX) maxX = mr;
                wHasContent = true;
            }

            if (!wHasContent) return 300;
            return maxX - minX;
        }

        // ═══════════════════════════════════════════════════════
        // 内部：内容更新辅助
        // ═══════════════════════════════════════════════════════

        private function _updateStandardContent(data:Object):void
        {
            // —— 更新海报/头像 ——
            // 移除旧海报（无论新数据有没有海报，先清再建）
            if (_posterBmp)
            {
                removeChild(_posterBmp);
                _posterBmp = null;
            }
            if (data.poster && data.poster.img)
            {
                var pSize:Array = data.poster.size || [64, 64];
                _posterBmp = new BitmapContainer(
                    Number(pSize[0]), Number(pSize[1]),
                    0, data.poster.img, "original");
                if (data.poster.position)
                {
                    _posterBmp.x = Number(data.poster.position[0]);
                    _posterBmp.y = Number(data.poster.position[1]);
                }
                addChild(_posterBmp);
            }

            // —— 更新标题 ——
            // 图片标题 → 图片标题：重建 BitmapContainer
            // 图片标题 → 文本标题：移除 BMP，创建 TF
            // 文本标题 → 图片标题：移除 TF，创建 BMP
            // 文本标题 → 文本标题：原地更新文本和样式

            var newTitleHasImg:Boolean = data.tf_title && data.tf_title.img;

            // 移除旧图片标题
            if (_titleBmp)
            {
                removeChild(_titleBmp);
                _titleBmp = null;
            }

            if (newTitleHasImg)
            {
                // 新数据是图片标题 → 创建 BitmapContainer
                var tSize:Array = data.tf_title.size || [200, 40];
                _titleBmp = new BitmapContainer(
                    Number(tSize[0]), Number(tSize[1]),
                    0, data.tf_title.img, "original");
                if (data.tf_title.position)
                {
                    _titleBmp.x = Number(data.tf_title.position[0]);
                    _titleBmp.y = Number(data.tf_title.position[1]);
                }
                addChild(_titleBmp);

                // 如果旧的是文本标题，移除 TextField
                if (_titleTF)
                {
                    removeChild(_titleTF);
                    _titleTF = null;
                }
            }
            else if (data.tf_title && data.tf_title.text)
            {
                // 新数据是文本标题
                if (!_titleTF)
                {
                    _titleTF = _makeTextField(data.tf_title);
                    addChild(_titleTF);
                }
                _titleTF.text = data.tf_title.text || "";
                _titleTF.setTextFormat(_titleTF.defaultTextFormat);
                _applyTextStyle(_titleTF, data.tf_title);
            }
            else if (_titleTF)
            {
                // 新数据无标题 → 移除旧文本标题
                removeChild(_titleTF);
                _titleTF = null;
            }

            // —— 更新正文 ——
            if (_messageTF && data.tf_message)
            {
                _applyTextStyle(_messageTF, data.tf_message);
            }

            // —— 重绘背景 ——
            if (_bgSprite && data.background)
            {
                while (_bgSprite.numChildren > 0)
                    _bgSprite.removeChildAt(0);
                _bgBmp = null;
                _drawBackground(data);
            }
        }

        private function _updateConciseContent(data:Object):void
        {
            var c:Object = data.concise;
            if (!c) return;

            // 更新角色名
            if (_nameTF)
            {
                _nameTF.text = c.name || "";
                _nameTF.setTextFormat(_nameTF.defaultTextFormat);
            }

            // 更新正文样式（文本内容由 Typewriter / _prepareText 负责）
            if (_messageTF && c)
            {
                _applyTextStyle(_messageTF, {
                    color: c.text_color,
                    font: c.font,
                    size: c.size
                });
            }
        }

        /** 更新 TextField 的 TextFormat。 */
        private function _applyTextStyle(tf:TextField, cfg:Object):void
        {
            if (!cfg) return;
            var fmt:TextFormat = tf.defaultTextFormat as TextFormat;
            var changed:Boolean = false;

            if (cfg.hasOwnProperty("color"))
            {
                fmt.color = ColorUtil.parse(cfg.color, 0xFFFFFF);
                changed = true;
            }
            if (cfg.hasOwnProperty("font"))
            {
                fmt.font = cfg.font;
                changed = true;
            }
            if (cfg.hasOwnProperty("size"))
            {
                fmt.size = Number(cfg.size);
                changed = true;
            }
            if (cfg.hasOwnProperty("align"))
            {
                fmt.align = cfg.align;
                changed = true;
            }

            if (changed)
            {
                tf.defaultTextFormat = fmt;
                tf.setTextFormat(fmt);
            }
        }

        // ═══════════════════════════════════════════════════════
        // 静态工具
        // ═══════════════════════════════════════════════════════

        /** 安全取数字值。 */
        private static function _num(value:*, defaultVal:Number = 0):Number
        {
            if (value == null || isNaN(Number(value)))
                return defaultVal;
            return Number(value);
        }
    }
}
