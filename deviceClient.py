import importlib

from twisted.internet import reactor
from lib import DeviceClientFactory

device_name = 'epson5030ub'
server_host = 'localhost'

if __name__ == "__main__":

    device = importlib.import_module('devices.' + device_name).Device

    deviceProtocol = device()
    deviceProtocol.startConnection()
    
    reactor.connectTCP(server_host, 8007, DeviceClientFactory(deviceProtocol))
    reactor.run()