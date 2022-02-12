import json


class Settings():
    def __init__(s):
        s.batteryMon = False
        try:
            with open('/etc/mbio.conf') as f:
                c = f.read()
                conf = json.loads(c)
                if 'battery_monitor' in conf and conf['battery_monitor'] == 'enable':
                    s.batteryMon = True
        except Exception as e:
            pass
