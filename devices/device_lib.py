from lib import QueuedLineSender

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort    

class SerialDevice(QueuedLineSender):
    """
    A base class for communicating with a device over a serial port
    
    The default connection settings are 9600 baud, no parity, 8 data bits and 1 stop bit.
    The com port should be in the format 'COM3' for Windows or '/dev/ttyS0' for linux.
    """
    
    def __init__(self, com_port, com_options={}):
        self.com_port = com_port
        self.com_options = com_options
        QueuedLineSender.__init__(self)
    
    def startConnection(self):
        # use the defaults which are: 9600 baud, no parity, 8 data bits and 1 stop bit
        SerialPort(self, self.com_port, reactor, **self.com_options)
