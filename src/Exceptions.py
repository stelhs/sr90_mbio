from sr90Exceptions import *

# Board IO exceptions

class PortNotRegistredError(AppError):
    pass


# Skynet server connection errors

class SkynetServerError(AppError):
    pass

class SkynetServerNetworkError(SkynetServerError):
    pass

class SkynetServerResponceError(SkynetServerError):
    pass



# Skynet notifier client errors

class SkynetNotifierError(AppError):
    pass

class SkynetNotifierConnectionError(SkynetNotifierError):
    pass

class SkynetNotifierSendError(SkynetNotifierError):
    pass

class SkynetNotifierResponseError(SkynetNotifierError):
    pass


# Huawei modem E353 errors

class HuaweiModemE353Error(AppError):
    pass

