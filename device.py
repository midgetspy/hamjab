import time
from twisted.internet import protocol, reactor, endpoints
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol

class DeviceClientProtocol(protocol.Protocol):
    def __init__(self, deviceId):
        self.deviceId = deviceId
    
    def connectionMade(self):
        print 'connected, sending my deviceId', self.deviceId
        self.transport.write(self.deviceId)
    
    def dataReceived(self, data):
        print 'received data', data
        time.sleep(2)
        print 'answering with response:' + data
        self.transport.write('response:' + data)

class DeviceClientFactory(protocol.ReconnectingClientFactory):
    maxDelay = 60
    
    def __init__(self, deviceId):
        self.deviceId = deviceId
    
    def startedConnecting(self, connector):
        print 'Attempting to connect to', connector.getDestination()
    
    def buildProtocol(self, addr):
        print 'Successfully connected to', addr
        self.resetDelay()
        return DeviceClientProtocol(self.deviceId)

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection.  Reason:', reason
        protocol.ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed. Reason:', reason
        protocol.ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

if __name__ == "__main__":
    reactor.connectTCP("localhost", 8007, DeviceClientFactory('myDevice'))
    reactor.run()