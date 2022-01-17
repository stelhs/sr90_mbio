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



class Mbio():
    class Ex(Exception):
        pass

    def __init__(s):
        s.lock = threading.Lock()
        s.log = Syslog("mbio")
        s.httpServer = HttpServer('0.0.0.0', 8890)
        s.httpServer.setReqCb("GET", "/io", s.httpReqIo)

        s.gpios = {}
        c = fileGetContent(".gpios.json")
        gpioTable = json.loads(c)
        for portNum, gpioNum in gpioTable.items():
            gpio = Gpio(gpioTable[portNum])
            s.gpios[int(portNum)] = gpio

        s.server = Server(s)
        s.name = fileGetContent(".mbio_name")

        s.setupTask = Task('setupPorts')
        s.setupTask.setCb(s.doSetupPorts)
        s.setupTask.start()


    def doSetupPorts(s):
        while(1):
            try:
                s.log.info("attempt to setup ports")
                for gpio in s.gpios.values():
                    if gpio.mode() == 'in':
                        gpio.unsetEvent()

                conf = s.server.mbioConfig()
                for portNum, name in conf['in'].items():
                    pn = int(portNum)
                    gpio = s.gpios[pn]
                    gpio.setMode('in')
                    gpio.setEventCb(s.inputEventCb)

                for portNum, name in conf['out'].items():
                    pn = int(portNum)
                    gpio = s.gpios[pn]
                    gpio.setMode('out')

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
                print(stat)
                for row in stat['io_states'].values():
                    if row['io_name'] != s.name:
                        continue

                    pn = row['port']
                    state = row['state']
                    print("set port %d to state %d\n" % (pn, state));
                    s.setOutPortState(pn, state)

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


    def setOutPortState(s, pn, state):
        if pn not in s.gpios:
            raise Mbio.Ex("can't setOutState: gpio %d not exist" % pn)
        gpio = s.gpios[pn]
        gpio.setValue(state)


    def inputEventCb(s, gpio, state, prevState):
        print('sendEvent')
        s.server.sendEvent(gpio.pn(), state, prevState)


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

        if pn not in s.gpios.keys():
            return json.dumps({'status': 'error',
                               'reason': "port number %d is not exist" % pn})
        gpio = s.gpios[pn]
        if gpio.mode() != 'out':
            return json.dumps({'status': 'error',
                               'reason': "port number %d: incorrect mode: %s" % (pn, gpio.mode())})

        try:
            gpio.setValue(state)
        except Gpio.Ex as e:
            return json.dumps({'status': 'error',
                               'reason': "%s" % e})

        return json.dumps({'status': 'ok'})

