import requests
from Exceptions import *
from Syslog import *


class Telegram():
    def __init__(s, conf):
        s.conf = conf
        s.log = Syslog('Telegram')


    def request(s, methodName, args):
        url = 'https://api.telegram.org/bot%s/%s' % (s.conf['token'], methodName)

        try:
            r = requests.post(url=url, data=args, timeout=4,
                          headers={'Content-Type': 'application/x-www-form-urlencoded'})
            return r.json()
        except requests.exceptions.RequestException as e:
            raise TelegramError(s.log, 'Request method "%s" error: %s' % (methodName, e)) from e


    def send(s, chatId, text, replyToMessage_id=0,
                    disableNotification=False):
        text = text.strip()
        if not text:
            return

        args = {'chat_id': chatId, 'text': text}
        if replyToMessage_id:
            args['reply_to_message_id'] = replyToMessage_id
        if disableNotification:
            args['disable_notification'] = disableNotification
        try:
            resp = s.request('sendMessage', args);
            if resp['ok'] != 1:
                raise TelegramError(s.log,
                        'Method sendMessage return responce with incorrect "ok" value: %s' % resp) from e
        except TypeError as e:
            raise TelegramError(s.log,
                    'Method sendMessage return JSON with absent field: %s' % e) from e


    def recv(s, fromUpdateId):
        resp = s.request('getUpdates',
                         {'offset': int(fromUpdateId) + 1,
                          'limit': 30,
                          'timeout': 1})

        try:
            if resp['ok'] != 1:
                s.log.err("recvMessages(): responce for POST request error: ok=%s" % resp['ok'])
                return []

            if not len(resp['result']):
                return []
        except TypeError as e:
            raise TelegramError(s.log,
                        'Method recvMessages return JSON with absent field: %s' % e) from e

        list = [];
        for row in resp['result']:
            if 'update_id' not in row:
                continue

            if 'message' not in row:
                continue

            if 'text' not in row['message']:
                continue

            msg = {'updateId': row['update_id'],
                   'msgId':    row['message']['message_id'],
                   'date':     row['message']['date'],
                   'fromName': row['message']['from']['first_name'],
                   'fromId':   row['message']['from']['id'],
                   'chatId':   row['message']['chat']['id'],
                   'chatType': row['message']['chat']['type'],
                   'text':     row['message']['text']}

            if row['message']['chat']['type'] == 'private':
                msg['chatName'] = row['message']['chat']['first_name']
            else:
                msg['chatName'] = row['message']['chat']['title']

            list.append(msg)
        return list


