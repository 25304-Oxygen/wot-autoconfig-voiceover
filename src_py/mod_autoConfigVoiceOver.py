from autoconfigvoiceover import g_autoConfigVoiceOverMod


def init():
    g_autoConfigVoiceOverMod.init()


def fini():
    g_autoConfigVoiceOverMod.fini()


def onAccountBecomePlayer():
    g_autoConfigVoiceOverMod.on_account_become_player()
