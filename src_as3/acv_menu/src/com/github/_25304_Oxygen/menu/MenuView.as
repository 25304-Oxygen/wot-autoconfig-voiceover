package com.github._25304_Oxygen.menu
{
    import flash.display.Sprite;
    import flash.display.Stage;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.geom.Point;
    import flash.geom.Rectangle;

    import net.wg.infrastructure.base.AbstractView;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.util.JsonWriter;
    import com.github._25304_Oxygen.shared.util.ColorUtil;
    import com.github._25304_Oxygen.shared.tween.Tween;
    import com.github._25304_Oxygen.shared.tween.Easing;
    import com.github._25304_Oxygen.shared.ui.DragBehavior;
    import com.github._25304_Oxygen.shared.ui.ImageCache;
    import com.github._25304_Oxygen.shared.i18n.L10n;

    import com.github._25304_Oxygen.menu.components.Theme;
    import com.github._25304_Oxygen.menu.pages.BasePage;
    import com.github._25304_Oxygen.menu.pages.HtmlContentPage;
    import com.github._25304_Oxygen.menu.pages.SettingsPage;
    import com.github._25304_Oxygen.menu.pages.VoiceSwitchPage;
    import com.github._25304_Oxygen.menu.pages.HelpPage;
    import com.github._25304_Oxygen.menu.pages.VoicePackDetailPage;
    import com.github._25304_Oxygen.menu.pages.PersonalSettingsPage;
    import com.github._25304_Oxygen.menu.pages.SubtitleSettingsPage;

    /**
     * ACV 菜单主视图（v2 — 三态布局）。
     *
     * 全折叠: 仅大圆 Φ260
     * 半折叠: 大圆 + 左侧 3 小圆 Φ84（弧形）+ 右圆角面板 620×260
     * 全展开: 半折叠 + 下方直角面板 680×500（弹出 overshoot）
     *
     * z-order（底→顶）:
     *   全展开面板 → 半折叠面板 → 小圆 → 大圆
     */
    public class MenuView extends AbstractView
    {
        private static const L:Object = Log.getLogger("MenuView");

        // ════════════════════════════════════
        // 尺寸常量
        // ════════════════════════════════════

        private static const BIG_D:int = 260;
        private static const BIG_R:int = 130;

        private static const SMALL_D:int = 84;
        private static const SMALL_R:int = 42;

        /** 大圆圆心到小圆圆心的距离 */
        private static const ARC_DIST:int = 210;

        /** 弧形角度: 28° 间隔（208=左上, 180=正左, 152=左下），总跨度 56° */
        private static const ARC_ANGLES:Array = [208, 180, 152];
        private static const SC_PAGE_IDS:Array = ["settings", "voiceSwitch", "help"];

        /** 右边缘回缩 50px（原 780 → 730） */
        private static const FULL_RIGHT:int = 730;

        private static const SEMI_X:int = BIG_R - 20;   // 110（左延 20px 遮盖圆角）
        private static const SEMI_W:int = FULL_RIGHT - SEMI_X;  // 620
        private static const SEMI_H:int = 260;
        private static const SEMI_R:int = 50;

        private static const FULL_X:int = 50;
        private static const FULL_W:int = FULL_RIGHT - FULL_X;  // 680
        private static const FULL_H:int = 500;
        /** 直角面板上移 50px */
        private static const FULL_Y:int = BIG_D - 60;     // 200

        // ════════════════════════════════════
        // 状态 & 动画
        // ════════════════════════════════════

        private static const ST_COLLAPSED:int = 0;
        private static const ST_SEMI:int      = 1;
        private static const ST_EXPANDED:int  = 2;

        private static const POP_OVER:Number = 14;

        /** scrollRect 四周外扩余量，防止描边被裁剪（panelStrokeW/2=1.5 向上取整 + 余量） */
        private static const STROKE_PAD:int = 3;

        // ════════════════════════════════════
        // 颜色
        // ════════════════════════════════════

        // — Dark+ 配色（VS Code Dark+ / testWindow 同款）—
        private var _bigFill:uint      = 0x1E1E1E;   // 编辑器黑
        private var _bigStroke:uint    = 0x555555;   // 边框灰
        private var _bigStrokeW:Number = 4;
        private var _smallFill:uint    = 0x3D6B9B;   // 钢蓝（testWindow 按钮色）
        private var _smallStroke:uint  = 0x555555;   // 边框灰（与大圆一致）
        private var _smallStrokeW:Number = 1;
        private var _semiBg:uint       = 0x252526;   // 侧栏灰
        private var _fullBg:uint       = 0x2D2D2D;   // 标签页灰
        private var _panelStroke:uint  = 0x888888;   // 浅灰描边
        private var _panelStrokeW:Number = 2;

        // ════════════════════════════════════
        // 显示对象
        // ════════════════════════════════════

        private var _container:Sprite;
        private var _fullPanelClip:Sprite;
        private var _fullPanel:PanelView;
        private var _semiPanelClip:Sprite;
        private var _semiPanel:PanelView;
        private var _semiContent:SemiPanelContent;
        private var _smallCircles:Array;
        private var _bigCircle:CircleButton;

        // ════════════════════════════════════
        // 状态
        // ════════════════════════════════════

        private var _state:int = ST_COLLAPSED;
        private var _currentPageId:String = null;
        private var _transitioning:Boolean = false;

        /** 动画期间用户点击排队: {type: "expand"|"collapse"|"toggle", pageId: String} */
        private var _pendingClick:Object = null;

        /** ESC 触发：正常折叠并保存状态后自动隐藏。 */
        private var _hideAfterCollapse:Boolean = false;

        /** 收起前最后非 COLLAPSED 状态，用于下次点击大圆恢复。 */
        private var _lastNonCollapsedState:int = ST_SEMI;
        private var _lastNonCollapsedPageId:String = "help";

        /** 左正方形按钮：小圆是否显示（默认 true，持久化）。 */
        private var _circlesEnabled:Boolean = true;

        /** 右正方形按钮：面板展开是否被锁定（true=收起态，大圆不能再全展开）。 */
        private var _panelLocked:Boolean = false;

        /** 面板收展意图：true=下方面板应当展开。点击收展按钮时立即翻转
         *  （箭头即时反馈），动画期间的点击在动画结束后由
         *  _reconcilePanelIntent() 按最终意图对账执行。 */
        private var _panelIntentExpanded:Boolean = false;

        private var _normX:Number = 0.5;
        private var _normY:Number = 0.5;
        private var _positioned:Boolean = false;

        private var _drag:DragBehavior;
        private var _dragStartMouse:Point;
        private var _dragStartContainer:Point;

        private var _pages:Object = {};

        // ════════════════════════════════════
        // 生命周期
        // ════════════════════════════════════

        public function MenuView()
        {
            super();
            L.info("构造");
        }

        override protected function onPopulate():void
        {
            super.onPopulate();
            Tween.init(stage);
            ImageCache.initLoaderHost(stage);
            L.info("onPopulate — " + stage.stageWidth + "x" + stage.stageHeight);

            _container = new Sprite();
            addChild(_container);

            _createFullPanel();      // z=0
            _createSemiPanel();      // z=1
            _createSmallCircles();   // z=2
            _createBigCircle();      // z=3

            // 注册主题回调——切换颜色方案后自动刷新所有视觉组件
            var self:MenuView = this;
            Theme.register(this, function():void { self._refreshStyle(); });

            // 注册 i18n 刷新回调——labels 推送（切语言）后刷新半折叠面板文本
            L10n.register(this, function():void { self._applyLabels(); });

            _drag = new DragBehavior(_container, _bigCircle, _onDragEnd);
            _drag.setHandleBounds(BIG_D, BIG_D);
            _drag.setMargins(100, 200, 40, 40);
            _bigCircle.addEventListener(MouseEvent.MOUSE_DOWN, _onDragStartTrack);  

            _pages["settings"]          = new SettingsPage();
            _pages["voiceSwitch"]       = new VoiceSwitchPage();
            _pages["help"]              = new HelpPage();
            _pages["voicePackDetail"]   = new VoicePackDetailPage();
            _pages["personalSettings"]  = new PersonalSettingsPage();
            _pages["subtitleSettings"]  = new SubtitleSettingsPage();

            // 立即初始化 SettingsPage，使其在 populate() 被 Python 调用前就准备好组件
            // 否则 Python 通过 __menuReady__ 信号推送数据时 _dropdown 等组件为 null
            (_pages["settings"] as SettingsPage).init();
            (_pages["voiceSwitch"] as VoiceSwitchPage).init();
            (_pages["help"] as HelpPage).init();
            (_pages["voicePackDetail"] as VoicePackDetailPage).init();
            (_pages["personalSettings"] as PersonalSettingsPage).init();
            (_pages["subtitleSettings"] as SubtitleSettingsPage).init();

            // VoiceSwitchPage 的用户操作回调 → Python onLog
            (_pages["voiceSwitch"] as VoiceSwitchPage).onAction = this.onLog;

            // SettingsPage 的用户操作回调 → Python onLog
            (_pages["settings"] as SettingsPage).onAction = this.onLog;

            // HtmlContentPage 子类的用户操作回调 → Python onLog
            (_pages["help"] as HelpPage).onAction = this.onLog;
            (_pages["voicePackDetail"] as VoicePackDetailPage).onAction = this.onLog;

            // PersonalSettingsPage 的用户操作回调 → Python onLog
            (_pages["personalSettings"] as PersonalSettingsPage).onAction = this.onLog;

            // SubtitleSettingsPage 的用户操作回调 → Python onLog
            (_pages["subtitleSettings"] as SubtitleSettingsPage).onAction = this.onLog;

            _positionContainer();
            stage.addEventListener(Event.RESIZE, _onStageResize);
            Log.setPythonLogger(this.onLog);
            L.info("就绪");

            // 通知 Python 端 MenuView 已完全就绪，可以推送设置数据
            if (this.onLog != null)
                this.onLog("__menuReady__");
        }

        override protected function onDispose():void
        {
            L.info("onDispose");
            Theme.unregister(this);
            L10n.unregister(this);
            if (stage) stage.removeEventListener(Event.RESIZE, _onStageResize);
            if (_bigCircle) _bigCircle.removeEventListener(MouseEvent.MOUSE_DOWN, _onDragStartTrack);

            for (var key:String in _pages)
            {
                var page:BasePage = _pages[key] as BasePage;
                if (page) page.dispose();
            }
            _pages = {};

            if (_drag) { _drag.dispose(); _drag = null; }
            Tween.kill(_container);
            ImageCache.clear();
            Tween.dispose();
            super.onDispose();
        }

        // ════════════════════════════════════
        // 创建组件
        // ════════════════════════════════════

        private function _createFullPanel():void
        {
            _fullPanelClip = new Sprite();
            _fullPanelClip.x = FULL_X;
            _fullPanelClip.y = FULL_Y;
            _fullPanelClip.scrollRect = new Rectangle(-STROKE_PAD, -STROKE_PAD,
                FULL_W + STROKE_PAD * 2, FULL_H + POP_OVER + STROKE_PAD * 2);

            _fullPanel = new PanelView(FULL_W, FULL_H, _fullBg, 1.0, 0, true,
                                       _panelStroke, _panelStrokeW);
            _fullPanel.setTarget(0, 0);
            _fullPanel.mouseEnabled = false;
            _fullPanel.mouseChildren = false;

            _fullPanelClip.addChild(_fullPanel);
            _fullPanelClip.visible = false;  // 初始折叠态隐藏
            _container.addChild(_fullPanelClip);
        }

        private function _createSemiPanel():void
        {
            _semiPanelClip = new Sprite();
            _semiPanelClip.x = SEMI_X;
            _semiPanelClip.y = -2;  // 补偿描边差异，视觉对齐大圆顶部
            _semiPanelClip.scrollRect = new Rectangle(-STROKE_PAD, -STROKE_PAD,
                SEMI_W + STROKE_PAD * 2, SEMI_H + STROKE_PAD * 2);

            _semiPanel = new PanelView(SEMI_W, SEMI_H, _semiBg, 1.0, SEMI_R, false,
                                       _panelStroke, _panelStrokeW);
            _semiPanel.setTarget(0, 0);
            _semiPanel.mouseEnabled = false;
            _semiPanel.mouseChildren = false;

            _semiContent = new SemiPanelContent(SEMI_W, SEMI_H);
            _semiContent.onToggle = _onToggle;
            _semiContent.onButtonClick = _onSemiButtonClick;
            _semiContent.onCircleToggle = _onCircleToggle;
            _semiContent.onPanelToggle = _onPanelToggle;
            _semiPanel.contentLayer.addChild(_semiContent);

            _semiPanelClip.addChild(_semiPanel);
            _semiPanelClip.visible = false;  // 初始折叠态隐藏
            _container.addChild(_semiPanelClip);
        }

        private function _createSmallCircles():void
        {
            _smallCircles = [];
            for (var i:int = 0; i < 3; i++)
            {
                var sc:CircleButton = new CircleButton(SMALL_D, _smallFill,
                    _smallStroke, _smallStrokeW, true);  // 挂图后隐藏填充+描边
                sc.alpha = 0;
                sc.mouseEnabled = false;
                sc.mouseChildren = false;
                sc.onClick = _makeSmallCircleHandler(i);
                _positionSmallAtCenter(sc);
                _container.addChild(sc);
                _smallCircles.push(sc);
            }
        }

        private function _makeSmallCircleHandler(index:int):Function
        {
            return function():void { _onSmallCircleClick(index); };
        }

        private function _createBigCircle():void
        {
            _bigCircle = new CircleButton(BIG_D, _bigFill, _bigStroke, _bigStrokeW);
            _bigCircle.x = 0;
            _bigCircle.y = 0;
            _bigCircle.onClick = _onBigCircleClick;
            _container.addChild(_bigCircle);
        }

        // ════════════════════════════════════
        // DAAPI
        // ════════════════════════════════════

        public var onLog:Function;

        /**
         * 接收 Python 推送的 UI 标签 dict（i18n 词典）并全局刷新。
         * 切换语言时 Python 端重推（MenuManager._push_settings_data 开头），
         * L10n.setLabels 会刷新所有已注册页面/组件的文本。
         */
        public function as_setLabels(labels:Object):void
        {
            L10n.setLabels(labels);
            L.info("界面标签已更新 (" + L10n.labelCount() + " 键)");
        }

        /** i18n 刷新回调——labels 更新后刷新半折叠面板的固定文本。 */
        private function _applyLabels():void
        {
            if (_semiContent)
                _semiContent.refreshTexts();
        }

        /** 拖拽松手后回调: onSavePosition(normX:Number, normY:Number) */
        public var onSavePosition:Function;

        /** 展开/收起/页面切换后回调: onSaveState(stateJson:String) */
        public var onSaveState:Function;

        public function as_setConfig(config:Object):void
        {
            if (!config || !config.colors) { L.warn("setConfig: 无颜色配置"); return; }
            var c:Object = config.colors;

            if (c.bigFill  != null) _bigFill  = ColorUtil.parse(c.bigFill,  _bigFill);
            if (c.bigStroke != null) _bigStroke = ColorUtil.parse(c.bigStroke, _bigStroke);
            if (c.bigStrokeWidth != null) _bigStrokeW = Number(c.bigStrokeWidth);
            if (c.smallFill != null) _smallFill = ColorUtil.parse(c.smallFill, _smallFill);
            if (c.smallStroke != null) _smallStroke = ColorUtil.parse(c.smallStroke, _smallStroke);
            if (c.smallStrokeWidth != null) _smallStrokeW = Number(c.smallStrokeWidth);
            if (c.semiBg    != null) _semiBg    = ColorUtil.parse(c.semiBg,    _semiBg);
            if (c.fullBg    != null) _fullBg    = ColorUtil.parse(c.fullBg,    _fullBg);
            if (c.panelStroke != null) _panelStroke = ColorUtil.parse(c.panelStroke, _panelStroke);
            if (c.panelStrokeWidth != null) _panelStrokeW = Number(c.panelStrokeWidth);

            _bigCircle.setColors(_bigFill, _bigStroke, _bigStrokeW);
            for (var i:int = 0; i < _smallCircles.length; i++)
                (_smallCircles[i] as CircleButton).setColors(_smallFill, _smallStroke, _smallStrokeW);
            _fullPanel.setStroke(_panelStroke, _panelStrokeW);
            _semiPanel.setStroke(_panelStroke, _panelStrokeW);
            L.info("颜色配置已更新");
        }

        /**
         * 显隐整个菜单视图（F10 热键 / ModsList 入口切换调用）。
         *
         * 必须由 AS3 自己设置 visible——Python 端直接写
         * flashObject.visible 会切断 Flash → Python 的 DAAPI 回调通道
         * （onLog 等全部失联，表现为按钮点击后无日志、
         * 大圆翻转等 Python 驱动的效果失效），且 WG 官方代码从不这样做。
         */
        public function as_setVisible(on:Boolean):void
        {
            this.visible = on;
            L.info(on ? "显示" : "隐藏");
        }

        /**
         * 接收 Python 端传入的设置页数据，转发到 SettingsPage。
         * @param data  字段: dropdownItems, iconPath, defaultText, tooltipHtml
         */
        public function as_populateSettings(data:Object):void
        {
            if (!data)
            {
                L.warn("as_populateSettings: data 为空");
                return;
            }

            var settingsPage:SettingsPage = _pages["settings"] as SettingsPage;
            if (settingsPage)
            {
                settingsPage.populate(data);
                L.info("设置页数据已转发");
            }
            else
            {
                L.warn("as_populateSettings: SettingsPage 未找到");
            }
        }

        /**
         * 接收 Python 端传入的语音切换页数据，转发到 VoiceSwitchPage。
         * @param data  字段: ingameVoices, outsideVoices, currentVoiceId,
         *                      volume, previewEvents, tooltipHtml
         */
        public function as_populateVoiceSwitches(data:Object):void
        {
            try
            {
                if (!data)
                {
                    L.warn("as_populateVoiceSwitches: data 为空");
                    return;
                }

                // 字幕按钮显隐——与语音切换页数据一起推送，避免独立 DAAPI
                // 调用失败时按钮状态不确定。
                if (data.hasOwnProperty("subtitleAvailable"))
                {
                    var avail:Boolean = data.subtitleAvailable == true
                                     || data.subtitleAvailable == 1;
                    if (_semiContent)
                        _semiContent.setSubtitleButtonVisible(avail);
                }

                var voiceSwitchPage:VoiceSwitchPage = _pages["voiceSwitch"] as VoiceSwitchPage;
                if (voiceSwitchPage)
                {
                    voiceSwitchPage.populate(data);
                    L.info("语音切换页数据已转发");
                }
                else
                {
                    L.warn("as_populateVoiceSwitches: VoiceSwitchPage 未找到");
                }
            }
            catch (e:Error)
            {
                L.error("as_populateVoiceSwitches 异常: " + e.message
                    + "\n" + e.getStackTrace());
            }
        }

        /**
         * 接收 Python 端传入的 HTML 内容页数据，转发到对应的 HtmlContentPage 子类。
         * @param pageId  页面标识 ("help"、"voicePackDetail" 等)
         * @param data    字段: title, html, titleTooltipHtml
         */
        public function as_populatePage(pageId:String, data:Object):void
        {
            if (!pageId || !data)
            {
                L.warn("as_populatePage: pageId 或 data 为空");
                return;
            }

            var page:HtmlContentPage = _pages[pageId] as HtmlContentPage;
            if (page)
            {
                page.populate(data);
                L.info(pageId + " 数据已转发");
            }
            else
            {
                L.warn("as_populatePage: 页面 " + pageId + " 未找到或不是 HtmlContentPage");
            }
        }

        /**
         * 接收 Python 端推送的个性设置页数据，转发到 PersonalSettingsPage。
         * @param data  字段: declarationText, spottedMessage,
         *              spottedAliveLe, replaceDropdownItems,
         *              replaceSelectedIndex, replaceText,
         *              replacePlaceholder, previewText, tooltips
         */
        public function as_populatePersonalSettings(data:Object):void
        {
            if (!data)
            {
                L.warn("as_populatePersonalSettings: data 为空");
                return;
            }

            var page:PersonalSettingsPage = _pages["personalSettings"] as PersonalSettingsPage;
            if (page)
            {
                page.populate(data);
                L.info("个性设置数据已转发");
            }
            else
            {
                L.warn("as_populatePersonalSettings: PersonalSettingsPage 未找到");
            }
        }

        /**
         * 接收 Python 端推送的字幕设置页数据，转发到 SubtitleSettingsPage。
         * @param data  字段: tooltips {pageTitle: html}
         */
        public function as_populateSubtitleSettings(data:Object):void
        {
            if (!data)
            {
                L.warn("as_populateSubtitleSettings: data 为空");
                return;
            }

            var subPage:SubtitleSettingsPage = _pages["subtitleSettings"] as SubtitleSettingsPage;
            if (subPage)
            {
                subPage.populate(data);
                L.info("字幕设置数据已转发");
            }
            else
            {
                L.warn("as_populateSubtitleSettings: SubtitleSettingsPage 未找到");
            }
        }

        /**
         * 运行时切换主题色板。
         * Python 端可随时调用，所有已注册组件立即重绘。
         * @param themeData  键值对，只更新传入的键，未传的保留当前值。
         *                   例: { accent: 0xFF6B6B, surface0: 0x1A1A2E }
         */
        public function as_applyTheme(themeData:Object):void
        {
            if (!themeData)
            {
                L.warn("as_applyTheme: themeData 为空");
                return;
            }
            Theme.apply(themeData);
            L.info("主题已切换");
        }

        /**
         * 运行时挂载/替换组件图片（与 as_applyTheme 同理，只处理传入的键）。
         * 值为空字符串 → 清除图片恢复默认外观；加载失败 → 保持默认外观。
         * @param data  可选键:
         *              bigCircle:String     大圆图片路径
         *              semiPanel:String     半折叠圆角面板背景图
         *              fullPanel:String     全展开直角面板背景图
         *              smallCircles:Array   三个小圆的图片路径 [设置, 语音, 帮助]
         *              （路径相对 res/gui/flash/，如 ../../mods/.../icon/menu.png）
         */
        public function as_setImages(data:Object):void
        {
            if (!data)
            {
                L.warn("as_setImages: data 为空");
                return;
            }

            if (data.hasOwnProperty("bigCircle"))
                _bigCircle.setImage(String(data.bigCircle));

            if (data.hasOwnProperty("semiPanel"))
                _semiPanel.setImage(String(data.semiPanel));

            if (data.hasOwnProperty("fullPanel"))
                _fullPanel.setImage(String(data.fullPanel));

            if (data.hasOwnProperty("smallCircles") && data.smallCircles)
            {
                var paths:Array = data.smallCircles as Array;
                if (paths)
                {
                    var n:int = Math.min(paths.length, _smallCircles.length);
                    for (var i:int = 0; i < n; i++)
                        (_smallCircles[i] as CircleButton).setImage(String(paths[i]));
                }
            }

            L.info("组件图片已更新");
        }

        /**
         * 触发大圆 2D 翻转（整个大圆绕圆心竖直轴压扁再展开）。
         * Python 端在启用/禁用、切换语音包时调用。
         * @param newImagePath  可选：翻转中点替换的新图片路径（切换语音包用）
         */
        public function as_flipBigCircle(newImagePath:String = null):void
        {
            if (!_bigCircle) return;

            if (newImagePath && newImagePath.length > 0)
                _bigCircle.flipWithImage(newImagePath);
            else
                _bigCircle.flip();
        }

        /**
         * 更新半折叠面板标题文本为当前语音包显示名称。
         * Python 端在切换语音后调用。
         */
        public function as_setTitleText(text:String):void
        {
            if (_semiContent)
                _semiContent.setInfoText(text);
        }

        /**
         * 切换语音包后，Python 端通知字幕功能是否可用。
         * 不可用时隐藏半折叠面板的"字幕"按钮；
         * 若当前正在字幕设置页则自动切回帮助页。
         * @param available  true=当前语音包有字幕样式 JSON
         */
        public function as_setSubtitleAvailable(available:Boolean):void
        {
            if (_semiContent)
                _semiContent.setSubtitleButtonVisible(available);

            // 字幕不可用 + 当前在字幕设置页 → 自动切到帮助页
            if (!available && _currentPageId == "subtitleSettings"
                && _state == ST_EXPANDED)
            {
                L.info("字幕不可用，自动切换 subtitleSettings → help");
                _toExpanded("help");
            }
        }

        /**
         * Python 端隐藏菜单（as_setVisible(false)）前调用（F10 / ModsList）。
         * 这种隐藏不走折叠动画，Flash 侧感知不到——由 Python 主动通知，
         * 让当前页面执行 hide() 生命周期（如字幕设置页的编辑中自动保存）。
         */
        public function as_notifyHidden():void
        {
            if (_state == ST_EXPANDED)
            {
                var page:BasePage = _pages[_currentPageId] as BasePage;
                if (page)
                {
                    page.hide();
                    L.info("as_notifyHidden: 当前页已通知隐藏 (" + _currentPageId + ")");
                }
            }
        }

        /**
         * ESC 触发：正常折叠 + 保存状态 + 隐藏（等价于点击大圆 + F10）。
         *
         * 与旧行为的区别：折叠完成后先通过 _notifyStateChange 保存
         * COLLAPSED 状态到配置文件，再隐藏视图。下次 F10 打开菜单后，
         * 点击大圆图标可恢复到本次收起前的展开状态。
         */
        public function as_collapseAndHide():void
        {
            if (_state == ST_COLLAPSED)
            {
                // 已经折叠 → 直接隐藏
                this.visible = false;
                if (onLog != null) onLog("menuHidden");
                L.info("ESC: 已隐藏（已处于折叠态）");
                return;
            }

            // 正常折叠流程，动画完成后自动隐藏（状态会被保存）
            _hideAfterCollapse = true;
            _toCollapsed();
            L.info("ESC: 触发折叠 → 保存状态 → 隐藏");
        }

        /**
         * 跨会话恢复：设置初始位置和页面状态（不走动画）。
         * Python 端在 __menuReady__ 后调用，传入上次保存的配置。
         */
        public function as_setInitialState(data:Object):void
        {
            if (!data)
            {
                L.warn("as_setInitialState: data 为空");
                return;
            }

            // ── 位置 ──
            if (data.position && data.position.normX != null)
            {
                _normX = Number(data.position.normX);
                _normY = Number(data.position.normY);
                _positioned = true;
                _applyNormalizedPosition();
                if (_drag) _drag.clamp();
                L.info("初始位置已恢复: normX=" + _normX.toFixed(3)
                    + ", normY=" + _normY.toFixed(3));
            }

            // ── 状态 ──
            if (data.lastState && data.lastState.state)
            {
                var ls:Object = data.lastState;
                var targetState:String = String(ls.state);

                // 恢复"收起前状态"——即使当前是 COLLAPSED 也要恢复，
                // 否则跨会话后点击大圆只能到 SEMI 而非上次的 EXPANDED。
                if (ls.lastNonCollapsedState)
                {
                    _lastNonCollapsedState = (String(ls.lastNonCollapsedState) == "EXPANDED")
                        ? ST_EXPANDED : ST_SEMI;
                    _lastNonCollapsedPageId = String(ls.lastNonCollapsedPageId || "help");
                }

                // 恢复正方形按钮状态
                if (ls.hasOwnProperty("circlesEnabled"))
                    _circlesEnabled = Boolean(ls.circlesEnabled);
                if (ls.hasOwnProperty("panelLocked"))
                    _panelLocked = Boolean(ls.panelLocked);

                if (targetState == "EXPANDED")
                    _restoreExpanded(ls);
                else if (targetState == "SEMI")
                    _restoreSemi(ls);
                // COLLAPSED: 不展开面板，但上面的 _lastNonCollapsed* 已恢复，
                //           点击大圆即可回到收起前的状态。

                L.info("初始状态已恢复: " + targetState
                    + " (lastNonCollapsed=" + (_lastNonCollapsedState == ST_EXPANDED ? "EXPANDED" : "SEMI")
                    + " " + _lastNonCollapsedPageId + ")");
            }
        }

        /** 无动画恢复到半折叠状态。 */
        private function _restoreSemi(ls:Object):void
        {
            _state = ST_SEMI;
            _currentPageId = String(ls.pageId || "help");
            _panelIntentExpanded = false;

            // 同步恢复记忆，确保后续收起→展开能回到此状态
            _lastNonCollapsedState = ST_SEMI;
            _lastNonCollapsedPageId = _currentPageId;

            // 半折叠面板 — 立即可见
            _semiPanelClip.visible = true;
            _semiPanel.showInstant();
            _semiPanel.mouseEnabled = true;
            _semiPanel.mouseChildren = true;

            // 小圆 — 仅在未锁定时直接放到目标位置
            if (_circlesEnabled)
            {
                for (var i:int = 0; i < 3; i++)
                {
                    var sc:CircleButton = _smallCircles[i] as CircleButton;
                    Tween.kill(sc);
                    var tp:Point = _smallCircleTarget(i);
                    sc.x = tp.x;
                    sc.y = tp.y;
                    sc.alpha = 1.0;
                sc.mouseEnabled = true;
                sc.mouseChildren = true;
            }
            }

            _updateSquareArrows();

            L.info("恢复 → 半折叠 (" + _currentPageId + ")");
        }

        /** 无动画恢复到全展开状态。 */
        private function _restoreExpanded(ls:Object):void
        {
            // 先恢复到半折叠
            _restoreSemi(ls);
            _state = ST_EXPANDED;
            _panelIntentExpanded = true;

            // 覆盖 _restoreSemi 的值：实际状态是全展开
            _lastNonCollapsedState = ST_EXPANDED;
            _lastNonCollapsedPageId = _currentPageId;

            // 全展开面板 — 立即可见
            _fullPanelClip.visible = true;
            _fullPanel.showInstant();
            _fullPanel.mouseEnabled = true;
            _fullPanel.mouseChildren = true;

            var pageId:String = String(ls.pageId || "help");
            var page:BasePage = _pages[pageId] as BasePage;
            if (!page)
            {
                // 旧配置遗留的无效 pageId → 回退到帮助页，避免空白面板
                L.warn("恢复时页面未注册: " + pageId + " → 回退 help");
                pageId = "help";
                page = _pages[pageId] as BasePage;
            }
            if (page)
            {
                _fullPanel.setContent(page);
                _currentPageId = pageId;
                page.show();    // 生命周期钩子：页面即将显示
            }

            _updateSquareArrows();

            L.info("恢复 → 全展开 (" + _currentPageId + ")");
        }

        // ════════════════════════════════════
        // 状态机
        // ════════════════════════════════════

        /**
         * 任一动画阶段完成后调用。如果有排队中的点击请求，
         * 则执行之（调用方可传入直接后继步骤以节约一帧延时）。
         */
        private function _onTransitionDone(postAction:Function = null):void
        {
            L.debug("_onTransitionDone 进入: _state=" + _state
                + " _hideAfterCollapse=" + _hideAfterCollapse
                + " _pendingClick=" + (_pendingClick != null ? _pendingClick.type : "null"));
            _transitioning = false;

            // — ESC 触发的隐藏优先于任何排队点击 —
            // 必须先检查 _hideAfterCollapse，否则 _pendingClick 处理中可能改变
            // _state（如 _toExpanded），导致 _state != ST_COLLAPSED 跳过隐藏。
            // 用户按 ESC 的意图是"关闭菜单"，优先级高于动画期间的排队操作。
            if (_hideAfterCollapse && _state == ST_COLLAPSED)
            {
                _hideAfterCollapse = false;
                // 先隐藏视图，再尝试保存状态——
                // _notifyStateChange() 可能因 DAAPI / JSON 序列化抛异常，
                // 若隐藏在后则异常导致菜单永远不隐藏。
                this.visible = false;
                if (onLog != null) onLog("menuHidden");
                L.info("ESC: 折叠完成，视图已隐藏");
                if (postAction != null) postAction();

                try
                {
                    _notifyStateChange();
                }
                catch (e:Error)
                {
                    L.warn("ESC: 状态保存失败: " + e.message);
                }

                return;                 // 不再处理排队点击——菜单已隐藏
            }

            if (_pendingClick)
            {
                var pending:Object = _pendingClick;
                _pendingClick = null;
                L.debug("执行排队操作: " + pending.type
                    + (pending.pageId ? " → " + pending.pageId : ""));
                if (pending.type == "expand")
                    _toExpanded(pending.pageId);
                else if (pending.type == "collapse")
                    _toCollapsed();
                else if (pending.type == "collapseFullPanel")
                    _toCollapsedFullPanel();
                else if (pending.type == "toggle")
                    _onBigCircleClick();
            }
            else
            {
                _updateSquareArrows();
                _notifyStateChange();
                if (postAction != null)
                    postAction();
                // 动画期间收展按钮的点击在此对账（可能启动新一轮收展动画）
                _reconcilePanelIntent();
            }
        }

        /** 构造状态对象并通过 onSaveState 回调通知 Python 保存。
         *  内部 try/catch 确保序列化或 DAAPI 异常不影响调用方。 */
        private function _notifyStateChange():void
        {
            if (onSaveState == null) return;

            try
            {
                var stateStr:String;
                if (_state == ST_SEMI) stateStr = "SEMI";
                else if (_state == ST_EXPANDED) stateStr = "EXPANDED";
                else stateStr = "COLLAPSED";

                var stateData:Object = {
                    state: stateStr,
                    pageId: _currentPageId || "help",
                    smallCircles: _areSmallCirclesVisible(),
                    semiPanel: _semiPanelClip.visible,
                    fullPanel: _fullPanelClip.visible,
                    lastNonCollapsedState: _lastNonCollapsedState == ST_EXPANDED
                        ? "EXPANDED" : "SEMI",
                    lastNonCollapsedPageId: _lastNonCollapsedPageId || "help",
                    circlesEnabled: _circlesEnabled,
                    panelLocked: _panelLocked
                };

                onSaveState(JsonWriter.write(stateData));
                L.debug("状态已通知保存: " + stateStr
                    + " lastNonCollapsed=" + (stateData.lastNonCollapsedState)
                    + " " + (stateData.lastNonCollapsedPageId));
            }
            catch (e:Error)
            {
                L.warn("_notifyStateChange 失败: " + e.message);
            }
        }

        /** 小圆是否处于展开（可见）状态。 */
        private function _areSmallCirclesVisible():Boolean
        {
            if (!_smallCircles || _smallCircles.length == 0) return false;
            var sc:CircleButton = _smallCircles[0] as CircleButton;
            return sc && sc.alpha > 0.5 && sc.mouseEnabled;
        }

        private function _toSemi():void
        {
            if (_transitioning)
            {
                // 动画中进行中 → 排队
                _pendingClick = {type: "toggle"};
                return;
            }
            if (_state != ST_COLLAPSED) return;
            _transitioning = true;
            _state = ST_SEMI;
            L.info("→ 半折叠");

            _semiPanel.mouseEnabled = true;
            _semiPanel.mouseChildren = true;
            _semiPanelClip.visible = true;
            if (_circlesEnabled)
                _animateSmallCirclesOut();
            _updateSquareArrows();
            // 面板滑入 → 大圆图片轻呼吸一次（与滑入时长一致）
            _bigCircle.breathe(1.06, 0.4);
            _semiPanel.showIn(function():void { _onTransitionDone(); });
        }

        private function _toCollapsed():void
        {
            if (_transitioning)
            {
                _pendingClick = {type: "collapse"};
                return;
            }
            if (_state == ST_COLLAPSED) return;
            _panelIntentExpanded = false;  // 面板整体收起，意图复位
            _updateSquareArrows();         // 收起一开始箭头即回到"朝上"

            // 记住本次展开状态，供下次点击大圆恢复
            _lastNonCollapsedState = _state;
            _lastNonCollapsedPageId = _currentPageId;
            L.info("_toCollapsed: 记忆收起前 _state="
                + (_state == ST_EXPANDED ? "EXPANDED" : "SEMI")
                + " pageId=" + _currentPageId
                + " (调用来源: _hideAfterCollapse=" + _hideAfterCollapse + ")");

            if (_state == ST_EXPANDED)
            {
                // 生命周期钩子：当前页即将隐藏（覆盖 ESC 关闭菜单路径）
                var curPage:BasePage = _pages[_currentPageId] as BasePage;
                if (curPage) curPage.hide();

                _transitioning = true;
                L.info("→ 全折叠（先弹回直角面板）");
                _fullPanel.popOut(function():void {
                    _fullPanel.mouseEnabled = false;
                    _fullPanel.mouseChildren = false;
                    _fullPanelClip.visible = false;
                    _collapseSemi();
                });
            }
            else if (_state == ST_SEMI)
            {
                _collapseSemi();
            }
        }

        private function _collapseSemi():void
        {
            _transitioning = true;
            _state = ST_COLLAPSED;
            _updateSquareArrows();  // 小圆随整体收起开始回收 → 左箭头同步翻向右
            _semiPanel.mouseEnabled = false;
            _semiPanel.mouseChildren = false;
            _animateSmallCirclesIn();
            // 面板滑出 → 大圆图片轻呼吸一次（与滑出时长一致）
            _bigCircle.breathe(1.06, 0.3);
            _semiPanel.showOut(function():void {
                L.debug("_collapseSemi: showOut 回调触发");
                _semiPanelClip.visible = false;
                _onTransitionDone();
            });
        }

        private function _toExpanded(pageId:String):void
        {
            _panelIntentExpanded = true;   // 同步意图（导航/恢复路径也走这里）
            _updateSquareArrows();         // 展开一开始箭头即指示方向，不等动画结束
            if (_transitioning)
            {
                // 动画中进行中 → 排队最近一次的页面请求
                _pendingClick = {type: "expand", pageId: pageId};
                return;
            }

            if (_state == ST_EXPANDED)
            {
                if (pageId == _currentPageId) { L.debug("已在当前页面: " + pageId); return; }
                _transitioning = true;
                // DEBUG：页面切换中间态（PanelView 的"切换到页面"记录最终落地）
                L.debug("全展开页面切换: " + _currentPageId + " → " + pageId);

                var newPage:BasePage = _pages[pageId] as BasePage;
                if (!newPage) { L.warn("页面未注册: " + pageId); _transitioning = false; return; }

                // 生命周期钩子：旧页即将隐藏、新页即将显示
                var oldPage:BasePage = _pages[_currentPageId] as BasePage;
                if (oldPage) oldPage.hide();
                _currentPageId = pageId;
                newPage.show();

                _fullPanel.switchPageVertical(newPage, function():void { _onTransitionDone(); });
            }
            else if (_state == ST_SEMI)
            {
                // 页面未注册（如旧配置遗留的无效 pageId）→ 回退到帮助页，
                // 避免弹出一块空白面板
                if (!(_pages[pageId] as BasePage))
                {
                    L.warn("页面未注册: " + pageId + " → 回退 help");
                    pageId = "help";
                }

                _transitioning = true;
                _state = ST_EXPANDED;
                _currentPageId = pageId;
                L.info("→ 全展开 (" + pageId + ")");

                var page:BasePage = _pages[pageId] as BasePage;
                if (page)
                {
                    _fullPanel.setContent(page);
                    page.show();    // 生命周期钩子：页面即将显示
                }
                _fullPanel.mouseEnabled = true;
                _fullPanel.mouseChildren = true;
                _fullPanelClip.visible = true;
                _fullPanel.popIn(function():void { _onTransitionDone(); });
            }
        }

        // ════════════════════════════════════
        // 小圆动画
        // ════════════════════════════════════

        private function _animateSmallCirclesOut():void
        {
            if (!_circlesEnabled) return;
            for (var i:int = 0; i < 3; i++)
            {
                var sc:CircleButton = _smallCircles[i] as CircleButton;
                Tween.kill(sc);
                _positionSmallAtCenter(sc);
                sc.alpha = 0;
                var tp:Point = _smallCircleTarget(i);
                Tween.to(sc, 0.35, { x: tp.x, y: tp.y, alpha: 1.0 }, Easing.easeOutCubic);
                sc.mouseEnabled = true;
                sc.mouseChildren = true;
            }
        }

        private function _animateSmallCirclesIn():void
        {
            for (var i:int = 0; i < 3; i++)
            {
                var sc:CircleButton = _smallCircles[i] as CircleButton;
                Tween.kill(sc);
                sc.mouseEnabled = false;
                sc.mouseChildren = false;
                var cp:Point = _smallCircleCenter();
                Tween.to(sc, 0.25, { x: cp.x, y: cp.y, alpha: 0 }, Easing.easeInCubic);
            }
        }

        private function _positionSmallAtCenter(sc:CircleButton):void
        {
            var cp:Point = _smallCircleCenter();
            sc.x = cp.x; sc.y = cp.y;
        }

        private function _smallCircleCenter():Point
        {
            return new Point(BIG_R - SMALL_R, BIG_R - SMALL_R);
        }

        private function _smallCircleTarget(i:int):Point
        {
            var rad:Number = ARC_ANGLES[i] * Math.PI / 180;
            var cx:Number = BIG_R + ARC_DIST * Math.cos(rad);
            var cy:Number = BIG_R + ARC_DIST * Math.sin(rad);
            // 上下两个圆向右偏移；第二、三个圆额外右移 10（最下面的圆偏最多）
            var xOffset:Number = (i == 0) ? 10 : (i == 1) ? 20 : 45;
            var yOffset:Number = 25;  // 整体下移（15 + 10）
            return new Point(cx - SMALL_R + xOffset, cy - SMALL_R + yOffset);
        }

        // ════════════════════════════════════
        // 点击事件
        // ════════════════════════════════════

        private function _onBigCircleClick():void
        {
            if (_dragStartMouse && _dragStartContainer)
            {
                var dx:Number = _container.x - _dragStartContainer.x;
                var dy:Number = _container.y - _dragStartContainer.y;
                if (Math.abs(dx) > 3 || Math.abs(dy) > 3) { L.debug("跳过点击（已拖拽）"); return; }
            }

            // 动画期间排队：记录 toggle 意图，动画结束后执行
            if (_transitioning)
            {
                _pendingClick = {type: "toggle"};
                return;
            }

            if (_state == ST_COLLAPSED)
            {
                // 恢复到上次的非折叠状态（面板锁定时上限为 SEMI）
                var expandTarget:int = (_panelLocked)
                    ? ST_SEMI
                    : _lastNonCollapsedState;
                if (expandTarget == ST_EXPANDED)
                {
                    var pageId:String = _lastNonCollapsedPageId || "help";
                    L.info("大圆: 恢复到全展开 (" + pageId + ")");
                    // 提前同步意图——半折叠滑入阶段箭头即指示最终的展开方向，
                    // 不必等排队的 expand 执行（_toSemi 内会重绘箭头）
                    _panelIntentExpanded = true;
                    _toSemi();
                    // 半折叠动画完成后自动继续到全展开
                    _pendingClick = {type: "expand", pageId: pageId};
                }
                else
                {
                    _toSemi();
                }
            }
            else
            {
                _toCollapsed();
            }
        }

        private function _onSmallCircleClick(index:int):void
        {
            // DEBUG：交互中间态，页面落地由 PanelView 的"切换到页面"记录
            L.debug("小圆点击: #" + index + " → " + SC_PAGE_IDS[index]);
            _panelLocked = false;  // 导航操作重置面板锁定
            _toExpanded(SC_PAGE_IDS[index]);
            _updateSquareArrows();
        }

        private function _onSemiButtonClick(pageId:String):void
        {
            L.info("半折叠按钮点击 → " + pageId);
            _panelLocked = false;  // 导航操作重置面板锁定
            _toExpanded(pageId);
            _updateSquareArrows();
        }

        private function _onToggle(enabled:Boolean):void
        {
            L.info("Toggle: " + (enabled ? "启用" : "禁用"));
            if (onLog != null) onLog("toggle," + (enabled ? "enabled" : "disabled"));
        }

        /** 左正方形按钮：切换小圆显隐。 */
        private function _onCircleToggle():void
        {
            _circlesEnabled = !_circlesEnabled;
            L.info("小圆显隐切换 → " + (_circlesEnabled ? "显示" : "隐藏"));

            if (_circlesEnabled)
            {
                // 恢复显示——仅在当前处于半展开或全展开时立即显示
                if (_state == ST_SEMI || _state == ST_EXPANDED)
                    _animateSmallCirclesOut();
            }
            else
            {
                // 隐藏小圆
                if (_state == ST_SEMI || _state == ST_EXPANDED)
                    _animateSmallCirclesIn();
            }

            _updateSquareArrows();
            _notifyStateChange();
        }

        /** 右正方形按钮：切换下方面板收展。
         *  动画期间照常可点击——每次点击翻转"意图"并立即更新箭头，
         *  面板等当前动画结束后（_onTransitionDone → _reconcilePanelIntent）
         *  按最终意图收展。 */
        private function _onPanelToggle():void
        {
            _panelIntentExpanded = !_panelIntentExpanded;
            _panelLocked = !_panelIntentExpanded;  // 收起意图 = 锁定（大圆只能展开到 SEMI）
            _updateSquareArrows();                  // 箭头即时反馈意图
            L.info("面板收展按钮 → 意图=" + (_panelIntentExpanded ? "展开" : "收起")
                + (_transitioning ? "（动画中，结束后执行）" : ""));

            if (_transitioning) return;             // 动画结束后统一对账

            _reconcilePanelIntent();
            if (!_transitioning)
                _notifyStateChange();               // 无需动画时也保存锁定状态变化
        }

        /** 让面板实际收展状态与用户意图一致（仅在无动画时调用）。 */
        private function _reconcilePanelIntent():void
        {
            if (_transitioning) return;
            if (_state == ST_COLLAPSED) return;     // 全折叠时面板整体隐藏，无需对账

            var expanded:Boolean = (_state == ST_EXPANDED);
            if (_panelIntentExpanded == expanded) return;

            if (_panelIntentExpanded)
                _toExpanded(_lastNonCollapsedPageId || "help");
            else
                _toCollapsedFullPanel();
        }

        /** 仅收回全展开面板（不改 _panelLocked 状态，用于大圆路径）。 */
        private function _toCollapsedFullPanel():void
        {
            _panelIntentExpanded = false;  // 同步意图
            if (_transitioning)
            {
                // 动画进行中 → 排队，动画结束后执行
                // （否则展开动画中点击收展按钮会静默丢弃收回命令）
                _pendingClick = {type: "collapseFullPanel"};
                return;
            }
            if (_state != ST_EXPANDED) return;

            // 记住收起前的页面——收展按钮再次展开时恢复到此页
            // （与 _toCollapsed 的记忆逻辑对应，否则再展开会用配置里的旧值）
            if (_currentPageId)
                _lastNonCollapsedPageId = _currentPageId;

            // 生命周期钩子：当前页即将隐藏
            var curPage:BasePage = _pages[_currentPageId] as BasePage;
            if (curPage) curPage.hide();

            _transitioning = true;
            _state = ST_SEMI;
            L.info("→ 收回直角面板（保留半折叠）");
            _fullPanel.popOut(function():void {
                _fullPanel.mouseEnabled = false;
                _fullPanel.mouseChildren = false;
                _fullPanelClip.visible = false;
                _onTransitionDone();
            });
        }

        /** 更新两个正方形按钮的箭头方向。
         *  左按钮: 反映小圆的视觉目标——启用且菜单未（正在）全折叠
         *          → 朝左（小圆可见/展开中）; 否则 → 朝右
         *  右按钮: 反映面板收展意图——展开 → 朝下; 收起 → 朝上
         *  （稳定状态下意图 == 实际状态；动画期间箭头提前指示目标状态） */
        private function _updateSquareArrows():void
        {
            if (!_semiContent) return;
            _semiContent.setCircleArrow(_circlesEnabled && _state != ST_COLLAPSED);
            _semiContent.setPanelArrow(_panelIntentExpanded);
        }

        // ════════════════════════════════════
        // 拖拽
        // ════════════════════════════════════

        private function _onDragStartTrack(event:MouseEvent):void
        {
            _dragStartMouse    = new Point(stage.mouseX, stage.mouseY);
            _dragStartContainer = new Point(_container.x, _container.y);
        }

        private function _onDragEnd(x:Number, y:Number):void
        {
            _saveNormalizedPosition();
            // 只在用户实际拖拽后保存位置（避免初始化时的误存）
            if (onSavePosition != null)
                onSavePosition(_normX, _normY);
        }

        // ════════════════════════════════════
        // 屏幕定位
        // ════════════════════════════════════

        /**
         * 容器定位：首次居中于屏幕，之后恢复上次归一化位置。
         *
         * 用 App.appWidth/appHeight（逻辑坐标）而非 stage.stageWidth/stageHeight
         * （物理分辨率）。interfaceScale（如 4K 2x）下 stage.scaleX/Y = 2 会把
         * 内容整体放大 2x，但 stage 尺寸仍返回物理值（3840×2160）；若按物理值
         * 定位（3840/2=1920），容器逻辑坐标会被放大到屏幕外。
         * 与 WG 各窗口居中写法（App.appWidth >> 1）一致。
         */
        private function _positionContainer():void
        {
            if (!stage) return;
            if (_positioned)
                _applyNormalizedPosition();
            else
            {
                _container.x = int(App.appWidth / 2) - BIG_R - int(SEMI_W / 2) + 10;
                _container.y = int(App.appHeight / 2) - BIG_R;
                _positioned = true;
                _saveNormalizedPosition();
            }
            if (_drag) _drag.clamp();
        }

        private function _onStageResize(event:Event):void
        {
            _applyNormalizedPosition();
            if (_drag) _drag.clamp();
        }

        /** 保存归一化位置——以逻辑屏幕尺寸（App.appWidth/Height）为基准。 */
        private function _saveNormalizedPosition():void
        {
            if (!stage) return;
            _normX = (_container.x + BIG_R) / App.appWidth;
            _normY = (_container.y + BIG_R) / App.appHeight;
        }

        /** 恢复归一化位置——保存/恢复使用同一基准，缩放无关。 */
        private function _applyNormalizedPosition():void
        {
            if (!stage) return;
            _container.x = int(_normX * App.appWidth - BIG_R);
            _container.y = int(_normY * App.appHeight - BIG_R);
        }

        // ════════════════════════════════════
        // 换肤 —— Theme.apply() 触发后同步全部组件
        // ════════════════════════════════════

        /**
         * 从 Theme 静态变量读取最新颜色，应用到所有视觉组件。
         * 由 Theme.apply() 通过注册回调自动触发。
         */
        private function _refreshStyle():void
        {
            // 同步实例变量
            _bigFill      = Theme.surface0;
            _bigStroke    = Theme.stroke;
            _smallFill    = Theme.accent;
            _smallStroke  = Theme.stroke;
            _semiBg       = Theme.surface3;
            _fullBg       = Theme.surface1;
            _panelStroke  = Theme.stroke;

            // 圆
            if (_bigCircle)
                _bigCircle.setColors(_bigFill, _bigStroke, _bigStrokeW);
            for (var i:int = 0; i < _smallCircles.length; i++)
            {
                var sc:CircleButton = _smallCircles[i] as CircleButton;
                if (sc) sc.setColors(_smallFill, _smallStroke, _smallStrokeW);
            }

            // 面板背景 + 描边
            if (_semiPanel)
                _semiPanel.setColors(_semiBg, _panelStroke);
            if (_fullPanel)
                _fullPanel.setColors(_fullBg, _panelStroke);

            // 半折叠面板内容（导航按钮 / 文字 / 箭头）
            if (_semiContent)
                _semiContent.refreshColors();

            // DEBUG：具体色值细节；"主题已切换"（as_applyTheme）已在 INFO 记录
            L.debug("主题已刷新 (surface0=" + _bigFill.toString(16)
                + " accent=" + _smallFill.toString(16)
                + " surface3=" + _semiBg.toString(16) + ")");
        }

        // ════════════════════════════════════
        // 工具
        // ════════════════════════════════════

    }
}
