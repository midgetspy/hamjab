from hamjab import lib
from hamjab.lib import QueuedLineSender
from twisted.internet.task import Clock
from twisted.trial import unittest
from twisted.test import proto_helpers

class QueuedLineSenderTestCase(unittest.TestCase):
    
    def setUp(self):
        self.protocol = QueuedLineSender()
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)
        
        self._reactor = hamjab.lib._reactor
    
    def tearDown(self):
        hamjab.lib._reactor = self._reactor
    
    def test_commands_queueing(self):
        d = self.protocol.sendLine('test1')
        self.assertEqual('test1\r', self.transport.value())
        self.transport.clear()
        d.addCallback(self.assertEqual, 'answer')
        
        d2 = self.protocol.sendLine('test2')
        self.assertEqual('', self.transport.value())
        d.addCallback(lambda x: self.assertEqual('test2\r', self.transport.value()))
        d2.addCallback(self.assertEqual, 'answer2')
        
        self.protocol.dataReceived('answer\r')
        self.protocol.dataReceived('answer2\r')
        
        return d2

    def test_simple_command(self):
        d = self.protocol.sendLine('test')
        self.assertEqual('test\r', self.transport.value())
        self.transport.clear()
        
        d.addCallback(self.assertEqual, 'answer')
        self.protocol.dataReceived('answer\r')
        
        return d

    def test_simple_command_broken_answer(self):
        d = self.protocol.sendLine('test')
        self.assertEqual('test\r', self.transport.value())
        self.transport.clear()
        
        d.addCallback(self.assertEqual, 'answer')
        self.protocol.dataReceived('an')
        self.protocol.dataReceived('swer')
        self.protocol.dataReceived('\r')
        
        return d

    def test_simple_command_timeout(self):
        
        hamjab.lib._reactor = Clock()
        
        d = self.protocol.sendLine('test')
        self.assertEqual('test\r', self.transport.value())
        self.transport.clear()
        
        d.addCallback(self.assertEqual, 'TIMEOUT')
        self.protocol.dataReceived('an')
        self.protocol.dataReceived('swer')

        hamjab.lib._reactor.advance(self.protocol.timeout)
        
        return d

    def test_unsolicited(self):

        d = self.protocol.getUnsolicitedData()
        
        d.addCallback(self.assertEqual, 'data')
        self.protocol.dataReceived('data\r')

        return d
