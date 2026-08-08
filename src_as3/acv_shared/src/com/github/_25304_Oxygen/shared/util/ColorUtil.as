package com.github._25304_Oxygen.shared.util
{
    /**
     * 颜色工具——解析各种格式的颜色字符串为 uint。
     *
     * 支持格式: 0xFFCC00 / 0xffcc00 / #FFCC00 / FFCC00 / undefined / null
     */
    public class ColorUtil
    {
        /**
         * @param value      颜色字符串或数字，null/undefined 返回 defaultVal
         * @param defaultVal  解析失败时的默认值
         * @return uint 颜色值
         */
        public static function parse(value:*, defaultVal:uint = 0xFFFFFF):uint
        {
            if (value == null)
                return defaultVal;

            var s:String = String(value);
            if (s.indexOf("0x") == 0 || s.indexOf("0X") == 0)
                s = s.substring(2);
            if (s.indexOf("#") == 0)
                s = s.substring(1);

            var result:uint = parseInt("0x" + s);
            return isNaN(result) ? defaultVal : result;
        }
    }
}
