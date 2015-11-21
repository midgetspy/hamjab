import json
import os.path

from lib import printToConsole, NO_DEVICE_FOUND, TIMEOUT, SUCCESS

from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.logger import Logger
from twisted.python.filepath import FilePath
from twisted.web.resource import Resource, NoResource, ErrorPage
from twisted.web.server import NOT_DONE_YET
from twisted.web.static import File
from twisted.web.template import Element, renderer, XMLFile, renderElement


class DeviceListResource(Resource):
    """
    A resource which returns the list of active devices as a json list.
    """
    isLeaf = True

    def __init__(self, commandSenderFactory):
        self.commandSenderFactory = commandSenderFactory

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return json.dumps(self.commandSenderFactory.devices.keys())
    
    
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

    def __init__(self, device, command, commandSenderFactory):
        DeferredLeafResource.__init__(self)
        self.device = device
        self.command = command
        self.commandSenderFactory = commandSenderFactory

    @inlineCallbacks
    def _delayedRender(self, request):
        result = yield self.commandSenderFactory.sendCommand(self.device, self.command)

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

    def __init__(self, device, commandSenderFactory):
        DeferredLeafResource.__init__(self)
        self.device = device
        self.commandSenderFactory = commandSenderFactory

    @inlineCallbacks
    def _delayedRender(self, request):
        result = yield self.commandSenderFactory.getUnsolicitedData(self.device)

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

    def __init__(self, device, commandSenderFactory):
        Resource.__init__(self)
        self.device = device
        self.commandSenderFactory = commandSenderFactory

    def getChild(self, name, request):
        if name == 'sendCommand':
            args = ('fromClient', 'command')
            for arg in args:
                result = ArgUtils._check_arg(arg, request.args)
                if result:
                    return result
                
            (client, command) = ArgUtils._get_args(request, args)
                        
            return SendCommandResource(self.device, command, self.commandSenderFactory)
        elif name == 'frontEnd':
            return File('frontends/{device}/'.format(device=self.device))
        elif name == 'getUnsolicited':
            return GetUnsolicitedResource(self.device, self.commandSenderFactory)
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

    def __init__(self, commandSenderFactory, macroName, macro):
        DeferredLeafResource.__init__(self)
        self.commandSenderFactory = commandSenderFactory
        self.macroName = macroName
        self.macro = macro

    @inlineCallbacks
    def _delayedRender(self, request):
        for command in self.macro['commands']:
            
            result = yield self.commandSenderFactory.sendCommand(command['device'], command['command'])
            
            if result in (NO_DEVICE_FOUND, TIMEOUT):
                self.log.warn("Command failed in macro {macroName}, halting execution. Command was {command}", macroName=self.macroName, command=command)
                request.setResponseCode(500)
                request.write(result)
                request.finish()
                returnValue(None)
        
        self.log.info("Finished running macro {macroName}", macroName=self.macroName)
        request.write(SUCCESS)
        request.finish()

class MainPageRenderer(Element):
    """
    A template renderer for the index page which displays a list of macros and a list of devices.
    """
    
    
    loader = XMLFile(FilePath('home/index.html'))

    def __init__(self, macros, commandSenderFactory):
        self.macros = macros
        self.commandSenderFactory = commandSenderFactory
    
    @renderer
    def macroList(self, request, tag):
        for macro in sorted(self.macros, key=lambda x: self.macros[x]['name']):
            yield tag.clone().fillSlots(macroName = self.macros[macro]['name'], macroId=macro)
    
    @renderer
    def deviceList(self, request, tag):
        for device in sorted(self.commandSenderFactory.devices):
            yield tag.clone().fillSlots(deviceName = device)

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
    
    def __init__(self, commandSenderFactory, macros):
        Resource.__init__(self)
        self.macros = macros
        self.commandSenderFactory = commandSenderFactory
    
    def getChild(self, name, request):
        
        if name == "listDevices":
            return DeviceListResource(self.commandSenderFactory)
        
        elif name == "macro":
            result = ArgUtils._check_arg("macroName", request.args)
            if result:
                return result
            
            (macroName, ) = ArgUtils._get_args(request, ("macroName",))
            
            if macroName not in self.macros:
                return NoResource().render(request)
            
            return MacroResource(self.commandSenderFactory, macroName, self.macros[macroName])
        
        elif name in self.commandSenderFactory.devices and '/' in request.path:
            return DeviceResource(name, self.commandSenderFactory)
        
        elif name == "home":
            templateParser = TemplateFile('home/')
            templateParser.addRenderer('index', MainPageRenderer(self.macros, self.commandSenderFactory))
            return templateParser
        
        return NoResource()

