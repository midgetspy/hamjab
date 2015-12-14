## Overview

HamJab is a set of programs which allow you to control devices via RS232/Ethernet remotely through your local network. There are a few different layers of functionality:

1) **Web UI**: Any phone/tablet/PC on your network can use the Web UI to control your devices and execute macros. Example use cases for this include:

- turn on your projector with your phone from another room so it's warmed up and ready by the time you get to the home theatre
- control Zone 2/3 on your receiver from somewhere else in your home using your phone/tablet

2) **Web API**: Any external program can control devices programmatically

- use an RF/bluetooth remote combined with EventGhost so no line of sight is required to your IR-controlled devices
- any existing scripts/program can control devices with the API

3) **Control Logic**: Use simple python logic to have HamJab automate your devices

- have your lights dim when XBMC/Kodi starts playing a movie, raise them when it's paused/stopped
- have your projector switch to 3D mode when XBMC/Kodi plays a 3D movie
- change your projector brightness automatically when watching with the lights on

## How does it work?

HamJab is has two main components:

### Device Client

Each of your devices must be connected to a PC which runs the "Device Client" software. You can connect multiple devices to one PC if you run multiple copies of the device client.

There are a number of ways to connect your RS232 devices to the device server:

- use a PC with a serial port + a long DB9 cable
- use a PC + a USB to RS232 adapter (PL2303), connected with USB or DB9 extension cables
- use a Raspberry Pi + MAX3232 Serial to TTL converter, connected with an ethernet cable
- use a Raspberry Pi + MAX3232 Serial to TTL convertor, connected with a USB wifi dongle

If your device has ethernet control then a device client for it can be run anywhere on the network.

Device clients can be created for anything you want to use in your control logic. For example HamJab ships with a Kodi/XBMC addon which allows it to generate events which can be used in your control logic.

### Server

This is the heart of the HamJab system. All of the device clients will communicate with the HamJab server and can be controlled by it. This server must be up 24/7 to allow reliable control of your devices. Any custom control logic you write will be run on the server.


## Which devices are supported?

Currently HamJab only has Device Client libraries for the devices I own or have had access to test:

- Epson 5030UB
- Lutron GRX-3100/3500
- Denon AVR-3212
- Sony VPL-HW30es
- Kodi

HamJab ships with a lot of helper code which means most devices should be quite simple to add. I'm happy to add support for your device as long as you will work with me to do the testing.

## Documentation

### Components

You can build individual packages from the main HamJab source. To do this run ```build.py```, results will be placed in the ```out``` folder.

### Web UI

Start the server by running ```server.py```. For more information run ```server.py -h```.

By default the server will serve the home page on http://localhost:8080/home

Any macros or connected devices will be available from that page. From the (?) icon you can see a list of possible commands and the related documentation.

If you know what command you want to send you can enter a custom command at http://localhost:8080/device_id/sendCommand 

### WEB API

Send a command to a device:
```
POST: http://localhost:8080/device_id/sendCommand
Body:
    command = The command data
Returns: The result of the command, or TIMEOUT if no response was received after 30 seconds
```

Run a macro:
```
POST: http://localhost:8080/sendMacro
Body:
    macroName: The name of the macro as specified in the macro file
Returns: SUCCESS if the macro succeeded, NO_DEVICE_FOUND/TIMEOUT/ERROR otherwise
```

Watch for events (aka unsolicited data from devices):
```
GET: http://localhost:8080/device_id/getUnsolicited
Returns: Blocks waiting for unsolicited data. If none is received in 30 seconds TIMEOUT is returned.
```
Meant for long polling.

### Control Logic

An empty sample file is provided as ```control_logic.py```. The functions there will be called any time the related events occur and will have the relevant data passed in. See the source code for more documentation.

### Macros

Macros are groups of commands which can span multiple devices and can be invoked by a single click/command. Macros should be saved in a text file and the name/location of that file should be passed in to ```server.py``` as an argument. An example follows:

```JSON
{
    "turnOnTheatre": {
        "name": "Turn on theatre",
        "commands": [
            {"device": "epson_5030ub", "command": "PWR ON"},
            {"device": "lutron_grx_3000", "command": ":A11"}
        ]
    },
    "turnOffTheatre": {
        "name": "Turn off theatre",
        "commands": [
            {"device": "epson_5030ub", "command": "PWR OFF"},
            {"device": "lutron_grx_3000", "command": ":A01"}
        ]
    }
}
```

### Kodi

In order to use Kodi as a supported device you must perform the following:

- clone https://github.com/midgetspy/script.module.twisted, zip it up, add it as an Add-on in Kodi
- run ```build.py kodi```, zip up the resulting folder and add it as an Add-on in Kodi

The kodi.resources.lib.common module has a number of helper functions for working with events generated from the Kodi HamJab client. Below is an example of a ```control_logic.py``` file which uses Kodi events:

```python
from kodi.resources.lib.common import EventName, MediaType, StereoscopicMode

def eventCallback(deviceServer, deviceId, event):
    if deviceId == 'kodi':
        if MediaType.isVideo(MediaType.get(event)):

            # toggle 3D mode on the projector when we watch a 3D movie
            if StereoscopicMode.get(event) == StereoscopicMode.HSBS:
                if EventName.get(event) == EventName.PLAYING:
                    deviceServer.runMacro('enable3D')
                elif EventName.get(event) == EventName.STOPPED:
                    deviceServer.runMacro('disable3D')
        
            # dim/raise the lights when we are watching a movie/TV
            if MediaType.get(event) != MediaType.TRAILER:
                if EventName.get(event) in (EventName.PLAYING, EventName.RESUMED):
                    # lower the lights
                    deviceServer.sendCommand('lutron_grx_3000', 'A01')
                elif EventName.get(event) in (EventName.PAUSED, EventName.STOPPED):
                    # raise the lights
                    deviceServer.sendCommand('lutron_grx_3000', 'A31')

def commandCallback(deviceServer, deviceId, command, response):
    pass
```

### EventGhost

In order to use the EventGhost plugin you must perform the following:

- ```build.py eg``` to generate the EventGhost plugin
- copy the contents of the out/eg folder to ```C:\Program Files (x86)\EventGhost\plugins\HamJab```

After restarting EventGhost you will be able to add the plugin and use it to send commands to any supported device.



