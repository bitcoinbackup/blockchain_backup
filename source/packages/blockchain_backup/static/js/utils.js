/**
 * Utilities.
 *
 * If you are viewing this in a browser, this code is automatically generated.
 * Use the source.
 *
 * Copyright 2020 DeNova
 * Last modified: 2020-09-18
**/

'use strict';

let _old_console_log = undefined;
{# Console log text is wiped out on every page load. #}
let console_log_history = [];

function local_storage_available() {
    return window.localStorage;
}

function click_by_id(id) {
    {% comment %}
        Click the element.

        This is to clearly differentiate from jquery's
            $('#id').click(...)
        which registers a click event handler.

        id:         element id
    {% endcomment %}

    let element = document.getElementById(id);
    element.click();
}

function on_enter_click_by_id(id) {
    {% comment %}
        On Enter, click the element.

        id:         element id
    {% endcomment %}

    function got_keypress(e) {
        if (e.which == 13) {
            console.log('enter key is pressed');
            click_by_id(id);
        }
    }

    $(document).keypress(got_keypress);
}

function show_dialog(id, onsubmit) {
    {% comment %}
        id:         dialog id
        onsubmit:   submit action function
    {% endcomment %}

    function submit_event_listener(e) {
        e.preventDefault();
        // debugger; // DEBUG
        onsubmit();
    }

    console.log('show dialog for #' + id);

    // debugger; // DEBUG
    if (onsubmit) {
        {# don't try to submit the form to a server #}
        console.log('add submit event listener for #' + id);
        let form = document.getElementById(id);
        form.addEventListener('submit', submit_event_listener);
    }

    {% comment %}
        avoid initial flash of dialog
        form starts hidden via class 'hidden'
        fadeIn() starts an async process, which gives us time to remove the 'hidden' class
    {% endcomment %}
    $('#' + id).fadeIn('fast');
    $('#' + id).removeClass('hidden');
}

function hide_dialog(id) {
    {% comment %}
        avoid flash of dialog
        form is hidden via class 'hidden'
        fadeOut() starts an async process, which gives us time to add the 'hidden' class
    {% endcomment %}

    // do we need the next line? why?
    // $('#' + id).fadeOut('fast');
    hide_by_id(id);
}

function hide_by_id(id) {
    $('#' + id).addClass('hidden');
}

function show_by_id(id) {
    $('#' + id).removeClass('hidden');
}

function disable_enter(id) {
    {% comment %}
        Disable submit on Enter key.
        Require that user make an explicit selection.

        id:         form id
    {% endcomment %}

    function no_enter(e) {
        e.preventDefault();
    }

    console.log('disable enter for #' + id);

    let form = document.getElementById(id);
    form.addEventListener('submit', no_enter);
}

function report_error(error, title) {
    {# Report error. #}

    debugger; // DEBUG

    console.log('error: ' + error);
    if (! title) {
        title = error.name;
    }

    console.log('title: ' + title);

    {# use the error form if we have it #}
    let title_out = document.getElementById('errorstitle');
    if (title_out) {
        title_out.innerHTML = title;
    }
    else {
        console.log('no errors form, so not updating it');
    }
    let errortext_element = document.getElementById('errorstext');
    let error_text = undefined;
    if (errortext_element) {
        errortext_element.innerHTML = error;
        let error_text = errortext_element.innerHTML;
    }
    else {
        error_text = error.message;
    }

    if (! (error instanceof Error)) {
        error = new Error(title);
    }

    let new_stack_lines = format_stack(error);

    {# save error details so user can send them to us #}
    // debugger; // DEBUG
    let details = {};
    details.title = title;
    details.error = error_text;
    details.console = console_log_history;
    details.stack = new_stack_lines;

    let details_element = document.getElementById('errordetails');
    if (details_element) {
        let details_json = JSON.stringify(details);
        details_element.innerHTML = details_json;

        show_dialog('errorsdialog');
    }

    {% if autoreport_javascript_errors %}
        try {
            {# alert('about to send error report'); // DEBUG #}
            console.log('send error report');
            let submit_id = 'send-report-id';
            // let submit_id = $('#errorsdialog submit').attr('id');
            // console.log('got submit id #' + submit_id); {# DEBUG #}
            click_by_id(submit_id);

            {# $.post seems less reliable than clicking submit in the form #}
            {# in fact apparently jquery implements $.post with a dynamically created form #}
            {% comment %}
            $.post('/error_report/',
                   {errordetails: details_json,
                    csrfmiddlewaretoken: django_csrf_token() });
            {% endcomment %}

            console.log('posted error report');

            {% comment %}
                # see http://hayageek.com/jquery-ajax-post/
                    ,
                    function(data, textStatus, jqXHR)
                    {
                          //data: Received from server
                    });
            {% endcomment %}

        }
        catch (e) {
            alert(e);
        }
    {% endif %}
}

function warn_exception(e, msg) {
    {# Log exception and warn user. #}

    if (msg) {
        console.log(msg);
    }
    console.log(e);

    report_error(e, msg);
}

function hide_error() {
    {# Hide error dialog. #}

    hide_dialog('errorsdialog');
}

function proxy_console_log() {
    {# Proxy console log to add timestamps, save log text. #}

    if (_old_console_log == undefined) {
        _old_console_log = console.log;

        console.log = replacement_console_log;
    }
}

function replacement_console_log(message) {

    {# add timestamp #}
    let timestamp = (new Date()).toISOString();
    message = timestamp + ' ' + message;
    console_log_history.push(message);

    {# log to browser console log as usual #}
    _old_console_log.apply(console, [message]);

    {% comment %} try to handle multiple args. processing 'arguments' is very unreliable
    {# add timestamp #}
    if (arguments.length) {

        {# add timestamp -- this apparently works with all browsers #}

        arguments['0'] = timestamp + ' ' + arguments['0'];

        {# save log text #}
        {# very simplified version of console formatting #}
        let line = '';
        for (let i=0; i < arguments.length; ++i) {
            if (line.length) {
                line = line + ' ';
            }
            line = line + arguments[i];
        }
        console_log_history.push(line);
    }

    {# log to browser console log as usual #}
    _old_console_log.apply(console, arguments);
    {% endcomment %}
}

function format_stack(error) {
    {# format stack trace with code lines in context #}

    {% comment %}
        The html returned by html.outerHTML is very different from the
        html the browser uses to calculate stack line numbers.
        So this doesn't work.
    {% endcomment %}

    return [];
}


function NOT_WORKING_format_stack(error) {
    {# format stack trace with code lines in context #}

    function show_context(html_lines, line_num, new_stack_lines) {
        console.log('before setting start_line: line_num ' + line_num + ', CONTEXT_LINES ' + CONTEXT_LINES); // DEBUG #}
        let start_line = line_num - CONTEXT_LINES;
        if (start_line < 1) {
            start_line = 1;
        }
        console.log('start_line: ' + start_line); // DEBUG #}
        let end_line = line_num + CONTEXT_LINES;
        console.log('end_line: ' + end_line); // DEBUG #}
        if (end_line >= html_lines.length) {
            {# console.log('end_line >= html_lines.length'); // DEBUG #}
            end_line = html_lines.length - 1;
        }
        console.log('line_num ' + line_num + ', start_line ' + start_line + ', end_line ' + end_line); // DEBUG #}

        for (let j = start_line;
             j <= end_line;
             j++) {

            let indent = undefined;
            if (j == line_num) {
                indent = '  * ';
            }
            else {
                indent = '    ';
            }
            {# html_lines is an array, and zero-based, so we use "-1" #}
            let context_line = indent + html_lines[j - 1];
            console.log('context_line: ' + context_line); // DEBUG #}
            new_stack_lines.push(context_line);
            console.log('new_stack_lines: ' + new_stack_lines); // DEBUG #}
        }
    }

    {% comment %}
        The html returned by html.outerHTML is very different from the
        html the browser uses to calculate stack line numbers.
        So this doesn't work.
    {% endcomment %}

    const CONTEXT_LINES = 5; {# lines shown before and after stacktrace lines #}

    let new_stack_lines = [];
    let body = document.getElementsByTagName('body')[0];
    let html = body.parentNode;
    {# Warning: assumes no white space before <html> #}
    let html_lines = html.outerHTML.split('\n');
    console.log(html_lines.length + ' html_lines');                     // DEBUG
    {% comment %}
    let html_line_num = 0;                                              // DEBUG #}
    for (line in html_lines) {                                          // DEBUG #}
        {# console.log(html_line_num + ' ' + html_lines[html_line_num]);   // DEBUG #}
        html_line_num = html_line_num + 1;                              // DEBUG #}
    }                                                                   // DEBUG #}
    {% endcomment %}

    let old_stack_lines = error.stack.split('\n');
    console.log('old_stack_lines.length: ' + old_stack_lines.length); // DEBUG
    for (let i = 0; i < old_stack_lines.length; i++) {
        let old_line = old_stack_lines[i];
        if (old_line.length > 0) {
            console.log('old_stack_lines[' + i + ']: ' + old_line); // DEBUG
            new_stack_lines.push(old_line);
            console.log('new_stack_lines: ' + new_stack_lines); // DEBUG

            let line_parts = old_line.split(':');
            {# console.log('line_parts:' + line_parts); // DEBUG #}
            {% comment %}
            The last 2 parts are line number and column number.
            Other parts are variable.
            Parse out line number of error.
            Line part numers are one-based and the html array is zero-based.
            So "- 1".
            {% endcomment %}
            let line_num = Number(line_parts[line_parts.length - 2] - 1);
            {# console.log('line_num: ' + line_num); // DEBUG #}
            if (line_num >= 1) {
                show_context(html_lines, line_num, new_stack_lines);
            }
        }
    }

    return new_stack_lines;
}

function django_csrf_token() {
    let csrf_token = document.getElementsByName('csrfmiddlewaretoken')[0].value;
    if (! csrf_token) {
        throw Error('no django csrfmiddlewaretoken');
    }
    return csrf_token;
}

function create_temp_form(url) {
    {# dynamically create temporary form #}

    let form = document.createElement('form');
    form.action = url;

    {# django csrf middleware #}
    form.innerHTML = '{% csrf_token %}' + '\n' + form.innerHTML;

    {% comment %} delete if unused 2020-03-01
    {# <input type="hidden" name="csrfmiddlewaretoken" value="..."> #}
    let csrf_token = document.createElement('input');
    csrf_token.type = 'hidden';
    csrf_token.name = 'csrfmiddlewaretoken';
    let token_value = django_csrf_token();
    csrf_token.value = token_value;
    form.appendChild(csrf_token);
    {% endcomment %}

    {# include submit button for us to click #}
    let submit = document.createElement('input');
    {# must match button name converntion from denova.django_addons.templatetags.custom #}
    submit.name = 'ok-button';
    submit.id = 'temp-ok-id';
    submit.value = 'Ok';
    submit.type = 'submit';
    form.appendChild(submit);

    document.body.appendChild(form);

    return form;
}

function post_temp_form(form) {
    form.method = 'post';
    send_temp_form(form);
}

function send_temp_form(form) {
    {# defaults to GET. use post_temp_form() to POST. #}
    click_by_id('temp-ok-id');
}

function onerror_event_handler(msg, url, line) {
    {# handle otherwise unhandled errors #}

    // debugger; // DEBUG

    description = msg + ': ' + url + ' ' + line;
    console.log('UNCAUGHT ERROR: ' + description);
    console.log('Caused by a missing try/catch');
    report_error(Error(description), msg);

    {# don't propagate the error up the stack #}
    {# except for firefox, which needs to return true; we just let firefox write to the console log #}
    return false;
}

// {# window.onerror = onerror_event_handler; #}
