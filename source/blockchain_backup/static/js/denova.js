/**
 * DeNova's utilities for javascript.
 *
 * If you are viewing this in a browser, this code is automatically generated.
 * Use the source.
 *
 * Copyright 2019-2021 DeNova
 * Last modified: 2021-06-13
**/

'use strict';

{# some of this is not working, and may be unused #}

var ELEMENT_NODE = 1;
var TEXT_NODE = 3;
var PROCESSING_INSTRUCTION_NODE = 7;
var COMMENT_NODE = 8;
var DOCUMENT_NODE = 9;
var DOCUMENT_TYPE_NODE = 10;
var DOCUMENT_FRAGMENT_NODE = 11;

function format_stack(error) {
    {# format stack trace with code lines in context #}

    // DEPRECATED. Use console.trace() if it's available.
    return [];
}

function dom(obj) {
    {# return first HTML DOM object from jQuery object #}

    var result;

    if (is_jquery_obj(obj)) {
        result = obj[0];
    }
    else if (is_dom_element(obj)) {
        result = obj;
    }
    else {
        throw new Error('not jQuery or dom: ' + classof(obj));
    }

    return result;
}

function is_jquery_obj(elem) {
    {# return true if elem is a jquery element. Else return false. #}

    var is_jquery;

    try {
        elem;
        elem[0];

        is_jquery = true;
    }
    catch (e) {
        is_jquery = false;
    }

    return is_jquery;
}

function is_dom_element(el) {
    {# return true if el is a dom element. Else return false. #}

    return ! is_undefined(el.innerHTML);
}

function jq_obj_name(jq_obj) {
    {# return a short description of a jQuery object. #}

    var name;
    if (is_jquery_obj(jq_obj)) {
        name = jq_obj.selector || ('jQuery ' + typeof jq_obj);
    }
    else {
        name = 'not a jQuery object';
    }
    return name;
}

function log_jq_obj(jq_obj) {
    {# log the result of a jQuery selector. #}

    // log_if_undefined(jq_obj.selector, 'jQuery selector');

    log(jq_obj_name(jq_obj));
    if (jq_obj.context) {
        log('    context: ' + jq_obj.context);
    }
    if (jq_obj.length) {
        {# don't clutter the display of a unique DOM object #}
        if (jq_obj.length > 1) {
            log('    length: ' + jq_obj.length);
        }
        for (var i = 0; i < jq_obj.length; i++) {
            var el = jq_obj[i];
            if (jq_obj.length > 1) {
                log(i + ':');
            }
            log_dom_obj(el);
        }
    }
    else {
        log(jq_obj_name(jq_obj) + ' selector did not match');
    }
}

function log_dom_obj(el) {
    {# log a javascript DOM object, also called a Node. Indented. #}

    if (is_dom_element(el)) {
        log('    is jquery: ' + is_jquery_obj(el));
        log('    class: ' + classof(el));
        log('    tag name: ' + el.nodeName);
        var attributes_str = attr_str(el);
        if (attributes_str) {
            log('    attributes: ' + attr_str(el));
        }
        log('    type: ' + classof(el));
        log('    node type: ' + node_type(el));
        log('    node value: ' + el.nodeValue);
        log('    text: ' + shorten(strip(el.textContent || el.innerText)));
        log('    inner html: ' + shorten(strip(el.innerHtml)));
    }
    else {
        log('    not a dom object');
    }
}

function log_obj(obj) {
    {# log members of obj, indented #}

    var object_class = classof(obj);
    log('    object class: ' + object_class);
    if (object_class === 'Array' || object_class === 'Object') {
        for (var field in obj) {
            log('    field class: ' + classof(field));

            var value = field.value;
            if (jQuery.isFunction(value)) {
                value = 'function';
            }
            log('    ' + field.name + ': ' + shorten(value));
        }
    }
}

function dom_text(el) {
    return el.textContent || el.innerText;
}

function node_type(el) {
    {# Return readable nodeType of DOM object. #}

    var node_names = [
        undefined,
        'element',
        undefined,
        'text',
        undefined,
        undefined,
        undefined,
        'processing instruction',
        'comment',
        'document',
        'document type',
        'document fragment'
    ];

    var result;

    if (is_undefined(el.nodeType) ||
         el.nodeType < ELEMENT_NODE ||
         el.nodeType > DOCUMENT_FRAGMENT_NODE) {
        result = 'undefined';
    }
    else {
        result = node_names[el.nodeType];
    }

    return result;
}

function attr_str(el) {
    {# return attributes as a comma separated string. #}

    var attr_string = '';

    log('enter attr_str()');

    for (var attr in el.attributes) {
        log('attr');
        if (classof(attr) === 'String') {
            log('    attr is String: "' + attr + '"');
        }
        if (el.attributes.propertyIsEnumerable(attr)) {
            log_obj(el.attributes[attr]);
        }
        else {
            log(attr + ' is not enumerable');
        }

        log('    attr class: ' + classof(attr));
        if (attr_string) {
            attr_string = attr_string + ', ';
        }
        log('    attr name: ' + attr.name);
        log('    attr value: ' + attr.value);
        attr_string = attr_string + attr.name + ': ' + attr.value;
    }

    log('exit attr_str()');
    return attr_string;
}

function log_if_undefined(x, msg) {
    {#  If x is undefined, log it. #}

    if (is_undefined(x)) {
        log('undefined: ' + msg);
    }
}

function alert_exception(e, message) {
    {# Alert user to exception. #}

    log_exception(e, message);
    if (message) {
        alert(message + '\n' + e);
    }
    else {
        log('Unable to report error alert exception')
        // alert(e);
    }
}

function log_exception(e, message) {
    {# Log exception. #}

    if (message) {
        log(message);
    }
    log(e);
}

function classof(obj) {
    {# Return class of obj as a string. If no class returns 'null' or'undefined'. #}

    var result;

    if (obj === null) {
        result = 'null';
    }
    else if (obj === undefined) {
        result = 'undefined';
    }
    else {
        result = Object.prototype.toString.call(obj).slice(8, -1);
    }

    return result;
}

function field_value(id) {
    {# get form field value #}

    function select_value(select_obj) {

        /**
        {% comment %}
        Return <select> field value.

        from JavaScript and jQuery The Missing Manual 3rd Edition[A4].pdf

            :selected selects all selected option elements within a list or menu, which lets
            you find which selection a visitor makes from a menu or list (<select> tag). For
            example, say you have a <select> tag with an ID of state, listing all 50 U.S.
            states. To find which state the visitor has selected, you can write this:

                var selectedState=$('#state :selected').val();

        {% endcomment %}
        **/

        var selected_option = select_obj.options[select_obj.selectedIndex];

        return selected_option.text;
    }

    var value;

    try {
        var el = $('#' + id);
        var dom_el = dom(el);
        if (dom_el.nodeName.toLowerCase() === 'select') {
            value = select_value(dom_el);
        }
        else {
            value = dom_el.value;
        }
    }
    catch (e) {
        value = null;
        log(e);
    }

    return value;
}

function shorten(s) {
    {# If a string is long, return a short version. Else return the string. #}

    var MAXLENGTH = 30;
    var result;

    s = String(s);

    if (s.length > MAXLENGTH) {
        result = s.substring(0, MAXLENGTH) + '...';
    }
    else {
        result = s;
    }

    return result;
}

function strip(text) {
    {# Return text with spaces stripped. #}

    var result;

    if (is_undefined(text)) {
        result = undefined;
    }
    else {
        result = text.replace(/^\s+|\s+$/g, '');
    }
}

function is_undefined(x) {
    {#  Return true if x is undefined. Else return false. #}

    return (typeof x) === 'undefined';
}

function onerror_event_handler(msg, url, line) {
    {# handle otherwise unhandled errors #}

    // debugger; // DEBUG

    log('onerror_event_handler: '+  msg); // DEBUG
    log('    '+  url); // DEBUG
    log('    '+  line); // DEBUG
    var description = msg + ': ' + url + ' ' + line;
    log('UNCAUGHT ERROR: ' + description);
    log('Caused by a missing try/catch');
    try {
        report_error(Error(description), msg);
    }
    catch (e) {
        log('Unable to report onerror event')
        // alert(e);
    }

    {# don't propagate the error up the stack except for firefox #}
    {# we just let firefox write to the console log #}

    return false;
}

function log_object(object, label) {

    function log_nested(key) {
        console.log('log_nested('+ key + ')'); // DEBUG
        log('    ' + key + ':');
        for (key in object[key]) {
            log('        ' + key + ': ' + object[key]);
        }
    }

    if (! label) {
        label = typeof object;
    }

    console.log('log_object() ' + label + ':'); // DEBUG
    log(label + ':');
    for (var key in object) {
        let value = object[key];
        if (typeof value === 'object') {
            log_object(value, key);
            // log(key);
            // log_nested(value);
        }
        else {
            console.log(key + ': ' + value); // DEBUG
            log('    ' + key + ': ' + value);
        }
    }
}

{# django csrf token, assuming django default name #}
var csrftoken = getCookie('csrftoken');

{# Log history is wiped out on every page load. #}
var log_history = [];

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
            log('enter key is pressed');
            click_by_id(id);
        }
    }

    $('#' + id).keypress(got_keypress);
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

    log('show dialog for #' + id);

    // debugger; // DEBUG
    if (onsubmit) {
        {# don't try to submit the form to a server #}
        log('add submit event listener for #' + id);
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

    log('disable enter for #' + id);

    let form = document.getElementById(id);
    form.addEventListener('submit', no_enter);
}

async function poll(poll_url,               // server
                    csrftoken,              // CSRF token from server
                    poll_handler,           // client data handler
                    prev_timestamp) {    // last timestamp

    // alert("poll: prev_timestamp=" + prev_timestamp); // DEBUG

    async function reconnect(poll_url, csrftoken, poll_handler, prev_timestamp) {
        let RECONNECT_DELAY = 100; // ms

        try {
            await poll(poll_url, csrftoken, poll_handler, prev_timestamp);
        }

        catch (e) {
            log(e + '. Retrying...');
            // delay reconnect
            setTimeout(reconnect, RECONNECT_DELAY,
                       poll_url, csrftoken, poll_handler, prev_timestamp);
        }
    }

    let timestamp = {};
    if ( prev_timestamp ) {
        log('prev_timestamp: ' + prev_timestamp);
        timestamp.timestamp = prev_timestamp;
    }
    else {
        log('no prev_timestamp')
        timestamp.timestamp = '';
    };

    let options = {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json;charset=utf-8',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify( timestamp )
    }

    log('poll url: ' + poll_url);
    // log_object(options, 'request options');
    let response = await fetch(poll_url, options);

    if (response.ok) {
        log("poll response ok")
        let json_data = await response.json();
        if (json_data && json_data.length > 0) {
            // log(json_data);
            var timestamped_data = JSON.parse(json_data);
            /**
            log("poll: got data: " + json_data.slice(0, 80) + '...');
            log("poll: new timestamp: " + timestamped_data.timestamp);
            log("poll: new html: " + timestamped_data.data.slice(0, 80) + '...');
            // alert('poll: got data'); // DEBUG
            */

            poll_handler(timestamped_data.data);
        }
        else {
            log('empty response: '+ poll_url);
        }

        // reconnect
        await poll(poll_url, csrftoken, poll_handler, timestamped_data.timestamp);
    }

    else {
        if (response.status == 502) {
            log("poll connection timeout");
        }
        else {
            let msg = "poll: unexpected error from server: " + response.status + " " + response.statusText;
            log(msg);
        }

        await reconnect(poll_url, csrftoken, poll_handler, prev_timestamp);
    }
}

function log() {
    // log replacement with timestamps and log history

    {# 'arguments' is not an array, so make one #}
    let args;
    for (var i = 0; i < arguments.length; i++) {
        let arg = arguments[i];
        // console.log('DEBUG log() typeof arg: ' + typeof arg); //DEBUG
        if (typeof arg === 'object') {
            console.log('DEBUG call log_object()'); //DEBUG
            log_object(arg);
        }
        else {
            {# add timestamp #}
            var timestamp = (new Date()).toISOString();
            var line = timestamp + ' ' + arg;
            {# save log text #}
            log_history.push(line);

            {# log to browser console log as usual #}
            console.log(line);
        }
    }
    // let args = Array.prototype.slice.call(arguments);
    // console.log('log(' + JSON.parse(JSON.stringify(args)) + ')'); // DEBUG
}

function django_csrf_token() {
    // for use with html forms
    let middleware_token = document.getElementsByName('csrfmiddlewaretoken');
    let csrf_token;
    if (middleware_token && middleware_token.length) {
        log('middleware_token: ' + middleware_token); //DEBUG
        csrf_token = middleware_token[0].value;
        if (! csrf_token) {
            throw Error('no django csrfmiddlewaretoken');
        }
        log('csrf_token: ' + csrf_token); //DEBUG
    }
    else {
        log('no csrf_token'); //DEBUG
    }
    return csrf_token;
}

function report_error(error, title) {
    {# Report error. #}

    // debugger; // DEBUG

    log('error: ' + error);
    if (! title) {
        title = error.name;
    }

    log('title: ' + title);

    {# use the error form if we have it #}
    let title_out = document.getElementById('errorstitle');
    if (title_out) {
        title_out.innerHTML = title;
    }
    else {
        log('no errors form, so not updating it');
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

    // debugger; // DEBUG

    {# save error details so user can send them to us #}
    let details = {};
    details.title = title;
    details.error = error_text;
    details.log = log_history;
    details.error_details = document.getElementById('errordetails');

    let details_element = document.getElementById('errordetails');
    if (details_element) {
        details.error_details = details_element;
    }

    let details_json = JSON.stringify(details);

    {% if autoreport_javascript_errors %}
        try {
            {# alert('about to send error report'); // DEBUG #}
            log('send error report');
            let submit_id = 'send-report-id';
            // let submit_id = $('#errorsdialog submit').attr('id');
            // log('got submit id #' + submit_id); {# DEBUG #}
            click_by_id(submit_id);

            send_client_report(details_json)
            log('posted error report');
        }
        catch (e) {
            log('Unable to report error')
            // alert(e);
        }
    {% else %}
        show_dialog('errorsdialog');
    {% endif %}
}

function send_client_report(contents) {
    {# Send report from this client to server. #}

    log('send client report');
    contents = JSON.stringify(contents);
    // alert('send_client_report( typeof contents:' + contents); // DEBUG
    $.post('/client_report/', {
           csrfmiddlewaretoken: django_csrf_token(),
           'Content-Type': 'text/html; charset=utf-8',
           'client-report-details': contents
    });

    {% comment %} NOT WORKING
    $.ajax({
        url: '/client_report/',
        type: 'post',
        data: {
            'csrfmiddlewaretoken': django_csrf_token(),
            'client-report-details': contents
        },
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'text/html; charset=utf-8',
        },
        dataType: 'json',
        success: function (data) {
            console.info(data);
        }
    });

    {# $.post seems less reliable than clicking submit in the form #}
    {# in fact apparently jquery implements $.post with a dynamically created form #}
    $.post('/client_report/',
           {'client-report-details': contents,
            'Accept': 'application/json',
            'Content-Type': 'text/html; charset=utf-8',
            'csrfmiddlewaretoken': django_csrf_token() });
    {% endcomment %}
}

function report_log() {
    {# Send log history to server. #}

    send_client_report(log_history);
}

function warn_exception(e, msg) {
    {# Log exception and warn user. #}

    if (msg) {
        log(msg);
    }
    log(e);

    report_error(e, msg);
}

function create_temp_form(url) {
    {# dynamically create temporary form #}

    let form = document.createElement('form');
    form.action = url;

    {# django csrf middleware #}
    form.innerHTML = '{% csrf_token %}' + '\n' + form.innerHTML;

    {# include submit button for us to click #}
    let submit = document.createElement('input');
    {# name and id must match button name convention from denova.django_addons.templatetags.custom.button_name_id() #}
    submit.name = 'temp-form-button';
    submit.id = 'id-temp-form';
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
    click_by_id('id-temp-form');
}

class Form {
    // NOT TESTED - Temporary form

    constructor(url) {
        {# dynamically create temporary form #}

        this.form = document.createElement('form');
        this.form.action = url;

        {# django csrf middleware #}
        this.form.innerHTML = '{% csrf_token %}' + '\n' + this.form.innerHTML;

        {# include submit button for us to click #}
        let submit = document.createElement('input');
        {# must match button name convention from denova.django_addons.templatetags.custom.button_name_id() #}
        submit.name = 'ok-button';
        submit.id = 'id-ok';
        submit.value = 'Ok';
        submit.type = 'submit';
        this.form.appendChild(submit);

        document.body.appendChild(this.form);
    }

    post() {
        this.form.method = 'post';
        send_temp_form(this.form);
    }

    send() {
        {# defaults to GET. use post_temp_form() to POST. #}
        click_by_id('temp-ok-id');
    }

}

// modified from django docs
function getCookie(name) {
    try {
        var cookieValue = Cookies.get(name);
    }

    catch(e) {
        // log('no Cookies lib; dropping to django getCookie()')
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
    }

    return cookieValue;
}

window.addEventListener("error", onerror_event_handler);
