import json
from lib import DeviceServerFactory
from web import CommandServer

from twisted.web import server
from twisted.internet import reactor, endpoints

macroJson = """
{
    "startTheatre": {
        "name": "Prepare theatre",
        "commands": [
            {"device": "epson5030ub", "command": "PWR ON"},
            {"device": "lutrongrx3000", "command": ":A11"}
        ]
    },
    "enable3D": {
        "name": "Enable 3D",
        "commands": [
            {"device": "epson5030ub", "command": "KEY AA"},
            {"device": "epson5030ub", "command": "KEY 59"},
            {"device": "epson5030ub", "command": "KEY 49"},
            {"device": "epson5030ub", "command": "KEY 3C"},
            {"device": "epson5030ub", "command": "KEY 9F"}
        ]
    },
    "disable3D": {
        "name": "Disable 3D",
        "commands": [
            {"device": "epson5030ub", "command": "KEY AA"},
            {"device": "epson5030ub", "command": "KEY 58"},
            {"device": "epson5030ub", "command": "KEY 49"},
            {"device": "epson5030ub", "command": "KEY 3C"},
            {"device": "epson5030ub", "command": "KEY 9F"}
        ]
    },
    "cycleLights": {
        "name": "Cycle the lights",
        "commands": [
            {"device": "lutrongrx3000", "command": ":A11"},
            {"device": "DELAY", "command": "3"},
            {"device": "lutrongrx3000", "command": ":A01"}
        ]
    }
}
"""

macros = json.loads(macroJson)

# start up the device server
factory = DeviceServerFactory()
endpoints.serverFromString(reactor, "tcp:8007").listen(factory)

# start up the control server
endpoints.serverFromString(reactor, "tcp:8080").listen(server.Site(CommandServer(factory, macros)))

# start the run loop
reactor.run()