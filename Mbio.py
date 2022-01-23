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

    class QueueItem():
        def __init__(s, port, state):
            s.port = port
            s.state = state


    def __init__(s, mbio):
        s.mbio = mbio
        c = fileGetContent(".server.json")
        inf = json.loads(c)
        s.host = inf['host']
        s.port = inf['port']
        s.task = Task("mbio_sender")
        s.task.setCb(s.doSender)
        s.task.start()
        s.lock = threading.Lock()
        s.eventQueue = []
        s.log = Syslog("Server")


    def doSender(s):
        while 1:
            s.task.waitMessage(1000)
            with s.lock:
                if len(s.eventQueue) == 0:
                    continue
                item = s.eventQueue[0]
                s.eventQueue.remove(item)

            s.log.info("send %d:%d" % (item.port.num(), item.state))
            try:
                s.sendEvent(item.port, item.state);
            except Exception as e:
                s.log.err("Can't send event %d:%d, server disconnected. Message: %s" % (
                            item.port.num(), item.state, e))


    def request(s, url, args = None):
        url = "http://%s:%d/%s" % (s.host, s.port, url)
        r = requests.get(url = url, params = args)
        d = r.json()

        if 'status' not in d:
            raise Server.ReqEx("Incorrect JSON responce: 'status' field does absent")

        if d['status'] != 'ok':
            raise Server.ReqEx(d['reason'])
        return d


    def sendEvent(s, port, state):
        return s.request('ioserver',
                         {'io': s.mbio.name(),
                          'port': port.num(),
                          'state': state})


    def sendEventAsync(s, port, state):
        now = round(time.time() * 1000)
        if (now - port.lastTrigTime) <= port.delay():
            s.log.info("skip event: port %d:%d, diff = %d" % (
                        port.num(), state, (now - port.lastTrigTime)))
            return

        port.lastTrigTime = now
        with s.lock:
            s.eventQueue.append(Server.QueueItem(port, state))
        s.task.sendMessage(None)


    def mbioConfig(s):
        d = s.request('ioconfig',
                      {'io': s.mbio.name()})

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
            s.task = Task('port_%d_blinking' % s.port.num(),
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


        def __str__(s):
            return "(d1:%d, d2:%d, cnt:%d)" % (
                    s.d1, s.d2, s.cnt)


    def __init__(s, mbio, pn, gpio):
        s.mbio = mbio
        s._num = pn
        s.gpio = gpio
        s.blinking = None
        s.setName("")
        s.log = Syslog("port%d" % s.num())
        s._edge = 'all'
        s.lastTrigTime = 0


    def num(s):
        return s._num


    def setMode(s, mode):
        s.log.info("set mode %s" % mode)
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


    def setDelay(s, msec):
        s._delay = msec


    def delay(s):
        return s._delay


    def setEdge(s, edge):
        s._edge = edge


    def edge(s):
        return s._edge


    def setName(s, name):
        s._name = name


    def name(s):
        return s._name


    def mode(s):
        return s.gpio.mode()


    def setState(s, state):
        if s.gpio.mode() != "out":
            s.log.err("Can't set state %s because port configured as %s" % (state, s.mode()))
            return

        s.log.info("set state %s" % state)
        if s.blinking:
            s.blinkStop()
        s.gpio.setValue(state)


    def state(s):
        if s.gpio.mode() == "not_configured":
            return "not_configured"

        if s.blinking:
            return "blinking %s" % s.blinking

        if s.gpio.mode() == 'in':
            return int(not s.gpio.value())
        return s.gpio.value()


    def blink(s, d1, d2 = 0, cnt = 0):

        if s.blinking:
            s.blinkStop()
        s.blinking = Port.Blink(s, d1, d2, cnt)
        s.log.info("run blinking %s" % s.blinking)


    def blinkStop(s):
        s.blinking.stop()
        s.blinking = None


    def reset(s):
        s.gpio.unsetEvent()


    def __str__(s):
        return "(%s/%s.%s.%d): %s" % (
                s.name(), s.mbio.name(), s.mode(), s.num(), s.state())



class Mbio():
    class Ex(Exception):
        pass

    def __init__(s):
        s.log = Syslog("mbio")
        s._name = fileGetContent(".mbio_name").strip()

        s.httpServer = HttpServer('0.0.0.0', 8890)
        s.httpServer.setReqCb("GET", "/io/relay_set", s.httpReqIo)
        s.httpServer.setReqCb("GET", "/io/input_get", s.httpReqInput)
        s.httpServer.setReqCb("GET", "/io/relay_get", s.httpReqInput)
        s.httpServer.setReqCb("GET", "/stat", s.httpReqStat)

        s.ports = []
        portTable = s.portTable()
        for portNum, gpioNum in portTable.items():
            port = Port(s, portNum, Gpio(portTable[portNum]))
            s.ports.append(port)

        s.server = Server(s)
        s.setState("started")

        s.setupTask = Task('setupPorts', autoremove=True)
        s.setupTask.setCb(s.doSetupPorts)
        s.setupTask.start()
        Gpio.startEvents()
        s.startTc = TimeCounter('start')
        s.startTc.start()


    def setState(s, state):
        s._state = state


    def state(s):
        return s._state


    def name(s):
        return s._name


    def portByGpioNum(s, gpioNum):
        for port in s.ports:
            if port.gpio.num == gpioNum:
                return port
        return None


    def portByNum(s, pn):
        for port in s.ports:
            if port.num() == pn:
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
        s.setState("setupPorts")
        while(1):
            try:
                s.log.info("attempt to setup ports")
                for port in s.ports:
                    if port.mode() == 'in':
                        port.reset()

                conf = s.server.mbioConfig()
                if len(conf['in']):
                    for portNum, pInfo in conf['in'].items():
                        pn = int(portNum)
                        port = s.portByNum(pn)
                        port.setMode('in')
                        port.setName(pInfo['name'])
                        if 'delay' in pInfo:
                            port.setDelay(pInfo['delay'])
                        if 'edge' in pInfo:
                            port.setEdge(pInfo['edge'])

                if len(conf['out']):
                    for portNum, name in conf['out'].items():
                        pn = int(portNum)
                        port = s.portByNum(pn)
                        port.setMode('out')
                        port.setName(name)

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
        s.setState("actualizeState")
        while(1):
            try:
                s.log.info("attempt to actualize ports")
                stat = s.server.stat()
                for row in stat['io_states'].values():
                    if row['io_name'] != s.name():
                        continue

                    pn = int(row['port'])
                    state = int(row['state'])
                    port = s.portByNum(pn)
                    port.setState(state)
                    s.log.info("actualizing: port %s" % port)

                s.log.info("ports successfully actualized")
                s.setupTask = None
                s.setState("ready")
                s.printStat()
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
        s.log.info("input event port %s" % port)
        if port.edge() == 'all':
            s.server.sendEventAsync(port, state)
            return

        if port.edge() == 'rise' and prevState == 0 and state == 1:
            s.server.sendEventAsync(port, state)
            return

        if port.edge() == 'fall' and prevState == 1 and state == 0:
            s.server.sendEventAsync(port, state)
            return


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
                               'reason': "port number %d: incorrect mode: %s" % (pn, port.mode())})

        if state != "0" and state != "1" and state != "blink":
            return json.dumps({'status': 'error',
                               'reason': ("state is not correct. state = %d" % state)})

        if state == "blink":
            if 'd1' not in args:
                return json.dumps({'status': 'error',
                                   'reason': "agrument 'd1' is absent where state = blink"})

            d1 = int(args['d1'])
            d2 = d1
            cnt = 0
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


    def uptime(s):
        return os.popen('uptime -p').read()


    def httpReqStat(s, args, body):
        list = TermoSensor.list()
        sensors = []
        try:
            for sensor in list:
                sensors.append({'name': sensor.name, 'temperature': sensor.t()})
        except Exception as e:
            return json.dumps({'status': 'error',
                               'reason': ("can't get termosensor, reason: %s" % e)})

        return json.dumps({'status': 'ok',
                           'termo_sensors': sensors,
                           'uptime': s.uptime()})


    def httpReqInput(s, args, body):
        if 'port' not in args:
            return json.dumps({'status': 'error',
                               'reason': "agrument 'port' is absent"})

        pn = int(args['port'])
        port = s.portByNum(pn)
        if not port:
            return json.dumps({'status': 'error',
                               'reason': "port number %d is not exist" % pn})

        s.log.info("request current port state %s" % port)
        return json.dumps({'status': 'ok', 'state': port.state()})


    def printStat(s):
        print("Mbio state: %s" % s.state())
        print("Port list:")
        for port in s.ports:
            print("\t%s" % port)
