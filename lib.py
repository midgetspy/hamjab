import json, traceback, unicodedata

from twisted.logger import Logger, ILogObserver, formatEventAsClassicLogText
from twisted.web import resource
from twisted.web.server import NOT_DONE_YET
from twisted.web.static import File
from twisted.internet import protocol, reactor, error
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks
from twisted.internet.task import deferLater
from twisted.protocols.basic import LineReceiver

from zope.interface import provider

def timeoutDeferred(deferred, timeout):
    delayedCall = reactor.callLater(timeout, deferred.cancel)
    def gotResult(result):
        if delayedCall.active():
            delayedCall.cancel()
        return result
    deferred.addBoth(gotResult)

################################################### common code
@provider(ILogObserver)
def printToConsole(event):
    log = formatEventAsClassicLogText(event)
    if log == None:
        print "NO LOG TRACEBACK", traceback.format_stack()
    print log,

############################## constants
TIMEOUT = 'TIMEOUT'
NO_DEVICE_FOUND = 'NO_DEVICE_FOUND'
SUCCESS = 'SUCCESS'
DELAY = 'DELAY'

class QueuedLineSender(LineReceiver):
    """
    A class which provides functionality for sending and receiving lines. It expects every line which is sent
    to result in a return line (even if it's empty). It will not send the next line until an answer has been received
    from the previous one - subsequent commands will be queued and executed once a response is received.
    
    If no response is received after L{timeout} seconds then a TIMEOUT will automatically be returned.
    """
    delimiter = '\r'
    sendDelimiter = '\r'
    timeout = 30

    log = Logger(observer=printToConsole)

    def __init__(self):
        self.responseDeferred = None
        self.unsoliticedDeferreds = []
        self._requests = []

    def lineReceived(self, line):
        if not self.responseDeferred:
            self._receivedUnsolicitedLine(line)
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
            self.lineReceived(TIMEOUT)
        else:
            #TODO: should maybe just be an exception
            self.log.warn("A deferred finished that wasn't in the front of the queue... looking for it to remove it to at least try and stay sane")
            self._requests = [x for x in self._requests if x[1] != deferred]

    def sendLine(self, line, callback):

        # create a deferred to be fired when this line receives a response
        requestDeferred = Deferred(self.timeoutDeferred)
        requestDeferred.addCallback(callback)
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
    
    def _timeoutUnsolicited(self, deferred):
        if deferred in self.unsoliticedDeferreds:
            deferred.callback(TIMEOUT)
            self.unsoliticedDeferreds.remove(deferred)
            
    def _receivedUnsolicitedLine(self, line):
        self.log.debug("Received unsolicited line: {line!r}", line=line)

        deferredList = self.unsoliticedDeferreds
        self.unsoliticedDeferreds = []

        for deferred in deferredList:
            deferred.callback(line)
    
    def getUnsolicitedData(self, callback):
        newDeferred = Deferred(self._timeoutUnsolicited)
        newDeferred.addCallback(callback)
        timeoutDeferred(newDeferred, self.timeout)
        
        self.unsoliticedDeferreds.append(newDeferred)
        
        return newDeferred


################################################# device client
class DeviceClientProtocol(protocol.Protocol):
    """
    A protocol for the Device Client. It announces its device ID on connection and then waits for commands
    to be sent to it. When it receives a command it sends the command to the device and then forwards along
    the device's response.
    """
    
    lineEnd = '\r'
    
    log = Logger(observer=printToConsole)
    
    def __init__(self, deviceProtocol):
        self.deviceProtocol = deviceProtocol
        
        self.deviceProtocol.getUnsolicitedData(self._receivedUnsolicited)
    
    def _receivedUnsolicited(self, data):
        if data != TIMEOUT:
            self._sendLine(data)
        
        self.deviceProtocol.getUnsolicitedData(self._receivedUnsolicited)
    
    def connectionMade(self):
        self.log.info("Connected, registering device {deviceId!s}", deviceId=self.deviceProtocol.deviceId)
        self._sendLine(self.deviceProtocol.deviceId)
    
    def dataReceived(self, data):
        data = data.rstrip(self.lineEnd)
        self.deviceProtocol.sendLine(data, self._sendLine)
        
    def _sendLine(self, line):
        self.transport.write(line + self.lineEnd)

