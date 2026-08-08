package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import net.wg.infrastructure.interfaces.entity.ISoundable;

    /**
     * 带游戏 UI 音效的 Sprite——供 Dropdown 列表项、语音列表项等动态创建的场景使用。
     *
     * 构造后自动向 App.soundMgr 注册，dispose() 时注销。
     *
     * 用法:
     *   var item:SoundableSprite = new SoundableSprite("dropDownItemRenderer");
     *   // ... 添加子对象、设置事件 ...
     *   item.dispose();  // 销毁前注销音效
     */
    public class SoundableSprite extends Sprite implements ISoundable
    {
        private var _soundType:String;
        private var _soundEnabled:Boolean = true;

        /**
         * @param soundType  声音类型（"dropDownItemRenderer"/"itemRenderer"/...）
         */
        public function SoundableSprite(soundType:String)
        {
            super();
            _soundType = soundType;
            if (App.soundMgr)
                App.soundMgr.addSoundsHdlrs(this);
        }

        /** 启用/禁用音效。 */
        public function setSoundEnabled(value:Boolean):void
        {
            _soundEnabled = value;
        }

        /** 注销音效并清理。 */
        public function disposeItem():void
        {
            if (App.soundMgr)
                App.soundMgr.removeSoundHdlrs(this);
        }

        // ═══════════════════════════════════════════════════════
        // ISoundable
        // ═══════════════════════════════════════════════════════

        public function canPlaySound(type:String):Boolean
        {
            return _soundEnabled && !SoundUtils.muted;
        }

        public function getSoundType():String { return _soundType; }

        public function getSoundId():String { return ""; }
    }
}
