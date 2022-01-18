import threading
from Task import *
from Syslog import *
from HttpServer import *
from TimeCounter import *
from Gpio import *
import json
import os, re
import datetime
import requests
import time


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
    def __init__(s, mbio, pn, gpio):
        s.mbio = mbio
        s.num = pn
        s.gpio = gpio


    def setMode(s, mode):
        if mode == 'in':
             s.gpio.setMode('in')
             s.gpio.setEventCb(s.mbio.inputEventCb)
             return
        if mode == 'out':
            gpio.setMode('out')
            return


    def mode(s):
        return s.gpio.mode()


    def setOutState(s, state):
        s.gpio.setValue(state)


    def reset(s):
        s.gpio.unsetEvent()



class Mbio():
    class Ex(Exception):
        pass

    def __init__(s):
        s.lock = threading.Lock()
        s.log = Syslog("mbio")
        s.httpServer = HttpServer('0.0.0.0', 8890)
        s.httpServer.setReqCb("GET", "/io", s.httpReqIo)

        s.ports = []
        portTable = s.portTable()
        for portNum, gpioNum in portTable.items():
            port = Port(s, portNum, Gpio(portTable[portNum]))
            s.ports.append(port)

        s.server = Server(s)
        s.name = fileGetContent(".mbio_name")

        s.setupTask = Task('setupPorts')
        s.setupTask.setCb(s.doSetupPorts)
        s.setupTask.start()
        Gpio.startEvents()
        s.startTime = time.time()


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
                s.setupTask.remove()
                s.setupTask = Task('actualizeStates')
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
                    port.setOutState(state)

                s.log.info("ports successfully actualized")
                s.setupTask.remove()
                s.setupTask = None
                return

            except Server.ReqEx as e:
                s.log.error("mbio actualize ports error: %s" % e)
                print("mbio actualize ports error: %s" % e)
            except Mbio.Ex as e:
                s.log.error("can't set out port: %s" % e)
                print("can't set out port: %s" % e)
            Task.sleep(2000)



    def inputEventCb(s, gpio, state, prevState):
        if (time.time() - s.startTime) < 5:
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
        state = int(args['state'])
        pn = int(args['port'])

        if state != 0 and state != 1:
            return json.dumps({'status': 'error',
                               'reason': ("state is not correct. state = %d" % state)})

        port = s.portByNum(pn)
        if not port:
            return json.dumps({'status': 'error',
                               'reason': "port number %d is not exist" % pn})
        if port.mode() != 'out':
            return json.dumps({'status': 'error',
                               'reason': "port number %d: incorrect mode: %s" % (pn, gpio.mode())})

        try:
            port.setState(state)
        except Gpio.Ex as e:
            return json.dumps({'status': 'error',
                               'reason': "%s" % e})

        return json.dumps({'status': 'ok'})

