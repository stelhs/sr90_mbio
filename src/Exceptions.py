import traceback

class AppError(Exception):
    def __init__(s, log, msg):
        super().__init__(s, msg)
        log.err("MBIO Exception: %s" % msg)



class ConfigError(AppError):
    pass


class PortNotRegistredError(AppError):
    pass



class SkynetServerError(AppError):
    pass

class SkynetServerNetworkError(SkynetServerError):
    pass

class SkynetServerConfigError(SkynetServerError):
    pass

class SkynetServerResponceError(SkynetServerError):
    pass



class GpioError(AppError):
    pass

class GpioNotRegistredError(GpioError):
    pass

class GpioNotConfiguredError(GpioError):
    pass

class GpioNumberIsBusyError(GpioError):
    pass

class GpioIncorrectStateError(GpioError):
    pass




class SkynetNotifierError(AppError):
    pass

class SkynetNotifierConnectionError(SkynetNotifierError):
    pass

class SkynetNotifierSendError(SkynetNotifierError):
    pass

class SkynetNotifierResponseError(SkynetNotifierError):
    pass



# Telegram client errors

class TelegramError(AppError):
    pass

class TelegramClientError(TelegramError):
    pass
