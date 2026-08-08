package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Bitmap;
    import flash.display.BitmapData;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    import com.github._25304_Oxygen.shared.ui.ImageCache;

    /**
     * 圆角按钮——支持文字标签或图片图标，Dark+ 配色。
     *
     * 状态: normal → hover → pressed
     * 颜色可通过 setColors() 自定义。
     *
     * 用法:
     *   var btn:BaseButton = new BaseButton(140, 36, "确定");
     *   btn.onClick = function():void { trace("clicked"); };
     *   addChild(btn);
     *
     *   // 图片按钮
     *   var btn2:BaseButton = new BaseButton(48, 48, "");
     *   btn2.setIcon("../mods/acv/icons/save.png");
     */
    public class BaseButton extends Sprite implements ISoundable
    {
        // ═══════════════════════════════════════════════════════
        // 默认颜色 (Dark+ 钢蓝风格，参考 testWindow)
        // ═══════════════════════════════════════════════════════

        private static const CORNER_RADIUS:Number = 8;

        // ═══════════════════════════════════════════════════════
        // 属性
        // ═══════════════════════════════════════════════════════

        private var _w:Number;
        private var _h:Number;
        private var _cornerRadius:Number;

        private var _labelText:String;
        private var _iconPath:String;

        private var _enabled:Boolean = true;
        private var _hovered:Boolean = false;
        private var _pressed:Boolean = false;

        // 颜色（由 _init() 从 Theme 初始化，_refreshStyle() 刷新）
        private var _fillNormal:uint;
        private var _fillHover:uint;
        private var _fillPressed:uint;
        private var _fillDisabled:uint;
        private var _strokeColor:uint;
        private var _strokeWidth:Number = 1.5;
        private var _textColor:uint;

        // 子对象
        private var _bg:Shape;
        private var _labelTF:TextField;
        private var _iconContainer:Sprite;  // 包裹 Bitmap

        /** 点击回调: function():void */
        public var onClick:Function;

        // ── 音效 ──
        private var _soundType:String = "normal";

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param w           按钮宽度
         * @param h           按钮高度
         * @param label       按钮文字（传空字符串表示纯图片按钮）
         * @param radius      圆角半径（不传使用默认 8，传 0 = 直角）
         * @param strokeWidth 描边宽度（不传使用默认 1.5，传 0 = 无描边）
         */
        public function BaseButton(w:Number, h:Number, label:String = "",
                                    radius:Number = -1, strokeWidth:Number = -1)
        {
            super();
            _w = w;
            _h = h;
            _labelText = label;
            _cornerRadius = radius >= 0 ? radius : CORNER_RADIUS;
            _strokeWidth = strokeWidth >= 0 ? strokeWidth : _strokeWidth;
            _iconPath = "";

            _init();
        }

        private function _init():void
        {
            this.buttonMode = true;
            this.mouseChildren = false;

            // 背景
            _bg = new Shape();
            addChild(_bg);

            // 文字标签
            if (_labelText.length > 0)
            {
                _labelTF = _createTextField();
                addChild(_labelTF);
            }

            // 图片容器（默认隐藏）
            _iconContainer = new Sprite();
            _iconContainer.visible = false;
            _iconContainer.mouseEnabled = false;
            _iconContainer.mouseChildren = false;
            addChild(_iconContainer);

            // 从 Theme 初始化颜色
            _fillNormal = Theme.accent;
            _fillHover = Theme.accentHover;
            _fillPressed = Theme.accentPress;
            _fillDisabled = Theme.surface1;
            _strokeColor = Theme.stroke;
            _textColor = Theme.textPrimary;

            _drawBackground(Theme.accent);

            Theme.register(this, _refreshStyle);

            addEventListener(MouseEvent.MOUSE_OVER,  _onMouseOver);
            addEventListener(MouseEvent.MOUSE_OUT,   _onMouseOut);
            addEventListener(MouseEvent.MOUSE_DOWN,  _onMouseDown);
            addEventListener(MouseEvent.CLICK,       _onClick);

            // 游戏 UI 音效
            SoundUtils.registerSound(this);
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 设置文字标签。传空字符串隐藏文字。 */
        public function setLabel(text:String):void
        {
            _labelText = text;
            if (!_labelTF && text.length > 0)
            {
                _labelTF = _createTextField();
                addChild(_labelTF);
            }
            if (_labelTF)
            {
                _labelTF.text = text;
                _labelTF.visible = text.length > 0;
            }
        }

        /** 设置图标（通过 ImageCache 加载）。传空字符串隐藏图标。 */
        public function setIcon(path:String):void
        {
            _iconPath = path;
            if (path.length == 0)
            {
                _iconContainer.visible = false;
                while (_iconContainer.numChildren > 0)
                    _iconContainer.removeChildAt(0);
                return;
            }

            _iconContainer.visible = true;
            var bmd:BitmapData = ImageCache.getCached(path);
            if (bmd)
            {
                _setIconBitmap(bmd);
            }
            else
            {
                // 异步加载
                ImageCache.load(path, function(loadedBmd:BitmapData, success:Boolean):void
                {
                    if (success && loadedBmd)
                        _setIconBitmap(loadedBmd);
                });
            }
        }

        /** 自定义按钮颜色。 */
        public function setColors(fillNormal:uint, fillHover:uint = 0,
                                   fillPressed:uint = 0, strokeColor:uint = 0,
                                   textColor:uint = 0):void
        {
            _fillNormal  = fillNormal;
            _fillHover   = fillHover  > 0 ? fillHover  : _fillHover;
            _fillPressed = fillPressed > 0 ? fillPressed : _fillPressed;
            _strokeColor = strokeColor > 0 ? strokeColor : _strokeColor;
            if (textColor > 0)
            {
                _textColor = textColor;
                if (_labelTF) _labelTF.textColor = _textColor;
            }
            _drawBackground(_currentFillColor());
        }

        /** 启用/禁用。 */
        public function setEnabled(value:Boolean):void
        {
            _enabled = value;
            this.mouseEnabled = value;
            this.buttonMode = value;
            if (!value)
            {
                _hovered = false;
                _pressed = false;
            }
            _drawBackground(_currentFillColor());
            if (_labelTF)
                _labelTF.textColor = value ? _textColor : Theme.textSecondary;
        }

        public function get enabled():Boolean { return _enabled; }

        /** 销毁。 */
        public function dispose():void
        {
            SoundUtils.removeSound(this);
            Theme.unregister(this);
            removeEventListener(MouseEvent.MOUSE_OVER, _onMouseOver);
            removeEventListener(MouseEvent.MOUSE_OUT,  _onMouseOut);
            removeEventListener(MouseEvent.MOUSE_DOWN, _onMouseDown);
            removeEventListener(MouseEvent.CLICK,      _onClick);
            onClick = null;
        }

        // ═══════════════════════════════════════════════════════
        // ISoundable —— 游戏 UI 音效
        // ═══════════════════════════════════════════════════════

        /** 设置声音类型（"normal"/"tab"/"checkBox"/"radioButton"/...）。 */
        public function setSoundType(value:String):void { _soundType = value; }

        public function canPlaySound(type:String):Boolean { return _enabled && !SoundUtils.muted; }

        public function getSoundType():String { return _soundType; }

        public function getSoundId():String { return ""; }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        private function _createTextField():TextField
        {
            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = _textColor;
            fmt.align = "center";

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.text = _labelText;
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.width = _w;
            tf.height = 22;
            tf.y = int((_h - 22) / 2);
            return tf;
        }

        private function _setIconBitmap(bmd:BitmapData):void
        {
            while (_iconContainer.numChildren > 0)
                _iconContainer.removeChildAt(0);

            var bmp:Bitmap = new Bitmap(bmd);
            bmp.smoothing = true;

            // 缩放到按钮内部区域（留 6px 内边距）
            var maxDim:Number = Math.min(_w, _h) - 12;
            var scale:Number = Math.min(maxDim / bmd.width, maxDim / bmd.height, 1.0);
            bmp.width  = int(bmd.width * scale);
            bmp.height = int(bmd.height * scale);
            bmp.x = int((_w - bmp.width) / 2);
            bmp.y = int((_h - bmp.height) / 2);

            _iconContainer.addChild(bmp);
            _iconContainer.visible = true;
        }

        private function _currentFillColor():uint
        {
            if (!_enabled)   return _fillDisabled;
            if (_pressed)    return _fillPressed;
            if (_hovered)    return _fillHover;
            return _fillNormal;
        }

        private function _refreshStyle():void
        {
            _fillNormal = Theme.accent;
            _fillHover = Theme.accentHover;
            _fillPressed = Theme.accentPress;
            _fillDisabled = Theme.surface1;
            _strokeColor = Theme.stroke;
            _textColor = Theme.textPrimary;
            _drawBackground(_currentFillColor());
            if (_labelTF) _labelTF.textColor = _enabled ? _textColor : Theme.textSecondary;
        }

        private function _drawBackground(fillColor:uint):void
        {
            _bg.graphics.clear();
            if (_strokeWidth > 0)
                _bg.graphics.lineStyle(_strokeWidth, _strokeColor);
            _bg.graphics.beginFill(fillColor, 1.0);
            _bg.graphics.drawRoundRect(0, 0, _w, _h,
                _cornerRadius * 2, _cornerRadius * 2);
            _bg.graphics.endFill();
        }

        // ═══════════════════════════════════════════════════════
        // 事件
        // ═══════════════════════════════════════════════════════

        private function _onMouseOver(event:MouseEvent):void
        {
            if (!_enabled) return;
            _hovered = true;
            _drawBackground(_fillHover);
        }

        private function _onMouseOut(event:MouseEvent):void
        {
            if (!_enabled) return;
            _hovered = false;
            _pressed = false;
            _drawBackground(_fillNormal);
        }

        private function _onMouseDown(event:MouseEvent):void
        {
            if (!_enabled) return;
            _pressed = true;
            _drawBackground(_fillPressed);
            // 在 stage 上监听 mouseUp 以确保即使鼠标移到按钮外也能恢复
            if (stage)
                stage.addEventListener(MouseEvent.MOUSE_UP, _onStageMouseUp);
        }

        private function _onStageMouseUp(event:MouseEvent):void
        {
            if (stage)
                stage.removeEventListener(MouseEvent.MOUSE_UP, _onStageMouseUp);
            _pressed = false;
            _drawBackground(_hovered ? _fillHover : _fillNormal);
        }

        private function _onClick(event:MouseEvent):void
        {
            if (!_enabled) return;
            if (onClick != null)
                onClick();
        }
    }
}
