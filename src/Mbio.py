import threading
from Task import *
from Syslog import *
from Exceptions import *
from HttpServer import *
from ConfMbio import *
from TimerCounter import *
from TermoSensorDs18b20 import *
from TelegramClient import *
from SkynetNotifier import *
from BatteryMonitor import *
from Gpio import *
from PeriodicNotifier import *
from HttpClient import *
from GsmModem import *
import os, re



class Mbio():
    def __init__(s):
        s.log = Syslog("Mbio")
        s.conf = ConfMbio()

        s._name = s.conf.mbio['name']

        s.termosensors = []
        s.ports = []

        s.tc = TelegramClient(s.conf.telegram)
        Task.setErrorCb(s.taskExceptionHandler)

        s.setState("started")
        s.initGpios()

        s.sn = SkynetNotifier('mbio',
                              s.conf.mbio['skynetServer']['host'],
                              s.conf.mbio['skynetServer']['port'],
                              s.conf.mbio['host'])

        s.periodicNotifier = PeriodicNotifier()
        s.skynetPortsUpdater = s.periodicNotifier.register("ports", s.skynetUpdatePortsHandler, 2000)
        s.skynetTermoUpdater = s.periodicNotifier.register("termosensors", s.skynetUpdateTermoHandler, 2000)

        s.batteryMon = None
        if 'batteryMonitor' in s.conf.mbio:
            s.batteryMon = BatteryMonitor(s)

        s.httpServer = HttpServer(s.conf.mbio['host'],
                                  s.conf.mbio['port'])
        s.httpHandlers = Mbio.HttpHandlers(s, s.httpServer)
        s.skynetClient = HttpClient('mbio', s.conf.mbio['skynetServer']['host'],
                                            s.conf.mbio['skynetServer']['port'])

        s.modem = None
        if 'modemHuaweiE353' in s.conf.mbio:
            s.modem = GsmModem(s)

        Task.asyncRunSingle('setup_mbio', s.doSetup)


    def initGpios(s):
        if s.state() != 'started':
            return

        portTable = s.portTable()
        for portNum, gpioNum in portTable.items():
            port = Port(s, portNum, Gpio(portTable[portNum]))
            s.ports.append(port)
        Gpio.startEvents()


    def taskExceptionHandler(s, task, errMsg):
        s.tc.sendToChat('stelhs',
                "%s: task '%s' error:\n%s" % (s.name(), task.name(), errMsg))


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
        raise PortNotRegistredError(s.log,
                'Port is not registred for GPIO "%s"' % gpioNum)


    def portByNum(s, pn):
        for port in s.ports:
            if port.num() == pn:
                return port
        raise PortNotRegistredError(s.log,
                'Port is not registred for pin number "%d"' % pn)


    def portTable(s):
        list = {}
        portTable = s.conf.mbio['portTable']
        for portNum, gpioNum in portTable.items():
            list[int(portNum)] = int(gpioNum)
        return list


    def doSetup(s):
        s.doSetupPorts()
        s.doSetupTermosensors()
        s.doActualizeState()


    def doSetupPorts(s):
        s.setState("setupPorts")
        while(1):
            s.log.info("attempt to setup ports")
            for port in s.ports:
                if port.mode() == 'in':
                    port.reset()

            try:
                conf = s.mbioConfig()
            except SkynetServerNetworkError:
                Task.sleep(5000)
                continue
            except SkynetServerResponceError as e:
                print("SkynetServerResponceError: %s" % e)
                Task.sleep(5000)
                continue

            s.startTc = TimerCounter('start')
            s.startTc.start()

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
            return



    def doSetupTermosensors(s):
        s.setState("setupTermosensors")
        while(1):
            try:
                conf = s.termosensorsConfig()
            except SkynetServerNetworkError:
                Task.sleep(5000)
                continue
            except SkynetServerResponceError as e:
                print("SkynetServerResponceError: %s" % e)
                Task.sleep(5000)
                continue

            for tSensor in s.termosensors:
                tSensor.destroy()
            s.termosensors = []

            s.termosensors = [TermoSensorDs18b20(addr, s.termosensorHandler) for addr in conf]
            s.log.info("thermosensors successfully configured")
            return


    def doActualizeState(s):
        s.setState("actualizeState")
        while(1):
            try:
                stat = s.outPortStates()
            except SkynetServerNetworkError:
                Task.sleep(5000)
                continue
            except SkynetServerResponceError as e:
                print("SkynetServerResponceError: %s" % e)
                Task.sleep(5000)
                continue

            try:
                for row in stat:
                    pn = int(row['pn'])
                    state = int(row['state'])
                    port = s.portByNum(pn)
                    port.setState(state)
                    s.log.info("actualizing: port %s" % port)
            except KeyError as e:
                err = "outPortStates() return incorrect responce: Field %s is absent. Response: %s" % (e, stat)
                s.log.err(err)
                print(err)
                Task.sleep(5000)
                continue
            except PortNotRegistredError as e:
                err = "outPortStates() return incorrect responce: port pn:%d is not registred" % pn
                s.log.err(err)
                print(err)
                Task.sleep(5000)
                continue

            s.log.info("ports successfully actualized")
            s.setState("ready")
            s.printStat()
            return


    def inputEventCb(s, gpio, state, prevState):
        if s.startTc.duration() < 5:
            return
        state = int(not state)
        prevState = int(not prevState)
        port = s.portByGpioNum(gpio.num)
        s.log.debug("input event port %s" % port)
        port.setCachedState(state)
        s.sn.notify('portTriggered',
                    {'io_name': s.name(),
                     'pn': port.num(),
                     'state': state})
        s.skynetPortsUpdater.call()


    def termosensorHandler(s, ts, t):
        s.skynetTermoUpdater.call()


    def skynetUpdatePortsHandler(s):
        if s.state() != "ready":
            return

        ports = [];
        for port in s.ports:
            if not port.name():
                continue

            try:
                state = port.state()
            except GpioError as e:
                continue

            info = {'port_name': port.name(),
                    'type': port.mode(),
                    'state': state}

            if port.mode() == 'out':
                if port.isBlinking():
                    with port._lock:
                        blinking = port.blinking

                    info['blinking'] = {'d1': round(blinking.d1 / 1000, 3),
                                        'd2': round(blinking.d2 / 1000, 3),
                                        'cnt': (blinking.number - blinking.cnt)}
            ports.append(info)

        s.sn.notify('portsStates',
                    {'io_name': s.name(),
                     'ports': ports})


    def skynetUpdateTermoHandler(s):
        termosensors = {}
        for ts in s.termosensors:
            termosensors[ts.addr()] = ts.t()

        s.sn.notify('termoStates',
                    {'io_name': s.name(),
                     'termosensors': termosensors})


    def uptime(s):
        return os.popen('uptime -p').read()


    def printStat(s):
        print("Mbio state: %s" % s.state())
        print("Port list:")
        for port in s.ports:
            print("\t%s" % port)



    def skynetRequest(s, op, args = None):
        try:
            return s.skynetClient.reqGet(op, args)
        except HttpClient.Error as e:
            raise SkynetServerNetworkError(s.log, e) from e


    def mbioConfig(s):
        try:
            d = s.skynetRequest('io/port_config', {'io': s.name()})
            return d['config']
        except KeyError as e:
            raise SkynetServerResponceError(s.log,
                    "field %s is absent in responce for mbioConfig(). Response: %s" % (e, d)) from e


    def termosensorsConfig(s):
        try:
            d = s.skynetRequest('io/termosensor_config', {'io': s.name()})
            return d['list']
        except KeyError as e:
            raise SkynetServerResponceError(s.log,
                    "field %s is absent in responce for termosensorsConfig(). Response: %s" % (e, d)) from e


    def outPortStates(s):
        try:
            d = s.skynetRequest('io/out_port_states', {'io': s.name()})
            return d['listStates']
        except KeyError as e:
            raise SkynetServerResponceError(s.log,
                    "field %s is absent in responce for outPortStates(). Response: %s" % (e, d)) from e


    def destroy(s):
        s.httpServer.destroy()


    class HttpHandlers():
        def __init__(s, mbio, httpServer):
            s.mbio = mbio
            s.httpServer = httpServer
            s.httpServer.setReqHandler("GET", "/io/output_set", s.outputSetHandler, ['pn', 'state'])
            s.httpServer.setReqHandler("GET", "/io/sync_state", s.portGetSyncStateHandler, ['pn'])
            s.httpServer.setReqHandler("GET", "/io/state", s.portGetStateHandler)
            s.httpServer.setReqHandler("GET", "/stat", s.statHandler)
            s.httpServer.setReqHandler("GET", "/reset", s.resetHandler)
            if 'batteryMonitor' in mbio.conf.mbio:
                s.httpServer.setReqHandler("GET", "/set_zero_charger_current", s.setZeroCurrentHandler)


        def outputSetHandler(s, args, conn):
            pn = int(args['pn'])
            state = args['state']

            try:
                port = s.mbio.portByNum(pn)
            except PortNotRegistredError as e:
                 raise HttpHandlerError("Port pn:%d is not registred" % pn)

            if port.mode() != 'out':
                raise HttpHandlerError("port number %d: incorrect mode: %s" % (pn, port.mode()))

            if state != "0" and state != "1" and state != "blink":
                raise HttpHandlerError("state is not correct. state = %d" % state)

            if state == "blink":
                if 'd1' not in args:
                    raise HttpHandlerError("agrument 'd1' is absent if state = blink")

                d1 = int(args['d1'])
                d2 = d1
                number = 0
                if d1 <= 0:
                    raise HttpHandlerError("d1 is not correct. d1 = %d" % d1)

                if 'd2' in args:
                    d2 = int(args['d2'])
                    if d2 <= 0:
                        raise HttpHandlerError("d2 is not correct. d2 = %d" % d2)

                if 'number' in args:
                    number = int(args['number'])
                    if number <= 0:
                        raise HttpHandlerError("'number' is not correct. number = %d" % number)

                try:
                    port.blink(d1, d2, number)
                except AppError as e:
                    raise HttpHandlerError("Can't set blink state: %s" % e)
                return


            try:
                port.setState(int(state))
            except AppError as e:
                raise HttpHandlerError("Can't set state: %s" % e)
            return


        def portGetSyncStateHandler(s, args, conn):
            pn = int(args['pn'])
            try:
                port = s.mbio.portByNum(pn)
                state = port.state(sync=True)
                return {'state': state}
            except PortNotRegistredError as e:
                raise HttpHandlerError("Port pn:%d is not registred" % pn)
            except GpioError as e:
                raise HttpHandlerError("Can't get state: %s" % e)


        def portGetStateHandler(s, args, conn):
            list = {}
            for port in s.mbio.ports():
                try:
                    state = port.state()
                except GpioError as e:
                    state = 'error'
                list[port.pn()] = state
            return {'states': list}


        def statHandler(s, args, conn):
            return {'uptime': s.mbio.uptime()}


        def resetHandler(s, args, conn):
            state = s.mbio.state()
            if state != 'ready':
                raise HttpHandlerError("Can't reset MBIO board. Current state is %s" % state)
            Task.asyncRunSingle('setup_mbio', s.mbio.doSetup)


        def setZeroCurrentHandler(s, args, conn):
            s.mbio.batteryMon.setZeroCurrent()



