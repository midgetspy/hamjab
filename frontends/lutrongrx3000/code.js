$(document).ready(function() {
    $('#more-scenes').click(function() {
        $('#extra-scenes').toggle();
    })

    $('.button').click(function() {
        var command = $(this).attr('data-command');
        
        sendCommand(command);
    });
    
    $('.zone-button').on('mousedown touchstart', function() {
        var zone = $(this).attr('data-zone');
        var command = $(this).attr('data-command');
        
        var toSend = ":";
        
        if (command == "up") {
            toSend += "B";
        }
        else if (command == "down") {
            toSend += "D";
        }
        
        toSend += "1";
        
        if (zone !== "0") {
            toSend += zone;
        }
        
        sendCommand(toSend);
    });
    
    $('.zone-button').on('mouseup touchend', function() {
        var zone = $(this).attr('data-zone');
        var command = $(this).attr('data-command');
        
        var toSend = ":";
        
        if (command == "up") {
            toSend += "C";
        }
        else if (command == "down") {
            toSend += "E";
        }

        sendCommand(toSend);
    });
    
    sendCommand(':G', handleSceneSelect);
    
    requestUnsolicited();
});

var requestUnsolicited = function() {
    var url = '../getUnsolicited';
    $.get(url, function(data) {
        handleSceneSelect(data);
        requestUnsolicited();
    })
    .fail(function() {
        console.log('send failed');
    });
};

var sceneRegex = /:ss (\d)M+/;
var handleSceneSelect = function(data) {
    var match = sceneRegex.exec(data);
    
    if (match === null) {
        return;
    } 
    else {
        var sceneNumber = match[1];
        
        var sceneLights = $('.scene-light');
        var sceneLight = $('#scene-' + sceneNumber + ' .scene-light');
        
        sceneLights.removeClass('light-on');
        sceneLight.addClass('light-on');
    }
};

var sendCommand = function(command, success) {
    var url = '../sendCommand?fromClient=webFrontEnd&toDevice=lutrongrx3000&command=' + command;
    $.get(url, function(data) {
        if (success !== undefined)
            success(data);
    })
    .fail(function() {
        console.log('send failed');
    });
};