class DeviceClientFactory(protocol.ReconnectingClientFactory):
    """
    A factory for creating device client protocols which will automatically reconnect and continue to try reconnecting
    for ever. Subsequent failures will cause the wait time to increase up to a max of 60 seconds.
    """
    maxDelay = 60
    
    log = Logger(observer=printToConsole)
    
    def __init__(self, deviceProtocol):
        self.deviceProtocol = deviceProtocol
    
    def startedConnecting(self, connector):
        self.log.info("Attempting to connect to {destination!s}", destination=connector.getDestination())
    
    def buildProtocol(self, addr):
        self.log.info("Successfully connected to {destination!s}", destination=addr)
        self.resetDelay()
        return DeviceClientProtocol(self.deviceProtocol)

    def clientConnectionLost(self, connector, reason):
        self.log.info("Lost connection. Reason: {reason!s}", reason=reason)
        protocol.ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        self.log.info("Connection failed. Reason: {reason!s}", reason=reason)
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
    log = Logger(observer=printToConsole)
    
    def __init__(self):
        self.devices = {}
    
    def addDevice(self, protocol):
        if protocol.deviceId in self.devices:
            self.log.warn("Received a registration for {deviceId} but one is already registered, ignoring the second device", deviceId=protocol.deviceId)
            protocol.disconnect()
        else:
            self.log.info("Device client with id {deviceId} connected", deviceId=protocol.deviceId)
            self.devices[protocol.deviceId] = protocol
    
    def removeDevice(self, protocol):
        if protocol.deviceId not in self.devices:
            self.log.warn("Attempted to unregister device {deviceId} but no device was found", deviceId=protocol.deviceId)
        else:
            self.log.info("Device client with id {deviceId} disconnected", deviceId=protocol.deviceId)
            del self.devices[protocol.deviceId]
        
    @inlineCallbacks
    def getUnsolicitedData(self, deviceId, callback):
        if deviceId not in self.devices:
            self.log.warn("Received a command for {deviceId} but no device is connected", deviceId=deviceId)
            returnValue(NO_DEVICE_FOUND)
        else:
            result = yield self.devices[deviceId].getUnsolicitedData(callback)
            returnValue(result)
        
    @inlineCallbacks
    def sendCommand(self, deviceId, command, callback):
        if deviceId not in self.devices and deviceId != DELAY:
            self.log.warn("Received a command for {deviceId} but no device is connected", deviceId=deviceId)
            returnValue(NO_DEVICE_FOUND)
        else:
            
            if type(command) is unicode:
                command = unicodedata.normalize('NFKD', command).encode('ascii', 'ignore')

            if deviceId == DELAY:
                length = int(command)
                self.log.debug("Starting a delay task for {length} seconds", length=length)
                result = yield deferLater(reactor, length, callback, DELAY)
            else:
    
                self.log.debug("Sending command {command} to device {deviceId}", command=command, deviceId=deviceId)
                result = yield self.devices[deviceId].sendLine(command, callback)
                self.log.debug("Result of command {command} was '{result}'", command=command, result=result)
            
            returnValue(result)

############# web server

class DeviceListResource(resource.Resource):
    isLeaf = True

    def __init__(self, commandSenderFactory):
        self.commandSenderFactory = commandSenderFactory

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps(self.commandSenderFactory.devices.keys())
    
    
class ResourceBase(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)

    def _check_arg(self, expectedArg, args): 
        if expectedArg not in args:
            return resource.ErrorPage(500, "Missing parameter", "Query String argument " + expectedArg + " is not optional")
        return None
    
    def _get_args(self, request, args):
        return [request.args[x][0] for x in args]

class SendCommandResource(ResourceBase):
    isLeaf = True
    
    log = Logger(observer=printToConsole)

    def __init__(self, device, command, commandSenderFactory):
        ResourceBase.__init__(self)
        self.device = device
        self.command = command
        self.commandSenderFactory = commandSenderFactory

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        
        deferredRender = self.commandSenderFactory.sendCommand(self.device, self.command, lambda x: self._delayedRender(request, x))
        
        # if it finishes prematurely then cancel the command
        finishedDeferred = request.notifyFinish()
        finishedDeferred.addErrback(lambda x: deferredRender.cancel())
        
        return NOT_DONE_YET
    
    def _delayedRender(self, request, result):
        if result == NO_DEVICE_FOUND:
            request.setResponseCode(500)
            request.write(NO_DEVICE_FOUND)
        else:
            request.write(str(result))
        request.finish()
        
        return result

class GetUnsolicitedResource(ResourceBase):
    isLeaf = True
    
    log = Logger(observer=printToConsole)

    def __init__(self, device, commandSenderFactory):
        ResourceBase.__init__(self)
        self.device = device
        self.commandSenderFactory = commandSenderFactory

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        
        deferredRender = self.commandSenderFactory.getUnsolicitedData(self.device, lambda x: self._delayedRender(request, x))
        
        # if it finishes prematurely then cancel the command
        finishedDeferred = request.notifyFinish()
        finishedDeferred.addErrback(lambda x: deferredRender.cancel())
        
        return NOT_DONE_YET
    
    def _delayedRender(self, request, result):
        if result == NO_DEVICE_FOUND:
            request.setResponseCode(500)
            request.write(NO_DEVICE_FOUND)
        else:
            request.write(str(result))
        request.finish()
        
        return result

