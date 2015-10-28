import json

from twisted.web import server, resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet import protocol, reactor, endpoints
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.internet import error
from twisted.internet.task import deferLater

from twisted.python.failure import Failure

class DeviceCommandSender(protocol.Protocol):
    def __init__(self):
        self.deviceId = None
        self.responseDeferred = None
        self._requests = []
    
    def connectionMade(self):
        pass

    def dataReceived(self, data):
        if not self.deviceId:
            self.deviceId = data
            self.factory.addDevice(self)
        else:
            if not self.responseDeferred:
                print 'no deferred found to use for data receipt'
            else:
                current_deferred = self.responseDeferred
                self.responseDeferred = None
                
                # if there are more requests then kick off the next one
                if self._requests:
                    command, queued_deferred = self._requests.pop(0)
                    self._sendCommand(command, queued_deferred)
                
                current_deferred.callback(data)

    def connectionLost(self, reason):
        if reason.type is not error.ConnectionAborted:
            self.factory.removeDevice(self)

    def disconnect(self):
        self.transport.abortConnection()

    def sendCommand(self, command):
        # if we are in the middle of a command then add this one to a queue
        requestDeferred = Deferred()
        if self.responseDeferred is None:
            self._sendCommand(command, requestDeferred)
        else:
            self._requests.append((command, requestDeferred))
        return requestDeferred
    
    def _sendCommand(self, command, deferred):
        self.responseDeferred = deferred
        self.transport.write(command)

class DeviceCommandFactory(protocol.Factory):
    protocol = DeviceCommandSender
    
    def __init__(self):
        self.devices = {}
    
    def addDevice(self, protocol):
        if protocol.deviceId in self.devices:
            print 'device already registered, dropping the second one'
            protocol.disconnect()
        self.devices[protocol.deviceId] = protocol
    
    def removeDevice(self, protocol):
        if protocol.deviceId not in self.devices:
            print 'no device found, not unregistering'
            return
        del self.devices[protocol.deviceId]
        
    @inlineCallbacks
    def sendCommand(self, deviceId, command):
        if deviceId not in self.devices:
            print 'device', deviceId, 'not connected'
        else:
            result = yield self.devices[deviceId].sendCommand(command)
            returnValue(result)

class DeviceCommandResource(resource.Resource):
    isLeaf = True

    def __init__(self, device, command, commandSenderFactory):
        self.device = device
        self.command = command or "No command"
        self.commandSenderFactory = commandSenderFactory

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        
        # TODO: is this a race?
        deferredRender = self.commandSenderFactory.sendCommand(self.device, self.command)
        deferredRender.addCallback(lambda x: self._delayedRender(request, x))
        
        return NOT_DONE_YET
    
    def _delayedRender(self, request, result):
        print self.command, 'result was', result
        request.write(str(self.command) + '=' + result + "\n")
        request.finish()

class DeviceListResource(resource.Resource):
    isLeaf = True

    def __init__(self, commandSenderFactory):
        self.commandSenderFactory = commandSenderFactory

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps(self.commandSenderFactory.devices.keys())
    

class CommandServer(resource.Resource):
    isLeaf = False
    
    def __init__(self, commandSenderFactory):
        resource.Resource.__init__(self)
        self.commandSenderFactory = commandSenderFactory
    
    def getChild(self, name, request):
        
        if name == "sendCommand":
            return self._handle_sendCommand(request)
        elif name == "listDevices":
            return DeviceListResource(self.commandSenderFactory)

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
            
        device = request.args['toDevice'][0]
        command = request.args['command'][0]
            
        return DeviceCommandResource(device, command, self.commandSenderFactory)


# start up the device server
factory = DeviceCommandFactory()
endpoints.serverFromString(reactor, "tcp:8007").listen(factory)

# start up the control server
endpoints.serverFromString(reactor, "tcp:8080").listen(server.Site(CommandServer(factory)))

# start the run loop
reactor.run()