import json

from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet import protocol, reactor
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks
from twisted.internet import error

from twisted.protocols.basic import LineReceiver

def timeoutDeferred(deferred, timeout):
    delayedCall = reactor.callLater(timeout, deferred.cancel)
    def gotResult(result):
        if delayedCall.active():
            delayedCall.cancel()
        return result
    deferred.addBoth(gotResult)

################################################### common code
class QueuedLineSender(LineReceiver):
    """
    A class which provides functionality for sending and receiving lines. It expects every line which is sent
    to result in a return line (even if it's empty). It will not send the next line until an answer has been received
    from the previous one - subsequent commands will be queued and executed once a response is received.
    
    If no response is received after L{timeout} seconds then a L{timeoutResponse} will automatically be returned.
    """
    delimiter = '\r'
    sendDelimiter = '\r'
    timeout = 30
    timeoutResponse = 'TIMEOUT'

    def __init__(self):
        self.responseDeferred = None
        self._requests = []
    
    def lineReceived(self, line):
        if not self.responseDeferred:
            print 'no deferred found to use for data receipt', repr(line)
        else:
            current_deferred = self.responseDeferred
            self.responseDeferred = None
            
            # if there are more requests then kick off the next one
            if self._requests:
                command, queued_deferred = self._requests.pop(0)
                self._sendLine(command, queued_deferred)
            
            current_deferred.callback(line)

    def timeoutDeferred(self, deferred):
        if self.responseDeferred == deferred:
            self.lineReceived(self.timeoutResponse)
        else:
            #TODO: should maybe just be an exception
            print "a deferred finished that wasn't in the front of the queue... looking for it to remove it to at least try and stay sane"
            self._requests = [x for x in self._requests if x[1] != deferred]

    def sendLine(self, line):

        requestDeferred = Deferred(self.timeoutDeferred)
        timeoutDeferred(requestDeferred, self.timeout)
        
        # if we are in the middle of a line then add this one to a queue
        if self.responseDeferred is None:
            self._sendLine(line, requestDeferred)
        else:
            self._requests.append((line, requestDeferred))
        return requestDeferred
    
    def _sendLine(self, line, deferred):
        self.responseDeferred = deferred
        self.transport.write(line + self.sendDelimiter)


################################################# device client
class DeviceClientProtocol(protocol.Protocol):
    """
    A protocol for the Device Client. It announces its device ID on connection and then waits for commands
    to be sent to it. When it receives a command it sends the command to the device and then forwards along
    the device's response.
    """
    def __init__(self, deviceProtocol):
        self.deviceProtocol = deviceProtocol
    
    def connectionMade(self):
        print 'connected, sending my deviceId', self.deviceProtocol.deviceId
        self._sendLine(self.deviceProtocol.deviceId)
    
    def dataReceived(self, data):
        data = data.rstrip('\r')
       
        #TODO: this is totally a race
        d = self.deviceProtocol.sendLine(data)
        d.addCallback(self._sendLine)
        
    def _sendLine(self, line):
        self.transport.write(line + '\r')

class DeviceClientFactory(protocol.ReconnectingClientFactory):
    """
    A factory for creating device client protocols which will automatically reconnect and continue to try reconnecting
    for ever. Subsequent failures will cause the wait time to increase up to a max of 60 seconds.
    """
    maxDelay = 60
    
    def __init__(self, deviceProtocol):
        self.deviceProtocol = deviceProtocol
    
    def startedConnecting(self, connector):
        print 'Attempting to connect to', connector.getDestination()
    
    def buildProtocol(self, addr):
        print 'Successfully connected to', addr
        self.resetDelay()
        return DeviceClientProtocol(self.deviceProtocol)

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection.  Reason:', reason
        protocol.ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed. Reason:', reason
        protocol.ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


##################################################### device server

class DeviceServerProtocol(QueuedLineSender):
    """
    A protocol for the server side of the device client communication. It represents a Device Client on the server
    side and is used to send commands to (and return responses from) the device which it represents.
    """
    
    timeout = 60
    
    def __init__(self):
        QueuedLineSender.__init__(self)
        self.deviceId = None
    
    def lineReceived(self, line):
        if not self.deviceId:
            self.deviceId = line
            self.factory.addDevice(self)
        else:
            QueuedLineSender.lineReceived(self, line)
    
    def connectionLost(self, reason):
        if reason.type is not error.ConnectionAborted:
            self.factory.removeDevice(self)

    def disconnect(self):
        self.transport.abortConnection()


class DeviceServerFactory(protocol.Factory):
    """
    A simple factory for DeviceServerProtocol instances. It instantiates a new instance of the protocol every time a new
    device connects. It also manages the list of devices and is a gateway for sending commands to devices.
    """
    protocol = DeviceServerProtocol
    
    def __init__(self):
        self.devices = {}
    
    def addDevice(self, protocol):
        if protocol.deviceId in self.devices:
            print 'deviceClient already registered, dropping the second one'
            protocol.disconnect()
        self.devices[protocol.deviceId] = protocol
    
    def removeDevice(self, protocol):
        if protocol.deviceId not in self.devices:
            print 'no deviceClient found, not unregistering'
            return
        del self.devices[protocol.deviceId]
        
    @inlineCallbacks
    def sendCommand(self, deviceId, command):
        if deviceId not in self.devices:
            print 'deviceClient', deviceId, 'not connected'
        else:
            result = yield self.devices[deviceId].sendLine(command)
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
        request.write(str(self.command) + '=' + str(result) + "\n")
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


