import threading
from Exceptions import *
from Telegram import *
from Syslog import *
from Task import *


class TelegramClient:
    def __init__(s, conf, recever=None):
        s.conf = conf
        s.log = Syslog("TelegramClient")
        s._lock = threading.Lock()
        s.sq = TelegramClient.SenderQueue()
        s.telegram = Telegram(s.conf)
        s.recever = recever

        s.lastChatMsg = {}
        for chatName, chatInfo in s.chats().items():
            s.lastChatMsg[chatName] = ["", 0]

        s.sendTask = Task('TelegramClient_send')
        s.sendTask.setCb(s.sender)
        s.sendTask.start()

        s.listenerPause = False
        if s.recever:
            s.lastRxIdFile = '.telegram_last_rx_update_id'
            s.recvLastId = int(fileGetContent(s.lastRxIdFile))
            s.listenerTask = Task('TelegramClient_listener')
            s.listenerTask.setCb(s.listener)
            s.listenerTask.start()


    def sender(s):
        while 1:
            if not s.sq.count():
                s.sendTask.waitMessage()

            while 1:
                row = s.sq.pop()
                if not row:
                    break

                chatId, msg, replyToMessageId, disableNotification = row
                while 1:
                    try:
                        s.telegram.send(chatId, msg, replyToMessageId, disableNotification)
                        break
                    except TelegramError:
                        Task.sleep(1000)
                        continue


    def listener(s):
        while 1:
            with s._lock:
                p = s.listenerPause
            if p:
                Task.sleep(300)
                continue

            try:
                rows = s.telegram.recv(s.recvLastId)
            except TelegramError:
                Task.sleep(1000)
                continue

            if not len(rows):
                continue

            for row in rows:
                s.recvLastId = row['updateId']
                s.recever(row['text'], row['msgId'], row['date'],
                          row['fromName'], row['fromId'],
                          row['chatId'], row['chatType'])

            try:
                filePutContent(s.lastRxIdFile, str(s.recvLastId))
            except FileError as e:
                s.log.error("write to '%s' failed: %s" % (s.lastRxIdFile, e))
                # TODO send telegram to admin
                s.listenerPause()


    def listenerPause(s):
        with s._lock:
            s.listenerPause = True


    def listenerResume(s):
        with s._lock:
            s.listenerPause = False


    def send(s, chatId, msg, replyToMessageId=0, disableNotification=False):
        s.sq.push(chatId, msg, replyToMessageId, disableNotification)
        s.sendTask.sendMessage('requestToSend')


    def sendToChat(s, name, srcMsg, replyToMessageId=0,
                   disableNotification=False):
        try:
            with s._lock:
                lastMsg = s.lastChatMsg[name][0]
                cnt = s.lastChatMsg[name][1]
            if srcMsg == lastMsg:
                s.lastChatMsg[name][1] = cnt + 1
                return

            if cnt:
                msg = "Сообщение ниже было отправленно %d раз:\n'%s'\n\n%s" % (
                    cnt, lastMsg, srcMsg)
                with s._lock:
                    s.lastChatMsg[name][1] = 0
            else:
                msg = srcMsg
                with s._lock:
                    s.lastChatMsg[name][0] = msg

            chatId = s.conf['chats'][name]['chatId']
            s.send(chatId, msg, replyToMessageId=0, disableNotification=False)
        except KeyError as e:
            raise TelegramClientError(s.log,
                    "Can't getting chatId by name '%s'. Field '%s' is absent in config" % (name, e))


    def chats(s):
        return s.conf['chats']


    class SenderQueue:
        def __init__(s):
            s.q = []
            s.lock = threading.Lock()


        def push(s, chatId, msg, replyToMessageId, disableNotification):
            with s.lock:
                s.q.append((chatId, msg, replyToMessageId, disableNotification))


        def pop(s):
            with s.lock:
                if not len(s.q):
                    return None
                row = s.q[0]
                s.q.remove(row)
                return row


        def count(s):
            with s.lock:
                return len(s.q)





