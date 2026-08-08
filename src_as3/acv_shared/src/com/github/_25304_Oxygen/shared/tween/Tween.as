package com.github._25304_Oxygen.shared.tween
{
    import flash.display.Stage;
    import flash.events.Event;
    import flash.utils.getTimer;
    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 通用补间引擎。
     *
     * 驱动任意对象的数字属性从当前值过渡到目标值，
     * 使用 Easing 中的缓动函数控制变化速率。
     *
     * 用法:
     *   // 简单调用
     *   Tween.to(mySprite, 0.5, {x: 200, alpha: 0});
     *
     *   // 带回调
     *   Tween.to(mySprite, 0.3, {alpha: 0}, Easing.easeOutSine, function():void {
     *       Log.info("淡出完成");
     *   });
     *
     *   // Builder 模式
     *   var t:Tween = new Tween(mySprite, 0.5, {x: 100, y: 200});
     *   t.easing = Easing.easeOutBack;
     *   t.onComplete = onDone;
     *   t.delay = 0.2;
     *   t.start();
     *
     * 生命周期:
     *   Tween.init(stage)   — 初始化（View 的 onPopulate 中调用一次）
     *   Tween.dispose()     — 清理所有补间（View 的 onDispose 中调用）
     *   Tween.kill(target)  — 终止指定对象上的所有补间
     */
    public class Tween
    {
        /** 模块级日志器 */
        private static const L:Object = Log.getLogger("Tween");

        // ═══════════════════════════════════════════════════════
        // 静态——全局驱动
        // ═══════════════════════════════════════════════════════

        private static var _tweens:Vector.<Tween> = new Vector.<Tween>();
        private static var _stage:Stage;
        private static var _initialized:Boolean = false;

        /** ENTER_FRAME 是否已挂载到 stage（按需挂载，空闲时移除）。 */
        private static var _driverActive:Boolean = false;

        /** 上一帧的墙钟时间（ms）——elapsed-time 驱动用，与语音播放保持同一时钟。 */
        private static var _lastFrameTime:int = 0;

        /** 初始化——View 的 onPopulate 中调用一次。 */
        public static function init(stage:Stage):void
        {
            if (_initialized) return;
            _stage = stage;
            _initialized = true;
            L.info("引擎已初始化（ENTER_FRAME 按需挂载）");
        }

        /** 清理所有补间并停止驱动。 */
        public static function dispose():void
        {
            if (!_initialized) return;
            _removeDriver();
            _tweens.length = 0;
            _stage = null;
            _initialized = false;
            L.info("引擎已清理");
        }

        /** 终止指定目标对象上的所有补间。 */
        public static function kill(target:Object):void
        {
            for (var i:int = _tweens.length - 1; i >= 0; i--)
            {
                if (_tweens[i]._target == target)
                {
                    _tweens[i]._active = false;
                    _tweens.splice(i, 1);
                }
            }
            if (_tweens.length == 0)
                _removeDriver();
        }

        /** 有补间需要驱动时挂载 ENTER_FRAME。 */
        private static function _ensureDriver():void
        {
            if (_driverActive) return;
            if (!_stage) return;
            _stage.addEventListener(Event.ENTER_FRAME, _onEnterFrame);
            _driverActive = true;
            // 挂载时复位时间戳，避免首帧拿到上次卸载后遗留的过期时间差
            _lastFrameTime = getTimer();
        }

        /** 无活跃补间时移除 ENTER_FRAME，避免空闲时每帧空转。 */
        private static function _removeDriver():void
        {
            if (!_driverActive) return;
            if (!_stage) return;
            _stage.removeEventListener(Event.ENTER_FRAME, _onEnterFrame);
            _driverActive = false;
        }

        /**
         * 快捷创建+启动。
         * @param target    要修改其属性的对象
         * @param duration  持续时间（秒）
         * @param props     属性→目标值映射，如 {x: 200, alpha: 0}
         * @param easing    缓动函数，默认 easeOutCubic
         * @param onComplete 完成回调
         * @return Tween 实例（可用来中途 stop()）
         */
        public static function to(target:Object, duration:Number, props:Object,
                                   easing:Function = null, onComplete:Function = null):Tween
        {
            var t:Tween = new Tween(target, duration, props, easing, onComplete);
            t.start();
            return t;
        }

        private static function _onEnterFrame(event:Event):void
        {
            // 真实帧间隔（墙钟），使补间时长与语音/字幕时间线（均不受帧率影响）同基准。
            var now:int = getTimer();
            var dt:Number = (now - _lastFrameTime) / 1000;
            _lastFrameTime = now;

            // 卡顿/后台恢复后的首帧 dt 会很大——clamp 防止补间瞬间跳变到终点
            if (dt <= 0) return;
            if (dt > 0.1) dt = 0.1;

            // 倒序遍历，方便在回调中安全删除自身
            for (var i:int = _tweens.length - 1; i >= 0; i--)
            {
                _tweens[i]._update(dt);
            }
        }

        // ═══════════════════════════════════════════════════════
        // 实例
        // ═══════════════════════════════════════════════════════

        private var _target:Object;
        private var _props:Object;
        private var _starts:Object;       // 起始值快照
        private var _duration:Number;
        private var _elapsed:Number = 0;
        private var _easing:Function;
        private var _active:Boolean = false;

        /** 每帧更新回调。 */
        public var onUpdate:Function;
        /** 完成回调。 */
        public var onComplete:Function;

        /** 启动前延迟（秒）。 */
        public var delay:Number = 0;

        /** 缓动函数，默认 easeOutCubic（末尾减速）。 */
        public var easing:Function;

        /**
         * @param target    要修改其属性的对象
         * @param duration  持续时间（秒）
         * @param props     属性→目标值映射
         * @param easing    缓动函数
         * @param onComplete 完成回调
         */
        public function Tween(target:Object, duration:Number, props:Object,
                               easing:Function = null, onComplete:Function = null)
        {
            _target = target;
            _duration = Math.max(0.001, duration); // 防止除以零
            _props = props;
            _starts = {};
            this.easing = easing || Easing.easeOutCubic;
            this.onComplete = onComplete;
        }

        // ═══════════════════════════════════════════════════════
        // 公开方法
        // ═══════════════════════════════════════════════════════

        /** 启动补间。记录起始值，加入驱动队列。 */
        public function start():void
        {
            if (_active) return;
            if (!_initialized)
            {
                L.warn("start() 在 init() 之前调用，跳过");
                return;
            }

            for (var prop:String in _props)
            {
                if (_target.hasOwnProperty(prop))
                    _starts[prop] = _target[prop];
                else
                    _starts[prop] = 0;
            }

            _elapsed = 0;
            _active = true;
            _tweens.push(this);
            _ensureDriver();

            var propList:String = "";
            for (var p:String in _props)
                propList += p + "→" + _props[p] + " ";
            L.debug("启动: " + propList + "时长=" + _duration.toFixed(2) + "s");
        }

        /** 终止补间。不会触发 onComplete。 */
        public function stop():void
        {
            if (!_active) return;
            _active = false;
            var idx:int = _tweens.indexOf(this);
            if (idx >= 0) _tweens.splice(idx, 1);
            if (_tweens.length == 0)
                _removeDriver();
            L.debug("已终止");
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        private function _update(dt:Number):void
        {
            if (!_active) return;

            if (delay > 0)
            {
                delay -= dt;
                return;
            }

            _elapsed += dt;
            var t:Number = _elapsed / _duration;
            var finished:Boolean = t >= 1.0;
            if (finished)
            {
                t = 1.0;
                _active = false;
                var idx:int = _tweens.indexOf(this);
                if (idx >= 0) _tweens.splice(idx, 1);
                if (_tweens.length == 0)
                    _removeDriver();
            }

            var et:Number = easing(t);
            for (var prop:String in _props)
            {
                _target[prop] = _starts[prop] + (_props[prop] - _starts[prop]) * et;
            }

            if (onUpdate != null)
                onUpdate();

            if (finished)
            {
                L.debug("完成");
                if (onComplete != null)
                    onComplete();
            }
        }
    }
}
