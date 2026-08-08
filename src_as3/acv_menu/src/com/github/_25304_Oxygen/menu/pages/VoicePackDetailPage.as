package com.github._25304_Oxygen.menu.pages
{
    import com.github._25304_Oxygen.shared.i18n.L10n;

    /**
     * 语音包详情页——当前语音包信息，内容由 Python 端推送。
     */
    public class VoicePackDetailPage extends HtmlContentPage
    {
        public function VoicePackDetailPage()
        {
            // 标题走词典（i18n）；populate data.title 由 Python 推翻译值
            super("voicePackDetail", L10n.get("detail/title", "语音包详情"), "detail/title");
        }
    }
}
