package com.github._25304_Oxygen.shared.i18n
{
    import flash.utils.Dictionary;

    /**
     * L10n —— 界面词典查询（i18n 第一期，2026-08）。
     *
     * 两端分工（开发文档 §5.4）：Flash 端不读文件——词典由 Python 侧
     * 经 as_setLabelsS 推送，本类负责存储与分发刷新。
     *
     * 用法:
     *   // 页面创建组件时取文本（labels 未到达前回退中文默认）
     *   new CheckBox(L10n.get("settings/cb_ui_sound", "开启界面交互音效"));
     *
     *   // 页面注册刷新回调（仿 Theme.register 模式）：
     *   L10n.register(this, _applyLabels);
     *   // dispose 时:
     *   L10n.unregister(this);
     *
     * 键与中文默认值（L10n.get 第二参数）照抄 Python l10n.py 的 UI_LABELS
     * 表——那是唯一权威来源，任何语言下 labels 推送后都会覆盖此默认值。
     *
     * ★ 命名说明: 本类名为 L10n 而非 L——各页面已用 `L` 作为日志器
     *   （Log.getLogger）常量，同名会遮蔽 import，编译冲突。
     */
    public class L10n
    {
        private static var _labels:Object = {};
        private static var _registrations:Dictionary = new Dictionary();

        /**
         * 查询键对应文本。
         * @param key        英文语义键（如 "settings/nation_voice_title"）
         * @param zhDefault  中文默认值（UI_LABELS 镜像；labels 未到时的首屏回退）
         */
        public static function get(key:String, zhDefault:String = ""):String
        {
            var v:* = _labels[key];
            if (v is String && String(v).length > 0)
                return String(v);
            return zhDefault;
        }

        /**
         * 接收 Python 推送的 labels dict 并刷新所有已注册组件。
         * 由 MenuView.as_setLabels 调用；切换语言后重推 labels 即全局生效。
         */
        public static function setLabels(labels:Object):void
        {
            _labels = (labels is Object) ? labels : {};
            for each (var refresh:Function in _registrations)
            {
                try
                {
                    refresh();
                }
                catch (e:Error)
                {
                    // 单个组件刷新失败不影响其他组件（与 Theme.apply 同策略）
                }
            }
        }

        /** 注册文本刷新回调（仿 Theme.register）。 */
        public static function register(target:*, refresh:Function):void
        {
            _registrations[target] = refresh;
        }

        /** 解绑文本刷新回调（dispose 时调用）。 */
        public static function unregister(target:*):void
        {
            delete _registrations[target];
        }

        /** 当前已推送的键数量（debug 用）。 */
        public static function labelCount():int
        {
            var n:int = 0;
            for (var k:String in _labels)
                n++;
            return n;
        }
    }
}
