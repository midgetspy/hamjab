import argparse

from twisted.internet import reactor
from lib import DeviceClientFactory, DEFAULT_DEVICE_SERVER_PORT

parser = argparse.ArgumentParser(description='Run a device client')
parser.add_argument('deviceServerHost',
                    help='The IP or hostname of the device server')
parser.add_argument('deviceType',
                    help='The id of the device that this client should talk to')
parser.add_argument('deviceConnectionString',
                    help='The connection string used to connect to the device. For a Serial device this is like COM3 or /dev/ttyS0, for an ethernet device it may be something like 192.168.1.50:8181.')
parser.add_argument('--deviceServerPort',
                    help='The port of the device server',
                    default=DEFAULT_DEVICE_SERVER_PORT,
                    type=int)
args = parser.parse_args()

try:
    device = __import__('devices.' + args.deviceType, globals(), locals(), ['Device']).Device
except ImportError:
    parser.error("Invalid deviceType: " + args.deviceType)

deviceProtocol = device(args.deviceConnectionString)
deviceProtocol.startConnection()

reactor.connectTCP(args.deviceServerHost, args.deviceServerPort, DeviceClientFactory(deviceProtocol))
reactor.run()