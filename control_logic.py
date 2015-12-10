def eventCallback(deviceServer, deviceId, event):
    """
        deviceServer: An reference directly to the device server which can be used to communicate
            with other devices and execute macros. See below for more information.
        deviceId: The ID of the device which sent this event
        event: The event string
    
        The following commands are available on the deviceServer instance:
            deviceServer.runMacro('myMacro')
            deviceServer.sendCommand('deviceId', 'myCommand')
        
        Both of the above commands return a Twisted Deferred object which you can
        use to watch for the result if you want. You can also 
    """
    #print ("{deviceId} event: {event}".format(deviceId=deviceId, event=event))
    pass
    
def commandCallback(deviceServer, deviceId, command, response):
    """
        deviceServer: An reference directly to the device server which can be used to communicate
            with other devices and execute macros. See below for more information.
        deviceId: The ID of the device which just executed a command
        command: The command which was executed 
        response: The response which was returned from the command execution
    
        The following commands are available on the deviceServer instance:
            deviceServer.runMacro('myMacro')
            deviceServer.sendCommand('deviceId', 'myCommand')
    """
    #print ("{deviceId} command: {command} -> {response}".format(deviceId=deviceId, command=command, response=response))
    pass

