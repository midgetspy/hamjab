import os

from hamjab.devices.device_lib import SerialDevice

class Device(SerialDevice):
    """
    A protocol which can send commands to an Epson 5030UB projector and return the
    responses it gives.
    """

    delimiter = ':'
    deviceId = os.path.splitext(os.path.basename(__file__))[0]
    
    def lineReceived(self, line):
        line = line.rstrip('\r')
        SerialDevice.lineReceived(self, line)

