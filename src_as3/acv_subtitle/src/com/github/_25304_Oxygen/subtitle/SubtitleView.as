package com.github._25304_Oxygen.subtitle
{
    import flash.display.Sprite;
    import flash.events.Event;
    import flash.events.MouseEvent;

    import net.wg.infrastructure.base.AbstractView;

    import com.github._25304_Oxygen.shared.util.Log;
    import com.github._25304_Oxygen.shared.tween.Tween;
    import com.github._25304_Oxygen.shared.ui.ImageCache;

    /**
     * 字幕主视图 — 接收 Python 端 SubtitleManager 的 6 条命令，
     * 管理 SubtitleRenderer 集合，将高度上报和淡出完成回调转发给 Python。
     *
     * 命令（6 条，由 Python dispatcher 分别调用）:
     *   as_create(id, data)         — 创建 renderer，播入场动画
     *   as_updateContent(id, data)  — 替换内容，跳过入场，重置打字机+额外动画
     *   as_shiftUp(id, distance)    — renderer 上移 N px
     *   as_shiftDown(id, distance)  — renderer 下移 N px
     *   as_fadeOut(id)              — 淡出 → 销毁 → 回调 Python onFadeOutDone
     *   as_clearAll()               — 立即清除全部 renderer
     *
     * 回调（2 条 → Python）:
     *   onSubtitleCallback("onReportHeight", id, height)
     *   onSubtitleCallback("onFadeOutDone", id, 0)
     *
     * 回调机制: public var onSubtitleCallback:Function 保持 null，
     * GFx 在调用 null Function 时自动回退到 script.onSubtitleCallback()，
     * 从而路由到 Python View 实例的同名方法。
     *
     * 容器定位: 屏幕底部居中。y 坐标为 stage.stageHeight - 80（默认）。
     * 未来可通过 as_setPosition 或 Python 配置扩展。
     */
    public class SubtitleView extends AbstractView
    {
        /** 模块级日志器 */
        private static const L:Object = Log.getLogger("SubtitleView");

        // ═══════════════════════════════════════════════════════
        // Python 回调（GFx 回退机制）
        // ═══════════════════════════════════════════════════════

        /**
         * 字幕回调 → Python。
         * 保持 null，由 GFx 在调用时回退到 script.onSubtitleCallback()。
         *
         * 调用签名:
         *   onSubtitleCallback(cmd:String, id:int, value:Number):void
         *
         * cmd 取值:
         *   "onReportHeight"  — renderer 上报实际像素高度（value=height）
         *   "onFadeOutDone"   — renderer 淡出完成，已从显示列表移除（value=0）
         */
        public var onSubtitleCallback:Function;

        /**
         * 拖拽偏移回调 → Python（GFx 回退机制）。
         * 保持 null，由 GFx 在调用时回退到 script.onEditOffset()。
         *
         * 调用签名: onEditOffset(target:String, x:Number, y:Number):void
         *   target — 组件名（poster / tf_title / background / tf_message）
         *   x, y   — 拖拽后的累积偏移（px）
         */
        public var onEditOffset:Function;

        // ═══════════════════════════════════════════════════════
        // 字幕管理
        // ═══════════════════════════════════════════════════════

        /** 活跃 renderer 集合: {id(int): SubtitleRenderer}。 */
        private var _renderers:Object;

        /** 字幕容器——所有 SubtitleRenderer 的 parent。 */
        private var _container:Sprite;

        /** 容器默认底边距（px）。 */
        private static const BOTTOM_MARGIN:Number = 80;

        // ═══════════════════════════════════════════════════════
        // 预览编辑模式
        // ═══════════════════════════════════════════════════════

        /** 预览用的静态 renderer。 */
        private var _previewRenderer:SubtitleRenderer;

        /** 是否正在显示预览。 */
        private var _previewActive:Boolean = false;

        /** 当前编辑目标组件名。 */
        private var _editTarget:String = null;

        /** 原始样式位置（偏移前），用于拖拽后计算纯偏移。{key: [x, y]} */
        private var _previewStylePos:Object = null;

        // 拖拽状态
        private var _dragActive:Boolean = false;
        private var _dragStartMouseX:Number = 0;
        private var _dragStartMouseY:Number = 0;
        private var _dragStartCompX:Number = 0;
        private var _dragStartCompY:Number = 0;

        // ═══════════════════════════════════════════════════════
        // 生命周期
        // ═══════════════════════════════════════════════════════

        public function SubtitleView()
        {
            super();
            _renderers = {};
            L.info("构造");
        }

        override protected function onPopulate():void
        {
            super.onPopulate();

            // 初始化公共引擎
            Tween.init(stage);
            ImageCache.initLoaderHost(stage);

            // 创建字幕容器
            _container = new Sprite();
            _container.mouseChildren = false;
            _container.mouseEnabled = false;
            addChild(_container);

            // 定位容器
            _positionContainer();

            // 响应窗口大小变化
            stage.addEventListener(Event.RESIZE, _onStageResize);

            L.info("onPopulate — stage: " +
                       stage.stageWidth + "×" + stage.stageHeight);
        }

        override protected function onDispose():void
        {
            L.info("onDispose");

            stage.removeEventListener(Event.RESIZE, _onStageResize);

            // 清理预览（含 stage 鼠标监听）
            _hidePreviewInternal();

            // 清理所有 renderer
            for (var key:String in _renderers)
            {
                var r:SubtitleRenderer = _renderers[key] as SubtitleRenderer;
                if (r)
                    r.disposeRenderer();
            }
            _renderers = {};

            Tween.kill(_container);
            Tween.dispose();
            ImageCache.clear();

            super.onDispose();
        }

        // ═══════════════════════════════════════════════════════
        // DAAPI: Python → Flash（6 条命令）
        // ═══════════════════════════════════════════════════════

        /**
         * 创建新字幕 renderer。
         * @param id    唯一 ID（由 Python 端分配）
         * @param data  渲染数据（见 manager._assemble_data 产出结构）
         */
        public function as_create(id:int, data:Object):void
        {
            if (!data)
            {
                L.warn("as_create: data 为空 id=" + id);
                return;
            }

            // 同 ID 已存在 → 覆盖（防御性处理）
            var old:SubtitleRenderer = _renderers[id];
            if (old)
            {
                L.warn("as_create: id=" + id + " 已存在，覆盖旧 renderer");
                old.disposeRenderer();
            }

            var r:SubtitleRenderer = new SubtitleRenderer(id, data, this);
            _renderers[id] = r;
            _container.addChild(r);

            // 初始位置: 容器底部（新字幕总是出现在最下方）
            r.x = 0;
            r.y = 0;

            r.show();
            L.debug("create: id=" + id + " mode=" + (data.mode || "standard"));
        }

        /**
         * 更新已有 renderer 的内容（同角色连续台词）。
         * @param id    目标 renderer ID
         * @param data  新渲染数据
         */
        public function as_updateContent(id:int, data:Object):void
        {
            if (!data)
            {
                L.warn("as_updateContent: data 为空 id=" + id);
                return;
            }

            var r:SubtitleRenderer = _renderers[id] as SubtitleRenderer;
            if (!r)
            {
                L.warn("as_updateContent: id=" + id + " 不存在");
                return;
            }

            r.updateContent(data);
            L.debug("update_content: id=" + id);
        }

        /**
         * renderer 上移指定像素。
         * @param id       目标 renderer ID
         * @param distance 上移距离（px，正值）
         */
        public function as_shiftUp(id:int, distance:Number):void
        {
            var r:SubtitleRenderer = _renderers[id] as SubtitleRenderer;
            if (!r) return;

            r.shift(-Math.abs(distance));
            L.debug("shift_up: id=" + id + " distance=" + distance.toFixed(0));
        }

        /**
         * renderer 下移指定像素。
         * @param id       目标 renderer ID
         * @param distance 下移距离（px，正值）
         */
        public function as_shiftDown(id:int, distance:Number):void
        {
            var r:SubtitleRenderer = _renderers[id] as SubtitleRenderer;
            if (!r) return;

            r.shift(Math.abs(distance));
            L.debug("shift_down: id=" + id + " distance=" + distance.toFixed(0));
        }

        /**
         * renderer 淡出 → 销毁 → 回调 Python onFadeOutDone。
         * @param id 目标 renderer ID
         */
        public function as_fadeOut(id:int):void
        {
            var r:SubtitleRenderer = _renderers[id] as SubtitleRenderer;
            if (!r) return;

            r.fadeOut();
            L.debug("fade_out: id=" + id);
        }

        /** 立即清除全部 renderer（不播动画）。 */
        public function as_clearAll():void
        {
            // DEBUG：战斗/切场景时的例行清理，逐次记录属诊断级
            L.debug("clear_all");
            _clearAllInternal();
        }

        /**
         * 批量预加载图片——样式图片提前加载到 ImageCache，
         * 后续 create / updateContent 中 BitmapContainer 命中缓存，避免加载延迟。
         * @param urls  VFS 风格路径数组（如 ["mods/voiceover/pack/subtitles/images/a.png", ...]）
         */
        public function as_preloadImages(urls:Array):void
        {
            if (!urls || urls.length == 0) return;
            L.info("预加载 " + urls.length + " 张图片");
            ImageCache.preload(urls);
        }

        // ═══════════════════════════════════════════════════════
        // DAAPI: 字幕位置编辑预览
        // ═══════════════════════════════════════════════════════

        /**
         * 显示字幕位置编辑的静态预览。
         * @param data    渲染数据（同 as_create，含 preview:true）
         * @param offsets 各组件偏移 {poster/tf_title/background/tf_message: {x, y}}
         */
        public function as_showPreview(data:Object, offsets:Object):void
        {
            L.info("showPreview");

            // 清除旧预览
            _hidePreviewInternal();

            if (!data)
            {
                L.warn("as_showPreview: data 为空");
                return;
            }

            // 将 offsets 叠加到各组件 position 上
            _applyOffsets(data, offsets);

            // 创建静态预览 renderer
            var r:SubtitleRenderer = new SubtitleRenderer(-1, data, this);
            _previewRenderer = r;
            _previewActive = true;

            _container.addChild(r);
            r.x = 0;
            r.y = 0;

            // 静态显示（跳过动画、绘制编辑边框）
            r.showStatic();

            // 临时启用容器鼠标事件（预览拖拽需要）
            _container.mouseChildren = true;
            _container.mouseEnabled = true;

            // 监听 stage 鼠标事件（拖拽用）。
            // Scaleform 中 View 被加载后 stage 有时尚未就绪（取决于加载时序），
            // 若 stage 为 null 则跳过拖拽监听——预览仍可显示，仅拖拽功能不可用。
            if (stage)
            {
                stage.addEventListener(MouseEvent.MOUSE_DOWN, _onPreviewMouseDown);
            }
            else
            {
                L.warn("as_showPreview: stage 为 null，跳过拖拽监听");
            }

            L.debug("预览已显示");
        }

        /** 隐藏字幕位置编辑的静态预览。 */
        public function as_hidePreview():void
        {
            L.info("hidePreview");
            _hidePreviewInternal();
        }

        /**
         * 设置当前编辑目标组件。
         * @param target poster / tf_title / background / tf_message
         */
        public function as_setEditTarget(target:String):void
        {
            L.info("setEditTarget: " + target);
            _editTarget = target;

            if (_previewRenderer)
                _previewRenderer.setEditTarget(target);
        }

        // ═══════════════════════════════════════════════════════
        // 子 renderer 回调（由 SubtitleRenderer 调用 → 转发 Python）
        // ═══════════════════════════════════════════════════════

        /**
         * renderer 上报实际像素高度。
         * 由 SubtitleRenderer 在入场动画完成后调用。
         */
        internal function onRendererHeight(rid:int, height:Number):void
        {
            L.debug("height report: id=" + rid + " h=" + height.toFixed(0));
            onSubtitleCallback("onReportHeight", rid, height);
        }

        /**
         * renderer 淡出完成。
         * 由 SubtitleRenderer 在淡出动画结束后调用。
         * 从字典和显示列表中移除该 renderer。
         */
        internal function onRendererFadeOutDone(rid:int):void
        {
            L.debug("fade out done: id=" + rid);

            var r:SubtitleRenderer = _renderers[rid] as SubtitleRenderer;
            if (r)
            {
                if (r.parent) r.parent.removeChild(r);
                delete _renderers[rid];
            }

            onSubtitleCallback("onFadeOutDone", rid, 0);
        }

        // ═══════════════════════════════════════════════════════
        // 定位
        // ═══════════════════════════════════════════════════════

        /** 容器定位: 屏幕底部居中。 */
        private function _positionContainer():void
        {
            if (!stage || !_container) return;

            _container.x = int(stage.stageWidth / 2);
            _container.y = stage.stageHeight - BOTTOM_MARGIN;

            L.debug("容器定位: (" + _container.x + "," + _container.y + ")");
        }

        private function _onStageResize(event:Event):void
        {
            L.debug("resize: " + stage.stageWidth + "×" + stage.stageHeight);
            _positionContainer();
        }

        // ═══════════════════════════════════════════════════════
        // 内部
        // ═══════════════════════════════════════════════════════

        /** 立即清除全部 renderer（不播动画，不触发回调）。 */
        private function _clearAllInternal():void
        {
            _hidePreviewInternal();

            for (var key:String in _renderers)
            {
                var r:SubtitleRenderer = _renderers[key] as SubtitleRenderer;
                if (r)
                    r.disposeRenderer();
            }
            _renderers = {};
        }

        // ═══════════════════════════════════════════════════════
        // 预览编辑模式：内部
        // ═══════════════════════════════════════════════════════

        /**
         * 将偏移叠加到各组件 style 位置。
         *
         * 标准模式: 修改 data 中 poster/background/tf_title/tf_message 的
         *           position 字段。
         * 简洁模式: 修改 data.concise.position。
         *
         * 同时保存原始样式位置到 _previewStylePos，供拖拽后计算纯偏移。
         */
        private function _applyOffsets(data:Object, offsets:Object):void
        {
            if (!offsets) return;

            _previewStylePos = {};

            // —— 简洁模式：偏移叠加到 data.concise.position ——
            if (data.mode == "concise" && data.concise)
            {
                var offConcise:Object = offsets["simple_mode"];
                var cPos:Array = data.concise.position;
                if (offConcise && cPos && cPos.length >= 2)
                {
                    _previewStylePos["tf_message"] = [Number(cPos[0]), Number(cPos[1])];

                    data.concise.position = [
                        Number(cPos[0]) + Number(offConcise.x || 0),
                        Number(cPos[1]) + Number(offConcise.y || 0),
                    ];
                }
                return;
            }

            // —— 标准模式：四个组件各自叠加 ——
            var keys:Array = ["poster", "background", "tf_title", "tf_message"];
            for each (var key:String in keys)
            {
                var comp:Object = data[key];
                var off:Object = offsets[key];
                if (!comp || !off) continue;

                var pos:Array = comp.position;
                if (pos && pos.length >= 2)
                {
                    // 保存原始样式位置（用于拖拽后计算纯偏移 = 最终位置 - 原始位置）
                    _previewStylePos[key] = [Number(pos[0]), Number(pos[1])];

                    comp.position = [
                        Number(pos[0]) + Number(off.x || 0),
                        Number(pos[1]) + Number(off.y || 0),
                    ];
                }
            }
        }

        /** 清除预览 renderer 及相关状态。 */
        private function _hidePreviewInternal():void
        {
            // 移除 stage 鼠标监听
            if (stage)
            {
                stage.removeEventListener(MouseEvent.MOUSE_DOWN, _onPreviewMouseDown);
                stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onPreviewMouseMove);
                stage.removeEventListener(MouseEvent.MOUSE_UP, _onPreviewMouseUp);
            }

            // 还原容器鼠标状态
            if (_container)
            {
                _container.mouseChildren = false;
                _container.mouseEnabled = false;
            }

            // 销毁预览 renderer
            if (_previewRenderer)
            {
                _previewRenderer.disposeRenderer();
                _previewRenderer = null;
            }

            _previewActive = false;
            _editTarget = null;
            _previewStylePos = null;
            _dragActive = false;
        }

        // ═══════════════════════════════════════════════════════
        // 预览编辑模式：鼠标拖拽
        // ═══════════════════════════════════════════════════════

        /** MOUSE_DOWN：开始拖拽选中的组件。 */
        private function _onPreviewMouseDown(e:MouseEvent):void
        {
            if (!_previewActive || !_editTarget || !_previewRenderer) return;

            // 只有点击激活组件自身的包围盒才进入拖拽，避免误触空白区域
            if (!_previewRenderer.componentHitTest(
                    _editTarget, stage.mouseX, stage.mouseY))
            {
                L.debug("拖拽忽略: 点击不在激活组件内");
                return;
            }

            // 记录起始位置
            _dragActive = true;
            _dragStartMouseX = stage.mouseX;
            _dragStartMouseY = stage.mouseY;
            _dragStartCompX = _previewRenderer.getComponentX(_editTarget);
            _dragStartCompY = _previewRenderer.getComponentY(_editTarget);

            // 开始监听 MOVE / UP
            stage.addEventListener(MouseEvent.MOUSE_MOVE, _onPreviewMouseMove);
            stage.addEventListener(MouseEvent.MOUSE_UP, _onPreviewMouseUp);

            L.debug("拖拽开始: " + _editTarget
                    + " mouse=(" + _dragStartMouseX.toFixed(0) + "," + _dragStartMouseY.toFixed(0) + ")"
                    + " comp=(" + _dragStartCompX.toFixed(0) + "," + _dragStartCompY.toFixed(0) + ")");
        }

        /** MOUSE_MOVE：实时移动组件。 */
        private function _onPreviewMouseMove(e:MouseEvent):void
        {
            if (!_dragActive || !_previewRenderer) return;

            var dx:Number = stage.mouseX - _dragStartMouseX;
            var dy:Number = stage.mouseY - _dragStartMouseY;

            _previewRenderer.setComponentPosition(
                _editTarget,
                _dragStartCompX + dx,
                _dragStartCompY + dy);
        }

        /** MOUSE_UP：停止拖拽，计算纯偏移并发给 Python。 */
        private function _onPreviewMouseUp(e:MouseEvent):void
        {
            if (!_dragActive) return;

            stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onPreviewMouseMove);
            stage.removeEventListener(MouseEvent.MOUSE_UP, _onPreviewMouseUp);

            _dragActive = false;

            if (!_previewRenderer)
            {
                L.debug("拖拽结束: renderer 已销毁");
                return;
            }

            var finalX:Number = _previewRenderer.getComponentX(_editTarget);
            var finalY:Number = _previewRenderer.getComponentY(_editTarget);

            // 计算纯偏移 = 最终位置 - 原始样式位置
            var origPos:Array = _previewStylePos ? _previewStylePos[_editTarget] : null;
            var offsetX:Number = finalX - (origPos ? origPos[0] : 0);
            var offsetY:Number = finalY - (origPos ? origPos[1] : 0);

            L.debug("拖拽结束: " + _editTarget
                    + " final=(" + finalX.toFixed(0) + "," + finalY.toFixed(0) + ")"
                    + " offset=(" + offsetX.toFixed(0) + "," + offsetY.toFixed(0) + ")");

            // 回调 Python（GFx 回退机制: onEditOffset 为 null → script.onEditOffset）
            if (onEditOffset != null)
                onEditOffset(_editTarget, int(offsetX), int(offsetY));
        }
    }
}
