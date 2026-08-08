package com.github._25304_Oxygen.menu.components
{
    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 管理一组 RadioButton 互斥选中。
     *
     * 用法:
     *   var group:RadioGroup = new RadioGroup();
     *   var rb1:RadioButton = new RadioButton("选项 A");
     *   var rb2:RadioButton = new RadioButton("选项 B");
     *   group.add(rb1); group.add(rb2);
     *   group.onSelectionChange = function(index:int):void { ... };
     */
    public class RadioGroup
    {
        private static const L:Object = Log.getLogger("RadioGroup");

        private var _buttons:Array = [];
        private var _selectedIndex:int = -1;
        private var _changeLock:Boolean = false;

        /** 选中变化回调: function(selectedIndex:int):void */
        public var onSelectionChange:Function;

        public function RadioGroup()
        {
        }

        /** 添加单选按钮到组。 */
        public function add(button:RadioButton):void
        {
            if (_buttons.indexOf(button) >= 0) return;
            _buttons.push(button);
            button._setGroup(this);

            // 如果按钮已经选中，更新组状态
            if (button.selected)
            {
                var idx:int = _buttons.length - 1;
                if (_selectedIndex >= 0 && _selectedIndex != idx)
                {
                    var prev:RadioButton = _buttons[_selectedIndex] as RadioButton;
                    if (prev) prev.setSelected(false, false);
                }
                _selectedIndex = idx;
            }
        }

        /** 移除单选按钮。 */
        public function remove(button:RadioButton):void
        {
            var idx:int = _buttons.indexOf(button);
            if (idx < 0) return;

            _buttons.splice(idx, 1);
            button._setGroup(null);

            if (_selectedIndex == idx)
            {
                _selectedIndex = -1;
            }
            else if (_selectedIndex > idx)
            {
                _selectedIndex--;
            }
        }

        /** 通过索引设置选中项。 */
        public function setSelectedIndex(index:int):void
        {
            if (index < 0 || index >= _buttons.length) return;
            _selectButton(_buttons[index] as RadioButton);
        }

        /** 获取选中索引。 */
        public function get selectedIndex():int { return _selectedIndex; }

        /** 获取选中按钮。 */
        public function get selectedButton():RadioButton
        {
            if (_selectedIndex < 0 || _selectedIndex >= _buttons.length)
                return null;
            return _buttons[_selectedIndex] as RadioButton;
        }

        /** 按钮数量。 */
        public function get length():int { return _buttons.length; }

        /** 销毁整组。 */
        public function dispose():void
        {
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var rb:RadioButton = _buttons[i] as RadioButton;
                if (rb) rb._setGroup(null);
            }
            _buttons = [];
            _selectedIndex = -1;
            onSelectionChange = null;
        }

        // ═══════════════════════════════════════════════════════════
        // 内部（RadioButton 调用）
        // ═══════════════════════════════════════════════════════════

        internal function _selectButton(button:RadioButton):void
        {
            if (_changeLock) return;
            _changeLock = true;

            var newIndex:int = _buttons.indexOf(button);
            if (newIndex < 0) { _changeLock = false; return; }

            var prevIndex:int = _selectedIndex;

            // 取消旧选中
            if (prevIndex >= 0 && prevIndex < _buttons.length)
            {
                var oldBtn:RadioButton = _buttons[prevIndex] as RadioButton;
                if (oldBtn) oldBtn.setSelected(false, true);
            }

            // 设置新选中
            _selectedIndex = newIndex;
            button.setSelected(true, true);

            // 回调
            if (prevIndex != newIndex && onSelectionChange != null)
                onSelectionChange(_selectedIndex);

            _changeLock = false;
            L.debug("选中 " + newIndex);
        }
    }
}
