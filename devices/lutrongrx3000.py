from twisted.internet import reactor

from lib import QueuedLineSender
from twisted.internet.serialport import SerialPort    

class Device(QueuedLineSender):
    """
    A protocol which can send commands to a Lutron GRX-3000 with a GRX-RS232
    """
    delimiter = '\r\n'
    deviceId = 'lutrongrx3000'
    
    def lineReceived(self, line):
        if line == '':
            return
        
        QueuedLineSender.lineReceived(self, line)
    
    def startConnection(self):
        SerialPort(self, 'COM3', reactor)

