/**
    Javascript module to subscribe to a websockets channel.

    This is a general purpose library not tied to a specific app.

    Copyright 2018-2019 DeNova
    Last modified: 2019-12-17
**/

'use strict';

function ws_subscribe(facility,         // websockets facility
                      message_type,     // websockets message type
                      callback        // callback function
                      ) {

    let ws_path = '{{ WEBSOCKET_URI }}' + facility + '?subscribe-broadcast';
    console.log('Connect to ' + ws_path);

    //let ws_socket = new WebSocket(ws_path);
    let ws_socket = WS4Redis({
        uri: ws_path,
        connecting: on_connecting,
        connected: on_connected,
        receive_message: receiveMessage,
        disconnected: on_disconnected,
        heartbeat_msg: '{{ WS4REDIS_HEARTBEAT }}'
    });


    #ws_socket.on_connecting = function on_connecting() {
    function on_connecting() {
        console.log('Websocket is connecting...');
    }

    #ws_socket.on_connected = function on_connected() {
    function on_connected() {
        ws_socket.send_message('Hello');
    }

    #ws_socket.on_disconnected = function on_disconnected(evt) {
    function on_disconnected(evt) {
        console.log('Websocket was disconnected: ' + JSON.stringify(evt));
    }

    // attach this function to an event handler on your site
    function sendMessage() {
        ws_socket.send_message('A message');
    }

    function receiveMessage(message) {
        console.log('Got websocket message');
        let data = JSON.parse(message);

        if (data.error) {
            console.log(data.error);
            return;
        }

        if (data.type === message_type) {
            // callback() must be defined by user of this module
            callback(data);
        }
        else {
            console.log('Error: Expected data type "' + message_type + '", got "' + data.type + '"');
            return;
        }
    }
};

function update_html(updates, names) {
    /** Update innerHTML for elements.
     *
     *  'names' is a array of element ids to be updated.
     *
     *  'updates' is an object with element names of id+"_html".
     *  'updates' values are the html for that id.
     */

    function update_element(element, name, value) {
        element.innerHTML = value;
        let time = updates[name+'_time_html'];
        if (time) {
            element.setAttribute('title', time);
        }
    }

    console.log('update html');

    for (i = 0; i < names.length; i++) {
        let name = names[i];
        let name_html = name + '_html';
        let value = updates[name_html];
        if (value) {
            if (value.length < 100) {
                console.log('update ' + name + ': ' + value);
            }
            else {
                console.log('update ' + name);
            }

            element = document.getElementById(name);
            if (element) {
                update_element(element, name, value);
            }
            else {
                // check if multiple elements to update
                elements = document.getElementsByName(name);
                if (elements) {
                    for (let i = 0; i < elements.length; ++i) {
                        update_element(elements[i], name, value);
                    }
                }
                else {
                console.log('no id or name found: ' + name);
                }
            }
        }
    }
}

function update_attribute(element, attr, value) {
    /** Update attribute for an element.
     */

    // if the attribute is the state, then change the classname
    if (attr == 'state') {
        let className = element.className;
        let k = className.indexOf('disabled');

        // enable the menu item
        if (value == 'enabled') {
            while (k >= 0) {
                element.className = className.slice(0, k);
                className = element.className;
                k = className.indexOf('disabled');
            }
        }
        else {
            // disable the item
            if (k == -1) {
                element.className = className + ' ' + value;
            }
        }
        console.log('updated classname: ' + element.className);
    }
    else if (attr == 'style') {
        if (element.hasAttribute(attr)) {
            let index = value.indexOf(':');
            let property = value.substring(0, index);
            let style = value.substring(index + 1, value.length);
            if (property == 'width') {
                console.log('set width to "' + style + '" for ' + element.id);
                element.style.width = style + '%';
            }
            else {
                element.setAttribute(attr, value);
                console.log('set ' + attr + ': "' + value + '" for ' + element.id);
            }
        }
        else {
            console.log('unknown property for style: ' + property);
        }
    }
    else {
        if (element.hasAttribute(attr)) {
            element.setAttribute(attr, value);
            console.log('set ' + attr + ': "' + value + '" for ' + element.id);
        }
        else {
            element.innerHTML = value;
            console.log('set inner html: ' + value);
        }
    }
}

function update_attributes(updates, names) {
    /** Update attributes for elements.
     *
     *  'updates' is an object with element names of id+"_html".
     *  'updates' values are the html for that id.
     *
     *  'names' is a array of element ids to be updated.
     */

    for (i = 0; i < names.length; i++) {
        let name = names[i];
        let name_html = name + '_html';
        let attr_value = updates[name_html];
        if (attr_value && attr_value.indexOf('=') >= 0) {

            let j = attr_value.indexOf('=');
            let attr = attr_value.substring(0, j);
            let value = attr_value.substring(j + 1, attr_value.length);

            let named_elements = document.getElementsByName(name);
            if (named_elements.length > 0) {
                console.log('changing ' + attr + ' to ' + value + ' for ' + named_elements.length + ' ' + name + ' elements');
                for (j = 0; j < named_elements.length; j++) {
                    update_attribute(named_elements[j], attr, value);
                }
            }
            else {
                console.log('no ' + name + ' element found');

                id_element = document.getElementById(name);
                if (id_element) {
                    update_attribute(id_element, attr, value);
                }
                else {
                    console.log('no id found: ' + name);
                }
            }
        }
    }
}

function update_location(updates, names) {
    /** Update location of the web page.
     *
     *  'location' is a the new url to go to.
     */
    for (i = 0; i < names.length; i++) {
        let name = names[i];
        let name_html = name + '_html';
        let new_location = updates[name_html];

        if (new_location != undefined) {
            let current_location = window.location.pathname;
            if (new_location != current_location) {
                console.log('current location: ' + current_location);
                console.log('new location: ' + new_location);
                window.location.assign(new_location);
            }
        }
    }
}
