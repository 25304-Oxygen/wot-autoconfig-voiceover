package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.display.Shape;

    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 选项卡组——水平排列 TabButton，管理互斥选中。
     *
     * 底部有一条横贯全宽的分隔线，选中选项卡通过底部强调条
     * "跨越"分隔线与下方内容区视觉连接。
     *
     * 用法:
     *   var group:TabGroup = new TabGroup();
     *   group.addTab(new TabButton("info", "信息"));
     *   group.addTab(new TabButton("settings", "设置"));
     *   group.onTabChange = function(tabId:String):void { trace(tabId); };
     *   addChild(group);
     *
     *   // 程序切换
     *   group.selectTabById("settings");
     */
    public class TabGroup extends Sprite
    {
        private static const L:Object = Log.getLogger("TabGroup");

        // ═══════════════════════════════════════════════════════
        // 常量
        // ═══════════════════════════════════════════════════════

        /** 选项卡间距（px）。 */
        private static const TAB_GAP:int = 0;

        // ═══════════════════════════════════════════════════════
        // 状态
        // ═══════════════════════════════════════════════════════

        private var _tabs:Array = [];
        private var _selectedTabId:String = "";
        private var _changeLock:Boolean = false;

        // ═══════════════════════════════════════════════════════
        // 子对象
        // ═══════════════════════════════════════════════════════

        /** 底部分隔线（重绘以匹配当前 totalWidth）。 */
        private var _separator:Shape;

        /** 选中变化回调: function(tabId:String):void */
        public var onTabChange:Function;

        // ═══════════════════════════════════════════════════════
        // 构造
        // ═══════════════════════════════════════════════════════

        public function TabGroup()
        {
            super();

            // 分隔线——最先加入，位于所有选项卡下方
            _separator = new Shape();
            addChild(_separator);

            Theme.register(this, _refreshStyle);
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 添加选项卡。如果是第一个则自动选中。 */
        public function addTab(tab:TabButton):void
        {
            if (!tab) return;
            if (_tabs.indexOf(tab) >= 0) return;

            _tabs.push(tab);
            tab._setGroup(this);
            addChild(tab);

            _layout();

            // 首个选项卡默认选中
            if (_tabs.length == 1)
            {
                _selectTab(tab);
            }
            else if (tab.selected)
            {
                // 加入时已处于选中状态，同步组
                _selectTab(tab);
            }

            L.debug("添加选项卡 " + tab.tabId);
        }

        /** 移除选项卡。若移除的是当前选中项，自动选第一个剩余项。 */
        public function removeTab(tab:TabButton):void
        {
            if (!tab) return;

            var idx:int = _tabs.indexOf(tab);
            if (idx < 0) return;

            _tabs.splice(idx, 1);
            tab._setGroup(null);
            if (contains(tab))
                removeChild(tab);

            // 若移除的是当前选中项，选第一个剩余的
            if (_selectedTabId == tab.tabId)
            {
                _selectedTabId = "";
                if (_tabs.length > 0)
                    _selectTab(_tabs[0] as TabButton);
            }

            _layout();
            L.debug("移除选项卡 " + tab.tabId);
        }

        /**
         * 通过 tabId 程序化切换选中选项卡。
         * @return 是否找到并切换成功
         */
        public function selectTabById(tabId:String):Boolean
        {
            for (var i:int = 0; i < _tabs.length; i++)
            {
                var tab:TabButton = _tabs[i] as TabButton;
                if (tab && tab.tabId == tabId)
                {
                    _selectTab(tab);
                    return true;
                }
            }
            L.warn("未找到选项卡 " + tabId);
            return false;
        }

        /** 当前选中选项卡的 id。 */
        public function get selectedTabId():String { return _selectedTabId; }

        /** 当前选中选项卡的索引（-1 表示无选中）。 */
        public function get selectedIndex():int
        {
            for (var i:int = 0; i < _tabs.length; i++)
            {
                var tab:TabButton = _tabs[i] as TabButton;
                if (tab && tab.tabId == _selectedTabId)
                    return i;
            }
            return -1;
        }

        /** 选项卡数量。 */
        public function get length():int { return _tabs.length; }

        /** 销毁整组及所有子选项卡。 */
        public function dispose():void
        {
            Theme.unregister(this);

            for (var i:int = 0; i < _tabs.length; i++)
            {
                var tab:TabButton = _tabs[i] as TabButton;
                if (tab)
                {
                    tab._setGroup(null);
                    if (contains(tab))
                        removeChild(tab);
                }
            }
            _tabs = [];
            _selectedTabId = "";
            onTabChange = null;
            L.debug("已销毁");
        }

        // ═══════════════════════════════════════════════════════════
        // 内部（TabButton 调用）
        // ═══════════════════════════════════════════════════════════

        /** TabButton 点击时回调。 */
        internal function _selectTab(tab:TabButton):void
        {
            if (_changeLock) return;
            if (!tab) return;

            // 点击已选中选项卡，不做任何操作
            if (tab.tabId == _selectedTabId) return;

            _changeLock = true;

            var prevId:String = _selectedTabId;

            // 取消其他选项卡的选中
            for (var i:int = 0; i < _tabs.length; i++)
            {
                var t:TabButton = _tabs[i] as TabButton;
                if (t && t.tabId != tab.tabId)
                    t.setSelected(false, false);
            }

            // 设置新选中
            _selectedTabId = tab.tabId;
            tab.setSelected(true, false);

            // 触发回调
            if (onTabChange != null)
                onTabChange(tab.tabId);

            _changeLock = false;
            L.debug("选中 " + tab.tabId);
        }

        // ═══════════════════════════════════════════════════════════
        // 布局
        // ═══════════════════════════════════════════════════════════

        /** 标签文字变化后重排选项卡（i18n 刷新用，TabButton.setLabel 调用）。 */
        internal function reflow():void
        {
            _layout();
        }

        /** 水平排列所有选项卡并重绘分隔线。 */
        private function _layout():void
        {
            var xPos:Number = 0;
            for (var i:int = 0; i < _tabs.length; i++)
            {
                var tab:TabButton = _tabs[i] as TabButton;
                if (!tab) continue;
                tab.x = xPos;
                tab.y = 0;
                xPos += tab.tabWidth + TAB_GAP;
            }

            var totalW:Number = xPos - TAB_GAP;
            if (totalW < 0) totalW = 0;
            _drawSeparator(totalW);
        }

        /** 绘制底部分隔线。 */
        private function _drawSeparator(totalW:Number):void
        {
            _separator.graphics.clear();
            if (totalW <= 0) return;

            _separator.y = TabButton.HEIGHT;
            _separator.graphics.lineStyle(1, Theme.stroke);
            _separator.graphics.moveTo(0, 0);
            _separator.graphics.lineTo(totalW, 0);
        }

        /** Theme 换肤回调——重绘分隔线。 */
        private function _refreshStyle():void
        {
            var totalW:Number = 0;
            for (var i:int = 0; i < _tabs.length; i++)
            {
                var tab:TabButton = _tabs[i] as TabButton;
                if (tab)
                    totalW += tab.tabWidth + TAB_GAP;
            }
            totalW -= TAB_GAP;
            if (totalW < 0) totalW = 0;
            _drawSeparator(totalW);
        }
    }
}
