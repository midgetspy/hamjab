var blinkInterval;
var pollTimeout;
var pollTimeoutSec = 10;
var powerStatus;
var wantedPowerStatus;

var POWER_OFF = "PWR=00";
var POWER_ON = "PWR=01";
var POWER_WARMING = "PWR=02";

$(document).ready(function() {
    $('.button').click(function() {
        var command = $(this).attr('data-command');
        
        if (this.id == 'power-button') {
            if (powerStatus == POWER_OFF) {
                command = 'PWR ON';
                wantedPowerStatus = POWER_ON;
            }
            else if (powerStatus == POWER_ON) {
                command = 'PWR OFF';
                wantedPowerStatus = POWER_OFF;
            }
            else {
                console.log('Unknown state, not sending any command.');
                return;
            }

            clearTimeout(pollTimeout);
            pollTimeoutSec = 1;
            pollForStatus();
        }
            
        sendCommand(command);
    });
    
    pollForStatus();
});

var setLightStatus = function(lightType, status) {
    var light = $('#' + lightType + '-light .light');
    
    if (status == 'on')
        light.addClass('light-on');
    else if (status == 'off')
        light.removeClass('light-on');
    else if (status == 'toggle')
        light.toggleClass('light-on');
};

var pollForStatus = function() {
    var callback = function(result) {
        setLights(result);
        pollTimeout = setTimeout(pollForStatus, pollTimeoutSec*1000);
    };
    
    sendCommand("PWR?", callback);
};

var setLights = function(curPowerStatus) {
    if (curPowerStatus == POWER_OFF) {
        clearInterval(blinkInterval);
        setLightStatus('power', 'off');
        setLightStatus('status', 'off');
    }
    else if (curPowerStatus == POWER_ON) {
        clearInterval(blinkInterval);
        setLightStatus('power', 'on');
        setLightStatus('status', 'on');
    }
    else if (curPowerStatus == POWER_WARMING) {
        setLightStatus('power', 'on');
        if (powerStatus !== POWER_WARMING) {
            clearInterval(blinkInterval);
            blinkInterval = setInterval(function(){
                setLightStatus('status', 'toggle');
            },1000);
        }
    }
    
    if (curPowerStatus && curPowerStatus === wantedPowerStatus) {
        wantedPowerStatus = null;
        pollTimeoutSec = 60;
    }
    
    powerStatus = curPowerStatus;
};

var sendCommand = function(command, success) {
    var url = '/sendCommand?fromClient=webFrontEnd&toDevice=epson5030ub&command=' + command;
    $.get(url, function(data) {
        if (success !== undefined)
            success(data);
    })
    .fail(function() {
        console.log('send failed');
    });
};