package com.github._25304_Oxygen.menu.components
{
    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 管理一组 ToggleButton 互斥选中（非显示对象，仿 RadioGroup）。
     *
     * 与 RadioGroup 的区别：按 id 而非索引寻址，支持整组启用/禁用
     * 和清除选中（回到"无选中"状态）。
     *
     * 用法:
     *   var group:ToggleGroup = new ToggleGroup();
     *   group.add(new ToggleButton("edit", "编辑"));
     *   group.add(new ToggleButton("done", "完成"));
     *   group.onChange = function(id:String):void { ... };
     */
    public class ToggleGroup
    {
        private static const L:Object = Log.getLogger("ToggleGroup");

        private var _buttons:Array = [];
        private var _selectedId:String = null;
        private var _changeLock:Boolean = false;

        /** 选中变化回调: function(id:String):void（点击已选中项不触发）。 */
        public var onChange:Function;

        public function ToggleGroup()
        {
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 添加按钮到组。 */
        public function add(button:ToggleButton):void
        {
            if (_buttons.indexOf(button) >= 0) return;
            _buttons.push(button);
            button._setGroup(this);
        }

        /** 移除按钮。 */
        public function remove(button:ToggleButton):void
        {
            var idx:int = _buttons.indexOf(button);
            if (idx < 0) return;

            _buttons.splice(idx, 1);
            button._setGroup(null);
            if (_selectedId == button.id)
                _selectedId = null;
        }

        /**
         * 程序化设置选中项。
         * @param dispatch 是否触发 onChange 回调（静默切换传 false）
         */
        public function selectById(id:String, dispatch:Boolean = true):void
        {
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var btn:ToggleButton = _buttons[i] as ToggleButton;
                if (btn && btn.id == id)
                {
                    _applySelection(btn, dispatch);
                    return;
                }
            }
            L.warn("selectById: 未找到 id=" + id);
        }

        /** 清除选中——所有按钮回到未选中态。 */
        public function clearSelection():void
        {
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var btn:ToggleButton = _buttons[i] as ToggleButton;
                if (btn) btn.setSelected(false, false);
            }
            _selectedId = null;
        }

        /** 整组启用/禁用。 */
        public function setEnabledAll(value:Boolean):void
        {
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var btn:ToggleButton = _buttons[i] as ToggleButton;
                if (btn) btn.setEnabled(value);
            }
        }

        /** 当前选中的 id（无选中返回 null）。 */
        public function get selectedId():String { return _selectedId; }

        /** 按钮数量。 */
        public function get length():int { return _buttons.length; }

        /** 销毁整组（不销毁按钮本身，由持有者 dispose）。 */
        public function dispose():void
        {
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var btn:ToggleButton = _buttons[i] as ToggleButton;
                if (btn) btn._setGroup(null);
            }
            _buttons = [];
            _selectedId = null;
            onChange = null;
        }

        // ═══════════════════════════════════════════════════════
        // 内部（ToggleButton 点击时调用）
        // ═══════════════════════════════════════════════════════

        internal function _selectButton(button:ToggleButton):void
        {
            _applySelection(button, true);
        }

        /** 互斥核心：取消旧选中 → 设置新选中 → 回调。 */
        private function _applySelection(button:ToggleButton, dispatch:Boolean):void
        {
            if (_changeLock) return;
            if (button.id == _selectedId) return;   // 点已选中项 = no-op
            _changeLock = true;

            // 取消旧选中
            for (var i:int = 0; i < _buttons.length; i++)
            {
                var btn:ToggleButton = _buttons[i] as ToggleButton;
                if (btn && btn != button && btn.selected)
                    btn.setSelected(false, false);
            }

            // 设置新选中
            _selectedId = button.id;
            button.setSelected(true, false);

            if (dispatch && onChange != null)
                onChange(_selectedId);

            _changeLock = false;
            L.debug("选中 " + _selectedId);
        }
    }
}
