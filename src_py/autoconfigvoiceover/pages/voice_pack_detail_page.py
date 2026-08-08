# coding=utf-8
"""VoicePackDetailPage —— 语音包详情面板。

对应 Flash: com.github._25304_Oxygen.menu.pages.VoicePackDetailPage
入口: 半折叠面板导航按钮 "详情"

用途: 展示单个语音包的详细信息。
Flash 端渲染 HTML，超链接通过 TextEvent.LINK → onLog("htmlLink,...") 回调。
"""

from autoconfigvoiceover.logger import Logger

logger = Logger('VoicePackDetailPage')


class VoicePackDetailPage(object):
    """语音包详情页的业务逻辑。

    Flash 端 HtmlContentPage 负责全部渲染，Python 端仅推送 HTML 内容。
    """

    def __init__(self, meta):
        """
        :param meta: ACVMenuMeta 实例，用于 DAAPI 通信
        """
        self._meta = meta

    # ── 数据推送 ──

    def push_data(self):
        """向 Flash 推送语音包详情页 HTML 内容。

        从当前活跃语音包的 info.html / info.txt 读取内容；
        内置语音或无 info 文件时显示占位提示。
        """
        from autoconfigvoiceover.voices import g_active_mgr

        av = g_active_mgr.current
        if av is not None and av.info_html:
            html = av.info_html
        else:
            # 占位提示走词典（i18n）
            from autoconfigvoiceover import l10n
            html = (
                '<p align="left">'
                + l10n.text('detail/no_info')
                + '</p>'
            )

        from autoconfigvoiceover import l10n
        data = {
            'title': l10n.text('detail/title'),
            'html': html,
        }
        self._meta.as_populatePageS('voicePackDetail', data)
        logger.info('语音包详情页数据已推送')

    # ── 回调处理 ──

    def handle_link(self, payload):
        """用户点击了详情页中的超链接。

        :param payload: href 中 "event:" 后的内容。
                        若为 http/https URL → 浏览器打开；
                        若为命名动作 → 按动作类型分发。
        """
        import BigWorld

        # 直接 URL → 浏览器打开（语音包 info.html 可包含任意外部链接）
        if payload.startswith('http://') or payload.startswith('https://'):
            logger.info('打开外部链接: %s', payload)
            try:
                if hasattr(BigWorld, 'wg_openWebBrowser'):
                    BigWorld.wg_openWebBrowser(payload)
                else:
                    BigWorld.openWebBrowser(payload)
            except Exception:
                logger.exception('打开链接失败: %s', payload)
            return
