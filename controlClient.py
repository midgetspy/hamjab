import urllib, urllib2

class ControlClient(object):
    def __init__(self, hostname, port):
        self.url_root = "http://{host}:{port}/".format(host = hostname, port = port)
    
    def _request_url(self, url_path, data):
        url = self.url_root + url_path
        page = urllib2.urlopen(url, data=urllib.urlencode(data))
        return page.read()
    
    def sendCommand(self, deviceId, command):
        url = "{deviceId}/sendCommand".format(deviceId=deviceId)
        data = { 'fromClient': 'pythonControlClient', 'deviceId': deviceId, 'command': command }
        return self._request_url(url, data)

    def sendMacro(self, macroName):
        url = "macro"
        return self._request_url(url, { 'macroName': macroName })

