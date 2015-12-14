from devices.sony_vpl_hw30es import Device, SonyException
from twisted.trial import unittest
from twisted.test import proto_helpers

class SonyDeviceTestCase(unittest.TestCase):
    
    def setUp(self):
        self.protocol = Device('COM3')
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)
    
    def errback(self, x, expectedExceptionType, expectedExceptionMessage=None):
        self.assertEquals(x.type, expectedExceptionType)
        if expectedExceptionMessage:
            self.assertTrue(x.value.message.startswith(expectedExceptionMessage))

    def test_simple_command_no_data(self):

        d = self.protocol.raw_command('0020000003')
        self.assertEqual('\xA9\x00\x20\x00\x00\x03\x23\x9A', self.transport.value())
        self.transport.clear()
        
        d.addCallback(self.assertEqual, '0000')
        self.protocol.dataReceived('\xA9\x00\x00\x03\x00\x00\x03\x9A')
        
        return d

    def test_simple_command_data(self):

        d = self.protocol.raw_command('0020000003')
        self.assertEqual('\xA9\x00\x20\x00\x00\x03\x23\x9A', self.transport.value())
        self.transport.clear()
        
        d.addCallback(self.assertEqual, 'DEAD')
        self.protocol.dataReceived('\xA9\x00\x00\x03\xde\xad\xff\x9A')
        
        return d

    def test_invalid_checksum(self):

        d = self.protocol.raw_command('0020000003')
        self.assertEqual('\xA9\x00\x20\x00\x00\x03\x23\x9A', self.transport.value())
        self.transport.clear()
        
        d.addErrback(lambda x: self.errback(x, SonyException, "Invalid checksum received"))
        self.protocol.dataReceived('\xA9\x00\x00\x03\xde\xad\x00\x9A')
        
        return d
