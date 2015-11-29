import json
import os
import sys

from lib import DeviceServerFactory
from web import CommandServer

from twisted.web import server
from twisted.internet import reactor, endpoints

root = os.path.dirname(os.path.realpath(__file__))

def usage():
    print "Usage: {file} [macro file]".format(file=os.path.basename(__file__))
    exit()

macros = {}

if len(sys.argv) > 2 or sys.argv[1] in ('--help', '-h', '/?'):
    usage()
elif len(sys.argv) == 2:
    macro_file_name = sys.argv[1]
    macro_file_path = os.path.join(root, macro_file_name)
    
    if not os.path.isfile(macro_file_path):
        print "Invalid macro file provided: ", macro_file_name
        exit()

    with open(macro_file_path) as macro_file:
        macros = json.load(macro_file)
    
    print "Loaded the following macros from", macro_file_name
    for macro in macros:
        print macro

# start up the device server
factory = DeviceServerFactory()
endpoints.serverFromString(reactor, "tcp:8007").listen(factory)

# start up the control server
endpoints.serverFromString(reactor, "tcp:8080").listen(server.Site(CommandServer(factory, macros)))

# start the run loop
reactor.run()