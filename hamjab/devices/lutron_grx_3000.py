import os

from hamjab.devices.device_lib import SerialDevice

class Device(SerialDevice):
    """
    A protocol which can send commands to a Lutron GRX-3100/3500 through a GRX-RS232, GRX-AV,
    GRX-PRG, GRX-CI-RS232, etc.
    
    If the "Scene Status" dipswitch is enabled on the RS232 unit the web UI will always
    correctly indicate the currently selected scene even if it's changed via the physical buttons.
    """
    delimiter = '\r\n'
    deviceId = os.path.splitext(os.path.basename(__file__))[0]

