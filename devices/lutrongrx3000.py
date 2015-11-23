from twisted.internet import reactor

from lib import QueuedLineSender
from twisted.internet.serialport import SerialPort    

class Device(QueuedLineSender):
    """
    A protocol which can send commands to a Lutron GRX-3100/3500 through a GRX-RS232, GRX-AV,
    GRX-PRG, GRX-CI-RS232, etc.
    
    If the "Scene Status" dipswitch is enabled on the RS232 unit the web UI will always
    correctly indicate the currently selected scene even if it's changed via the physical buttons.
    """
    delimiter = '\r\n'
    deviceId = 'lutrongrx3000'
    
    def lineReceived(self, line):
        if line == '':
            return
        
        QueuedLineSender.lineReceived(self, line)
    
    def startConnection(self):
        SerialPort(self, 'COM3', reactor)

