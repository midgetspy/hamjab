$(document).ready(function() {

    $.get('../frontEnd/device.json', function(data) {
        device = JSON.parse(data);
        
        var root = $('#help-container');
        
        root.append(create_command(device));
        $('.group-container > .command-container').hide();
    });

    $(document).on('click', '.group-container > h2', function() {
        $(this).siblings('.command-container').toggle();
        if ($(this).hasClass('group-contracted')) {
            $(this).removeClass('group-contracted');
            $(this).addClass('group-expanded');
        }
        else {
            $(this).removeClass('group-expanded');
            $(this).addClass('group-contracted');
        }
        return false;
    });
    
});

var create_command = function(command) {

    if (command.hasOwnProperty('commands')) {
        var element = $('<div class="group-container">').append('<h2 class="group-contracted">' + command['name'] + '</h2>');
        $.each(command['commands'], function(i,e) {
            element.append(create_command(e));
        })
        
        element.append('</div>');
        return element;
    }

    var args = $('<div class="command-args">');
    
    $.each(command['command']['args'], function(i,e){
        args.append($('<div class="command-arg">')
            .append('<span class="command-label">' + e['id'] + '</span>')
            .append('<span class="command-value">' + e['description'].replace(/\n/g,'<br />') + '</span>')
            .append('<input type="text" size="6" name="' + e['id'] + '" />'))
        .append('</div>');
    });
    
    args.append('</div>');

    var descriptionDiv = '';
    if (command['description']) {
        descriptionDiv = '<div class="command-description">' + command['description'] + '</div>';
    }

    var element = $('<div class="command-container">')
        .append($('<form action="../sendCommand" method="POST" target="_blank">')
            .append('<input type="hidden" name="fromClient" value="webForm" />')
            .append('<div class="command-name">' + command['name'] + '</div>')
            .append(descriptionDiv)
            .append($('<div class="command-format">')
                .append('<span class="command-label">Format</span>')
                .append('<span class="command-value">' + command['command']['format'] + '</span>')
                .append('<input type="hidden" name="command" value="' + command['command']['format'] + '" />')
                .append(args)
            .append('</div>')
            .append('<input type="submit" value="Send" />')))
        .append('</form>');
    
    if (command.hasOwnProperty('response')) {
        element.append($('<div class="command-response">')
            .append('<span class="command-label">Response</span>')
            .append('<span class="command-value">' + command['response']['description'].replace(/\n/g,'<br />') + '</span>'))
        .append('</div>');
    }
        
    if (command.hasOwnProperty('examples')) {
        var examples = $('<div class="command-example-list">');
    
        $.each(command['examples'], function(i,e) {
            examples.append($('<div class="command-example">')
                .append('<span class="command-label">' + e['command'] + '</span>')
                .append('<span class="command-value">' + e['description'].replace(/\n/g,'<br />') + '</span>'))
            .append('</div>');
        });
        
        examples.append('</div>');
        
        element.append($('<div class="command-examples">')
            .append('<span class="command-label">Examples</span>')
            .append(examples))
        .append('</div>');
    }
        
    element.append('</div>');
    
    return element;
}