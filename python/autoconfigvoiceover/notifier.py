# coding=utf-8
"""
    wot允许在邮件消息中使用HTML超链接标签，但是不会处理单击事件，或者说仅会相应某些链接。
    我引用了KoreanRandom中的解决方案，支持在自定义消息中使用超链接后，可以通过鼠标点击，在外部浏览器中打开网址。
"""
# Web link: https://koreanrandom.com/forum/topic/84763-гайд-вывод-уведомлений-в-игре-мир-танков/#comment-548649
from typing import List, Tuple  # noqa: F401
from Singleton import Singleton
from gui import SystemMessages
from notification.actions_handlers import NotificationsActionsHandlers
from helpers import dependency
from skeletons.gui.shared.utils import IHangarSpace
import BigWorld
# 仅用来将链接信息写入我的日志
from myLogger import MyLogger
mylogger = MyLogger('notifier')

openWebBrowser = BigWorld.wg_openWebBrowser if hasattr(BigWorld, 'wg_openWebBrowser') else BigWorld.openWebBrowser

CUSTOM_EVENT_OPEN_URL = 'CUSTOM_EVENT_OPEN_URL:'


def new_handleAction(obj, *a, **k):
    Notifier.instance().events_handleAction(old_handleAction, obj, *a, **k)


old_handleAction = NotificationsActionsHandlers.handleAction
NotificationsActionsHandlers.handleAction = new_handleAction


class Notifier(Singleton):

    @staticmethod
    def instance():
        return Notifier()

    __isHangarLoaded = False
    __showTimer = None
    __notificationQueue = []  # type: List[Tuple[str, SystemMessages.SM_TYPE, str, any, any]]
    __hangarSpace = dependency.descriptor(IHangarSpace)  # type: IHangarSpace

    def _singleton_init(self):
        self.__hangarSpace.onSpaceCreate += self.__onHangarSpaceCreate
        self.__hangarSpace.onSpaceDestroy += self.__onHangarSpaceDestroy

    def events_handleAction(self, oldHandler, obj, *a, **k):
        try:
            _, _, _, actionName = a
            if actionName.startswith(CUSTOM_EVENT_OPEN_URL):
                target = actionName.split(CUSTOM_EVENT_OPEN_URL)[1]
                print('Opening url %s' % target)
                openWebBrowser(target)
                # 保存链接访问记录
                mylogger.info('打开链接：[%s]' % target)
            else:
                oldHandler(obj, *a, **k)
        except:
            oldHandler(obj, *a, **k)

    def showNotification(self, text, type=SystemMessages.SM_TYPE.Information, priority=None, messageData=None,
                         savedData=None):
        # type: (str, SystemMessages.SM_TYPE, str, any, any) -> None

        if self.__isHangarLoaded:
            print("Showing notification: [%s-%s] %s; Data: %s" % (type, priority, text, messageData))
            SystemMessages.pushMessage(text, type, priority, messageData, savedData)
        else:
            self.__notificationQueue.append((text, type, priority, messageData, savedData))

    def showNotificationFromData(self, message):
        # type: (dict) -> None

        text = message.get('text', None)
        if text is None: return

        self.showNotification(text,
                              SystemMessages.SM_TYPE.of(message.get('type', 'Information')),
                              message.get('priority', None),
                              message.get('messageData', None),
                              message.get('savedData', None))

    def __onHangarSpaceCreate(self):
        if self.__isHangarLoaded: return
        self.__isHangarLoaded = True

        def showNotifications():
            for notification in self.__notificationQueue:
                self.showNotification(notification[0], notification[1], notification[2], notification[3],
                                      notification[4])
            self.__notificationQueue = []
            self.__showTimer = None

        self.__showTimer = BigWorld.callback(1, showNotifications)

    def __onHangarSpaceDestroy(self, *a, **k):
        self.__isHangarLoaded = False
        if self.__showTimer:
            BigWorld.cancelCallback(self.__showTimer)
            self.__showTimer = None

# Usage 1: Notifier.instance().showNotification(text, type, priority, messageData, savedData)
# Usage 2: SystemMessages.pushMessage(text, type, priority, messageData, savedData)
