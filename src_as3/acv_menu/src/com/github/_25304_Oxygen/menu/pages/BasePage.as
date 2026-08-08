package com.github._25304_Oxygen.menu.pages
{
    import flash.display.Sprite;

    /**
     * 菜单页面基类——所有页面必须继承此类。
     *
     * 每个页面是一个独立的 Sprite，可管理自己的子显示对象、
     * 事件监听器、控件等。MenuView 通过此接口与页面交互。
     *
     * 生命周期:
     *   init()   → 创建所有子显示对象（舞台就绪后调用一次）
     *   show()   → 页面即将显示（面板滑入前/同时调用）
     *   hide()   → 页面即将隐藏（面板滑出前调用）
     *   dispose()→ 销毁页面，释放所有资源
     */
    public class BasePage extends Sprite
    {
        /**
         * 全展开面板顶部被半折叠面板遮挡的高度（px）。
         *
         * 布局关系: SEMI_H(260) - FULL_Y(200) = 60
         * 全展开时 semiPanel 覆盖 fullPanel 顶部 60px 区域。
         * 所有页面组件应定位在 y ≥ SAFE_TOP，避开遮挡区。
         */
        public static const SAFE_TOP:Number = 60;

        /** 页面唯一标识——用于注册和切换。 */
        private var _pageId:String;

        public function BasePage(pageId:String)
        {
            super();
            _pageId = pageId;
        }

        /** 页面 ID（"info"、"settings" 等）。 */
        public function get pageId():String { return _pageId; }

        /**
         * 初始化——在 PanelView 设置此页面后调用。
         * 在这里创建 TextField、图片、控件等子元素。
         */
        public function init():void
        {
        }

        /** 页面即将显示。重入场的准备工作（如果有）。 */
        public function show():void
        {
        }

        /** 页面即将隐藏。暂停动画、保存状态等。 */
        public function hide():void
        {
        }

        /**
         * 销毁页面。移除所有事件监听器、停止动画、释放引用。
         * 重写时必须调用 super.dispose()。
         */
        public function dispose():void
        {
            if (parent)
                parent.removeChild(this);
        }
    }
}
