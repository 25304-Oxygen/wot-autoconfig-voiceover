package com.github._25304_Oxygen.menu.controls
{
    import flash.display.Sprite;

    /**
     * 控件基类——所有菜单控件必须继承此类。
     *
     * 定义统一接口: label / value / enabled / onChange。
     * 后续具体控件（CheckBox、Slider、Dropdown 等）均继承此类。
     *
     * 用法:
     *   var cb:CheckBox = new CheckBox("启用字幕", true);
     *   cb.onChange = function(value:*):void { Log.info("新值: " + value); };
     *   settingsPage.addControl(cb);
     */
    public class BaseControl extends Sprite
    {
        private var _label:String;
        private var _value:*;
        private var _enabled:Boolean = true;

        /** 值变更回调: function(value:*):void */
        public var onChange:Function;

        public function BaseControl(label:String, defaultValue:* = null)
        {
            super();
            _label = label;
            _value = defaultValue;
        }

        // ═══════════════════════════════════════════════════════
        // 属性
        // ═══════════════════════════════════════════════════════

        public function get label():String     { return _label; }
        public function set label(v:String):void { _label = v; }

        public function get value():*          { return _value; }
        public function set value(v:*):void
        {
            _value = v;
            _notifyChange();
        }

        public function get enabled():Boolean    { return _enabled; }
        public function set enabled(v:Boolean):void { _enabled = v; }

        // ═══════════════════════════════════════════════════════
        // 布局
        // ═══════════════════════════════════════════════════════

        /**
         * 返回控件的自然高度（像素）。
         * 子类根据实际内容重写此方法，供页面的布局管理器使用。
         */
        public function get preferredHeight():Number
        {
            return 30;
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        /** 子类在值发生变更后调用此方法。 */
        protected function _notifyChange():void
        {
            if (onChange != null)
                onChange(_value);
        }
    }
}
