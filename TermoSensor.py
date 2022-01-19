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

        of = open("/sys/bus/w1/devices/%s/temperature" % name, "r")

        for i in range(10):
            of.seek(0)
            val = of.read().strip()
            if not val:
                Task.sleep(100)
                continue

            of.close()
            return float(int(val) / 1000)

        err = "Can't read correct value. val = %d" % val
        s.log.err(err)
        raise TermoSensor.Ex(err)


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
    def byName(name):
        for sensor in TermoSensor.sensors:
            if sensor.name == name:
                return sensor
        return None


