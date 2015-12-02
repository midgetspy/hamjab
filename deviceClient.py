from twisted.internet import reactor
from lib import DeviceClientFactory

device_name = 'epson5030ub'
server_host = 'localhost'
com_port = 'COM3'

if __name__ == "__main__":

    device = __import__('devices.' + device_name, globals(), locals(), ['Device']).Device

    deviceProtocol = device(com_port)
    deviceProtocol.startConnection()
    
    reactor.connectTCP(server_host, 8007, DeviceClientFactory(deviceProtocol))
    reactor.run()