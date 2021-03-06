$(document).ready(function() {

    $('#macro-container .list-element').click(function() {
        var macro = $(this).attr('data-macro');
        
        sendCommand(macro);
    });

    $('#status-container .list-element').click(function() {
        $.get('../toggleStatus')
        .always(function() {
            location.reload();
        });
    });

    $('.macro-status').hide();
});

var hideMacroResultTimeoutInSec = 30;
var hideMacroResultTimer;

var sendCommand = function(macroName) {

    clearTimeout(hideMacroResultTimer);

    var url = '../macro';
    var data = { macroName: macroName}
    handleMacroResult(macroName, 'LOADING');
    
    $.post(url, data, function(data) {
        handleMacroResult(macroName, data);
    })
    .fail(function(data) {
        handleMacroResult(macroName, data);
    });
};    

var handleMacroResult = function(macro, result) {
    var macroStatuses = $(".list-element[data-macro='" + macro + "'] .macro-status");
    
    var hideStatuses = function() {
        macroStatuses.hide();
    };

    hideStatuses();
    
    if (result === 'SUCCESS') {
        macroStatuses.filter('.checkmark').show();
        hideMacroResultTimer = setTimeout(hideStatuses, hideMacroResultTimeoutInSec * 1000);
    }
    else if (result === 'LOADING') {
        macroStatuses.filter('.loading').show();
    }
    else {
        macroStatuses.filter('.fail').show();
        hideMacroResultTimer = setTimeout(hideStatuses, hideMacroResultTimeoutInSec * 1000);
    }
};