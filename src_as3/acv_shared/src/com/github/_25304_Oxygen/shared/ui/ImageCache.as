package com.github._25304_Oxygen.shared.ui
{
    import flash.display.Bitmap;
    import flash.display.BitmapData;
    import flash.display.Loader;
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.IOErrorEvent;
    import flash.geom.Point;
    import flash.geom.Rectangle;
    import flash.net.URLRequest;
    import flash.utils.Dictionary;
    import com.github._25304_Oxygen.shared.util.Log;

    /**
     * 全局图片缓存——同一 URL 只加载一次，多个 renderer 共享同一份 BitmapData。
     *
     * 用法:
     *   ImageCache.load("voicepacks/gup/avatar.png", onReady);
     *   function onReady(bmd:BitmapData, success:Boolean):void {
     *       if (success) { ... 使用 bmd ... }
     *   }
     *
     *   // 批量预加载
     *   ImageCache.preload(["url1", "url2"], onAllReady);
     *
     * 核心逻辑:
     *   - 首次请求 → 创建 Loader → 加载中 → 回调排队
     *   - 二次请求同一 URL → 如果已加载: 立即触发回调; 如果加载中: 排队
     *   - 加载失败 → _failed 标记，后续请求不会重试
     */
    public class ImageCache
    {
        /** 模块级日志器 */
        private static const L:Object = Log.getLogger("ImageCache");

        /** 缓存: url → BitmapData */
        private static var _cache:Dictionary = new Dictionary();

        /** 加载中队列: url → {loader:Loader, callbacks:Vector.<Function>} */
        private static var _pending:Dictionary = new Dictionary();

        /** 失败的 url 集合——不重试 */
        private static var _failed:Dictionary = new Dictionary();

        /** Scaleform 中 Loader 必须加入显示列表才能触发加载事件。 */
        private static var _loaderHost:Sprite;

        /**
         * 初始化 Loader 宿主容器。
         * Scaleform 中 Loader 必须加到显示列表才能触发 COMPLETE/IO_ERROR 事件。
         * 调用方必须在获得 stage 引用后调用此方法（MenuView.onPopulate 中）。
         */
        public static function initLoaderHost(stage:Object):void
        {
            if (!_loaderHost)
            {
                _loaderHost = new Sprite();
                _loaderHost.visible = false;
                _loaderHost.mouseEnabled = false;
                _loaderHost.mouseChildren = false;
            }
            if (stage && !_loaderHost.stage)
                stage.addChild(_loaderHost);
            L.info("LoaderHost 已就绪");
        }

        /**
         * 加载图片。加载完成（或命中缓存）后调用 onReady(bitmapData, success)。
         *
         * 路径支持两种写法，最终都以规范化后的 url 作为缓存键:
         *   - VFS 风格: "mods/autoconfigvoiceover/..."（推荐，与 Python 端
         *     ResMgr 路径一致）——自动补 "../../" 转为 SWF 相对路径
         *   - SWF 相对: "../../mods/..."（SWF 位于 res/gui/flash/）
         *
         * @param url      图片路径
         * @param onReady  回调: function(bmd:BitmapData, success:Boolean):void
         *                 已缓存的图 success=true 且同步触发
         */
        public static function load(url:String, onReady:Function):void
        {
            if (!url || url.length == 0)
            {
                L.warn("load: url 为空");
                if (onReady != null) onReady(null, false);
                return;
            }

            // VFS 风格路径自动转换：Loader 以 res/gui/flash/ 为基准目录，
            // "mods/" 开头的路径补 "../../" 回到 res/ 根
            url = normalizeUrl(url);

            // 已缓存 → 立即触发
            if (_cache[url] != null)
            {
                L.debug("缓存命中: " + url);
                if (onReady != null)
                {
                    var bmd:BitmapData = _cache[url] as BitmapData;
                    onReady(bmd, true);
                }
                return;
            }

            // 之前失败过 → 不再重试
            if (_failed[url] != null)
            {
                // DEBUG：首次失败的 WARN 已在 _onError 记录；此路径每次
                // 请求都会重放，降级避免对同一 URL 反复刷屏。
                L.debug("跳过已失败的 URL: " + url);
                if (onReady != null) onReady(null, false);
                return;
            }

            // 正在加载中 → 排队
            if (_pending[url] != null)
            {
                var entry:Object = _pending[url];
                if (onReady != null)
                    entry.callbacks.push(onReady);
                L.debug("加入等待队列: " + url +
                          " (队列 " + entry.callbacks.length + ")");
                return;
            }

            // 首次请求 → 开始加载
            // DEBUG：与"加载成功"成对的起止标记，成功结果已在 INFO 记录。
            L.debug("开始加载: " + url);
            var loader:Loader = new Loader();
            var callbacks:Vector.<Function> = new Vector.<Function>();
            if (onReady != null)
                callbacks.push(onReady);

            _pending[url] = {loader: loader, callbacks: callbacks};

            loader.contentLoaderInfo.addEventListener(Event.COMPLETE, _onComplete);
            loader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, _onError);

            // Scaleform 要求 Loader 必须在显示列表中才能触发加载事件
            if (_loaderHost)
                _loaderHost.addChild(loader);

            loader.load(new URLRequest(url));
        }

        /**
         * 批量预加载。所有图片加载完成后调用 onAllReady()。
         * 已缓存的不重复加载。
         */
        public static function preload(urls:Array, onAllReady:Function = null):void
        {
            if (!urls || urls.length == 0)
            {
                if (onAllReady != null) onAllReady();
                return;
            }

            var remaining:int = urls.length;
            var allDone:Boolean = false;

            function onOneDone(bmd:BitmapData, success:Boolean):void
            {
                if (allDone) return;
                remaining--;
                if (remaining <= 0)
                {
                    allDone = true;
                    L.info("预加载完成: " + urls.length + " 张");
                    if (onAllReady != null) onAllReady();
                }
            }

            for (var i:int = 0; i < urls.length; i++)
            {
                load(urls[i], onOneDone);
            }
        }

        /**
         * 规范化路径——与 load() 使用相同的缓存键格式。
         * VFS 风格路径 "mods/..." → SWF 相对路径 "../../mods/..."
         */
        public static function normalizeUrl(url:String):String
        {
            if (!url || url.length == 0) return url;
            if (url.indexOf("mods/") == 0)
                return "../../" + url;
            return url;
        }

        /** 返回已缓存的 BitmapData，未缓存则返回 null。 */
        public static function getCached(url:String):BitmapData
        {
            return _cache[normalizeUrl(url)] as BitmapData;
        }

        /** 指定 URL 是否已缓存。 */
        public static function has(url:String):Boolean
        {
            return _cache[url] != null;
        }

        /** 清除所有缓存（释放内存）。调用后需重新加载。 */
        public static function clear():void
        {
            // 终止所有加载中的请求
            for (var key:String in _pending)
            {
                var entry:Object = _pending[key];
                try { entry.loader.close(); } catch (e:Error) {}
                entry.callbacks.length = 0;
            }
            _pending = new Dictionary();

            // 释放缓存的 BitmapData
            for (var k:String in _cache)
            {
                var bmd:BitmapData = _cache[k] as BitmapData;
                if (bmd) bmd.dispose();
            }
            _cache = new Dictionary();
            _failed = new Dictionary();
            L.info("已清除全部缓存");
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        private static function _onComplete(event:Event):void
        {
            var info:Object = event.target;
            var loader:Loader = info.loader;
            var url:String = _findUrlByLoader(loader);

            // 提取 BitmapData
            var bmp:Bitmap = loader.content as Bitmap;
            var bmd:BitmapData = null;
            var success:Boolean = false;

            if (bmp)
            {
                bmd = bmp.bitmapData;
                if (bmd)
                {
                    // Scaleform 可能把纹理填充到对齐尺寸（右/下多出透明区），
                    // bitmapData 尺寸虚大会破坏 cover 缩放计算——
                    // 用 contentLoaderInfo 报告的真实图片尺寸裁掉填充区。
                    var realW:int = int(info.width);
                    var realH:int = int(info.height);
                    if (realW > 0 && realH > 0 &&
                        (bmd.width != realW || bmd.height != realH))
                    {
                        // DEBUG：仅 Scaleform 纹理对齐尺寸时触发，属加载细节
                        L.debug("裁剪纹理填充: " + bmd.width + "×" + bmd.height
                            + " → " + realW + "×" + realH);
                        var cropped:BitmapData =
                            new BitmapData(realW, realH, true, 0x00000000);
                        cropped.copyPixels(bmd,
                            new Rectangle(0, 0, realW, realH),
                            new Point(0, 0));
                        bmd.dispose();
                        bmd = cropped;
                    }

                    _cache[url] = bmd;
                    success = true;
                    L.info("加载成功: " + url +
                             " (" + bmd.width + "×" + bmd.height + ")");
                }
                else
                {
                    L.warn("BitmapData 为空 " + url);
                }
            }
            else
            {
                L.warn("非 Bitmap 内容 " + url);
            }

            // 通知所有排队回调
            _notifyCallbacks(url, bmd, success);

            // 清理
            loader.contentLoaderInfo.removeEventListener(Event.COMPLETE, _onComplete);
            loader.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR, _onError);
            if (_loaderHost && loader.parent == _loaderHost)
                _loaderHost.removeChild(loader);
            try { loader.close(); } catch (e:Error) {}
            delete _pending[url];
        }

        private static function _onError(event:IOErrorEvent):void
        {
            var info:Object = event.target;
            var loader:Loader = info.loader;
            var url:String = _findUrlByLoader(loader);

            L.warn("加载失败: " + url);
            _failed[url] = true;

            _notifyCallbacks(url, null, false);

            loader.contentLoaderInfo.removeEventListener(Event.COMPLETE, _onComplete);
            loader.contentLoaderInfo.removeEventListener(IOErrorEvent.IO_ERROR, _onError);
            if (_loaderHost && loader.parent == _loaderHost)
                _loaderHost.removeChild(loader);
            try { loader.close(); } catch (e:Error) {}
            delete _pending[url];
        }

        /** 在 _pending 字典中根据 loader 查找 url。 */
        private static function _findUrlByLoader(loader:Loader):String
        {
            for (var key:String in _pending)
            {
                var entry:Object = _pending[key];
                if (entry.loader == loader)
                    return key;
            }
            return "";
        }

        private static function _notifyCallbacks(url:String, bmd:BitmapData,
                                                  success:Boolean):void
        {
            var entry:Object = _pending[url];
            if (!entry) return;

            var callbacks:Vector.<Function> = entry.callbacks;
            for (var i:int = 0; i < callbacks.length; i++)
            {
                var cb:Function = callbacks[i];
                if (cb != null)
                    cb(bmd, success);
            }
            callbacks.length = 0;
        }
    }
}
