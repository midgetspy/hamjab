from devices.device_lib import EthernetDevice
from twisted.trial import unittest

class EthernetDeviceTestCase(unittest.TestCase):
    
    def test_no_port(self):
        toTest = EthernetDevice('192.168.2.1')
        self.assertEqual('192.168.2.1', toTest._host)
        self.assertEqual(23, toTest._port)
    
    def test_with_port(self):
        toTest = EthernetDevice('192.168.2.1:88')
        self.assertEqual('192.168.2.1', toTest._host)
        self.assertEqual(88, toTest._port)

    def test_invalid_format(self):
        self.assertRaises(Exception, EthernetDevice, '192.168.2.1:88:3')

    def test_invalid_port(self):
        self.assertRaises(Exception, EthernetDevice, '192.168.2.1:a')
