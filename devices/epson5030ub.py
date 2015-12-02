from device_lib import SerialDevice

class Device(SerialDevice):
    """
    A protocol which can send commands to an Epson 5030UB projector and return the
    responses it gives.
    """
    delimiter = ':'
    deviceId = 'epson5030ub'
    
    def lineReceived(self, line):
        line = line.rstrip('\r')
        SerialDevice.lineReceived(self, line)

