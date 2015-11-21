import json
import traceback, unicodedata
import os.path

from twisted.logger import Logger, ILogObserver, formatEventAsClassicLogText
from twisted.web.resource import Resource, NoResource, ErrorPage
from twisted.web.server import NOT_DONE_YET
from twisted.web.static import File
from twisted.web.template import Element, renderer, XMLFile, renderElement
from twisted.internet import protocol, reactor, error
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks
from twisted.internet.task import deferLater
from twisted.protocols.basic import LineReceiver
from twisted.python.filepath import FilePath

from zope.interface import provider

def timeoutDeferred(deferred, timeout):
    delayedCall = reactor.callLater(timeout, deferred.cancel)
    def gotResult(result):
        if delayedCall.active():
            delayedCall.cancel()
        return result
    deferred.addBoth(gotResult)

############################## constants
TIMEOUT = 'TIMEOUT'
NO_DEVICE_FOUND = 'NO_DEVICE_FOUND'
SUCCESS = 'SUCCESS'
DELAY = 'DELAY'

################################################### common code
@provider(ILogObserver)
def printToConsole(event):
    log = formatEventAsClassicLogText(event)
    if log == None:
        print "NO LOG TRACEBACK", traceback.format_stack()
    print log,


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

    def sendLine(self, line):

        # create a deferred to be fired when this line receives a response
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
    
    def getUnsolicitedData(self):
        newDeferred = Deferred(self._timeoutUnsolicited)
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
        d = self.deviceProtocol.getUnsolicitedData()
        d.addCallback(self._receivedUnsolicited)
    
    def _receivedUnsolicited(self, data):
        if data != TIMEOUT:
            self._sendLine(data)
        
        d = self.deviceProtocol.getUnsolicitedData()
        d.addCallback(self._receivedUnsolicited)
    
    def connectionMade(self):
        self.log.info("Connected, registering device {deviceId!s}", deviceId=self.deviceProtocol.deviceId)
        self._sendLine(self.deviceProtocol.deviceId)
    
    def dataReceived(self, data):
        data = data.rstrip(self.lineEnd)
        d = self.deviceProtocol.sendLine(data)
        d.addCallback(self._sendLine)
        
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
    def getUnsolicitedData(self, deviceId):
        if deviceId not in self.devices:
            self.log.warn("Received a command for {deviceId} but no device is connected", deviceId=deviceId)
            returnValue(NO_DEVICE_FOUND)
        else:
            result = yield self.devices[deviceId].getUnsolicitedData()
            returnValue(result)
        
    @inlineCallbacks
    def sendCommand(self, deviceId, command):
        if deviceId not in self.devices and deviceId != DELAY:
            self.log.warn("Received a command for {deviceId} but no device is connected", deviceId=deviceId)
            returnValue(NO_DEVICE_FOUND)
        else:
            
            if type(command) is unicode:
                command = unicodedata.normalize('NFKD', command).encode('ascii', 'ignore')

            if deviceId == DELAY:
                length = int(command)
                self.log.debug("Starting a delay task for {length} seconds", length=length)
                result = yield deferLater(reactor, length, lambda x: None, DELAY)
            else:
    
                self.log.debug("Sending command {command} to device {deviceId}", command=command, deviceId=deviceId)
                result = yield self.devices[deviceId].sendLine(command)
                self.log.debug("Result of command {command} was '{result}'", command=command, result=result)
            
            returnValue(result)

############# web server

class DeviceListResource(Resource):
    """
    A resource which returns the list of active devices as a json list.
    """
    isLeaf = True

    def __init__(self, commandSenderFactory):
        self.commandSenderFactory = commandSenderFactory

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps(self.commandSenderFactory.devices.keys())
    
    
class ArgUtils(object):
    """
    A helper class with a few methods to simplify and standardize dealing with request arguments.
    """
    @staticmethod
    def _check_arg(expectedArg, args): 
        if expectedArg not in args:
            return ErrorPage(500, "Missing parameter", "Query String argument " + expectedArg + " is not optional")
        return None
    
    @staticmethod
    def _get_args(request, args):
        return [request.args[x][0] for x in args]


