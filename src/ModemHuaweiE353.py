import requests, re
from Exceptions import *
from Task import *
from Syslog import *
from SimpleXML import *


class ModemHuaweiE353():
    class RespError(Exception):
        pass

    def __init__(s, conf, smsReceiver=None):
        s.conf = conf
        s.log = Syslog('ModemHuaweiE353')
        s.smsReceiverCb = smsReceiver
        if smsReceiver:
            s.smslistenerTask = Task('ModemHuaweiE353SmsListenerTask', s.listener)
            s.smslistenerTask.start()


    def request(s, method):
        url = 'http://%s:%d%s' % (s.conf['host'], s.conf['port'], method)

        try:
            r = requests.get(url=url, timeout=10)
            data = SimpleXML(r.text)
            try:
                code = data.item('error/code')
                err = "modem response error: %s" % code
                if code == '113018':
                    err = "modem is busy"
                raise ModemHuaweiE353.RespError("POST request %s: %s" % (method, err))
            except SimpleXML.Error:
                pass
            return data
        except requests.exceptions.RequestException as e:
            raise HuaweiModemE353Error(s.log, 'Request method "%s" error: %s' % (method, e)) from e
        except KeyError as e:
            raise HuaweiModemE353Error(s.log, 'Request method "%s" error: Key %s is absent in responce' % (
                                       method, e)) from e


    def postRequest(s, method, request):
        url = 'http://%s%s' % (s.conf['host'], method)

        query = '<?xml version="1.0" encoding="UTF-8"?>' \
                '<request>%s</request>' % request

        try:
            r = requests.post(url=url, data=query, timeout=10,
                          headers={'Content-Type': 'application/x-www-form-urlencoded'})
            data = SimpleXML(r.text)
            try:
                code = data.item('error/code')
                err = "modem response error: %s" % code
                if code == '113018':
                    err = "modem is busy"
                raise ModemHuaweiE353.RespError("POST request %s: %s" % (method, err))
            except SimpleXML.Error:
                pass
            return data

        except requests.exceptions.RequestException as e:
            raise HuaweiModemE353Error(s.log, 'Request method "%s" error: %s' % (method, e)) from e
        except KeyError as e:
            raise HuaweiModemE353Error(s.log, 'Request method "%s" error: Key %s is absent in responce' % (
                                       method, e)) from e


    def smsList(s, boxType):
        # boxType: 1 - incomming, 2 - outgoing
        query = '<PageIndex>1</PageIndex>' \
                '<ReadCount>50</ReadCount>' \
                '<BoxType>%s</BoxType>' \
                '<SortType>0</SortType>' \
                '<Ascending>0</Ascending>' \
                '<UnreadPreferred>0</UnreadPreferred>' % boxType

        try:
            data = s.postRequest('/api/sms/sms-list', query)
            countSms = int(data.item('response/Count'))
            if countSms <= 0:
                return []
            smsListRaw = data.list('response/Messages')
            return list(map(lambda row: row['Message'], smsListRaw))

        except SimpleXML.Error as e:
            raise HuaweiModemE353Error(s.log, "smsList(): modem response incorrect XML: %s" % e) from e
        except ModemHuaweiE353.RespError as e:
            raise HuaweiModemE353Error(s.log, "smsList() error: %s" % e) from e


    def smsIncommingList(s):
        return s.smsList(1)


    def smsOutgoingList(s):
        return s.smsList(2)


    def smsSend(s, pnoneNumber, text):
        # remove stored outgoing sms
        smsList = s.smsOutgoingList()
        if len(smsList):
            for row in smsList:
                smsIndex = row['Index']
                s.smsRemove(smsIndex)

        query =  '<Index>-1</Index>' \
                 '<Phones>' \
                     '<Phone>%s</Phone>' \
                 '</Phones>' \
                 '<Content>%s</Content>' \
                 '<Length>%d</Length>' \
                 '<Reserved>0</Reserved>' \
                 '<Date>111</Date>' % (pnoneNumber, text, len(text))

        try:
            s.postRequest('/api/sms/send-sms', query)
        except ModemHuaweiE353.RespError as e:
            raise HuaweiModemE353Error(s.log, "smsSend() error: %s" % e) from e

        for i in range(30):
            Task.sleep(1000)
            resp = s.request('/api/sms/send-status')
            try:
                Phone = resp.item('response/Phone')
                SucPhone = resp.item('response/SucPhone')
                FailPhone = resp.item('response/FailPhone')
            except SimpleXML.Error as e:
                raise HuaweiModemE353Error(s.log, "smsSend(): incorrect sms " \
                                                  "send-status: %s" % resp.xml()) from e
            if SucPhone == pnoneNumber:
                return
            if FailPhone == pnoneNumber:
                raise HuaweiModemE353Error(s.log, "smsSend(): sms send failed. " \
                                                  "Check sim balance or phone number.")
            if Phone != pnoneNumber:
                raise HuaweiModemE353Error(s.log, "smsSend() error: modem " \
                                                  "not trying to send sms: %s" % resp.xml())

        raise HuaweiModemE353Error(s.log, "smsSend() timeout: sms delivering is not confirmed")


    def smsRemove(s, smsIndex):
        query = '<Index>%s</Index>' % smsIndex
        s.postRequest('/api/sms/delete-sms', query);


    def smsRemoveAll(s):
        smsList = s.smsIncommingList()
        smsList.extend(s.smsOutgoingList())
        if len(smsList):
            for row in smsList:
                smsIndex = row['Index']
                s.smsRemove(smsIndex)


    def ussdRecv(s):
        data = s.request('/api/ussd/get');
        try:
            resp = data.item('response')['content']
            return resp
        except SimpleXML.Error as e:
            raise HuaweiModemE353Error(s.log, "ussdRecv(): modem response incorrect XML: %s" % e) from e
        except KeyError as e:
            raise HuaweiModemE353Error(s.log, "ussdRecv(): modem response " \
                                              "incorrect XML responce: %s" % data.xml()) from e


    def ussdSend(s, text):
        query = '<content>%s</content>' \
                '<codeType>CodeType</codeType>' % text
        s.postRequest('/api/ussd/send', query)


    def ussdRequest(s, text):
        try:
            s.ussdSend(text)
        except ModemHuaweiE353.RespError as e:
            raise HuaweiModemE353Error(s.log, "ussdRequest() error: %s" % e) from e
        err = ""
        for i in range(5):
            Task.sleep(1000)
            try:
                return s.ussdRecv()
            except ModemHuaweiE353.RespError as e:
                err = str(e)
                continue
        raise HuaweiModemE353Error(s.log, "ussdRequest('%s'): 5 attempts exceded " \
                                          "but no success. Error: %s" % (text, err))


    def simBalance(s):
        resp = s.ussdRequest('*100#')
        try:
            balance = re.findall('Balans=([\d\.]+)', resp)[0]
            return float(balance)
        except IndexError:
            raise HuaweiModemE353Error(s.log, "simBalanse(): Can't parse sim balance. " \
                                              "Modem return: %s" % resp)


    def trafficStat(s):
        data = s.request('/api/monitoring/traffic-statistics');
        try:
            return data.item('response')
        except SimpleXML.Error as e:
            raise HuaweiModemE353Error(s.log, "trafficStat(): modem response incorrect XML: %s" % e) from e


    def resetTrafficStatistics(s):
        query = '<ClearTraffic>1</ClearTraffic>';
        try:
             s.postRequest('/api/monitoring/clear-traffic', query)
        except ModemHuaweiE353.RespError as e:
            raise HuaweiModemE353Error(s.log, "resetTrafficStatistics() error: %s" % e) from e


    def stat(s):
        try:
            data = s.request('/api/monitoring/status')
            return data.item('response')
        except SimpleXML.Error as e:
            raise HuaweiModemE353Error(s.log, "stat(): modem response incorrect XML: %s" % e) from e
        except ModemHuaweiE353.RespError as e:
            raise HuaweiModemE353Error(s.log, "stat() error: %s" % e) from e


    def listener(s):
        while 1:
            Task.sleep(1000)
            try:
                smsList = s.smsIncommingList()
            except HuaweiModemE353Error as e:
                continue # TODO
            if not len(smsList):
                continue

            for sms in smsList:
                s.smsReceiverCb(sms)
                s.smsRemove(sms['Index'])



