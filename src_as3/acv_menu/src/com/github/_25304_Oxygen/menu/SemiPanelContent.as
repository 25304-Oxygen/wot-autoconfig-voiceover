package com.github._25304_Oxygen.menu
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.display.GradientType;
    import flash.geom.Matrix;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import com.github._25304_Oxygen.menu.components.SoundableSprite;
    import com.github._25304_Oxygen.menu.components.Theme;
    import com.github._25304_Oxygen.shared.i18n.L10n;

    /**
     * 半折叠面板的固定 UI 内容。
     *
     * 包含: 右上角启用/禁用 toggle、中间文本框、下方 3 个功能按钮。
     * 通过回调与 MenuView 通信，不直接依赖 MenuView。
     */
    public class SemiPanelContent extends Sprite
    {
        // 面板尺寸
        private var _w:Number;
        private var _h:Number;

        // Toggle
        private var _toggleBtn:Sprite;
        private var _toggleBtnLabel:TextField;
        private var _toggleEnabled:Boolean = true;

        // 文本框
        private var _infoTF:TextField;

        // 功能按钮
        private var _buttons:Array;
        private var _buttonBgs:Array;   // 每个按钮的背景 Shape（换肤用）
        private var _buttonTfs:Array;   // 每个按钮的 TextField（换肤用）
        private var _buttonWidths:Array; // 每个按钮当前宽度（i18n 切语言后自适应重排）

        // 控制按钮（右下正方形）
        private var _circleBtn:Sprite;    // 控制小圆显隐
        private var _panelBtn:Sprite;     // 控制下方面板收展
        private var _circleArrowDir:String = "left";   // 当前箭头方向（换肤重绘用）
        private var _panelArrowDir:String  = "up";

        // ═══════════════════════════════════════════════════════
        // 回调
        // ═══════════════════════════════════════════════════════

        /** toggle 状态变更: function(enabled:Boolean):void */
        public var onToggle:Function;

        /** 功能按钮点击: function(pageId:String):void */
        public var onButtonClick:Function;

        /** 小圆控制按钮: function():void */
        public var onCircleToggle:Function;

        /** 面板收展按钮: function():void */
        public var onPanelToggle:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param w  面板内容区宽度
         * @param h  面板内容区高度
         */
        public function SemiPanelContent(w:Number, h:Number)
        {
            super();
            _w = w;
            _h = h;
            _buttonBgs = [];
            _buttonTfs = [];
            _buttonWidths = [];
            _create();
            var self:SemiPanelContent = this;
            Theme.register(this, function():void { self.refreshColors(); });
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 获取 toggle 当前状态。 */
        public function get toggleEnabled():Boolean { return _toggleEnabled; }

        /** 程序化设置 toggle 状态。 */
        public function setToggleEnabled(value:Boolean):void
        {
            _toggleEnabled = value;
            _drawToggleButton();
        }

        /**
         * 显示或隐藏"字幕"按钮。
         * 当前语音包无字幕样式 JSON 时，Python 端调用此方法隐藏按钮。
         * @param visible  true=可见可用，false=不可见不可用
         */
        public function setSubtitleButtonVisible(visible:Boolean):void
        {
            if (_buttons.length < 3) return;
            var subtitleBtn:Sprite = _buttons[2] as Sprite;
            if (!subtitleBtn) return;
            subtitleBtn.visible = visible;
            subtitleBtn.mouseEnabled = visible;
            subtitleBtn.buttonMode = visible;
        }

        /** 设置标题文本框内容（切换语音后由 Python 端调用）。 */
        public function setInfoText(text:String):void
        {
            if (_infoTF)
            {
                _infoTF.text = text;
                // Scaleform 中 defaultTextFormat 不会自动应用到 set text；
                // 必须显式调用 setTextFormat 才能让字体/大小/颜色生效
                _infoTF.setTextFormat(_infoTF.defaultTextFormat);
            }
        }

        /**
         * i18n 刷新——labels 推送（切语言）后更新固定文本。
         * 由 MenuView._applyLabels 经 L10n 注册回调调用。
         */
        public function refreshTexts():void
        {
            // 3 个导航按钮
            var btnLabels:Array = [
                L10n.get("semi_panel/btn_detail", "详情"),
                L10n.get("semi_panel/btn_personal", "个性化"),
                L10n.get("semi_panel/btn_subtitle", "字幕"),
            ];
            for (var i:int = 0; i < _buttonTfs.length && i < btnLabels.length; i++)
            {
                var tf:TextField = _buttonTfs[i] as TextField;
                if (tf)
                    tf.text = btnLabels[i] as String;
            }
            // 按新文本重排导航按钮宽/位（英文长文本自适应）
            _layoutButtons();
            // 启用/禁用 toggle 文本（重绘重建标签，文字自适应宽）
            _drawToggleButton();
            // 标题文本框宽度随 toggle 右缘位置联动
            _layoutInfoText();
        }

        /**
         * 换肤刷新——由 Theme.apply() 触发。
         * 更新信息文字颜色、导航按钮背景/文字、收展按钮箭头颜色。
         * （toggle 启用按钮不受影响）
         */
        public function refreshColors():void
        {
            if (!_infoTF) return;

            // 信息文字颜色
            var infoFmt:TextFormat = _infoTF.defaultTextFormat;
            infoFmt.color = Theme.titleText;
            _infoTF.defaultTextFormat = infoFmt;
            _infoTF.textColor = Theme.titleText;
            _infoTF.setTextFormat(infoFmt);

            // 导航按钮背景 + 文字（宽度用 _layoutButtons 实测的自适应值，防换肤回退固定宽）
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var btn:Sprite = _buttons[i] as Sprite;
                if (!btn) continue;
                var btnH:Number = 25;
                var btnW:Number = (_buttonWidths && _buttonWidths.length > i)
                    ? Number(_buttonWidths[i]) : 66;
                if (i < _buttonBgs.length)
                {
                    var bg:Shape = _buttonBgs[i] as Shape;
                    if (bg) _drawButtonBg(bg, btnW, btnH);
                }
                if (i < _buttonTfs.length)
                {
                    var tf:TextField = _buttonTfs[i] as TextField;
                    if (tf)
                    {
                        tf.textColor = Theme.textPrimary;
                        tf.setTextFormat(tf.defaultTextFormat);
                    }
                }
            }

            // 收展按钮箭头重绘（用上次记录的方向）
            if (_circleBtn)  _drawTriangle(_circleBtn, _circleArrowDir);
            if (_panelBtn)   _drawTriangle(_panelBtn,  _panelArrowDir);
        }

        // ═══════════════════════════════════════════════════════
        // 创建 UI
        // ═══════════════════════════════════════════════════════

        private function _create():void
        {
            _createToggle();
            _createInfoText();
            _createButtons();
            _createControlButtons();
        }

        /** 启用按钮最小宽度——实际按文字实测自适应（i18n 英文更宽） */
        private static const TOGGLE_W:Number = 54;
        private static const TOGGLE_H:Number = 25;

        private function _createToggle():void
        {
            _toggleBtn = new Sprite();
            _toggleBtn.y = 15;                  // 上移 15（原 30）
            _drawToggleButton();                // x 由内部按自适应宽设定（右缘固定距面板 25px）
            _toggleBtn.addEventListener(MouseEvent.CLICK, _onToggleClick);
            _toggleBtn.buttonMode = true;
            addChild(_toggleBtn);
        }

        private function _createInfoText():void
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TitleFont";
            fmt.size = 26;
            fmt.color = Theme.titleText;  // 菜单大标题颜色，跟随主题
            fmt.align = "center";  // 居中对齐（自动换行后的每行同样居中）

            _infoTF = new TextField();
            _infoTF.defaultTextFormat = fmt;
            _infoTF.text = "";  // 初始为空，Python 端切换语音后填入显示名称
            _infoTF.selectable = false;
            _infoTF.mouseEnabled = false;
            _infoTF.x = 160;  // 距大圆右切线（面板局部 x=150）10px（左伸 10）
            _infoTF.y = 30;   // 上移 10（原 40）
            _infoTF.height = 100;
            _infoTF.wordWrap = true;
            addChild(_infoTF);
            // 右边缘到启用按钮的间距 10px（右伸 10），随启用按钮位置联动
            _layoutInfoText();
        }

        /** 标题文本框宽度 = 从 x 到 toggle 按钮左缘留 10px。切语言后 toggle 变宽时需联动。 */
        private function _layoutInfoText():void
        {
            if (_infoTF && _toggleBtn)
                _infoTF.width = _toggleBtn.x - 10 - _infoTF.x;
        }

        private function _createButtons():void
        {
            _buttons = [];
            _buttonBgs = [];
            _buttonTfs = [];
            // 标签走词典（i18n）；默认值与 l10n.py UI_LABELS 一致
            var labels:Array  = [
                L10n.get("semi_panel/btn_detail", "详情"),
                L10n.get("semi_panel/btn_personal", "个性化"),
                L10n.get("semi_panel/btn_subtitle", "字幕"),
            ];
            var pageIds:Array = ["voicePackDetail", "personalSettings", "subtitleSettings"];
            // 初始按钮宽度（_layoutButtons 会按文本实测自适应，此处只建组件）
            var btnW:Number = 66;
            var btnH:Number = 25;

            for (var i:int = 0; i < 3; i++)
            {
                var btn:Sprite = _buildButton(labels[i], btnW, btnH);
                btn.buttonMode = true;

                // 函数工厂——正确捕获循环索引
                var handler:Function = _makeButtonHandler(pageIds[i]);
                btn.addEventListener(MouseEvent.CLICK, handler);

                // "字幕"按钮默认隐藏——Python 端检测到字幕可用后主动显示。
                // 避免 DAAPI 调用失败时按钮永远可见，导致用户进入空页面。
                if (i == 2)
                {
                    btn.visible = false;
                    btn.mouseEnabled = false;
                    btn.buttonMode = false;
                }

                addChild(btn);
                _buttons.push(btn);
            }

            // 按文本实测统一量宽/定位（英文长标签自适应，字母不出界）
            _layoutButtons();
        }

        // ═══════════════════════════════════════════════════════
        // 按钮构建
        // ═══════════════════════════════════════════════════════

        /**
         * 按当前标签实测宽度重排 3 个导航按钮（i18n——英文长文本自适应）。
         * 每次切语言后调用：量出每个按钮文字宽，按钮宽 = max(66, 文字宽+留白)，
         * 重绘背景、重定位并记录宽度（换肤重绘用）。
         */
        private function _layoutButtons():void
        {
            var btnH:Number = 25;
            var startX:Number = 120;   // 整体左移 40（原 160）
            var gap:Number = 10;
            var btnY:Number = 225;      // 上移 5（原 230）

            _buttonWidths = [];
            var cx:Number = startX;
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var btn:Sprite = _buttons[i] as Sprite;
                var bg:Shape = _buttonBgs[i] as Shape;
                var tf:TextField = _buttonTfs[i] as TextField;

                var w:Number = 66;
                if (tf && tf.textWidth > 0)
                    w = Math.max(66, tf.textWidth + 8);  // 文字实测宽 + 左右各 4px 留白
                _buttonWidths.push(w);

                if (bg) _drawButtonBg(bg, w, btnH);
                if (btn)
                {
                    btn.x = cx;
                    btn.y = btnY;
                }
                if (tf)
                {
                    // 文本框比按钮更宽 + align=center：文字视觉居中，不被裁成左对齐
                    tf.width = w + 20;
                    tf.x = -10;
                }
                cx += w + gap;
            }
        }

        /** 绘制单个导航按钮背景（双层填充模拟描边）。供 _buildButton 和 refreshColors 复用。 */
        private function _drawButtonBg(bg:Shape, w:Number, h:Number):void
        {
            bg.graphics.clear();
            // 底层 = 描边色
            bg.graphics.beginFill(Theme.stroke);
            bg.graphics.drawRoundRect(0, 0, w, h, 8, 8);
            bg.graphics.endFill();
            // 上层 = 暗色渐变（surface2 → surface1），四周留出 1px 描边
            var m:Matrix = new Matrix();
            m.createGradientBox(w - 2, h - 2, Math.PI / 2, 1, 1);
            bg.graphics.beginGradientFill(GradientType.LINEAR,
                [Theme.surface2, Theme.surface1], [1, 1], [0, 255], m);
            bg.graphics.drawRoundRect(1, 1, w - 2, h - 2, 7, 7);
            bg.graphics.endFill();
        }

        private function _buildButton(label:String, w:Number, h:Number):Sprite
        {
            var btn:SoundableSprite = new SoundableSprite("normal");

            // Scaleform 对纯 stroke 路径的右边缘渲染不可靠——
            // 改用双层填充模拟描边：底层铺描边色，上层内缩 1px 铺渐变
            var bg:Shape = new Shape();
            _drawButtonBg(bg, w, h);
            btn.addChild(bg);

            // 文字
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 15;
            fmt.color = Theme.textPrimary;
            fmt.align = "center";

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.text = label;
            tf.selectable = false;
            tf.mouseEnabled = false;
            // 文本框比按钮更宽 + align=center：即使文字（如"个性化"）
            // 略超按钮宽度也保持视觉居中，不会被裁成左对齐
            tf.width = w + 20;
            tf.x = -10;
            tf.height = 22;
            tf.y = int((h - 22) / 2);
            btn.addChild(tf);

            // 存储引用供换肤时重绘
            _buttonBgs.push(bg);
            _buttonTfs.push(tf);

            return btn;
        }

        /** 函数工厂——AS3 var 无块级作用域，必须用函数参数捕获。 */
        private function _makeButtonHandler(pageId:String):Function
        {
            return function(event:MouseEvent):void
            {
                if (onButtonClick != null)
                    onButtonClick(pageId);
            };
        }

        // ═══════════════════════════════════════════════════════
        // 控制按钮（右下角正方形 ×2）
        // ═══════════════════════════════════════════════════════

        private static const SQUARE_SIZE:int = 20;   // 与功能按钮同高
        private static const SQUARE_GAP:int = 0;     // 两按钮无间距
        private static const SQUARE_MARGIN_RIGHT:int = 30;  // 距面板右缘
        private static const SQUARE_Y:int = 230;             // 与功能按钮同 Y

        private function _createControlButtons():void
        {
            // 右按钮：控制下方面板收展（透明背景，只显示箭头图案）
            _panelBtn = _buildSquareButton(true);
            _panelBtn.x = _w - SQUARE_MARGIN_RIGHT - SQUARE_SIZE;
            _panelBtn.y = SQUARE_Y;
            _panelBtn.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void {
                if (onPanelToggle != null) onPanelToggle();
            });
            addChild(_panelBtn);

            // 左按钮：控制小圆显隐（紧贴右按钮左侧，同样透明只显示箭头）
            _circleBtn = _buildSquareButton(true);
            _circleBtn.x = _panelBtn.x - SQUARE_SIZE - SQUARE_GAP;
            _circleBtn.y = SQUARE_Y;
            _circleBtn.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void {
                if (onCircleToggle != null) onCircleToggle();
            });
            addChild(_circleBtn);

            // 初始三角箭头（后续 setCircleArrow/setPanelArrow 复用同一个 Shape）
            _drawTriangle(_circleBtn, "left");   // 默认小圆可见 → 朝左
            _drawTriangle(_panelBtn,  "up");     // 初始面板未伸出 → 朝上
        }

        /** 创建正方形按钮（暗色渐变 + 1px 描边 + 三角形箭头）。
         *  @param transparent true 时不绘制背景和描边，只保留透明点击区域 */
        private function _buildSquareButton(transparent:Boolean = false):Sprite
        {
            var btn:SoundableSprite = new SoundableSprite("normal");
            btn.buttonMode = true;

            var bg:Shape = new Shape();
            if (transparent)
            {
                // 透明背景——alpha=0 填充保留点击热区，无填充色和描边
                bg.graphics.beginFill(0x000000, 0);
                bg.graphics.drawRect(0, 0, SQUARE_SIZE, SQUARE_SIZE);
                bg.graphics.endFill();
            }
            else
            {
                var m:Matrix = new Matrix();
                m.createGradientBox(SQUARE_SIZE, SQUARE_SIZE, Math.PI / 2);
                bg.graphics.beginGradientFill(GradientType.LINEAR,
                    [0x3C3C3C, 0x333333], [1, 1], [0, 255], m);
                bg.graphics.drawRoundRect(0, 0, SQUARE_SIZE, SQUARE_SIZE, 0, 0);
                bg.graphics.endFill();
                // 描边内缩 0.5px，避免右/下边缘的线被裁掉
                bg.graphics.lineStyle(1, 0x555555);
                bg.graphics.drawRoundRect(0.5, 0.5,
                    SQUARE_SIZE - 1, SQUARE_SIZE - 1, 0, 0);
            }
            btn.addChild(bg);

            return btn;
        }

        /** 在小正方形内绘制三角箭头。left=true → 朝左，否则朝右。 */
        private function _drawTriangle(btn:Sprite, direction:String):void
        {
            // 获取或创建持久三角 Shape（index 1；index 0 是背景）
            var arrow:Shape;
            if (btn.numChildren > 1)
                arrow = btn.getChildAt(1) as Shape;
            else
            {
                arrow = new Shape();
                btn.addChild(arrow);
            }

            arrow.graphics.clear();
            var cx:Number = SQUARE_SIZE / 2;
            var cy:Number = SQUARE_SIZE / 2;
            var r:Number = 7;  // 三角形外接圆半径

            arrow.graphics.beginFill(Theme.sbBtnArrow, 1.0);

            if (direction == "left")
            {
                // ◀
                arrow.graphics.moveTo(cx - r + 2, cy);
                arrow.graphics.lineTo(cx + r - 1, cy - r);
                arrow.graphics.lineTo(cx + r - 1, cy + r);
            }
            else if (direction == "right")
            {
                // ▶
                arrow.graphics.moveTo(cx + r - 2, cy);
                arrow.graphics.lineTo(cx - r + 1, cy - r);
                arrow.graphics.lineTo(cx - r + 1, cy + r);
            }
            else if (direction == "down")
            {
                // ▼
                arrow.graphics.moveTo(cx, cy + r - 2);
                arrow.graphics.lineTo(cx - r, cy - r + 1);
                arrow.graphics.lineTo(cx + r, cy - r + 1);
            }
            else if (direction == "up")
            {
                // ▲
                arrow.graphics.moveTo(cx, cy - r + 2);
                arrow.graphics.lineTo(cx - r, cy + r - 1);
                arrow.graphics.lineTo(cx + r, cy + r - 1);
            }

            arrow.graphics.endFill();
        }

        /** 设置小圆控制按钮箭头方向。
         *  @param left true=朝左（小圆可见，点击将隐藏）; false=朝右（已隐藏） */
        public function setCircleArrow(left:Boolean):void
        {
            if (!_circleBtn) return;
            _circleArrowDir = left ? "left" : "right";
            _drawTriangle(_circleBtn, _circleArrowDir);
        }

        /** 设置面板收展按钮箭头方向。
         *  @param down true=朝下（面板已伸出）; false=朝上（面板已收起） */
        public function setPanelArrow(down:Boolean):void
        {
            if (!_panelBtn) return;
            _panelArrowDir = down ? "down" : "up";
            _drawTriangle(_panelBtn, _panelArrowDir);
        }

        // ═══════════════════════════════════════════════════════
        // Toggle 按钮
        // ═══════════════════════════════════════════════════════

        private function _onToggleClick(event:MouseEvent):void
        {
            _toggleEnabled = !_toggleEnabled;
            _drawToggleButton();

            if (onToggle != null)
                onToggle(_toggleEnabled);
        }

        private function _drawToggleButton():void
        {
            _toggleBtn.graphics.clear();

            var h:Number = TOGGLE_H;
            var color:uint = _toggleEnabled ? 0x44BB44 : 0xDD4444;

            if (_toggleBtnLabel && _toggleBtn.contains(_toggleBtnLabel))
                _toggleBtn.removeChild(_toggleBtnLabel);

            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = 0xFFFFFF;
            fmt.align = "center";
            fmt.bold = true;

            _toggleBtnLabel = new TextField();
            _toggleBtnLabel.defaultTextFormat = fmt;
            // 文本走词典（i18n）；默认值与 l10n.py UI_LABELS 一致
            _toggleBtnLabel.text = _toggleEnabled
                ? L10n.get("semi_panel/toggle_on", "启用中")
                : L10n.get("semi_panel/toggle_off", "禁用中");
            _toggleBtnLabel.selectable = false;
            _toggleBtnLabel.mouseEnabled = false;
            _toggleBtnLabel.height = 20;
            _toggleBtnLabel.y = int((h - 20) / 2);

            // 按文字实测宽自适应（i18n 英文 "Enabled/Disabled" 超固定宽），
            // 右缘固定距面板右缘 25px——x 随宽度联动
            var w:Number = Math.max(TOGGLE_W, _toggleBtnLabel.textWidth + 12);
            _toggleBtnLabel.width = w;
            _toggleBtnLabel.x = 0;
            _toggleBtn.x = _w - 25 - w;

            _toggleBtn.graphics.beginFill(color);
            _toggleBtn.graphics.drawRoundRect(0, 0, w, h, 6, 6);
            _toggleBtn.graphics.endFill();

            _toggleBtn.addChild(_toggleBtnLabel);
        }
    }
}