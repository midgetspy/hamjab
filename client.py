from twisted.internet import reactor
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.internet.defer import inlineCallbacks, returnValue

root_url = 'http://localhost:8080/sendCommand'

agent = Agent(reactor)

class SyncronousWebClient(object):
    
    @inlineCallbacks
    def _get(self, url):
        response = yield agent.request('GET', url, self.headers, None)
        responseBody = yield readBody(response)
        returnValue(responseBody)
    
class AutomationWebClient(SyncronousWebClient):
    headers = Headers({'User-Agent': ['Client']})
    
    def __init__(self, name):
        self.name = name

    def _build_url(self, toDevice, command):
        return '{}?fromClient={}&toDevice={}&command={}'.format(root_url, self.name, toDevice, command) 
    
    def executeCommand(self, toDevice, command):
        url = self._build_url(toDevice, command)
        print "Sending request to", url
        return self._get(url)

    
client = AutomationWebClient('MyClient')
result = client.executeCommand('myDevice', 'myCommand')
result.addCallback(lambda x: print_it(x))

def print_it(x):
    print x

#reactor.run()
