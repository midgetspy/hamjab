from hamjab.devices.device_lib import EthernetDevice

class Device(EthernetDevice):
    """
    A device module for a Denon AVR-3312 over ethernet. Also tested on Denon AVR-X4000. Refer
    to the documentation for your particular receiver for differences in the commands.
    """
    deviceId = 'denon_avr_3312'
