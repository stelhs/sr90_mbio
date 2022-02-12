import os, re
from Task import *


class BatteryMonitor():
    class Queue():
        def __init__(s, size):
            s.size = size
            s.clear()

        def push(s, val):
            s._q.append(val)
            if len(s._q) > s.size:
                s._q = s._q[1:]


        def round(s):
            s._q.sort()
            return s._q[int((len(s._q) / 2) - 1)]


        def clear(s):
            s._q = []



    def __init__(s):
        s.task = Task('battery_monitor')
        s.task.setCb(s.do)
        s.task.start()
        s.lock = threading.Lock()
        s._voltage = None
        s._current = None
        s.voltageQueue = BatteryMonitor.Queue(5)


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
                            val = int(m.groups()[0]) - 2970 # 2970 - Current 0A
                            c = round(val * c_step, 2)
                            continue

            except Exception as e:
                Task.sleep(1000)
                with s.lock:
                    s._voltage = None
                    s._current = None
                continue

            with s.lock:
                s.voltageQueue.push(v)
                s._voltage = s.voltageQueue.round()
                s._current = c


    def voltage(s):
        with s.lock:
            return s._voltage


    def current(s):
        with s.lock:
            return s._current



