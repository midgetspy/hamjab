import argparse
import json
import os

from hamjab.lib import DeviceServerFactory, DEFAULT_DEVICE_SERVER_PORT
from hamjab.web import CommandServer

from control_logic import eventCallback, commandCallback

from twisted.web import server
from twisted.internet import reactor, endpoints

def parse_macro_file(parser, macro_file_name):
    root = os.path.dirname(os.path.realpath(__file__))
    macro_file_path = os.path.join(root, macro_file_name)
    if not os.path.isfile(macro_file_path):
        parser.error("Invalid macro file provided: " + macro_file_name)
    
    with open(macro_file_path) as macro_file:
        macros = json.load(macro_file)
    
        print "Loaded the following macros from", macro_file_name
        for macro in macros:
            print macro

        return macros

parser = argparse.ArgumentParser(description='Run a device and control server')
parser.add_argument('macros',
                    help='The location of the file containing the macros that will be supported',
                    type=lambda x: parse_macro_file(parser, x),
                    metavar='macroFile',
                    nargs='?',
                    default={})
parser.add_argument('--controlServerPort',
                    help='The port of the control (web) server',
                    default=8080,
                    type=int)
parser.add_argument('--deviceServerPort',
                    help='The port of the device server',
                    default=DEFAULT_DEVICE_SERVER_PORT,
                    type=int)
parser.add_argument('--interface',
                    help='The interface that the ports should be bound to',
                    default='')

args = parser.parse_args()

# start up the device server
factory = DeviceServerFactory(args.macros, eventCallback, commandCallback)
endpoints.TCP4ServerEndpoint(reactor, args.deviceServerPort, interface=args.interface).listen(factory)

# start up the control server
endpoints.TCP4ServerEndpoint(reactor, args.controlServerPort, interface=args.interface).listen(server.Site(CommandServer(factory)))

# start the run loop
reactor.run()