class DeferredLeafResource(Resource):
    """
    A base class for resources which are leaf nodes which have deferred rendering of their content. It prevents errors if the request
    is canceled before the deferred is finished.
    """
    do_render = True
    isLeaf = True
    
    def __init__(self):
        Resource.__init__(self)

    def render_GET(self, request):
        # if it finishes prematurely then cancel the command
        finishedDeferred = request.notifyFinish()
        finishedDeferred.addErrback(self.dont_render)

        request.setHeader("content-type", "text/plain")
    
        self._delayedRender(request)
        
        return NOT_DONE_YET

    def dont_render(self, ignored):
        self.do_render = False

    def _delayedRender(self, request):
        raise Exception("Shouldn't call this")

class SendCommandResource(DeferredLeafResource):
    """
    A resource which receives a request to sendCommand and uses the query parameters given to send a command
    to the specified device. It will wait until the command result comes back before sending the response.
    """
    log = Logger(observer=printToConsole)

    def __init__(self, device, command, commandSenderFactory):
        DeferredLeafResource.__init__(self)
        self.device = device
        self.command = command
        self.commandSenderFactory = commandSenderFactory

    @inlineCallbacks
    def _delayedRender(self, request):
        result = yield self.commandSenderFactory.sendCommand(self.device, self.command)

        if not self.do_render:
            self.log.debug("Command finished with result {result} but nobody is waiting for the result", result=result)
            returnValue(None)
            
        if result == NO_DEVICE_FOUND:
            request.setResponseCode(500)
            request.write(NO_DEVICE_FOUND)
        else:
            request.write(str(result))
        request.finish()

class GetUnsolicitedResource(DeferredLeafResource):
    """
    A resource which handles requests for unsolicited messages for a particular device.
    """
    
    log = Logger(observer=printToConsole)

    def __init__(self, device, commandSenderFactory):
        DeferredLeafResource.__init__(self)
        self.device = device
        self.commandSenderFactory = commandSenderFactory

    @inlineCallbacks
    def _delayedRender(self, request):
        result = yield self.commandSenderFactory.getUnsolicitedData(self.device)

        if not self.do_render:
            self.log.debug("Command finished with result {result} but nobody is waiting for the result", result=result)
            returnValue(None)
            
        if result == NO_DEVICE_FOUND:
            request.setResponseCode(500)
            request.write(NO_DEVICE_FOUND)
        else:
            request.write(str(result))
        request.finish()

class DeviceResource(Resource):
    """
    The resource which serves up all resource related to a device (currently sendCommand, frontEnd, and getUnsolicited). 
    """
    
    isLeaf = False
    
    log = Logger(observer=printToConsole)

    def __init__(self, device, commandSenderFactory):
        Resource.__init__(self)
        self.device = device
        self.commandSenderFactory = commandSenderFactory

    def getChild(self, name, request):
        if name == 'sendCommand':
            args = ('fromClient', 'command')
            for arg in args:
                result = ArgUtils._check_arg(arg, request.args)
                if result:
                    return result
                
            (client, command) = ArgUtils._get_args(request, args)
                        
            return SendCommandResource(self.device, command, self.commandSenderFactory)
        elif name == 'frontEnd':
            return File('frontends/{device}/'.format(device=self.device))
        elif name == 'getUnsolicited':
            return GetUnsolicitedResource(self.device, self.commandSenderFactory)
        else:
            self.log.warn("Unknown page requested: {name!r} as part of {path}", name=repr(name), path=request.path)

        return NoResource()

