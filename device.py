import time
from twisted.internet import protocol, reactor, endpoints

class Echo(protocol.Protocol):
    def dataReceived(self, data):
        print "echoing:", data
        time.sleep(1)
        self.transport.write('reply: ' + data)
        self.transport.loseConnection()

class EchoFactory(protocol.Factory):
    def buildProtocol(self, addr):
        print "building", addr
        return Echo()
    
if __name__ == "__main__":
    endpoints.serverFromString(reactor, "tcp:1234").listen(EchoFactory())
    reactor.run()