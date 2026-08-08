package com.github._25304_Oxygen.shared.tween
{
    /**
     * 缓动函数库。
     *
     * 所有函数接受 t ∈ [0, 1]，返回缓动后的值 ∈ [0, 1]。
     * 命名规则: ease + 类型 + In/Out/InOut（InOut 无后缀时默认 t < 0.5 走 In，其余走 Out）。
     *
     * cubicBezier(x1, y1, x2, y2) 返回一个缓动函数，
     * 模拟 CSS transition-timing-function 的三次贝塞尔曲线。
     */
    public class Easing
    {
        // ═══════════════════════════════════════════════════════
        // 线性
        // ═══════════════════════════════════════════════════════

        public static function linear(t:Number):Number
        {
            return t;
        }

        // ═══════════════════════════════════════════════════════
        // Quad
        // ═══════════════════════════════════════════════════════

        public static function easeInQuad(t:Number):Number
        {
            return t * t;
        }

        public static function easeOutQuad(t:Number):Number
        {
            return -t * (t - 2);
        }

        public static function easeInOutQuad(t:Number):Number
        {
            t *= 2;
            if (t < 1) return 0.5 * t * t;
            t--;
            return -0.5 * (t * (t - 2) - 1);
        }

        // ═══════════════════════════════════════════════════════
        // Cubic
        // ═══════════════════════════════════════════════════════

        public static function easeInCubic(t:Number):Number
        {
            return t * t * t;
        }

        public static function easeOutCubic(t:Number):Number
        {
            t--;
            return t * t * t + 1;
        }

        public static function easeInOutCubic(t:Number):Number
        {
            t *= 2;
            if (t < 1) return 0.5 * t * t * t;
            t -= 2;
            return 0.5 * (t * t * t + 2);
        }

        // ═══════════════════════════════════════════════════════
        // Quart
        // ═══════════════════════════════════════════════════════

        public static function easeInQuart(t:Number):Number
        {
            return t * t * t * t;
        }

        public static function easeOutQuart(t:Number):Number
        {
            t--;
            return -(t * t * t * t - 1);
        }

        // ═══════════════════════════════════════════════════════
        // Sine（字幕淡入淡出常用）
        // ═══════════════════════════════════════════════════════

        public static function easeInSine(t:Number):Number
        {
            return 1 - Math.cos(t * Math.PI * 0.5);
        }

        public static function easeOutSine(t:Number):Number
        {
            return Math.sin(t * Math.PI * 0.5);
        }

        public static function easeInOutSine(t:Number):Number
        {
            return -0.5 * (Math.cos(Math.PI * t) - 1);
        }

        // ═══════════════════════════════════════════════════════
        // Expo
        // ═══════════════════════════════════════════════════════

        public static function easeInExpo(t:Number):Number
        {
            return t == 0 ? 0 : Math.pow(2, 10 * (t - 1));
        }

        public static function easeOutExpo(t:Number):Number
        {
            return t == 1 ? 1 : -Math.pow(2, -10 * t) + 1;
        }

        // ═══════════════════════════════════════════════════════
        // Back（超出后回弹——菜单入场效果）
        // ═══════════════════════════════════════════════════════

        private static const BACK_OVERSHOOT:Number = 1.70158;

        public static function easeOutBack(t:Number):Number
        {
            t--;
            return t * t * ((BACK_OVERSHOOT + 1) * t + BACK_OVERSHOOT) + 1;
        }

        // ═══════════════════════════════════════════════════════
        // Elastic（弹性——情绪摇晃效果）
        // ═══════════════════════════════════════════════════════

        public static function easeOutElastic(t:Number):Number
        {
            if (t == 0 || t == 1) return t;
            return Math.pow(2, -10 * t) * Math.sin((t - 0.075) * (2 * Math.PI) / 0.3) + 1;
        }

        // ═══════════════════════════════════════════════════════
        // Bounce
        // ═══════════════════════════════════════════════════════

        public static function easeOutBounce(t:Number):Number
        {
            if (t < 1 / 2.75)
                return 7.5625 * t * t;
            else if (t < 2 / 2.75)
            {
                t -= 1.5 / 2.75;
                return 7.5625 * t * t + 0.75;
            }
            else if (t < 2.5 / 2.75)
            {
                t -= 2.25 / 2.75;
                return 7.5625 * t * t + 0.9375;
            }
            else
            {
                t -= 2.625 / 2.75;
                return 7.5625 * t * t + 0.984375;
            }
        }

        // ═══════════════════════════════════════════════════════
        // 自定义三次贝塞尔
        // ═══════════════════════════════════════════════════════

        /**
         * 生成一个模拟 CSS cubic-bezier(x1, y1, x2, y2) 的缓动函数。
         *
         * 控制点限制: x1, x2 ∈ [0, 1]; y1, y2 无限制（允许 overshoot）。
         * 使用牛顿迭代法求解 x(t) → t，再代入 y(t) 求值。
         *
         * 常用预设:
         *   cubicBezier(0.42, 0, 1, 1)         // ease-in
         *   cubicBezier(0, 0, 0.58, 1)        // ease-out
         *   cubicBezier(0.42, 0, 0.58, 1)     // ease-in-out
         */
        public static function cubicBezier(x1:Number, y1:Number, x2:Number, y2:Number):Function
        {
            // 牛顿迭代求 t 对应的 x 参数
            return function(t:Number):Number
            {
                if (t <= 0) return 0;
                if (t >= 1) return 1;

                // 初始猜测
                var guess:Number = t;
                for (var i:int = 0; i < 8; i++)
                {
                    var x:Number = _sampleCurveX(x1, x2, guess) - t;
                    if (Math.abs(x) < 0.001) break;
                    guess -= x / _sampleCurveDerivativeX(x1, x2, guess);
                }
                return _sampleCurveY(y1, y2, guess);
            };
        }

        private static function _sampleCurveX(x1:Number, x2:Number, t:Number):Number
        {
            var u:Number = 1 - t;
            return 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t;
        }

        private static function _sampleCurveY(y1:Number, y2:Number, t:Number):Number
        {
            var u:Number = 1 - t;
            return 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t;
        }

        private static function _sampleCurveDerivativeX(x1:Number, x2:Number, t:Number):Number
        {
            var u:Number = 1 - t;
            return 3 * u * u * x1 + 6 * u * t * (x2 - x1) + 3 * t * t * (1 - x2);
        }
    }
}