import threading
import socket
import select
import json
from Task import *


class HttpHandlerError(Exception):
    def __init__(s, msg, errCode=""):
        s.errCode = errCode
        super().__init__(msg)


    def code(s):
        return s.errCode



class HttpServer():
    subscribers = []
    def __init__(s, host, port, wwwDir = None):
        s._host = host
        s._port = port
        s._wwwDir = wwwDir
        s._listenedSock = None
        s._connections = []
        s._lock = threading.Lock()

        s._task = Task('http_server_%s:%d' % (host, port))
        s._task.setCb(s.taskDo)
        s._task.start()


    def taskDo(s):
        s._listenedSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s._listenedSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s._listenedSock.bind((s._host, s._port))
        s._listenedSock.settimeout(1.0)
        s._listenedSock.listen(50)
        while 1:
            Task.sleep(0)
            while 1:
                Task.sleep(0)
                try:
                    conn, addr = s._listenedSock.accept()
                except socket.error:
                    continue
                break

            if not s._listenedSock:
                return
            httpConn = HttpServer.Connection(s, conn, addr, s._wwwDir)
            with s._lock:
                s._connections.append(httpConn)
            httpConn.run()


    def setReqHandler(s, method, page, cb, requiredFields=[], retJson=True):
        HttpServer.subscribers.append((method, page, cb, requiredFields, retJson))


    def destroy(s):
        s._task.remove()
        with s._lock:
            connections = s._connections

        for conn in connections:
            conn.close()
        s._listenedSock.shutdown(socket.SHUT_RDWR)
        s._listenedSock.close()
        s._listenedSock = None


    def wwwDir(s):
        return s._wwwDir


    @staticmethod
    def parseHttpRequest(req):
        parts = req.split("\r\n\r\n")
        if not len(parts):
            return

        header = parts[0]
        body = None
        if len(parts) > 1:
            body = parts[1]

        lines = header.split("\n")
        if not len(lines):
            return None

        if not len(lines):
            return None

        parts = lines[0].split()
        if len(parts) < 2:
            return None

        method, url, version = parts

        attrs = {}
        for line in lines[1:]:
            if not line.strip():
                continue

            row = line.split(":")
            name = row[0].strip()
            val = row[1].strip()
            attrs[name] = val

        return (method, url, version, attrs, body)


    @staticmethod
    def parseHttpResponce(resp):
        parts = resp.split("\r\n\r\n")
        if not len(parts):
            return

        header = parts[0]
        body = None
        if len(parts) > 1:
            body = parts[1]

        lines = header.split("\n")
        if not len(lines):
            return None

        if not len(lines):
            return None

        parts = lines[0].split()
        if len(parts) < 3:
            return None

        version = parts[0]
        code = parts[1]

        attrs = {}
        for line in lines[1:]:
            if not line.strip():
                continue

            row = line.split(":")
            name = row[0].strip()
            val = row[1].strip()
            attrs[name] = val

        return (version, code, attrs, body)


    @staticmethod
    def parseParamsString(line):
        argsText = line.split("&")
        args = {}
        for keyVal in argsText:
            row = keyVal.split("=")
            if len(row) < 2:
                continue
            key, val = keyVal.split("=")
            args[key] = val
        return args




    class Connection():
        def __init__(s, server, conn, remoteAddr, wwwDir = None):
            s._server = server
            s._conn = conn
            s._wwwDir = wwwDir
            s._name = "%s:%d" % (remoteAddr[0], remoteAddr[1])
            s.log = Syslog("http_connection_%s:%d" % (remoteAddr[0], remoteAddr[1]))
            s.log.mute('debug')
            s._task = Task("http_connection_%s:%d" % (remoteAddr[0], remoteAddr[1]))
            s._keep_alive = False
            s._task.setCb(s.taskDo)


        def run(s):
            s._task.start()


        def task(s):
            return s._task


        def taskDo(s):
            with s._conn:
                poll = select.poll()
                poll.register(s._conn.fileno(), select.POLLIN)
                while 1:
                    Task.sleep(0)

                    poll_list = poll.poll(100)
                    if not len(poll_list):
                        continue

                    data = None;
                    try:
                        data = s._conn.recv(65535)
                    except:
                        pass

                    if not s._conn:
                        return

                    if (not data) or (not len(data)):
                        s.close()
                        return

                    try:
                        req = data.decode()
                    except:
                        s.close()
                        return

                    parts = HttpServer.parseHttpRequest(req)
                    if not parts:
                        s.close()
                        return

                    method, url, version, attrs, body = parts

                    for name, val in attrs.items():
                        if name == 'Connection' and val == 'keep-alive':
                            s._keep_alive = True

                    s.log.debug("%s %s" % (method, url))

                    page, args = s.parseUrl(url)
                    if not args:
                        args = {}

                    if ('Content-Type' in attrs and
                            attrs['Content-Type'] == 'application/x-www-form-urlencoded'):
                        postArgs = HttpServer.parseParamsString(body)
                        args.update(postArgs)

                    subscriberSucessProcessed = False
                    content = ""
                    for (sMethod, sPage, sCb, requiredFields, retJson) in HttpServer.subscribers:
                        if sMethod != method or sPage != page:
                            continue

                        subscriberSucessProcessed = True
                        for reqFiled in requiredFields:
                            if reqFiled not in args:
                                content = json.dumps({'status': 'error',
                                                      'reason': "filed '%s' is absent in %s request" % (
                                                                reqFiled, sMethod)})
                                break

                        if not content:
                            try:
                                ret = sCb(args, body, attrs, s)
                                content = ret

                                if retJson:
                                    if not ret:
                                        ret = {}
                                    ret['status'] = 'ok'
                                    content = json.dumps(ret)
                            except HttpHandlerError as e:
                                content = json.dumps({'status': 'error',
                                                      'reason': '%s' % e,
                                                      'errCode': e.code()})
                        break

                    if subscriberSucessProcessed:
                        s.log.debug('response 200 OK')
                        s.respOk(content)
                    else:
                        if not s._wwwDir:
                            s.log.debug('response 404 ERROR')
                            s.resp404()

                        if url == '/':
                            url = 'index.html'

                        fileName = "%s/%s" % (s._wwwDir, url)
                        if not os.path.exists(fileName):
                            s.log.debug('response 404 ERROR')
                            s.resp404()
                        else:
                            content = fileGetBinary(fileName)
                            s.log.debug('response 200 OK, file "%s" is exist' % fileName)
                            mimeType = s.mimeTypeByFileName(fileName)
                            s.respOk(content, mimeType)

                    if s._keep_alive:
                        continue

                    s.close()
                    return

        def close(s):
            if not s._conn:
                return
            s._conn.close()
            s._conn = None
            s._task.remove()
            with s._server._lock:
                s._server._connections.remove(s)


        def name(s):
            return s._name


        def mimeTypeByFileName(s, fileName):
            types = {"jpeg": "image/jpeg",
                     "jpg": "image/jpeg",
                     "png": "image/png",
                     "html": "text/html",
                     "htm": "text/html",
                     "js": "text/javascript",
                     "css": "text/css",
                     "txt": "text/plain",
                     };

            for type, mime in types.items():
                if fileName[-len(type):] == type:
                    return mime

            return "text/plain";


        def parseUrl(s, url):
            parts = url.split("?")
            if not parts:
                return None

            if len(parts) == 1:
                return (url, None)

            page = parts[0]
            args = HttpServer.parseParamsString(parts[1])
            return (page, args)


        def respOk(s, data = "", ctype = "text/plain"):
            if not s._conn:
                return

            if str(type(data)) == "<class 'str'>":
                data = data.encode('utf-8')

            header = "HTTP/1.1 200 OK\r\n"
            header += "Content-Type: %s\r\n" % ctype
            header += "Content-Length: %d\r\n" % len(data)
            if s._keep_alive:
                header += "Connection: Keep-Alive\r\n"
            header += "\r\n"
            headerBytes = header.encode('utf-8')
            try:
                s._conn.send(headerBytes + data)
            except Exception as e:
                s.log.err("respOk error: %s" % e)


        def respBadRequest(s, data = ""):
            if not s._conn:
                return
            if str(type(data)) == "<class 'str'>":
                data = data.encode('utf-8')

            header = "HTTP/1.1 400 Bad Request\r\n"
            header += "Content-Type: text/plain\r\n"
            header += "Content-Length: %d\r\n" % len(data)
            header += "\r\n"
            headerBytes = header.encode('utf-8')
            try:
                s._conn.send(headerBytes + data)
            except Exception as e:
                s.log.err("respBadRequest error: %s" % e)


        def resp404(s):
            if not s._conn:
                return
            data = "404 Page not found".encode('utf-8')
            header = "HTTP/1.1 404 Page Not Found\r\n"
            header += "Content-Type: text/plain\r\n"
            header += "Content-Length: %d\r\n" % len(data)
            header += "\r\n"
            headerBytes = header.encode('utf-8')
            try:
                s._conn.send(headerBytes + data)
            except Exception as e:
                s.log.err("resp404 error: %s" % e)