class Port():
    class Blink():
        def __init__(s, port, d1, d2, number):
            s.port = port
            s.skynetPortsUpdater = port.mbio.skynetPortsUpdater
            s.d1 = d1
            s.d2 = d2
            if not s.d2:
                s.d2 = s.d1
            s.number = number
            s.cnt = 0

            def blinkFinished():
                s.port.gpio.setValue(0)
                s.port.setCachedState(0)
                with s.port._lock:
                    s.port.blinking = None
                s.skynetPortsUpdater.call()

            s.task = Task('port_%d_blinking' % s.port.num(),
                          s.do,
                          blinkFinished,
                          autoremove = True)
            s.task.start()


        def do(s):
            mode = "d1"
            s.port.gpio.setValue(1)
            while 1:
                if mode == "d1":
                    Task.sleep(s.d1)
                    s.port.gpio.setValue(1)
                    s.port.setCachedState(1)
                    if s.d1 > 300:
                        s.skynetPortsUpdater.call()
                    mode = "d2"
                else:
                    Task.sleep(s.d2)
                    s.port.gpio.setValue(0)
                    s.port.setCachedState(0)
                    if s.d2 > 300:
                        s.skynetPortsUpdater.call()
                    mode = "d1"
                    s.cnt += 1
                if s.number and s.cnt >= s.number:
                    return


        def stop(s):
            s.task.remove()


        def __str__(s):
            return "(d1:%d, d2:%d, number:%d)" % (
                    s.d1, s.d2, s.number)


    def __init__(s, mbio, pn, gpio):
        s._lock = threading.Lock()
        s.mbio = mbio
        s._num = pn
        s.gpio = gpio
        s.blinking = None
        s.setName("")
        s.log = Syslog("port%d" % s.num())
        s.log.mute('debug')
        s._edge = 'all'
        s.lastTrigTime = [0, 0]
        s.setDelay(0)
        s._cachedState = None


    def num(s):
        return s._num


    def setMode(s, mode):
        s.log.debug("set mode %s" % mode)

        if s.isBlinking():
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

        s.log.debug("set state %s" % state)
        if s.isBlinking():
            s.blinkStop()

        s.gpio.setValue(state)
        s.setCachedState(state)

        s.mbio.sn.notify('portTriggered',
                         {'io_name': s.mbio.name(),
                          'pn': s.num(),
                          'state': state})

        s.mbio.skynetPortsUpdater.call()


    def state(s, sync=False):
        if s.gpio.mode() == "not_configured":
            return "not_configured"

        if not sync and s._cachedState != None:
            return s._cachedState

        if s.gpio.mode() == 'in':
            state = int(not s.gpio.value())
            s.setCachedState(state)
            return state

        state = s.gpio.value()
        s.setCachedState(state)
        return state


    def setCachedState(s, state):
        s._cachedState = state


    def isBlinking(s):
        with s._lock:
            return bool(s.blinking)


    def blink(s, d1, d2 = 0, number = 0):

        if s.isBlinking():
            s.blinkStop()

        with s._lock:
            s.blinking = Port.Blink(s, d1, d2, number)
        s.log.debug("run blinking %s" % s.blinking)


    def blinkStop(s):
        s.blinking.stop()
        with s._lock:
            s.blinking = None


    def reset(s):
        s.gpio.reset()


    def __repr__(s):
        return "p:%s/%s.%s.%d: %s" % (
                s.name(), s.mbio.name(), s.mode(), s.num(), s.state())


    def __str__(s):
        return "%s/%s.%s.%d: %s" % (
                s.name(), s.mbio.name(), s.mode(), s.num(), s.state())







