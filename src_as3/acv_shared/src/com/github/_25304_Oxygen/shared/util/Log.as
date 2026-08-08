package com.github._25304_Oxygen.shared.util
{
    /**
     * 统一日志工具——双路径输出 + 等级过滤 + 来源标识。
     *
     * 路径 1: trace() → 游戏 python.log（始终生效，DAAPI 未就绪时的唯一路径）
     * 路径 2: Python 回调 → script.log（DAAPI 就绪后生效，可读性更好）
     *
     * 日志等级（数值越大越重要）:
     *   DEBUG (0) — 高频/诊断信息（逐帧补间、拖拽中...）
     *   INFO  (1) — 常规状态变更（组件创建/销毁、动画开始/结束）
     *   WARN  (2) — 可恢复异常（资源加载失败但有 fallback）
     *   ERROR (3) — 需要关注的错误（DAAPI 通信失败）
     *
     * 设置等级后，低于该等级的日志不输出。
     *   Log.level = Log.INFO;   // 屏蔽 DEBUG，保留 INFO/WARN/ERROR
     *   Log.level = Log.DEBUG;  // 全部输出（开发阶段默认）
     *
     * DAAPI 就绪前积累的消息在 setPythonLogger() 注册时批量发送。
     *
     * —— 来源标识（source）——
     *
     * 两种用法，效果相同:
     *
     *   方式 1 —— 每次传 source 参数:
     *     Log.info("数据已应用", "PersonalSettingsPage");
     *     // → [flash] [PersonalSettingsPage] [INFO]: 数据已应用
     *
     *   方式 2 —— getLogger() 创建模块级实例（推荐，对标 Python Logger）:
     *     private static const L:Object = Log.getLogger("Dropdown");
     *     L.info("选项已更新");  // → [flash] [Dropdown] [INFO]: 选项已更新
     *
     * 不传 source 时保持旧格式:
     *   Log.info("MenuView 构造");
     *   // → [flash] [INFO]: MenuView 构造
     */
    public class Log
    {
        // ── 日志等级 ──────────────────────────────
        public static const DEBUG:int = 0;
        public static const INFO:int  = 1;
        public static const WARN:int  = 2;
        public static const ERROR:int = 3;

        private static const LEVEL_NAMES:Array = ["DEBUG", "INFO", "WARN", "ERROR"];

        /** 当前最低输出等级，默认 DEBUG（全部输出）。 */
        public static var level:int = DEBUG;

        // ── Python 回调 & 缓冲 ───────────────────
        private static var _pyLog:Function = null;
        private static var _queue:Array = [];
        private static const MAX_QUEUE:int = 200;

        /** 由 DAAPI 就绪后调用，注册 Python 端日志回调。 */
        public static function setPythonLogger(callback:Function):void
        {
            _pyLog = callback;
            if (_queue.length > 0)
            {
                _flushQueue();
            }
        }

        private static function _flushQueue():void
        {
            for each (var msg:String in _queue)
            {
                _pyLog(msg);
            }
            _queue.length = 0;
        }

        // ── 核心输出 ──────────────────────────────

        /**
         * 低级输出——需要自定义 source 时使用。
         * @param lvl    日志等级
         * @param msg    日志内容
         * @param source 来源标识（类名/模块名），空字符串 = 不显示
         */
        public static function log(lvl:int, msg:String, source:String = ""):void
        {
            if (lvl < level) return;

            var line:String;
            if (source.length > 0)
                line = "[" + LEVEL_NAMES[lvl] + "] [Flash:" + source + "]: " + msg;
            else
                line = "[" + LEVEL_NAMES[lvl] + "] [flash]: " + msg;

            // trace 仅 WARN/ERROR 落入 python.log，避免刷屏
            if (lvl >= WARN)
                trace(line);

            if (_pyLog != null)
            {
                _pyLog(line);
            }
            else if (_queue.length < MAX_QUEUE)
            {
                _queue.push(line);
            }
            else
            {
                _queue.shift();
                _queue.push(line);
            }
        }

        // ── 公开方法（可选 source 参数）──────────

        public static function debug(msg:String, source:String = ""):void
        {
            log(DEBUG, msg, source);
        }

        public static function info(msg:String, source:String = ""):void
        {
            log(INFO, msg, source);
        }

        public static function warn(msg:String, source:String = ""):void
        {
            log(WARN, msg, source);
        }

        public static function error(msg:String, source:String = ""):void
        {
            log(ERROR, msg, source);
        }

        // ── getLogger —— 对标 Python Logger ──────

        /**
         * 创建带来源标识的日志记录器（推荐在类顶部声明）。
         *
         * 用法:
         *   private static const L:Object = Log.getLogger("PersonalSettingsPage");
         *   L.info("数据已应用");
         *
         * @param source 来源标识（通常为类名）
         * @return 包含 debug/info/warn/error 四个方法的简单对象
         */
        public static function getLogger(source:String):Object
        {
            return {
                debug: function(msg:String):void { Log.log(Log.DEBUG, msg, source); },
                info:  function(msg:String):void { Log.log(Log.INFO,  msg, source); },
                warn:  function(msg:String):void { Log.log(Log.WARN,  msg, source); },
                error: function(msg:String):void { Log.log(Log.ERROR, msg, source); }
            };
        }
    }
}
