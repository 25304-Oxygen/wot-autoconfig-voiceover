package com.github._25304_Oxygen.shared.util
{
    /**
     * 轻量 JSON 序列化——绕开 playerglobal 与 SWC 同名 JSON 类冲突。
     *
     * 仅支持 Object (字符串键)、Array、String、Boolean、Number、null。
     * 不支持循环引用、Date、自定义类。
     *
     * 用法: JsonWriter.write({state: "COLLAPSED", count: 3})
     * 输出: {"state":"COLLAPSED","count":3}
     */
    public class JsonWriter
    {
        /** 将简单对象/数组序列化为 JSON 字符串。 */
        public static function write(value:*):String
        {
            if (value == null)
                return "null";

            if (value is String)
                return '"' + _escape(String(value)) + '"';

            if (value is Boolean || value is Number)
                return String(value);

            if (value is Array)
                return _writeArray(value as Array);

            // 兜底: 当作 Object 处理
            return _writeObject(value);
        }

        // ── 内部 ──

        private static function _writeObject(obj:Object):String
        {
            var parts:Array = [];
            for (var key:String in obj)
            {
                var val:* = obj[key];
                if (val == undefined)
                    continue;
                parts.push('"' + _escape(key) + '":' + write(val));
            }
            return "{" + parts.join(",") + "}";
        }

        private static function _writeArray(arr:Array):String
        {
            var parts:Array = [];
            for (var i:int = 0; i < arr.length; i++)
            {
                parts.push(write(arr[i]));
            }
            return "[" + parts.join(",") + "]";
        }

        private static function _escape(s:String):String
        {
            var out:String = "";
            for (var i:int = 0; i < s.length; i++)
            {
                var ch:String = s.charAt(i);
                switch (ch)
                {
                    case '"':  out += '\\"';  break;
                    case '\\': out += '\\\\'; break;
                    case '\n': out += '\\n';  break;
                    case '\r': out += '\\r';  break;
                    case '\t': out += '\\t';  break;
                    default:   out += ch;     break;
                }
            }
            return out;
        }
    }
}
