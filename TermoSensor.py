import re, os
from Task import *
from common import *
from Syslog import *


class TermoSensor():
    sensors = []
    class Ex(Exception):
        pass

    def __init__(s, name):
        s.name = name
        s.log = Syslog("termo_sensor_%s" % name)
        s._fake = None
        s.lock = threading.Lock()

        if os.path.exists('FAKE'):
            s._fake = True

        if s._fake:
            s._fakeFileName = 'FAKE/%s' % name
            if not os.path.exists(s._fakeFileName):
                filePutContent(s._fakeFileName, "18.0")
            return


    def t(s):
        if s._fake:
            return float(fileGetContent(s._fakeFileName))

        with s.lock:
            try:
                of = open("/sys/bus/w1/devices/%s/w1_slave" % s.name, "r")
                for i in range(10):
                    of.seek(0)
                    c = of.read().strip()
                    res = re.search("t=([\d-]+)", c)
                    if not res:
                        Task.sleep(100)
                        continue
                    temperature = float(res.groups()[0]) / 1000.0
                    of.close()
                    return temperature
            except Exception as e:
                err = "Can't read termosensor, reason: %s" % e
                s.log.err(err)

        raise TermoSensor.Ex(err)


    def __str__(s):
        return "%s: %.1f" % (s.name, s.t())


    @staticmethod
    def list():
        if os.path.exists('FAKE'):
            list = os.listdir('FAKE/')
        else:
            list = os.listdir('/sys/bus/w1/devices')

        for f in list:
            res = re.search("^\d{2}-[\dabcdef]+", f)
            if not res:
                continue
            name = res.group()
            if TermoSensor.byName(name):
                continue

            s = TermoSensor(name)
            TermoSensor.sensors.append(s)
        return TermoSensor.sensors


    @staticmethod
    def printList():
        list = TermoSensor.list()
        print("Termosensors list:")
        for sensor in list:
            print("\t%s" % sensor)


    @staticmethod
    def byName(name):
        for sensor in TermoSensor.sensors:
            if sensor.name == name:
                return sensor
        return None


