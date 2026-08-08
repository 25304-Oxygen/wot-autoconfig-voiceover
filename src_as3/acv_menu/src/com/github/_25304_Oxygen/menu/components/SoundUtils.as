package com.github._25304_Oxygen.menu.components
{
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.events.Event;
    import net.wg.infrastructure.interfaces.entity.ISoundable;

    /**
     * UI 音效工具类——全局静音 + SoundManager 注册/注销辅助。
     *
     * 组件在 configUI/init 中调 SoundUtils.registerSound(this, soundType)，
     * dispose 中调 SoundUtils.removeSound(this)，canPlaySound 中检查
     * SoundUtils.muted。
     *
     * SettingsPage 的"开启界面交互音效"复选框直接设 setMuted()。
     */
    public class SoundUtils
    {
        /** 全局静音标志——true=静音，false=正常播放。 */
        private static var _muted:Boolean = false;

        /** SoundManager 引用，init 时缓存。 */
        private static var _soundMgr:* = null;

        // ═══════════════════════════════════════════════════════
        // 初始化
        // ═══════════════════════════════════════════════════════

        /** 缓存 SoundManager 引用（页面 init 时调一次即可）。 */
        public static function init():void
        {
            try { _soundMgr = App.soundMgr; }
            catch (e:Error) { _soundMgr = null; }
        }

        // ═══════════════════════════════════════════════════════
        // 静音控制
        // ═══════════════════════════════════════════════════════

        /** 查询是否静音。 */
        public static function get muted():Boolean { return _muted; }

        /** 设置静音（SettingsPage 复选框回调）。 */
        public static function setMuted(value:Boolean):void
        {
            _muted = value;
        }

        // ═══════════════════════════════════════════════════════
        // SoundManager 注册/注销
        // ═══════════════════════════════════════════════════════

        /** 向 SoundManager 注册组件（内部调用 addSoundsHdlrs）。 */
        public static function registerSound(target:Sprite):void
        {
            if (_soundMgr == null)
                init();
            if (_soundMgr != null)
                _soundMgr.addSoundsHdlrs(target);
        }

        /** 从 SoundManager 注销组件。 */
        public static function removeSound(target:Sprite):void
        {
            if (_soundMgr == null)
                init();
            if (_soundMgr != null)
                _soundMgr.removeSoundHdlrs(target);
        }
    }
}
