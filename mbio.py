import sys
sys.path.append('sr90lib/')
sys.path.append('src/')

from math import *
import rlcompleter, readline, atexit
readline.parse_and_bind('tab:complete')


from Mbio import *

mbio = Mbio()


def exitCb():
    print("call exitCb")
    mbio.destroy()
atexit.register(exitCb)



print("help:")
print("\tmbio.printStat()")
print("\tTask.printList()")
print("\tTermoSensor.printList()")
