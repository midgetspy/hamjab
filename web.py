import json
import os.path

from lib import printToConsole, NO_DEVICE_FOUND, TIMEOUT, SUCCESS, DELAY, DISABLED

from twisted.internet import reactor
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.internet.task import deferLater
from twisted.logger import Logger
from twisted.python.filepath import FilePath
from twisted.web.resource import Resource, NoResource, ErrorPage, ForbiddenResource
from twisted.web.server import NOT_DONE_YET
from twisted.web.static import File
from twisted.web.template import Element, renderer, XMLFile, renderElement


class DeviceListResource(Resource):
    """
    A resource which returns the list of active devices as a json list.
    """
    isLeaf = True

    def __init__(self, deviceServerFactory):
        self.deviceServerFactory = deviceServerFactory

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps(self.deviceServerFactory.devices.keys())
    
    
class ArgUtils(object):
    """
    A helper class with a few methods to simplify and standardize dealing with request arguments.
    """
    @staticmethod
    def _check_arg(expectedArg, args): 
        if expectedArg not in args:
            return ErrorPage(500, "Missing parameter", "Query String argument " + expectedArg + " is not optional")
        return None
    
    @staticmethod
    def _get_args(request, args):
        return [request.args[x][0] for x in args]


class DeferredLeafResource(Resource):
    """
    A base class for resources which are leaf nodes which have deferred rendering of their content. It prevents errors if the request
    is canceled before the deferred is finished.
    """
    do_render = True
    isLeaf = True
    
    def __init__(self):
        Resource.__init__(self)

    def render_GET(self, request):
        # if it finishes prematurely then cancel the command
        finishedDeferred = request.notifyFinish()
        finishedDeferred.addErrback(self.dont_render)

        request.setHeader("content-type", "text/plain")
    
        self._delayedRender(request)
        
        return NOT_DONE_YET

    def dont_render(self, ignored):
        self.do_render = False

    def _delayedRender(self, request):
        raise Exception("Shouldn't call this")

class SendCommandResource(DeferredLeafResource):
    """
    A resource which receives a request to sendCommand and uses the query parameters given to send a command
    to the specified device. It will wait until the command result comes back before sending the response.
    """
    log = Logger(observer=printToConsole)

    def __init__(self, device, command):
        DeferredLeafResource.__init__(self)
        self.device = device
        self.command = command

    @inlineCallbacks
    def _delayedRender(self, request):
        result = yield self.device.sendCommand(self.command)

        if not self.do_render:
            self.log.debug("Command finished with result {result} but nobody is waiting for the result", result=result)
            returnValue(None)
            
        if result == NO_DEVICE_FOUND:
            request.setResponseCode(500)
            request.write(NO_DEVICE_FOUND)
        else:
            request.write(str(result))
        request.finish()

class GetUnsolicitedResource(DeferredLeafResource):
    """
    A resource which handles requests for unsolicited messages for a particular device.
    """
    
    log = Logger(observer=printToConsole)

    def __init__(self, device):
        DeferredLeafResource.__init__(self)
        self.device = device

    @inlineCallbacks
    def _delayedRender(self, request):
        result = yield self.device.getUnsolicitedData()

        if not self.do_render:
            self.log.debug("Command finished with result {result} but nobody is waiting for the result", result=result)
            returnValue(None)
            
        if result == NO_DEVICE_FOUND:
            request.setResponseCode(500)
            request.write(NO_DEVICE_FOUND)
        else:
            request.write(str(result))
        request.finish()

class DeviceResource(Resource):
    """
    The resource which serves up all resource related to a device (currently sendCommand, frontEnd, and getUnsolicited). 
    """
    
    isLeaf = False
    
    log = Logger(observer=printToConsole)

    def __init__(self, device):
        Resource.__init__(self)
        self.device = device

    def getChild(self, name, request):
        if name == 'sendCommand':
            args = ('fromClient', 'command')
            for arg in args:
                result = ArgUtils._check_arg(arg, request.args)
                if result:
                    return result
                
            (client, command) = ArgUtils._get_args(request, args)
                        
            return SendCommandResource(self.device, command)
        
        elif name == 'frontEnd':
            return File('etc/devices/{device}'.format(device=self.device.deviceId))

        elif name == 'help':
            return File('etc/help/')

        elif name == 'getUnsolicited':
            return GetUnsolicitedResource(self.device)
        
        else:
            self.log.warn("Unknown page requested: {name!r} as part of {path}", name=repr(name), path=request.path)

        return NoResource()

