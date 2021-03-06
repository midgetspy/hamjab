from hamjab.lib import QueuedLineSender

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort    
from twisted.internet.endpoints import connectProtocol, TCP4ClientEndpoint

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

class EthernetDevice(QueuedLineSender):
    """
    A base class for communicating with a device through ethernet
    
    host_string: Should be IP or hostname and optionally also the port number in the format <host>:<port> (ie. 192.168.1.60:23)
    """
    
    DEFAULT_PORT = 23
    
    def __init__(self, connection_string):
        num_occurrences = connection_string.count(':')
        if num_occurrences == 0:
            self._host = connection_string
            self._port = self.DEFAULT_PORT
        elif num_occurrences == 1:
            self._host, self._port = connection_string.split(':')
            self._port = int(self._port)
        else:
            raise Exception("Invalid connection string {}".format(connection_string))

        QueuedLineSender.__init__(self)
    
    def startConnection(self):
        endpoint = TCP4ClientEndpoint(reactor, self._host, self._port)
        connectProtocol(endpoint, self)
