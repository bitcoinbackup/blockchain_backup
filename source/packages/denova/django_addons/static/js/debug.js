/**
 * Javascript and jQuery debugging and error checking.
 *
 * If you are viewing this in a browser, this code is automatically generated.
 * Use the source.
 *
 * Copyright 2019 DeNova
 * Last modified: 2019-08-20
**/

// {# a lot of this isn't working, and may be unused #}

'use strict';

var ELEMENT_NODE = 1;
var TEXT_NODE = 3;
var PROCESSING_INSTRUCTION_NODE = 7;
var COMMENT_NODE = 8;
var DOCUMENT_NODE = 9;
var DOCUMENT_TYPE_NODE = 10;
var DOCUMENT_FRAGMENT_NODE = 11;

function dom(obj) {
    // {# return first HTML DOM object from jQuery object #}

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
    // {# return true if elem is a jquery element. Else return false. #}

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
    // {# return true if el is a dom element. Else return false. #}

    return ! is_undefined(el.innerHTML);
}

function jq_obj_name(jq_obj) {
    // {# return a short description of a jQuery object. #}

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
    // {# log the result of a jQuery selector. #}

    // log_if_undefined(jq_obj.selector, 'jQuery selector');

    console.log(jq_obj_name(jq_obj));
    if (jq_obj.context) {
        console.log('    context: ' + jq_obj.context);
    }
    if (jq_obj.length) {
        // {# don't clutter the display of a unique DOM object #}
        if (jq_obj.length > 1) {
            console.log('    length: ' + jq_obj.length);
        }
        for (var i = 0; i < jq_obj.length; i++) {
            var el = jq_obj[i];
            if (jq_obj.length > 1) {
                console.log(i + ':');
            }
            log_dom_obj(el);
        }
    }
    else {
        console.log(jq_obj_name(jq_obj) + ' selector did not match');
    }
}

function log_dom_obj(el) {
    // {# log a javascript DOM object, also called a Node. Indented. #}

    if (is_dom_element(el)) {
        console.log('    is jquery: ' + is_jquery_obj(el));
        console.log('    class: ' + classof(el));
        console.log('    tag name: ' + el.nodeName);
        var attributes_str = attr_str(el);
        if (attributes_str) {
            console.log('    attributes: ' + attr_str(el));
        }
        console.log('    type: ' + classof(el));
        console.log('    node type: ' + node_type(el));
        console.log('    node value: ' + el.nodeValue);
        console.log('    text: ' + shorten(strip(el.textContent || el.innerText)));
        console.log('    inner html: ' + shorten(strip(el.innerHtml)));
    }
    else {
        console.log('    not a dom object');
    }
}

function log_obj(obj) {
    // {# log members of obj, indented #}

    var object_class = classof(obj);
    console.log('    object class: ' + object_class);
    if (object_class === 'Array' || object_class === 'Object') {
        for (var field in obj) {
            console.log('    field class: ' + classof(field));

            var value = field.value;
            if (jQuery.isFunction(value)) {
                value = 'function';
            }
            console.log('    ' + field.name + ': ' + shorten(value));
        }
    }
}

function dom_text(el) {
    return el.textContent || el.innerText;
}

function node_type(el) {
    // {# Return readable nodeType of DOM object. #}

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
    // {# return attributes as a comma separated string. #}

    var attr_string = '';

    console.log('enter attr_str()');

    for (var attr in el.attributes) {
        console.log('attr');
        if (classof(attr) === 'String') {
            console.log('    attr is String: "' + attr + '"');
        }
        if (el.attributes.propertyIsEnumerable(attr)) {
            log_obj(el.attributes[attr]);
        }
        else {
            console.log(attr + ' is not enumerable');
        }

        console.log('    attr class: ' + classof(attr));
        if (attr_string) {
            attr_string = attr_string + ', ';
        }
        console.log('    attr name: ' + attr.name);
        console.log('    attr value: ' + attr.value);
        attr_string = attr_string + attr.name + ': ' + attr.value;
    }

    console.log('exit attr_str()');
    return attr_string;
}

function log_if_undefined(x, msg) {
    // {#  If x is undefined, log it. #}

    if (is_undefined(x)) {
        console.log('undefined: ' + msg);
    }
}

function alert_exception(e, message) {
    // {# Alert user to exception. #}

    log_exception(e, message);
    if (message) {
        alert(message + '\n' + e);
    }
    else {
        alert(e);
    }
}

function log_exception(e, message) {
    // {# Log exception. #}

    if (message) {
        console.log(message);
    }
    console.log(e);
}

function classof(obj) {
    // {# Return class of obj as a string. If no class returns 'null' or'undefined'. #}

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
    // {# get form field value #}

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
        console.log(e);
    }

    return value;
}

function shorten(s) {
    // {# If a string is long, return a short version. Else return the string. #}

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
    // {# Return text with spaces stripped. #}

    var result;

    if (is_undefined(text)) {
        result = undefined;
    }
    else {
        result = text.replace(/^\s+|\s+$/g, '');
    }
}

function is_undefined(x) {
    // {#  Return true if x is undefined. Else return false. #}

    return (typeof x) === 'undefined';
}
