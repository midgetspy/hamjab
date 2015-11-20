$(document).ready(function() {

    $('#macro-container .list-element').click(function() {
        var macro = $(this).attr('data-macro');
        
        sendCommand(macro);
    });

    $('.macro-status').hide();

});

var sendCommand = function(macroName) {
    var url = '../macro?macroName=' + macroName
    handleMacroResult(macroName, 'LOADING')
    $.get(url, function(data) {
        handleMacroResult(macroName, data);
    })
    .fail(function(data) {
        handleMacroResult(macroName, data);
    });
};    

var handleMacroResult = function(macro, result) {
    var macroStatuses = $(".list-element[data-macro='" + macro + "'] .macro-status")
    
    macroStatuses.hide();
    
    if (result === 'SUCCESS') {
        macroStatuses.filter('.checkmark').show();
    }
    else if (result === 'LOADING') {
        macroStatuses.filter('.loading').show();
    }
    else {
        macroStatuses.filter('.fail').show();
    }
}