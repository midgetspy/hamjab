import urllib2

class ControlClient(object):
    def __init__(self, hostname, port):
        self.url_root = "http://{host}:{port}/".format(host = hostname, port = port)
    
    def _request_url(self, url_path):
        url = self.url_root + url_path
        page = urllib2.urlopen(url)
        return page.read()
    
    def sendCommand(self, deviceId, command):
        url = "{deviceId}/sendCommand?fromClient=controlClient&command={command}".format(deviceId = deviceId, command = command)
        return self._request_url(url)

    def sendMacro(self, macroName):
        url = "macro?macroName={macroName}".format(macroName = macroName)
        return self._request_url(url)

