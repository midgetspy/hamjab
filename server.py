from lib import DeviceCommandFactory, CommandServer

from twisted.web import server
from twisted.internet import reactor, endpoints

# start up the deviceClient server
factory = DeviceCommandFactory()
endpoints.serverFromString(reactor, "tcp:8007").listen(factory)

# start up the control server
endpoints.serverFromString(reactor, "tcp:8080").listen(server.Site(CommandServer(factory)))

# start the run loop
reactor.run()