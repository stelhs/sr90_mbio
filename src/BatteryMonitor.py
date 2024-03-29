import os, re, json
from Task import *
from AveragerQueue import *
from Storage import *


class BatteryMonitor():
    def __init__(s, mbio):
        s.mbio = mbio
        s.conf = mbio.conf.mbio['batteryMonitor']
        s.lock = threading.Lock()
        s._voltage = None
        s._current = None
        s._prevVoltage = None
        s._prevCurrent = None

        s.storage = Storage('battery_monitor.json', s.conf['storageDir'])
        s.currentOffset = s.storage.key('/currentOffset', 2831)

        if not s.conf["enabled"]:
            return

        s.voltageQueue = AveragerQueue(10)
        s.currentRawQueue = AveragerQueue(5)
        s.skynetUpdater = s.mbio.periodicNotifier.register("battery", s.skynetUpdateHandler, 2000)

        s.task = Task('battery_monitor')

        if s.conf["emulate"]:
            s.task.setFn(s.emulateDo)
            s.task.start()
            return

        s.task.setFn(s.do)
        s.task.start()


    def do(s):
        v_step = 12.91 / 3089
        c_step = 3.5 / 820
        v = None
        c = None
        while True:
            try:
                with open('/dev/ttyUSB0') as f:
                    for line in f:
                        if v and c:
                            break

                        m = re.search('CH3:([0-9]+)', line)
                        if m:
                            val = int(m.groups()[0])
                            v = round(val * v_step, 2)
                            continue

                        m = re.search('CH1:([0-9]+)', line)
                        if m:
                            c = int(m.groups()[0])
                            continue

            except (OSError, UnicodeDecodeError):
                Task.sleep(1000)
                with s.lock:
                    s._voltage = None
                    s._current = None
                    v = None
                    c = None
                continue


            with s.lock:
                s.voltageQueue.push(v)
                s.currentRawQueue.push(c)
                s._voltage = s.voltageQueue.round()
                s._current = round((s.currentRawQueue.round() - s.currentOffset.val) * c_step, 2)

            if s._voltage != s._prevVoltage or s._current != s._prevCurrent:
                s.skynetUpdater.call()

            with s.lock:
                s._prevVoltage = s._voltage
                s._prevCurrent = s._current
                v = None
                c = None


    def setZeroCurrent(s):
        s.currentOffset.set(s.currentRawQueue.round())


    def emulateDo(s):
        if not os.path.exists('FAKE/battery'):
            data = {'voltage': 12.8,
                    'current': 0.0}
            filePutContent('FAKE/battery', json.dumps(data))

        while True:
            c = fileGetContent('FAKE/battery')
            data = json.loads(c)
            with s.lock:
                s._voltage = float(data['voltage'])
                s._current = float(data['current'])

            if s._voltage != s._prevVoltage or s._current != s._prevCurrent:
                s.skynetUpdater.call()

            with s.lock:
                s._prevVoltage = s._voltage
                s._prevCurrent = s._current
            Task.sleep(1000)


    def skynetUpdateHandler(s):
        data = {'io_name': s.mbio.name()}
        ok = False
        v = s.voltage()
        if v != None:
            data['voltage'] = v
            ok = True

        c = s.current()
        if c != None:
            data['current'] = c
            ok = True

        if ok:
            s.mbio.sn.notify('batteryStatus', data)


    def voltage(s):
        with s.lock:
            return s._voltage


    def current(s):
        with s.lock:
            return s._current



