import os
import operator

from serial import PARITY_EVEN

from hamjab.devices.device_lib import SerialDevice

class SonyException(Exception):
    pass

class Device(SerialDevice):
    """
    An untested device client for a Sony VPL-HW30ES
    """
    deviceId = os.path.splitext(os.path.basename(__file__))[0]

    START = 0xA9
    END = 0x9A
    
    delimiter = chr(END)
    sendDelimiter = chr(END)

    SET = 0x00
    GET = 0x01
    REPLY_DATA = 0x02
    REPLY_NO_DATA = 0x03

    DUMMY_DATA = '0000'
    
    IR_PROJECTOR = 0x17
    IR_PROJECTOR_E = 0x19
    IR_PROJECTOR_EE = 0x1B
    
    SUCCESS = '0000'
    ERRORS = {
               '0101': 'Undefined Command',
               '0104': 'Size Error',
               '0105': 'Select Error',
               '0106': 'Range Over',
               '010A': 'Not Applicable',
               'F010': 'Checksum Error',
               'F020': 'Framing Error',
               'F030': 'Parity Error',
               'F040': 'Over Run Error',
               'F050': 'Other Comm Error',
               }

    def __init__(self, com_port):
        com_options = { 'baudrate': 38400, 'parity': PARITY_EVEN }
        
        SerialDevice.__init__(self, com_port, com_options)

    def ir(self, command_type, code):
        return self._build_packet([command_type, code], self.SET)

    def set(self, item_number, data=DUMMY_DATA):
        return self._build_packet(item_number, self.SET, data)
    
    def get(self, item_number):
        return self._build_packet(item_number, self.GET)

    def raw_command(self, body):
        # convert them to ints because the _build_packet function expects that if it's a str it has to decode it (but we've already done that) 
        body_bytes = [ord(x) for x in self._check_format(body, 5)]
        packet = self._build_packet(body_bytes[0:2], body_bytes[2], body_bytes[3:5])
        return self.sendLine(packet)

    def _bytearray_to_str(self, to_convert):
        return str(to_convert).encode('hex').upper()

    def _process_line(self, reply):
        reply = bytearray(reply)
        
        if len(reply) != 7:
            raise SonyException("Expected the reply to be 8 bytes but it was {length}".format(length=len(reply)))
        elif reply[0] != self.START:
            print type(reply[0]), type(self.START)
            raise SonyException("Invalid start code {!r}".format(reply[0]))
        
        result = reply[1:3]
        command_type = reply[3]
        data = reply[4:6]
        checksum = reply[6]
        
        # check the checksum
        if checksum != self._checksum(reply[1:6]):
            raise SonyException("Invalid checksum received")
        
        if command_type not in (self.REPLY_DATA, self.REPLY_NO_DATA):
            raise SonyException("Unknown reply type received: {}".format(command_type))
        
        result_string = self._bytearray_to_str(result)
        if result_string != self.SUCCESS:
            if result_string in self.ERRORS:
                raise SonyException("Error code in reply: {}".format(self.ERRORS[result_string]))
            else:
                raise SonyException("Unknown result code in reply: {}".format(result_string)) 

        return self._bytearray_to_str(data)

    def _check_format(self, data, length):
        if type(data) is int:
            actual_length = 1
        elif type(data) in (bytearray, list):
            data = [self._check_format(x, 1) for x in data]
            actual_length = len(data)
        elif type(data) is str:
            data = data.decode('hex')
            actual_length = len(data)
        else:
            raise SonyException("Invalid type for input: " + str(type(input)))
        
        if actual_length != length:
            raise SonyException("Invalid length, {data!r} is length {actual_length} not expected length {length}".format(data=data, actual_length=actual_length, length=length))
        
        return data

    def _checksum(self, data):
        return reduce(operator.__or__, data)

    def _build_packet(self, item_number, command_type, data=DUMMY_DATA):
        packet = bytearray(7)
        
        packet[0] = self.START
        
        packet[1:3] = self._check_format(item_number, 2)
        
        packet[3] = self._check_format(command_type, 1)
        
        packet[4:6] = self._check_format(data, 2)
        
        packet[6] = self._checksum(packet[1:6])
        
        return packet
