from twisted.internet import reactor

from lib import QueuedLineSender
from twisted.internet.serialport import SerialPort    

class Device(QueuedLineSender):
    """
    A protocol which can send commands to an Epson 5030UB projector and return the
    responses it gives.
    """
    delimiter = ':'
    deviceId = 'epson5030ub'
    
    def lineReceived(self, line):
        line = line.rstrip('\r')
        QueuedLineSender.lineReceived(self, line)
    
    def startConnection(self):
        SerialPort(self, 'COM3', reactor)