class MacroResource(DeferredLeafResource):
    """
    A resource which will fire off the specified macro, wait for it to complete, and return the status. If all commands in the
    macro are able to run successfully the result will be SUCCESS, otherwise a failure result will be provided.
    """
    
    arg = "macroName"
    
    log = Logger(observer=printToConsole)

    def __init__(self, deviceServerFactory, macroName, macro):
        DeferredLeafResource.__init__(self)
        self.deviceServerFactory = deviceServerFactory
        self.macroName = macroName
        self.macro = macro

    @inlineCallbacks
    def _delayedRender(self, request):
        
        def fail(result):
            self.log.warn("Command failed in macro {macroName}, halting execution. Command was {command}", macroName=self.macroName, command=command)
            request.setResponseCode(500)
            request.write(result)
            request.finish()
            returnValue(None)
        
        for command in self.macro['commands']:
            
            deviceId = command['device']
            
            if deviceId == DELAY:
                length = int(command['command'])
                self.log.debug("Starting a delay task for {length} seconds", length=length)
                yield deferLater(reactor, length, lambda x: None, DELAY)

            elif not self.deviceServerFactory.isDeviceRegistered(deviceId):
                fail(NO_DEVICE_FOUND)
            
            else:
                device = self.deviceServerFactory.getDevice(deviceId)
                
                result = yield device.sendCommand(command['command'])
                if result in (NO_DEVICE_FOUND, TIMEOUT):
                    fail(result)
        
        self.log.info("Finished running macro {macroName}", macroName=self.macroName)
        request.write(SUCCESS)
        request.finish()

class MainPageRenderer(Element):
    """
    A template renderer for the index page which displays a list of macros and a list of devices.
    """
    
    loader = XMLFile(FilePath('etc/home/index.html'))

    def __init__(self, macros, deviceServerFactory):
        self.macros = macros
        self.deviceServerFactory = deviceServerFactory
    
    @renderer
    def macroList(self, request, tag):
        if not CommandServer.isDisabled:
            for macro in sorted(self.macros, key=lambda x: self.macros[x]['name']):
                yield tag.clone().fillSlots(macroName = self.macros[macro]['name'], macroId=macro)
    
    @renderer
    def deviceList(self, request, tag):
        if not CommandServer.isDisabled:
            for device in sorted(self.deviceServerFactory.devices):
                try:
                    device_path = FilePath('etc/devices/{device}/device.json'.format(device=device))
                    with device_path.open() as device_file:
                        device_data = json.load(device_file)
                        deviceName = device_data['name'] 
                except Exception as e:
                    deviceName = device
                yield tag.clone().fillSlots(deviceId = device, deviceName = deviceName)
                
    @renderer
    def status(self, request, tag):
        if CommandServer.isDisabled:
            status = 'Enable'
        else:
            status = 'Disable'
            
        return tag.fillSlots(status=status)

class TemplateResource(Resource):
    """
    A small wrapper around the Resource object which takes in an Element and renders that element to the request.
    """
    
    isLeaf = True
    
    def __init__(self, renderer):
        Resource.__init__(self)
        self.renderer = renderer

    def render_GET(self, request):
        request.setHeader("content-type", "text/html")
        return renderElement(request, self.renderer)

class TemplateFile(File):
    """
    A class which can optionally template any .html file if an appropriate renderer is provided. Any file which doesn't
    have a template renderer associated with it will just be served up like normal.
    """
    
    def __init__(self, *args, **kwargs):
        File.__init__(self, *args, **kwargs)
        self.processors = {'.html': self._processTemplate}
        self.renderers = {}
 
    def addRenderer(self, name, renderer):
        self.renderers[name] = renderer
 
    def _processTemplate(self, path, registry):
        file_name = os.path.splitext(os.path.basename(path))[0]
        if file_name in self.renderers:
            return TemplateResource(self.renderers[file_name])
        else:
            return File(path)

class CommandServer(Resource):
    """
    The root resource. Serves the root resources (devices, macro, and home).
    """
    
    isLeaf = False
    isDisabled = False
    
    def __init__(self, deviceServerFactory, macros):
        Resource.__init__(self)
        self.macros = macros
        self.deviceServerFactory = deviceServerFactory
    
    def getChild(self, name, request):
        
        if name == "home":
            templateParser = TemplateFile('etc/home/')
            templateParser.addRenderer('index', MainPageRenderer(self.macros, self.deviceServerFactory))
            return templateParser

        elif name == "toggleStatus":
            CommandServer.isDisabled = not CommandServer.isDisabled
            return ErrorPage(200, "Status", "Toggled the site status")

        elif CommandServer.isDisabled:
            return ForbiddenResource("The site is disabled")

        elif name == "listDevices":
            return DeviceListResource(self.deviceServerFactory)
        
        elif name == "macro":
            result = ArgUtils._check_arg("macroName", request.args)
            if result:
                return result
            
            (macroName, ) = ArgUtils._get_args(request, ("macroName",))
            
            if macroName not in self.macros:
                return NoResource()
            
            return MacroResource(self.deviceServerFactory, macroName, self.macros[macroName])
        
        elif self.deviceServerFactory.isDeviceRegistered(name) and '/' in request.path:
            
            device = self.deviceServerFactory.getDevice(name)
            
            return DeviceResource(device)
        
        
        return NoResource()

