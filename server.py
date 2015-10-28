from twisted.web import server, resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet import protocol, reactor, endpoints
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.internet.task import deferLater

class DeviceCommandSender(protocol.Protocol):
    def __init__(self, deferred):
        self.responseDeferred = deferred
    
    def connectionMade(self):
        self.output = []

    def dataReceived(self, data):
        self.output.append(data)

    def connectionLost(self, reason):
        self.responseDeferred.callback(''.join(self.output))

    @staticmethod
    @inlineCallbacks
    def sendCommandToDevice(message, hostname, deferred):
        point = TCP4ClientEndpoint(reactor, hostname, 1234)
        protocol = yield connectProtocol(point, DeviceCommandSender(deferred))
        protocol.transport.write(message)
        yield protocol.responseDeferred
        returnValue(protocol.responseDeferred)

class DeviceCommandResource(resource.Resource):
    isLeaf = True

    def __init__(self, command):
        self.command = command or "No command"

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        
        deferredRender = Deferred()
        deferredRender.addCallback(lambda x: self._delayedRender(request, x))

        DeviceCommandSender.sendCommandToDevice(self.command, "localhost", deferredRender)
        
        return NOT_DONE_YET
    
    def _delayedRender(self, request, result):
        request.write(str(self.command) + '=' + result + "\n")
        request.finish()


class CommandServer(resource.Resource):
    isLeaf = False
    
    def getChild(self, name, request):
        
        if name == "sendCommand":
            return self._handle_sendCommand(request)

        return resource.NoResource()

    def _check_arg(self, expectedArg, args): 
        if expectedArg not in args:
            return resource.ErrorPage(500, "Missing parameter", "Query String argument " + expectedArg + " is not optional")
        return None
    
    def _handle_sendCommand(self, request):
        for arg in ("fromClient", "toDevice", "command"):
            result = self._check_arg(arg, request.args)
            if result:
                return result
            
        return DeviceCommandResource(request.args['command'][0])



endpoints.serverFromString(reactor, "tcp:8080").listen(server.Site(CommandServer()))
reactor.run()