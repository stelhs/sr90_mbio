import threading
from Task import *
from Syslog import *
from HttpServer import *
from TimeCounter import *
from TermoSensor import *
from Gpio import *
import json
import os, re
import requests


class Server():
    class ReqEx(Exception):
        pass

    def __init__(s, mbio):
        s.mbio = mbio
        c = fileGetContent(".server.json")
        inf = json.loads(c)
        s.host = inf['host']
        s.port = inf['port']


    def request(s, url, args = None):
        url = "http://%s:%d/%s" % (s.host, s.port, url)
        try:
            r = requests.get(url = url,
                             params = args)
            d = r.json()
        except Exception as e:
            raise Server.ReqEx("Server request error: %s" % e)

        if 'status' not in d:
            raise Server.ReqEx("Incorrect JSON responce: 'status' field does absent")

        if d['status'] != 'ok':
            raise Server.ReqEx(d['reason'])
        return d


    def sendEvent(s, portNum, state, prevState):
        return s.request('ioserver',
                         {'io': s.mbio.name,
                          'port': portNum,
                          'state': state,
                          'prev_state': prevState})


    def mbioConfig(s):
        d = s.request('ioconfig',
                      {'io': s.mbio.name})

        if 'ports' not in d:
            raise Exception("incorrect mbio config: field 'ports' is absent, content: %s" % d)

        if 'in' not in d['ports']:
            raise Exception("incorrect mbio config: field 'in' is absent, content: %s" % d)

        if 'out' not in d['ports']:
            raise Exception("incorrect mbio config: field 'out' is absent, content: %s" % d)
        return d['ports']


    def stat(s):
        d = s.request('stat')
        if 'io_states' not in d:
            raise Exception("incorrect server stat: field 'io_states' is absent, content: %s" % d)
        return d



class Port():
    class Blink():
        def __init__(s, port, d1, d2, cnt):
            s.port = port
            s.d1 = d1
            s.d2 = d2
            if not s.d2:
                s.d2 = s.d1
            s.cnt = cnt
            s.task = Task('port_%d_blinking' % s.port.num,
                          lambda: s.port.gpio.setValue(0),
                          autoremove = True)
            s.task.setCb(s.do)
            s.task.start()


        def do(s):
            mode = "d1"
            s.port.gpio.setValue(1)
            cnt = 0
            while 1:
                if mode == "d1":
                    Task.sleep(s.d1)
                    s.port.gpio.setValue(0)
                    mode = "d2"
                    cnt += 1
                else:
                    Task.sleep(s.d2)
                    s.port.gpio.setValue(1)
                    mode = "d1"
                if s.cnt and cnt >= s.cnt:
                    return


        def stop(s):
            s.task.remove()


    def __init__(s, mbio, pn, gpio):
        s.mbio = mbio
        s.num = pn
        s.gpio = gpio
        s.blinking = None


    def setMode(s, mode):
        s.reset()

        if s.blinking:
            s.blinkStop()

        if mode == 'in':
             s.gpio.setMode('in')
             s.gpio.setEventCb(s.mbio.inputEventCb)
             return
        if mode == 'out':
            s.gpio.setMode('out')
            return


    def mode(s):
        return s.gpio.mode()


    def setState(s, state):
        if s.blinking:
            s.blinkStop()

        s.gpio.setValue(state)


    def blink(s, d1, d2 = 0, cnt = None):
        if s.blinking:
            s.blinkStop()
        s.blinking = Port.Blink(s, d1, d2, cnt)


    def blinkStop(s):
        s.blinking.stop()
        s.blinking = None


    def reset(s):
        s.gpio.unsetEvent()