class MacroResource(DeferredLeafResource):
    """
    A resource which will fire off the specified macro, wait for it to complete, and return the status. If all commands in the
    macro are able to run successfully the result will be SUCCESS, otherwise a failure result will be provided.
    """
    
    arg = "macroName"
    
    log = Logger(observer=printToConsole)

    def __init__(self, commandSenderFactory, macroName, macro):
        DeferredLeafResource.__init__(self)
        self.commandSenderFactory = commandSenderFactory
        self.macroName = macroName
        self.macro = macro

    @inlineCallbacks
    def _delayedRender(self, request):
        for command in self.macro['commands']:
            
            result = yield self.commandSenderFactory.sendCommand(command['device'], command['command'])
            
            if result in (NO_DEVICE_FOUND, TIMEOUT):
                self.log.warn("Command failed in macro {macroName}, halting execution. Command was {command}", macroName=self.macroName, command=command)
                request.setResponseCode(500)
                request.write(result)
                request.finish()
                returnValue(None)
        
        self.log.info("Finished running macro {macroName}", macroName=self.macroName)
        request.write(SUCCESS)
        request.finish()

class MainPageRenderer(Element):
    """
    A template renderer for the index page which displays a list of macros and a list of devices.
    """
    
    
    loader = XMLFile(FilePath('home/index.html'))

    def __init__(self, macros, commandSenderFactory):
        self.macros = macros
        self.commandSenderFactory = commandSenderFactory
    
    @renderer
    def macroList(self, request, tag):
        for macro in sorted(self.macros, key=lambda x: self.macros[x]['name']):
            yield tag.clone().fillSlots(macroName = self.macros[macro]['name'], macroId=macro)
    
    @renderer
    def deviceList(self, request, tag):
        for device in sorted(self.commandSenderFactory.devices):
            yield tag.clone().fillSlots(deviceName = device)

class TemplateResource(Resource):
    """
    A small wrapper around the Resource object which takes in an Element and renders that element to the request.
    """
    
    isLeaf = True
    
    def __init__(self, renderer):
        Resource.__init__(self)
        self.renderer = renderer

    def render_GET(self, request):
        request.setHeader("content-type", "text/html")
        return renderElement(request, self.renderer)

class TemplateFile(File):
    """
    A class which can optionally template any .html file if an appropriate renderer is provided. Any file which doesn't
    have a template renderer associated with it will just be served up like normal.
    """
    
    def __init__(self, *args, **kwargs):
        File.__init__(self, *args, **kwargs)
        self.processors = {'.html': self._processTemplate}
        self.renderers = {}
 
    def addRenderer(self, name, renderer):
        self.renderers[name] = renderer
 
    def _processTemplate(self, path, registry):
        file_name = os.path.splitext(os.path.basename(path))[0]
        if file_name in self.renderers:
            return TemplateResource(self.renderers[file_name])
        else:
            return File(path)

class CommandServer(Resource):
    """
    The root resource. Serves the root resources (devices, macro, and home).
    """
    
    isLeaf = False
    
    def __init__(self, commandSenderFactory, macros):
        Resource.__init__(self)
        self.macros = macros
        self.commandSenderFactory = commandSenderFactory
    
    def getChild(self, name, request):
        
        if name == "listDevices":
            return DeviceListResource(self.commandSenderFactory)
        
        elif name == "macro":
            result = ArgUtils._check_arg("macroName", request.args)
            if result:
                return result
            
            (macroName, ) = ArgUtils._get_args(request, ("macroName",))
            
            if macroName not in self.macros:
                return NoResource().render(request)
            
            return MacroResource(self.commandSenderFactory, macroName, self.macros[macroName])
        
        elif name in self.commandSenderFactory.devices and '/' in request.path:
            return DeviceResource(name, self.commandSenderFactory)
        
        elif name == "home":
            templateParser = TemplateFile('home/')
            templateParser.addRenderer('index', MainPageRenderer(self.macros, self.commandSenderFactory))
            return templateParser
        
        return NoResource()

