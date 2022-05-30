import os

class FileError(Exception):
    pass

def filePutContent(filename, data):
    try:
        with open(filename, "w") as f:
            f.write(data)
            f.flush()
    except Exception as e:
        raise FileError("filePutContents(%s) error: %s" % (filename, e)) from e


def fileGetContent(filename):
    try:
        with open(filename, "r") as f:
            data = f.read()
            return data
    except Exception as e:
        raise FileError("fileGetContent(%s) error: %s" % (filename, e)) from e


def fileGetBinary(filename):
    try:
        with open(filename, "rb") as f:
            data = f.read()
            return data
    except Exception as e:
        raise FileError("fileGetBinary(%s) error: %s" % (filename, e)) from e


def timeStr(time):
    if time < 60:
        return "%d sec" % time

    if time < 3600:
        return "%d min, %d sec" % (time / 60,
                 time - (int(time / 60) * 60))

    if time < 60 * 60 * 24:
        return "%d hour, %d min" % (time / 3600, (time - (int(time / 3600) * 3600)) / 60)

