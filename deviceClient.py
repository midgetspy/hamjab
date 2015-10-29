from twisted.internet import reactor

from lib import DeviceClientFactory

if __name__ == "__main__":
    reactor.connectTCP("localhost", 8007, DeviceClientFactory('myDevice'))
    reactor.run()