package com.github._25304_Oxygen.menu.pages
{
    import com.github._25304_Oxygen.shared.i18n.L10n;

    /**
     * 帮助页——使用说明，内容由 Python 端推送。
     */
    public class HelpPage extends HtmlContentPage
    {
        public function HelpPage()
        {
            // 标题走词典（i18n）；populate data.title 由 Python 推翻译值
            super("help", L10n.get("help/title", "帮助"), "help/title");
        }
    }
}