class DeviceResource(ResourceBase):
    isLeaf = False
    
    log = Logger(observer=printToConsole)

    def __init__(self, device, commandSenderFactory):
        ResourceBase.__init__(self)
        self.device = device
        self.commandSenderFactory = commandSenderFactory

    def getChild(self, name, request):
        if name == 'sendCommand':
            args = ('fromClient', 'command')
            for arg in args:
                result = self._check_arg(arg, request.args)
                if result:
                    return result
                
            (client, command) = self._get_args(request, args)
                        
            return SendCommandResource(self.device, command, self.commandSenderFactory)
        elif name == 'frontEnd':
            return File('frontends/{device}/'.format(device=self.device))
        elif name == 'getUnsolicited':
            return GetUnsolicitedResource(self.device, self.commandSenderFactory)
        else:
            self.log.warn("Unknown page requested: {name!r} as part of {path}", name=repr(name), path=request.path)

        return resource.NoResource()

class MacroResource(ResourceBase):
    isLeaf = True
    
    log = Logger(observer=printToConsole)

    macroJson = """
{
    "startTheatre": {
        "name": "Prepare theatre",
        "commands": [
            {"device": "epson5030ub", "command": "PWR ON"},
            {"device": "lutrongrx3000", "command": ":A11"}
        ]
    },
    "enable3D": {
        "name": "Enable 3D",
        "commands": [
            {"device": "epson5030ub", "command": "KEY AA"},
            {"device": "epson5030ub", "command": "KEY 59"},
            {"device": "epson5030ub", "command": "KEY 49"},
            {"device": "epson5030ub", "command": "KEY 3C"},
            {"device": "epson5030ub", "command": "KEY 9F"}
        ]
    },
    "disable3D": {
        "name": "Disable 3D",
        "commands": [
            {"device": "epson5030ub", "command": "KEY AA"},
            {"device": "epson5030ub", "command": "KEY 58"},
            {"device": "epson5030ub", "command": "KEY 49"},
            {"device": "epson5030ub", "command": "KEY 3C"},
            {"device": "epson5030ub", "command": "KEY 9F"}
        ]
    },
    "cycleLights": {
        "name": "Cycle the lights",
        "commands": [
            {"device": "lutrongrx3000", "command": ":A11"},
            {"device": "DELAY", "command": "3"},
            {"device": "lutrongrx3000", "command": ":A01"}
        ]
    }
}
"""

    macros = json.loads(macroJson)
    
    def __init__(self, commandSenderFactory):
        ResourceBase.__init__(self)
        self.commandSenderFactory = commandSenderFactory

    @inlineCallbacks
    def _handle_runMacro(self, request, macroName):
        macro = self.macros[macroName]
        
        for command in macro['commands']:
            
            result = yield self.commandSenderFactory.sendCommand(command['device'], command['command'], lambda x: x)
            
            if result in (NO_DEVICE_FOUND, TIMEOUT):
                self.log.warn("Command failed in macro {macroName}, halting execution. Command was {command}", macroName=macroName, command=command)
                request.setResponseCode(500)
                request.write(result)
                request.finish()
                returnValue(None)
        
        self.log.info("Finished running macro {macroName}", macroName=macroName)
        request.write(SUCCESS)
        request.finish()

    def render_GET(self, request):
        request.setHeader("content-type", "text/plain")
        arg = "macroName"
        result = self._check_arg(arg, request.args)
        if result:
            returnValue(result)
        
        (macroName, ) = self._get_args(request, (arg,))
        
        if macroName not in self.macros:
            return resource.NoResource().render(request)

        self._handle_runMacro(request, macroName)
        
        return NOT_DONE_YET


class CommandServer(ResourceBase):
    isLeaf = False
    
    def __init__(self, commandSenderFactory):
        ResourceBase.__init__(self)
        self.commandSenderFactory = commandSenderFactory
    
    def getChild(self, name, request):
        
        if name == "listDevices":
            return DeviceListResource(self.commandSenderFactory)
        elif name == "macro":
            return MacroResource(self.commandSenderFactory)
        elif name in self.commandSenderFactory.devices and '/' in request.path:
            return DeviceResource(name, self.commandSenderFactory)

        return resource.NoResource()


