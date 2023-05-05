from ModemHuaweiE353 import *
from Exceptions import *
from HttpServer import *


class GsmModem():
    def __init__(s, mbio):
        s.mbio = mbio
        s.conf = mbio.conf.mbio
        s.sn = mbio.sn
        s.dev = ModemHuaweiE353(s.conf['modemHuaweiE353'], s.smsListener)
        s.httpHandlers = GsmModem.HttpHandlers(s, mbio.httpServer)


    def smsListener(s, sms):
        s.sn.notify('sms',
                    {'phone': sms['Phone'],
                     'text': sms['Content'],
                     'date': sms['Date']})
        s.bla = sms['Content']
        print(sms)


    class HttpHandlers():
        def __init__(s, modem, httpServer):
            s.modem = modem
            s.mbio = modem.mbio
            s.httpServer = httpServer
            s.httpServer.setReqHandler("POST", "/modem/sms_send",
                                       s.smsSendHandler)
            s.httpServer.setReqHandler("GET", "/modem/balance",
                                       s.balanceHandler)
            s.httpServer.setReqHandler("GET", "/modem/stat",
                                       s.statHandler)


        def smsSendHandler(s, args, conn):
            try:
                req = conn.bodyJson()
                phone = req['phone']
                msg = req['message']
                s.modem.dev.smsSend(phone, msg)
            except HuaweiModemE353Error as e:
               raise HttpHandlerError(e)
            except HttpConnectionBodyError as e:
                raise HttpHandlerError("Incorrect json body format: %s" % e)


        def balanceHandler(s, args, conn):
            try:
                return {"balance": s.modem.dev.simBalance()}
            except HuaweiModemE353Error as e:
               raise HttpHandlerError(e)


        def statHandler(s, args, conn):
            try:
                return {"stat": s.modem.dev.stat()}
            except HuaweiModemE353Error as e:
               raise HttpHandlerError(e)

