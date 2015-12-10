import traceback, unicodedata

from twisted.logger import Logger, ILogObserver, formatEventAsClassicLogText
from twisted.internet import protocol, reactor, error
from twisted.internet.defer import Deferred, returnValue, inlineCallbacks
from twisted.protocols.basic import LineReceiver

from zope.interface import provider

_reactor = reactor
def timeoutDeferred(deferred, timeout):
    delayedCall = _reactor.callLater(timeout, deferred.cancel)
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
DISABLED = 'DISABLED'

DEFAULT_DEVICE_SERVER_PORT = 8007

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
        if line == '':
            return

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

        if type(line) is unicode:
            line = unicodedata.normalize('NFKD', line).encode('ascii', 'ignore')

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
    
    @inlineCallbacks
    def getUnsolicitedData(self):
        newDeferred = Deferred(self._timeoutUnsolicited)
        timeoutDeferred(newDeferred, self.timeout)
        
        self.unsoliticedDeferreds.append(newDeferred)
        
        result = yield newDeferred
        returnValue(result)


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

    @inlineCallbacks
    def sendCommand(self, command):
        self.log.debug("Sending command {command} to device {deviceId}", command=command, deviceId=self.deviceId)
        result = yield self.sendLine(command)
        self.log.debug("Result of command {command} was '{result}'", command=command, result=result)
        
        returnValue(result)

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
        
    def isDeviceRegistered(self, deviceId):
        return deviceId in self.devices
        
    def getDevice(self, deviceId):
        if self.isDeviceRegistered(deviceId):
            return self.devices[deviceId]
