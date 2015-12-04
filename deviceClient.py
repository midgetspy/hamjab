import argparse
import pkgutil

from twisted.internet import reactor
from lib import DeviceClientFactory, DEFAULT_DEVICE_SERVER_PORT

excluded_packages = ['test', 'device_lib']
device_list = [y for x,y,z in pkgutil.iter_modules(['devices']) if y not in excluded_packages]

parser = argparse.ArgumentParser(description='Run a device client')
parser.add_argument('deviceServerHost',
                    help='The IP or hostname of the device server')
parser.add_argument('deviceType',
                    help='The id of the device that this client should talk to',
                    choices=device_list)
parser.add_argument('deviceConnectionString',
                    help='The connection string used to connect to the device. For a Serial device this the name of the COM port (ie. COM3 or /dev/ttyS0). For an ethernet device this is the ip/host (and port if it is not the device default).')
parser.add_argument('--deviceServerPort',
                    help='The port of the device server',
                    default=DEFAULT_DEVICE_SERVER_PORT,
                    type=int)
args = parser.parse_args()

try:
    device = __import__('devices.' + args.deviceType, globals(), locals(), ['Device']).Device
except (ImportError, AttributeError):
    parser.error("Unable to load deviceType {}".format(args.deviceType))

deviceProtocol = device(args.deviceConnectionString)
deviceProtocol.startConnection()

reactor.connectTCP(args.deviceServerHost, args.deviceServerPort, DeviceClientFactory(deviceProtocol))
reactor.run()