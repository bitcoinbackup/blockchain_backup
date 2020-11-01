/**
    Javascript to dynamicically update blockchain management progress.

    Copyright 2018-2019 DeNova
    Last modified: 2019-12-16
**/

function update(data) {
    /**
     *  Update fields with the latest data.
     *
     *  data: JSON encoded updates.
     **/

    console.log('Got update: ' + data.update);

    updates = JSON.parse(data.update);

    update_html(updates,
                ['header',
                 'notice',
                 'subnotice',
                 'progress',
                 'button',
                 ]);

    update_attributes(updates,
                      ['alert',
                       'nav-link',
                      ]);

    update_location(updates, ['location']);
}

function subscribe() {
    ws_subscribe('{{ update_facility }}',
                 '{{ update_type }}',
                 update);
}

$(subscribe);
