/**
    Javascript to dynamicically update bitcoin progress.
    AJAX backup because websockets is unreliable.
    Load and display the latest info periodically.

    Copyright 2019 DeNova
    Last modified: 2019-12-16
**/

'use strict';

var update_period = {{ update_interval }};
setInterval(update_ajax, update_period);
console.log('update interval: ' + update_period);

function update_ajax() {

    $.get('/bitcoin/ajax/', process_response);
}

function process_response(message) {
    /** Process the response from an ajax request.
     *
     *  message is json encoded dictionary of keys and their values.
     */

    if (message != undefined) {
        let data = JSON.parse(message);

        if (data.error) {
            console.log(data.error);
        }

        else if (data == undefined) {
            console.log('no data to update');
        }

        else {
            for (var name in data) {
                var value = data[name];
                if (name == 'header' ||
                    name == 'notice' ||
                    name == 'subnotice' ||
                    name == 'progress') {

                    update_html(name, value);
                }

                else if (name == 'alert' ||
                         name == 'nav-link') {

                    update_attribute(name, value);
                }

                else if (name == 'location') {
                    update_location(value);
                }
            }
        }
    }
}

function update_html(name, value) {
    /** Update innerHTML for named element.
     *
     *  'name' is an object with an element with the name or id.
     *  'value' is the html to set the element.
     */

    // console.log('updating html in ' + name + ' with '' + value + ''')

    let element = document.getElementById(name);
    if (element) {
        element.innerHTML = value;
    }
    else {
        // check if multiple elements to update
        let elements = document.getElementsByName(name);
        if (elements) {
            for (let i = 0; i < elements.length; ++i) {
                elements[i].innerHTML = value;
            }
        }
        else {
            console.log('no id or name found: "' + name + '"');
        }
    }
}

function update_attribute(name, value) {
    /** Update attribute for elements.
     *
     *  'name' is an object with an element with the name or id.
     *  'value' is the attribute to set the element.
     */

    console.log('updating attribute in ' + name + ' with "' + value + '"');

    if (value && value.indexOf('=') >= 0) {

        let j = value.indexOf('=');
        let attr = value.substring(0, j);
        let new_value = value.substring(j + 1, value.length);

        let named_elements = document.getElementsByName(name);
        if (named_elements.length > 0) {
            console.log('changing ' + attr + ' to ' + new_value +
              ' for ' + named_elements.length + ' ' + name + ' elements');
            for (j = 0; j < named_elements.length; j++) {
                update_element(named_elements[j], attr, new_value);
            }
        }
        else {
            console.log('no ' + name + ' element found');

            id_element = document.getElementById(name);
            if (id_element == undefined) {
                console.log('no id found: ' + name);
            }
            else {
                update_element(id_element, attr, new_value);
            }
        }
    }
}

function update_element(element, attr, value) {
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
                console.log("set width to '" + style + "' for " + element.id);
                element.style.width = style + '%';
            }
            else {
                element.setAttribute(attr, value);
                console.log('set ' + attr + ': "' + value +
                  '" for ' + element.id);
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

function update_location(url) {
    /** Update the web page being displayed.
     *
     *  'url' is the new web page.
     */
    if (url != undefined) {
        let current_location = window.location.pathname;
        if (url != current_location) {
            console.log('current location: ' + current_location);
            console.log('new location: ' + url);
            window.location.assign(url);
        }
    }
}
