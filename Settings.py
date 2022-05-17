import json


class Settings():
    def __init__(s):
        s.conf = {}
        try:
            with open('/etc/mbio.conf') as f:
                c = f.read()
                s.conf = json.loads(c)
        except Exception as e:
            pass

        s.batteryMon = False
        if 'battery_monitor' in s.conf and s.conf['battery_monitor'] == 'enable':
            s.batteryMon = True

        s.httpListenHost = '0.0.0.0'
        if 'http_listen_host' in s.conf and s.conf['http_listen_host']:
            s.httpListenHost = s.conf['http_listen_host']

        s.httpListenPort = 8892
        if 'http_listen_port' in s.conf and s.conf['http_listen_port']:
            s.httpListenPort = s.conf['http_listen_port']

        s.uiServerHost = '127.0.0.1'
        if 'ui_server_host' in s.conf and s.conf['ui_server_host']:
            s.uiServerHost = s.conf['ui_server_host']

        s.uiServerPort = 8890
        if 'ui_server_port' in s.conf and s.conf['ui_server_port']:
            s.uiServerPort = s.conf['ui_server_port']

        s.mbioHost = '127.0.0.1'
        if 'mbio_host' in s.conf and s.conf['mbio_host']:
            s.mbioHost = s.conf['mbio_host']
