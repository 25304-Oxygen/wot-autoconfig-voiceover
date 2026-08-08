package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;

    /**
     * 分组框——带标题的描边容器，将相关控件视觉分组。
     *
     * 标签嵌在边框左上角（fieldset 风格），内容通过 content 属性添加。
     *
     * 用法:
     *   var gb:GroupBox = new GroupBox(600, 150, "按钮设置");
     *   gb.content.addChild(someButton);
     *   gb.content.addChild(someDropdown);
     *   addChild(gb);
     *
     *   // 无标题分组框（纯矩形边框）
     *   var gb2:GroupBox = new GroupBox(400, 200);
     */
    public class GroupBox extends Sprite
    {
        // ═══════════════════════════════════════════════════════
        // 外观常量
        // ═══════════════════════════════════════════════════════

        /** 默认圆角半径（小圆角，区别于按钮的 8px）。 */
        private static const DEFAULT_RADIUS:Number = 4;

        /** 标签文字与左边框的距离。 */
        private static const LABEL_INDENT:Number = 14;

        /** 标签文字两侧的留白（用于遮盖边框线）。 */
        private static const LABEL_PAD_X:Number = 6;

        /** 标签纵向中点 = 上边框线的 Y 坐标。 */
        private static const LABEL_MID_Y:Number = 8;

        /** 标签背景遮盖矩形的最大高度（labelMidY * 2 + 余量）。 */
        private static const LABEL_BG_H:Number = 18;

        /** 内容区内边距：上（从边框线往下）、左右、下。 */
        public static const PAD_TOP_DRAW:Number = 22;
        private static const PAD_SIDE:Number = 14;
        private static const PAD_BOTTOM:Number = 14;

        // ═══════════════════════════════════════════════════════
        // 属性
        // ═══════════════════════════════════════════════════════

        private var _w:Number;
        private var _h:Number;
        private var _title:String;
        private var _cornerRadius:Number;
        private var _labelBgColor:uint;
        private var _labelBgVisible:Boolean = false;  // 透明背景（fieldset 缺口风格）

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        /** 边框 Shape。 */
        private var _border:Shape;

        /** 标签后面的背景色块（遮盖边框线）。 */
        private var _labelBg:Shape;

        /** 标签文字。 */
        private var _labelTF:TextField;

        /** 内容容器——用户把子组件 addChild 到这里。 */
        public var content:Sprite;

        /** 标签区域点击区（透明）——用于绑定 Tooltip，只覆盖标题不冒泡到子组件。 */
        public var titleHitArea:Sprite;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param w            分组框宽度
         * @param h            分组框高度
         * @param title        标签文字（空字符串 = 无标签的纯矩形框）
         * @param cornerRadius 圆角半径（-1 使用默认 4，传 0 = 直角）
         */
        public function GroupBox(w:Number, h:Number, title:String = "",
                                 cornerRadius:Number = -1)
        {
            super();
            _w = w;
            _h = h;
            _title = title;
            _cornerRadius = cornerRadius >= 0 ? cornerRadius : DEFAULT_RADIUS;
            _labelBgColor = Theme.surface0;

            _init();
        }

        private function _init():void
        {
            this.mouseEnabled = false;  // 让鼠标事件穿透到子组件

            // 边框（最底层）
            _border = new Shape();
            addChild(_border);

            // 标签背景遮盖（边框之上）
            _labelBg = new Shape();
            addChild(_labelBg);

            // 标签文字（最上层）
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 13;
            fmt.color = Theme.textPrimary;
            fmt.bold = true;

            _labelTF = new TextField();
            _labelTF.defaultTextFormat = fmt;
            _labelTF.text = _title;
            _labelTF.selectable = false;
            _labelTF.mouseEnabled = false;
            _labelTF.autoSize = "left";
            _labelTF.visible = _title.length > 0;
            addChild(_labelTF);

            // 标签区域透明点击区——覆盖标题文字区域，用于 Tooltip 绑定。
            // 放在 label 之上、content 之下，Tooltip attach 到此处不会被子组件冒泡触发。
            // 初始禁用手型——Tooltip.attach() 会启用。
            titleHitArea = new Sprite();
            titleHitArea.mouseChildren = false;
            titleHitArea.buttonMode = false;
            titleHitArea.useHandCursor = false;
            addChild(titleHitArea);

            // 内容容器
            content = new Sprite();
            content.mouseEnabled = false;
            addChild(content);

            _draw();
            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 修改标签文字。传空字符串隐藏标签和遮盖。 */
        public function setTitle(text:String):void
        {
            _title = text;
            _labelTF.text = text;
            _labelTF.visible = text.length > 0;
            _draw();
        }

        /**
         * 运行时调整尺寸（i18n max 排版用——GroupBox 高度按内容实测后重算）。
         * 重绘边框，内容坐标不变。
         */
        public function setSize(w:Number, h:Number):void
        {
            _w = w;
            _h = h;
            _draw();
        }

        /** 获取当前标签文字。 */
        public function get title():String
        {
            return _title;
        }

        /**
         * 设置标签背景色——用于匹配父容器背景。
         * 默认值: Theme.surface0（ScrollPane 内容区背景色）。
         * 如果在浅色面板上使用，改为 Theme.surface1。
         */
        public function setLabelBgColor(color:uint):void
        {
            _labelBgColor = color;
            _draw();
        }

        /**
         * 控制标签背景色块是否可见。
         * 设为 false 时标签后面不再绘制遮盖色块（边框线会透过文字）。
         * 默认 true。状态持久化——主题刷新重绘后仍保持。
         */
        public function set labelBgVisible(value:Boolean):void
        {
            _labelBgVisible = value;
            _draw();
        }

        /** 销毁。 */
        public function dispose():void
        {
            Theme.unregister(this);
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        /** 主题换肤回调。 */
        private function _refreshStyle():void
        {
            _labelTF.textColor = Theme.textPrimary;
            _draw();
        }

        /**
         * 重绘边框和标签遮盖。
         *
         * 有标题时：上边框线位于 LABEL_MID_Y，标签纵向上居中于该线，
         *           标签后面用与父容器同色的矩形遮盖掉边框线。
         * 无标题时：绘制完整的矩形边框。
         */
        private function _draw():void
        {
            var hasLabel:Boolean = _title.length > 0;
            var borderTopY:Number = hasLabel ? LABEL_MID_Y : 0;
            var cr:Number = Math.max(0, _cornerRadius);

            // ── 边框 ──
            _border.graphics.clear();
            _border.graphics.lineStyle(1, Theme.stroke);

            if (hasLabel && !_labelBgVisible)
            {
                // 无遮盖模式：顶边在标签区域留缺口（fieldset 风格），
                // 手绘圆角矩形路径，避免边框线横穿标题文字。
                var gapL:Number = LABEL_INDENT - 2;
                var gapR:Number = LABEL_INDENT + _labelTF.width
                    + LABEL_PAD_X * 2 + 2;

                _border.graphics.moveTo(gapR, borderTopY);
                _border.graphics.lineTo(_w - cr, borderTopY);
                _border.graphics.curveTo(_w, borderTopY, _w, borderTopY + cr);
                _border.graphics.lineTo(_w, _h - cr);
                _border.graphics.curveTo(_w, _h, _w - cr, _h);
                _border.graphics.lineTo(cr, _h);
                _border.graphics.curveTo(0, _h, 0, _h - cr);
                _border.graphics.lineTo(0, borderTopY + cr);
                _border.graphics.curveTo(0, borderTopY, cr, borderTopY);
                _border.graphics.lineTo(gapL, borderTopY);
            }
            else
            {
                _border.graphics.drawRoundRect(0, borderTopY, _w,
                    _h - borderTopY, _cornerRadius * 2, _cornerRadius * 2);

                // Scaleform 的 drawRoundRect 偶发不闭合右侧边，手动补一笔竖线
                _border.graphics.moveTo(_w, borderTopY + cr);
                _border.graphics.lineTo(_w, _h - cr);
            }

            // ── 标签遮盖 & 文字定位 ──
            if (hasLabel)
            {
                // 文字：左边缩进 + 留白，纵向上居中于边框线
                _labelTF.x = LABEL_INDENT + LABEL_PAD_X;
                _labelTF.y = int(LABEL_MID_Y - _labelTF.height / 2);

                // 遮盖矩形：覆盖标签区域的边框线段
                _labelBg.graphics.clear();
                _labelBg.graphics.beginFill(_labelBgColor);
                _labelBg.graphics.drawRect(LABEL_INDENT, 0,
                    _labelTF.width + LABEL_PAD_X * 2, LABEL_BG_H);
                _labelBg.graphics.endFill();
                _labelBg.visible = _labelBgVisible;

                // 透明点击区——覆盖标签区域，用于 Tooltip 绑定
                titleHitArea.x = LABEL_INDENT;
                titleHitArea.y = 0;
                titleHitArea.graphics.clear();
                titleHitArea.graphics.beginFill(0x000000, 0);  // 完全透明
                titleHitArea.graphics.drawRect(0, 0,
                    _labelTF.width + LABEL_PAD_X * 2, LABEL_BG_H);
                titleHitArea.graphics.endFill();
                titleHitArea.visible = true;

                // 内容从边框线下方向下偏移
                content.x = PAD_SIDE;
                content.y = LABEL_MID_Y + PAD_TOP_DRAW;
            }
            else
            {
                _labelBg.visible = false;
                titleHitArea.visible = false;
                content.x = PAD_SIDE;
                content.y = PAD_TOP_DRAW;
            }
        }
    }
}
