from controlClient import ControlClient

import urllib2, json
import os

import wx
import eg

eg.RegisterPlugin(
    name = "Control Client",
    author = "Nic Wolfe",
    version = "0.0.1",
    kind = "external",
    description = "This plugin allows you to send control commands to a Control Server.",
)

class Text:
    host = "Host:"
    port = "Port:"
    device = "Device:"
    command = "Command:"
    macroName = "Macro Name:"
    tcpBox = "Server Settings"
    commandBox = "Command"
    examples = "Examples"

class ControlClientPlugin(eg.PluginBase):
    def __init__(self):
        self.AddAction(SendGenericCommand)
        self.AddAction(SendMacroCommand)
        
        command_file_paths = []
        
        # look for device descriptions
        devices_dir = os.path.join(os.path.dirname(__file__), "devices")
        if os.path.exists(devices_dir):
            for device_dir in os.listdir(devices_dir):
                command_file_path = os.path.join(devices_dir, device_dir, 'device.json')
                if os.path.exists(command_file_path):
                    command_file_paths.append(command_file_path)
        
        # make an action for each command
        for command_file_path in command_file_paths:
            with open(command_file_path) as command_file:
                deviceInfo = json.load(command_file)
                
                self._add_group(self, deviceInfo['id'], deviceInfo)
    
    def _add_group(self, parent, device_id, group):
        new_group = parent.AddGroup(group['name'], "Description")
        
        for cur_item in group['commands']:
            if 'commands' in cur_item:
                self._add_group(new_group, device_id, cur_item)
            else:
                command_id = device_id + cur_item['name']
                
                class Action(DataDrivenAction):
                    command = cur_item
                    deviceId = device_id

                    name = cur_item['name']
                    description = cur_item['description'] if 'description' in cur_item else ''
                Action.__name__ = str(command_id)
                new_group.AddAction(Action)
    
    def __start__(self, host, port):
        self.host = host
        self.port = port
        
        self.controlClient = ControlClient(host, port)
    
    def Configure(self, host="127.0.0.1", port=8080):
        panel = eg.ConfigPanel()
        hostCtrl = panel.TextCtrl(host)
        portCtrl = panel.SpinIntCtrl(port, max=65535)

        st1 = panel.StaticText(Text.host)
        st2 = panel.StaticText(Text.port)
        eg.EqualizeWidths((st1, st2))
        tcpBox = panel.BoxedGroup(
            Text.tcpBox,
            (st1, hostCtrl),
            (st2, portCtrl),
        )

        panel.sizer.Add(tcpBox, 0, wx.EXPAND)

        while panel.Affirmed():
            panel.SetResult(
                hostCtrl.GetValue(),
                portCtrl.GetValue(),
            )


class DataDrivenAction(eg.ActionBase):

    def __call__(self, *args):

        command_args = self.command['command']['args']       
        command_format = self.command['command']['format']
        
        assert len(args) == len(command_args)

        format_args = {}
        for i in range(len(command_args)):
            format_args[command_args[i]['id']] = args[i]
        
        command_text = command_format.format(**format_args)
        
        result = self.plugin.controlClient.sendCommand(self.deviceId, command_text)
        print "Result of command {command} to device {device} was {result}".format(device=self.deviceId, command=command_text, result=result)
        return result
    
    def Configure(self, *args):
        command_args = self.command['command']['args']
        
        if not command_args:
            return eg.ActionBase.Configure(self, *args)
        
        panel = eg.ConfigPanel()

        controls = []
        
        assert len(args) == 0 or len(args) == len(command_args)

        for i in range(len(command_args)):
            arg = command_args[i]
            
            if len(args) == 0:
                defaultValue = ''
            else:
                defaultValue = args[i]
            
            ctrl = panel.TextCtrl(defaultValue)
            labelText = panel.StaticText(arg['name'])
            descriptionText = panel.StaticText(arg['description'])
            controls.append((labelText, ctrl, descriptionText))
        
        eg.EqualizeWidths([x[0] for x in controls])
        
        commandBox = panel.BoxedGroup(
            Text.commandBox,
            *[(x[0], x[1], x[2]) for x in controls]
        )

        panel.sizer.Add(commandBox, 0, wx.EXPAND)

        if 'examples' in self.command and self.command['examples']:
            examples = []
            for example in self.command['examples']:
                commandText = panel.StaticText(example['command'])
                descriptionText = panel.StaticText(example['description'])
                
                examples.append((commandText, descriptionText))
                
            eg.EqualizeWidths([x[0] for x in examples])
                
            exampleBox = panel.BoxedGroup(Text.examples, *examples)
            panel.sizer.Add(exampleBox, 0, wx.EXPAND)

        while panel.Affirmed():
            panel.SetResult(
                *[x[1].GetValue() for x in controls]
            )

class SendGenericCommand(eg.ActionBase):
    name = "Send Generic Command"
    description = "Sends a generic command to the Control Server"
    
    def __call__(self, device, command):
        result = self.plugin.controlClient.sendCommand(device, command)
        print "Result of command {command} to device {device} was {result}".format(device=device, command=command, result=result)
        return result
        
    def Configure(self, device="", command=""):
        panel = eg.ConfigPanel()
        deviceCtrl = panel.TextCtrl(device)
        commandCtrl = panel.TextCtrl(command)

        st1 = panel.StaticText(Text.device)
        st2 = panel.StaticText(Text.command)
        eg.EqualizeWidths((st1, st2))
        commandBox = panel.BoxedGroup(
            Text.commandBox,
            (st1, deviceCtrl),
            (st2, commandCtrl),
        )

        panel.sizer.Add(commandBox, 0, wx.EXPAND)

        while panel.Affirmed():
            panel.SetResult(
                deviceCtrl.GetValue(),
                commandCtrl.GetValue(),
            )
        
class SendMacroCommand(eg.ActionBase):
    name = "Send Macro Command"
    description = "Sends a macro command Control Server"
    
    def __call__(self, macroName):
        result = self.plugin.controlClient.sendMacro(macroName)
        print "Result of macro {macroName} was {result}".format(macroName=macroName, result=result)
        return result
        
    def Configure(self, macroName=""):
        panel = eg.ConfigPanel()
        macroCtrl = panel.TextCtrl(macroName)

        st1 = panel.StaticText(Text.macroName)
        commandBox = panel.BoxedGroup(
            Text.commandBox,
            (st1, macroCtrl),
        )

        panel.sizer.Add(commandBox, 0, wx.EXPAND)

        while panel.Affirmed():
            panel.SetResult(
                macroCtrl.GetValue(),
            )
        
        