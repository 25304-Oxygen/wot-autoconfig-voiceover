package com.github._25304_Oxygen.menu.components
{
    import flash.utils.Dictionary;

    /**
     * 全局主题色板——纯静态类。
     *
     * 所有 UI 组件从 Theme 读取颜色，不再硬编码。Python 端传入
     * 一个包含部分颜色的 dict → Theme.apply(config) → 所有已注册
     * 组件自动刷新。
     *
     * 用法:
     *   // 组件注册（构造时）
     *   Theme.register(this, _refreshStyle);
     *
     *   // Python 端换肤
     *   Theme.apply({ accent: 0xFF6B6B, accentHover: 0xFF8B8B });
     *
     *   // 组件注销（dispose 时）
     *   Theme.unregister(this);
     */
    public class Theme
    {
        // ═══════════════════════════════════════════════════════
        // 表面色（4 级灰度梯度）
        // ═══════════════════════════════════════════════════════

        /** 最深 — 面板背景、弹窗、下拉展开态 */
        public static var surface0:uint = 0x1E1E1E;

        /** 中等 — 输入框背景、下拉触发器、复选框未选中 */
        public static var surface1:uint = 0x2D2D2D;

        /** 较浅 — 滚动条轨道、步进器轨道 */
        public static var surface2:uint = 0x3C3C3C;

        /** 特殊 — 下拉列表选项行 */
        public static var surface3:uint = 0x252526;

        // ═══════════════════════════════════════════════════════
        // 强调色（3 级亮度）
        // ═══════════════════════════════════════════════════════

        /** 主色 — 按钮正常、选中态、进度填充、聚焦描边 */
        public static var accent:uint = 0x3D6B9B;

        /** 悬停 — 按钮悬停、步进器拇指 */
        public static var accentHover:uint = 0x4D8BC5;

        /** 按下 — 按钮按下 */
        public static var accentPress:uint = 0x2D5B7B;

        // ═══════════════════════════════════════════════════════
        // 边框 & 文字
        // ═══════════════════════════════════════════════════════

        /** 通用描边（聚焦 = accent，不单独设 slot）。 */
        public static var stroke:uint = 0x888888;

        /** 正文/标签。 */
        public static var textPrimary:uint = 0xD4D4D4;

        /** 次要文字 — 禁用、占位、分类标签。 */
        public static var textSecondary:uint = 0x666666;

        /** 菜单大标题 — 默认与 textPrimary 一致，可独立设置。 */
        public static var titleText:uint = 0xD4D4D4;

        // ═══════════════════════════════════════════════════════
        // 滚动条（轨道复用 surface2）
        // ═══════════════════════════════════════════════════════

        /** 拇指（= textSecondary 同默认值但不绑定，可独立设置）。 */
        public static var sbThumb:uint = 0x666666;

        /** ▲▼ 按钮背景。 */
        public static var sbBtn:uint = 0x555555;

        /** ▲▼ 箭头。 */
        public static var sbBtnArrow:uint = 0xCCCCCC;

        // ═══════════════════════════════════════════════════════
        // 注册 / 通知
        // ═══════════════════════════════════════════════════════

        /** 已注册的刷新回调（key=组件实例, value=刷新函数）。 */
        private static var _registrations:Dictionary = new Dictionary();

        /**
         * 注册组件的刷新回调。
         * @param target  组件实例（用作 key，dispose 时需传入同一个引用注销）
         * @param refresh 无参刷新函数，会重绘组件全部外观
         */
        public static function register(target:*, refresh:Function):void
        {
            _registrations[target] = refresh;
        }

        /** 注销组件的刷新回调。 */
        public static function unregister(target:*):void
        {
            delete _registrations[target];
        }

        /**
         * 应用主题配置并刷新全部已注册组件。
         * @param config  包含任意颜色槽位的 Object，未指定的保持原值。
         *                键名使用字符串: "surface0", "accent", "textPrimary" 等。
         */
        public static function apply(config:Object):void
        {
            if (!config) return;

            _setIf(config, "surface0",     function(v:uint):void { surface0 = v; });
            _setIf(config, "surface1",     function(v:uint):void { surface1 = v; });
            _setIf(config, "surface2",     function(v:uint):void { surface2 = v; });
            _setIf(config, "surface3",     function(v:uint):void { surface3 = v; });
            _setIf(config, "accent",       function(v:uint):void { accent = v; });
            _setIf(config, "accentHover",  function(v:uint):void { accentHover = v; });
            _setIf(config, "accentPress",  function(v:uint):void { accentPress = v; });
            _setIf(config, "stroke",       function(v:uint):void { stroke = v; });
            _setIf(config, "textPrimary",  function(v:uint):void { textPrimary = v; });
            _setIf(config, "textSecondary",function(v:uint):void { textSecondary = v; });
            _setIf(config, "titleText",    function(v:uint):void { titleText = v; });
            _setIf(config, "sbThumb",      function(v:uint):void { sbThumb = v; });
            _setIf(config, "sbBtn",        function(v:uint):void { sbBtn = v; });
            _setIf(config, "sbBtnArrow",   function(v:uint):void { sbBtnArrow = v; });

            // 通知全部已注册组件刷新
            for each (var refresh:Function in _registrations)
            {
                if (refresh != null)
                {
                    try { refresh(); }
                    catch (e:Error) { /* 组件可能已半销毁，忽略 */ }
                }
            }
        }

        /** 仅当 config 中存在指定 key 时才调用 setter。 */
        private static function _setIf(config:Object, key:String,
                                       setter:Function):void
        {
            if (config.hasOwnProperty(key))
            {
                var v:uint = uint(config[key]);
                setter(v);
            }
        }
    }
}