from devices.epson_5030ub import Device
from twisted.trial import unittest
from twisted.test import proto_helpers

class EpsonDeviceTestCase(unittest.TestCase):
    
    def setUp(self):
        self.protocol = Device('COM3')
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)
    
    def test_simple_command(self):
        d = self.protocol.sendLine('test')
        self.assertEqual('test\r', self.transport.value())
        self.transport.clear()
        
        d.addCallback(self.assertEqual, 'result')
        self.protocol.dataReceived('result\r')
        self.protocol.dataReceived(':')
        
        return d
