package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.DisplayObject;
    import flash.display.Shape;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.events.MouseEvent;
    import flash.events.Event;
    import flash.geom.Point;
    import flash.geom.Rectangle;

    import net.wg.infrastructure.interfaces.entity.ISoundable;

    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 下拉列表——卡通风格，Dark+ 配色。
     *
     * 弹出列表挂载到 stage 层，避免被父容器 scrollRect 裁剪。
     * 点击外部自动关闭。超过 MAX_VISIBLE 条时自动出现滚动条，支持鼠标滚轮。
     *
     * 用法:
     *   var dd:Dropdown = new Dropdown(220, ["选项1", "选项2", "选项3"]);
     *   dd.onSelect = function(index:int, label:String):void { ... };
     *   addChild(dd);
     *
     * 选项支持两种格式（setItems / 构造器通用）:
     *   字符串数组  ["a", "b"]                —— value 与 label 相同（旧用法）
     *   对象数组    [{value:"x", label:"a"}, ...] —— 显示 label，value 供
     *               onAction 回传与 setSelectedValue 恢复（存储 token 化）
     */
    public class Dropdown extends Sprite implements ISoundable
    {
        private static const L:Object = Log.getLogger("Dropdown");

        // ═══════════════════════════════════════════════════════
        // 尺寸 & 颜色
        // ═══════════════════════════════════════════════════════

        private static const TRIGGER_H:int = 32;
        private static const CORNER_RADIUS:int = 0;   // 直角边框
        private static const ARROW_SIZE:int = 8;

        private static const STROKE_W:Number  = 1;

        // 列表项
        private static const ITEM_H:uint = 30;
        private static const ITEM_TEXT_H:uint = 20;   // 中文字形需要更多垂直空间
        private static const ITEM_GAP:uint = 2;
        private static const MAX_VISIBLE:int = 8;

        // 滚动条
        private static const SCROLLBAR_W:int = 6;
        private static const SCROLLBAR_MARGIN:int = 4;
        private static const SCROLL_THUMB_MIN_H:int = 20;

        // ═══════════════════════════════════════════════════════

        private var _w:Number;
        private var _items:Array;      // 显示文本数组（label）
        private var _values:Array;     // 存储 value 数组（对象选项模式；字符串选项为 null）
        private var _selectedIndex:int = -1;
        private var _isOpen:Boolean = false;

        // 触发器
        private var _triggerBg:Shape;
        private var _triggerLabel:TextField;
        private var _arrowShape:Shape;

        // 弹出层
        private var _overlay:Sprite;
        private var _overlayBg:Shape;
        private var _itemContainer:Sprite;   // 包含全部 item，由 scrollRect 裁剪
        private var _scrollTrack:Shape;
        private var _scrollThumb:Sprite;

        // 滚动状态
        private var _scrollPos:Number = 0;         // 当前滚动偏移
        private var _maxScroll:Number = 0;          // 最大滚动值
        private var _needsScroll:Boolean = false;   // 是否需要滚动条
        private var _scrollDragging:Boolean = false;
        private var _scrollDragStartY:Number = 0;
        private var _scrollDragStartPos:Number = 0;

        private var _enabled:Boolean = true;

        /** 选中回调: function(index:int, label:String):void */
        public var onSelect:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        /**
         * @param w      下拉框宽度
         * @param items  选项：字符串数组或 [{value,label}] 对象数组
         */
        public function Dropdown(w:Number, items:Array)
        {
            super();
            _w = w;
            _applyItems(items);
            _buildTrigger();

            // 游戏 UI 音效（trigger 点击音）
            SoundUtils.registerSound(this);

            Theme.register(this, _refreshStyle);
        }

        private function _buildTrigger():void
        {
            this.buttonMode = true;

            _triggerBg = new Shape();
            addChild(_triggerBg);

            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = Theme.textPrimary;

            _triggerLabel = new TextField();
            _triggerLabel.defaultTextFormat = fmt;
            _triggerLabel.text = _items.length > 0 ? _items[0] : "";
            _triggerLabel.selectable = false;
            _triggerLabel.mouseEnabled = false;
            _triggerLabel.x = 10;
            _triggerLabel.y = int((TRIGGER_H - 16) / 2);
            _triggerLabel.width = _w - 30;
            _triggerLabel.height = 18;
            addChild(_triggerLabel);

            _arrowShape = new Shape();
            addChild(_arrowShape);

            _drawTrigger(Theme.surface1);

            addEventListener(MouseEvent.CLICK, _onTriggerClick);
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        public function get selectedIndex():int { return _selectedIndex; }

        public function get selectedLabel():String
        {
            if (_selectedIndex < 0 || _selectedIndex >= _items.length)
                return "";
            return _items[_selectedIndex];
        }

        /** 当前选中项的存储 value。字符串选项模式下 value 即 label。 */
        public function get selectedValue():String
        {
            if (_values)
            {
                if (_selectedIndex < 0 || _selectedIndex >= _values.length)
                    return "";
                return _values[_selectedIndex];
            }
            return selectedLabel;
        }

        /** 根据 label 查找索引，找不到返回 -1。 */
        public function getItemIndex(label:String):int
        {
            for (var i:int = 0; i < _items.length; i++)
            {
                if (_items[i] == label) return i;
            }
            return -1;
        }

        /** 根据 value 查找索引，找不到返回 -1（字符串选项模式下无意义）。 */
        public function getItemIndexByValue(value:String):int
        {
            if (!_values) return -1;
            for (var i:int = 0; i < _values.length; i++)
            {
                if (_values[i] == value) return i;
            }
            return -1;
        }

        /** 程序化设置选中项（按索引）。 */
        public function setSelectedIndex(index:int, dispatch:Boolean = false):void
        {
            if (index < 0 || index >= _items.length) return;
            _selectedIndex = index;
            _triggerLabel.text = _items[index];

            if (dispatch && onSelect != null)
                onSelect(index, _items[index]);
        }

        /** 程序化设置选中项（按存储 value）。找不到时保持当前选择，返回 false。 */
        public function setSelectedValue(value:String, dispatch:Boolean = false):Boolean
        {
            var idx:int = getItemIndexByValue(value);
            if (idx < 0) return false;
            setSelectedIndex(idx, dispatch);
            return true;
        }

        /** 更新选项列表（字符串数组或 [{value,label}] 对象数组）。 */
        public function setItems(items:Array):void
        {
            _applyItems(items);
            _selectedIndex = -1;
            _triggerLabel.text = _items.length > 0 ? _items[0] : "";
            if (_isOpen) _closeList();
        }

        /**
         * 拆分选项为内部 label/value 数组：
         *   字符串数组 → value 与 label 相同（_values = null）；
         *   对象数组   → _items 存 label，_values 存 value。
         */
        private function _applyItems(items:Array):void
        {
            _values = null;
            if (items && items.length > 0 && typeof(items[0]) == "object")
            {
                _items = [];
                _values = [];
                for each (var obj:Object in items)
                {
                    _items.push(obj.label);
                    _values.push(obj.value);
                }
            }
            else
            {
                _items = items ? items.concat() : [];
            }
        }

        public function setEnabled(value:Boolean):void
        {
            _enabled = value;
            this.mouseEnabled = value;
            this.buttonMode = value;
            this.alpha = value ? 1.0 : 0.5;
            if (!value && _isOpen) _closeList();
        }

        /** 收起弹出列表（若已展开）——容器被隐藏前调用，
         *  避免挂在 stage 上的 overlay 残留在屏幕上。 */
        public function close():void
        {
            if (_isOpen) _closeList();
        }

        /** 销毁。 */
        public function dispose():void
        {
            SoundUtils.removeSound(this);
            if (_isOpen) _closeList();
            removeEventListener(MouseEvent.CLICK, _onTriggerClick);
            Theme.unregister(this);
            onSelect = null;
        }

        // ═══════════════════════════════════════════════════════
        // ISoundable
        // ═══════════════════════════════════════════════════════

        public function canPlaySound(type:String):Boolean { return _enabled && !SoundUtils.muted; }

        public function getSoundType():String { return "normal"; }

        public function getSoundId():String { return ""; }

        // ═══════════════════════════════════════════════════════
        // 触发按钮绘制
        // ═══════════════════════════════════════════════════════

        private function _refreshStyle():void
        {
            _drawTrigger(_isOpen ? Theme.surface0 : Theme.surface1);
            if (_triggerLabel)
            {
                var fmt:TextFormat = _triggerLabel.defaultTextFormat;
                fmt.color = Theme.textPrimary;
                _triggerLabel.defaultTextFormat = fmt;
                _triggerLabel.textColor = Theme.textPrimary;
                _triggerLabel.setTextFormat(fmt);
            }
            // Note: items are rebuilt when opening, so no need to refresh closed overlay
        }

        private function _drawTrigger(fillColor:uint):void
        {
            _triggerBg.graphics.clear();
            _triggerBg.graphics.lineStyle(STROKE_W, Theme.stroke);
            _triggerBg.graphics.beginFill(fillColor, 1.0);
            _triggerBg.graphics.drawRoundRect(0, 0, _w, TRIGGER_H,
                CORNER_RADIUS * 2, CORNER_RADIUS * 2);
            _triggerBg.graphics.endFill();

            _arrowShape.graphics.clear();
            _arrowShape.graphics.beginFill(Theme.textPrimary);
            var ax:Number = _w - 18;
            var ay:Number = int((TRIGGER_H - ARROW_SIZE) / 2);
            if (_isOpen)
            {
                // ▲ 展开态——箭头朝上，表示"点击收起"
                _arrowShape.graphics.moveTo(ax + ARROW_SIZE / 2, ay);
                _arrowShape.graphics.lineTo(ax, ay + ARROW_SIZE - 1);
                _arrowShape.graphics.lineTo(ax + ARROW_SIZE, ay + ARROW_SIZE - 1);
            }
            else
            {
                // ▼ 折叠态——箭头朝下，表示"点击展开"
                _arrowShape.graphics.moveTo(ax, ay);
                _arrowShape.graphics.lineTo(ax + ARROW_SIZE, ay);
                _arrowShape.graphics.lineTo(ax + ARROW_SIZE / 2, ay + ARROW_SIZE - 1);
            }
            _arrowShape.graphics.endFill();
        }

        // ═══════════════════════════════════════════════════════
        // 弹出列表
        // ═══════════════════════════════════════════════════════

        private function _onTriggerClick(event:MouseEvent):void
        {
            if (!_enabled) return;
            if (_isOpen) _closeList();
            else _openList();
        }

        private function _openList():void
        {
            if (_items.length == 0) return;
            _isOpen = true;
            _scrollPos = 0;
            _drawTrigger(Theme.surface0);

            // ── 计算尺寸 ──
            var itemAreaW:Number = _w - SCROLLBAR_W - SCROLLBAR_MARGIN * 2;
            var totalH:Number = _items.length * (ITEM_H + ITEM_GAP) + ITEM_GAP;
            var visibleH:Number = MAX_VISIBLE * (ITEM_H + ITEM_GAP) + ITEM_GAP;
            _needsScroll = _items.length > MAX_VISIBLE;
            var overlayH:Number = _needsScroll ? visibleH : totalH;
            _maxScroll = totalH - visibleH;

            // ── 弹出层 ──
            _overlay = new Sprite();

            // 背景
            _overlayBg = new Shape();
            _overlayBg.graphics.lineStyle(STROKE_W, Theme.stroke);
            _overlayBg.graphics.beginFill(Theme.surface0, 1.0);
            _overlayBg.graphics.drawRoundRect(0, 0, _w, overlayH,
                CORNER_RADIUS * 2, CORNER_RADIUS * 2);
            _overlayBg.graphics.endFill();
            _overlay.addChild(_overlayBg);

            // 列表项容器
            _itemContainer = new Sprite();
            _itemContainer.x = 0;
            _itemContainer.y = ITEM_GAP;
            _itemContainer.scrollRect = new Rectangle(
                0, 0, itemAreaW, overlayH - ITEM_GAP * 2);

            for (var i:int = 0; i < _items.length; i++)
            {
                var itemSpr:Sprite = _buildItemSprite(i, itemAreaW);
                itemSpr.y = i * (ITEM_H + ITEM_GAP);
                _itemContainer.addChild(itemSpr);
            }
            _overlay.addChild(_itemContainer);

            // ── 滚动条（仅在需要时）──
            if (_needsScroll)
            {
                var trackX:Number = _w - SCROLLBAR_W - SCROLLBAR_MARGIN;
                var trackY:Number = ITEM_GAP;
                var trackH:Number = overlayH - ITEM_GAP * 2;

                _scrollTrack = new Shape();
                _scrollTrack.graphics.beginFill(Theme.surface2, 1.0);
                _scrollTrack.graphics.drawRoundRect(0, 0, SCROLLBAR_W, trackH,
                    3, 3);
                _scrollTrack.graphics.endFill();
                _scrollTrack.x = trackX;
                _scrollTrack.y = trackY;
                _overlay.addChild(_scrollTrack);

                var thumbH:Number = Math.max(
                    SCROLL_THUMB_MIN_H,
                    overlayH / totalH * trackH);
                _scrollThumb = new Sprite();
                _scrollThumb.graphics.beginFill(Theme.sbThumb, 1.0);
                _scrollThumb.graphics.drawRoundRect(0, 0, SCROLLBAR_W, thumbH,
                    3, 3);
                _scrollThumb.graphics.endFill();
                _scrollThumb.x = trackX;
                _scrollThumb.y = trackY;
                _scrollThumb.buttonMode = true;
                _scrollThumb.addEventListener(MouseEvent.MOUSE_DOWN,
                    _onScrollThumbDown);
                _overlay.addChild(_scrollThumb);

                // 鼠标滚轮
                _overlay.addEventListener(MouseEvent.MOUSE_WHEEL,
                    _onOverlayWheel);
            }

            // ── 挂载到 stage ──
            var pos:Point = this.localToGlobal(new Point(0, TRIGGER_H));

            // ── 初始滚动：选中项滚到可视区第一行 ──
            // 靠近列表底部时 _updateScroll 会钳制到最大滚动值
            //（即最后一屏不再继续下滑，选中项不一定在第一行）。
            if (_needsScroll && _selectedIndex > 0)
            {
                _scrollPos = _selectedIndex * (ITEM_H + ITEM_GAP);
                _updateScroll();
            }

            if (this.stage)
            {
                this.stage.addChild(_overlay);
                this.stage.addEventListener(MouseEvent.MOUSE_DOWN,
                    _onStageClick);
                // ENTER_FRAME 跟踪位置——当 Dropdown 因父容器滚动/移动时，
                // overlay 自动跟随，避免列表"漂移"在原处。
                _overlay.addEventListener(Event.ENTER_FRAME,
                    _onOverlayEnterFrame);
            }
            else
            {
                if (this.parent) this.parent.addChild(_overlay);
            }

            _overlay.x = pos.x;
            _overlay.y = pos.y;

            L.debug("弹出 " + _items.length + " 条"
                + (_needsScroll ? " (可滚动)" : ""));
        }

        private function _closeList():void
        {
            _isOpen = false;
            _drawTrigger(Theme.surface1);

            // 停止滚动条拖拽
            if (_scrollDragging)
            {
                _scrollDragging = false;
                if (this.stage)
                {
                    this.stage.removeEventListener(MouseEvent.MOUSE_MOVE,
                        _onScrollThumbMove);
                    this.stage.removeEventListener(MouseEvent.MOUSE_UP,
                        _onScrollThumbUp);
                }
            }

            if (_scrollThumb)
            {
                _scrollThumb.removeEventListener(MouseEvent.MOUSE_DOWN,
                    _onScrollThumbDown);
                _scrollThumb = null;
            }

            if (_overlay)
            {
                _overlay.removeEventListener(MouseEvent.MOUSE_WHEEL,
                    _onOverlayWheel);
                _overlay.removeEventListener(Event.ENTER_FRAME,
                    _onOverlayEnterFrame);

                // 注销列表项的音效监听
                if (_itemContainer)
                {
                    while (_itemContainer.numChildren > 0)
                    {
                        var child:* = _itemContainer.getChildAt(0);
                        if (child is SoundableSprite)
                            SoundableSprite(child).disposeItem();
                        _itemContainer.removeChildAt(0);
                    }
                }

                if (_overlay.parent)
                    _overlay.parent.removeChild(_overlay);
                _overlay = null;
                _overlayBg = null;
                _itemContainer = null;
                _scrollTrack = null;
            }

            if (this.stage)
                this.stage.removeEventListener(MouseEvent.MOUSE_DOWN,
                    _onStageClick);
        }

        // ═══════════════════════════════════════════════════════
        // 列表项构建
        // ═══════════════════════════════════════════════════════

        private function _buildItemSprite(index:int, itemW:Number):Sprite
        {
            var spr:SoundableSprite = new SoundableSprite("dropDownItemRenderer");
            spr.name = "item_" + index;
            spr.buttonMode = true;

            var bg:Shape = new Shape();
            bg.name = "bg";
            spr.addChild(bg);

            var fmt:TextFormat = new TextFormat();
            fmt.font = "$TextFont";
            fmt.size = 14;
            fmt.color = Theme.textPrimary;

            var tf:TextField = new TextField();
            tf.defaultTextFormat = fmt;
            tf.text = _items[index];
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.x = 8;
            tf.y = int((ITEM_H - ITEM_TEXT_H) / 2);
            tf.width = itemW - 16;
            tf.height = ITEM_TEXT_H;
            spr.addChild(tf);

            var isSel:Boolean = (index == _selectedIndex);
            _drawItemBg(spr, isSel ? Theme.accent : Theme.surface3, itemW);

            spr.addEventListener(MouseEvent.ROLL_OVER, function(e:MouseEvent):void {
                _drawItemBg(e.currentTarget as Sprite, Theme.accent, itemW);
            });
            spr.addEventListener(MouseEvent.ROLL_OUT, function(e:MouseEvent):void {
                var idx:int = parseInt((e.currentTarget as Sprite).name.split("_")[1]);
                _drawItemBg(e.currentTarget as Sprite,
                    idx == _selectedIndex ? Theme.accent : Theme.surface3, itemW);
            });
            spr.addEventListener(MouseEvent.CLICK, function(e:MouseEvent):void {
                var idx:int = parseInt((e.currentTarget as Sprite).name.split("_")[1]);
                _onItemClick(idx);
            });

            return spr;
        }

        private function _drawItemBg(spr:Sprite, color:uint, itemW:Number):void
        {
            var bg:Shape = spr.getChildByName("bg") as Shape;
            if (!bg) return;
            bg.graphics.clear();
            bg.graphics.beginFill(color, 1.0);
            bg.graphics.drawRoundRect(2, 0, itemW - 4, ITEM_H, 8, 8);
            bg.graphics.endFill();
        }

        private function _onItemClick(index:int):void
        {
            _selectedIndex = index;
            _triggerLabel.text = _items[index];
            _closeList();

            if (onSelect != null)
                onSelect(index, _items[index]);

            L.debug("选中 #" + index + " → " + _items[index]);
        }

        // ═══════════════════════════════════════════════════════
        // 滚动
        // ═══════════════════════════════════════════════════════

        private function _updateScroll():void
        {
            if (!_itemContainer) return;

            _scrollPos = Math.max(0, Math.min(_maxScroll, _scrollPos));
            var itemAreaW:Number = _w - SCROLLBAR_W - SCROLLBAR_MARGIN * 2;
            _itemContainer.scrollRect = new Rectangle(
                0, _scrollPos, itemAreaW,
                _itemContainer.scrollRect.height);

            // 更新滚动条拇指位置
            if (_scrollThumb && _scrollTrack && _needsScroll)
            {
                var trackH:Number = _scrollTrack.height;
                var thumbH:Number = _scrollThumb.height;
                var travel:Number = trackH - thumbH;
                if (travel > 0)
                    _scrollThumb.y = _scrollTrack.y
                        + (_scrollPos / _maxScroll) * travel;
            }
        }

        private function _onOverlayWheel(event:MouseEvent):void
        {
            if (!_needsScroll) return;
            var delta:int = event.delta > 0 ? -1 : 1;
            _scrollPos += delta * (ITEM_H + ITEM_GAP) * 2;  // 一次滚 2 行
            // 这里乘2是为了在实际使用中感觉更灵敏，不符合预期可以改成1
            _updateScroll();
        }

        private function _onScrollThumbDown(event:MouseEvent):void
        {
            _scrollDragging = true;
            _scrollDragStartY = event.stageY;
            _scrollDragStartPos = _scrollPos;

            if (this.stage)
            {
                this.stage.addEventListener(MouseEvent.MOUSE_MOVE,
                    _onScrollThumbMove);
                this.stage.addEventListener(MouseEvent.MOUSE_UP,
                    _onScrollThumbUp);
            }
            event.stopImmediatePropagation();
        }

        private function _onScrollThumbMove(event:MouseEvent):void
        {
            if (!_scrollDragging || !_scrollTrack) return;

            var deltaY:Number = event.stageY - _scrollDragStartY;
            var trackH:Number = _scrollTrack.height;
            var thumbH:Number = _scrollThumb ? _scrollThumb.height : SCROLL_THUMB_MIN_H;
            var travel:Number = trackH - thumbH;

            if (travel > 0)
            {
                var ratio:Number = deltaY / travel;
                _scrollPos = Math.max(0, Math.min(_maxScroll,
                    _scrollDragStartPos + ratio * _maxScroll));
                _updateScroll();
            }
        }

        private function _onScrollThumbUp(event:MouseEvent):void
        {
            _scrollDragging = false;
            if (this.stage)
            {
                this.stage.removeEventListener(MouseEvent.MOUSE_MOVE,
                    _onScrollThumbMove);
                this.stage.removeEventListener(MouseEvent.MOUSE_UP,
                    _onScrollThumbUp);
            }
        }

        /**
         * 每帧更新 overlay 位置，确保弹出列表跟随 Dropdown 组件移动。
         * 同时检测祖先 scrollRect 裁剪——当 Dropdown 被卷出可视区时隐藏 overlay，
         * 避免列表悬浮在裁剪区上方。
         */
        private function _onOverlayEnterFrame(event:Event):void
        {
            if (!_overlay || !_isOpen) return;
            var pos:Point = this.localToGlobal(new Point(0, TRIGGER_H));
            _overlay.x = pos.x;
            _overlay.y = pos.y;

            // 检查祖先 scrollRect 是否裁剪了 Dropdown 触发器区域。
            // overlay 挂在 stage 上不受 scrollRect 限制，但如果组件本身
            // 已被裁出可视区，列表也应该隐藏。
            var centerX:Number = pos.x + _w / 2;
            var centerY:Number = pos.y + TRIGGER_H / 2;
            var clipped:Boolean = false;
            var o:DisplayObject = this.parent;
            while (o && o != this.stage)
            {
                if (o.scrollRect && o.scrollRect.width > 0 && o.scrollRect.height > 0)
                {
                    var lp:Point = o.globalToLocal(new Point(centerX, centerY));
                    var sr:Rectangle = o.scrollRect;
                    if (lp.x < sr.x || lp.x > sr.x + sr.width ||
                        lp.y < sr.y || lp.y > sr.y + sr.height)
                    {
                        clipped = true;
                        break;
                    }
                }
                o = o.parent;
            }
            _overlay.visible = !clipped;
        }

        // ═══════════════════════════════════════════════════════
        // 外部点击关闭
        // ═══════════════════════════════════════════════════════

        private function _onStageClick(event:MouseEvent):void
        {
            var target:DisplayObject = event.target as DisplayObject;
            if (!target) return;

            if (target == this || this.contains(target))
                return;
            if (_overlay && (target == _overlay || _overlay.contains(target)))
                return;

            _closeList();
        }
    }
}
