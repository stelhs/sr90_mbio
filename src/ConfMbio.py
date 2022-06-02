from ConfParser import *


class ConfMbio(ConfParser):
    def __init__(s):
        super().__init__()
        s.addConfig('mbio', 'mbio.conf')
        s.addConfig('telegram', 'telegram.conf')