class Mbio():
    class Ex(Exception):
        pass

    def __init__(s):
        s.log = Syslog("mbio")
        s.httpServer = HttpServer('0.0.0.0', 8890)
        s.httpServer.setReqCb("GET", "/io", s.httpReqIo)
        s.httpServer.setReqCb("GET", "/stat", s.httpReqStat)

        s.ports = []
        portTable = s.portTable()
        for portNum, gpioNum in portTable.items():
            port = Port(s, portNum, Gpio(portTable[portNum]))
            s.ports.append(port)

        s.server = Server(s)
        s.name = fileGetContent(".mbio_name")

        s.setupTask = Task('setupPorts', autoremove=True)
        s.setupTask.setCb(s.doSetupPorts)
        s.setupTask.start()
        Gpio.startEvents()
        s.startTc = TimeCounter('start')
        s.startTc.start()


    def portByGpioNum(s, gpioNum):
        for port in s.ports:
            if port.gpio.num == gpioNum:
                return port
        return None


    def portByNum(s, pn):
        for port in s.ports:
            if port.num == pn:
                return port
        return None


    def portTable(s):
        list = {}
        c = fileGetContent(".gpios.json")
        portTable = json.loads(c)
        for portNum, gpioNum in portTable.items():
            list[int(portNum)] = int(gpioNum)
        return list


    def doSetupPorts(s):
        while(1):
            try:
                s.log.info("attempt to setup ports")
                for port in s.ports:
                    if port.mode() == 'in':
                        port.reset()

                conf = s.server.mbioConfig()
                if len(conf['in']):
                    for portNum, name in conf['in'].items():
                        pn = int(portNum)
                        port = s.portByNum(pn)
                        port.setMode('in')

                if len(conf['out']):
                    for portNum, name in conf['out'].items():
                        pn = int(portNum)
                        port = s.portByNum(pn)
                        port.setMode('out')

                s.log.info("ports successfully configured")
                s.setupTask = Task('actualizeStates', autoremove=True)
                s.setupTask.setCb(s.doActualizeState)
                s.setupTask.start()
                return

            except Server.ReqEx as e:
                s.log.error("mbio setup ports error: %s" % e)
                print("mbio setup ports error: %s" % e)
            Task.sleep(2000)


    def doActualizeState(s):
        while(1):
            try:
                s.log.info("attempt to actualize ports")
                stat = s.server.stat()
                for row in stat['io_states'].values():
                    if row['io_name'] != s.name:
                        continue

                    pn = row['port']
                    state = row['state']
                    print("set port %d to state %d\n" % (pn, state));
                    port = s.portByNum(pn)
                    port.setState(state)

                s.log.info("ports successfully actualized")
                s.setupTask = None
                return

            except Server.ReqEx as e:
                s.log.err("mbio actualize ports error: %s" % e)
                print("mbio actualize ports error: %s" % e)
            except Mbio.Ex as e:
                s.log.err("can't set out port: %s" % e)
                print("can't set out port: %s" % e)
            Task.sleep(2000)



    def inputEventCb(s, gpio, state, prevState):
        if s.startTc.duration() < 5:
            return
        port = s.portByGpioNum(gpio.num)
        print('sendEvent %d' % port.num)
        s.server.sendEvent(port.num, state, prevState)


    def httpReqIo(s, args, body):
        if 'port' not in args:
            return json.dumps({'status': 'error',
                               'reason': "agrument 'port' is absent"})

        if 'state' not in args:
            return json.dumps({'status': 'error',
                               'reason': "agrument 'state' is absent"})
        state = args['state']
        pn = int(args['port'])

        port = s.portByNum(pn)
        if not port:
            return json.dumps({'status': 'error',
                               'reason': "port number %d is not exist" % pn})
        if port.mode() != 'out':
            return json.dumps({'status': 'error',
                               'reason': "port number %d: incorrect mode: %s" % (pn, gpio.mode())})

        if state != "0" and state != "1" and state != "blink":
            return json.dumps({'status': 'error',
                               'reason': ("state is not correct. state = %d" % state)})

        if state == "blink":
            if 'd1' not in args:
                return json.dumps({'status': 'error',
                                   'reason': "agrument 'd1' is absent where state = blink"})

            d1 = int(args['d1'])
            d2 = d1
            cnt = None
            if d1 <= 0:
                return json.dumps({'status': 'error',
                                   'reason': "d1 is not correct. d1 = %d" % d1})
            if 'd2' in args:
                d2 = int(args['d2'])
                if d2 <= 0:
                    return json.dumps({'status': 'error',
                                       'reason': "d2 is not correct. d2 = %d" % d2})
            if 'cnt' in args:
                cnt = int(args['cnt'])
                if cnt <= 0:
                    return json.dumps({'status': 'error',
                                       'reason': "cnt is not correct. cnt = %d" % cnt})

            try:
                port.blink(d1, d2, cnt)
            except Gpio.Ex as e:
                return json.dumps({'status': 'error',
                                   'reason': "%s" % e})
            return json.dumps({'status': 'ok'})


        try:
            port.setState(int(state))
        except Gpio.Ex as e:
            return json.dumps({'status': 'error',
                               'reason': "%s" % e})

        return json.dumps({'status': 'ok'})


    def httpReqStat(s, args, body):
        list = TermoSensor.list()
        sensors = []
        try:
            for sensor in list:
                sensors.append({'name': sensor.name, 'temperature': sensor.t()})
        except Exception as e:
            return json.dumps({'status': 'error',
                               'reason': ("can't get termosensor, reason: %s" % e)})

        return json.dumps({'status': 'ok', 'termo_sensors': sensors})

