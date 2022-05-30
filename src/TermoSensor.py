import re, os
from Task import *
from common import *
from Syslog import *
from AveragerQueue import *


class TermoSensor():
    def __init__(s, addr):
        s._addr = addr
        s.log = Syslog("termo_sensor_%s" % addr)
        s.lock = threading.Lock()
        s._fake = None
        s._t = None
        s.queue = AveragerQueue(5)

        s.task = Task("termo_sensor_%s" % addr)
        s.task.setCb(s.do)
        s.task.start()

        if os.path.exists('FAKE'):
            s._fake = True

        if s._fake:
            s._fakeFileName = 'FAKE/%s' % addr
            if not os.path.exists(s._fakeFileName):
                filePutContent(s._fakeFileName, "18.0")
            return


    def addr(s):
        return s._addr


    def t(s):
        if s._fake:
            return float(fileGetContent(s._fakeFileName))
        with s.lock:
            return s._t


    def do(s):
        while True:
            Task.sleep(1000)
            try:
                of = open("/sys/bus/w1/devices/%s/w1_slave" % s._addr, "r")
                for i in range(10):
                    of.seek(0)
                    c = of.read().strip()
                    res = re.search("t=([\d-]+)", c)
                    if not res:
                        Task.sleep(100)
                        continue
                    t = float(res.groups()[0]) / 1000.0
                    with s.lock:
                        s.queue.push(t)
                        s._t = s.queue.round()
                of.close()
            except Exception as e:
                err = "Can't read termosensor, reason: %s" % e
                s.log.err(err)
                with s.lock:
                    s._t = None
                Task.sleep(30000) # TODO


    def destroy(s):
        if s.task:
            s.task.remove()


    def __repr__(s):
        return "t:%s" % s._addr


    def __str__(s):
        return "%s:%.1f" % (s._addr, s.t())




