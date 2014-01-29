
function load_peers() {
    $('#peers table').dataTable({
        "bProcessing": true,
        "sAjaxSource": "api/peers",
        "sAjaxDataProp": "data",
        "sPaginationType": "full_numbers",
        "bJQueryUI": false,
        "bStateSave": true,
        "aoColumns": [
            { "sTitle": "IPv", "mData": "ver" },
            { "sTitle": "Router", "mData": "router" },
            { "sTitle": "IP", "mData": "ip" },
            { "sTitle": "ASN", "mData": "asn" },
            { "sTitle": "Prefixes", "mData": "prefixes" },
            { "sTitle": "State", "mData": "state" },
            { "sTitle": "Last Change", "mData": "last_change" }
        ],
        "fnDrawCallback" : function() {
            $('#peers p.status span').text('loaded at ' + new Date());
        }
    });
}

function load_routers() {
    $('#routers table').dataTable({
        "bProcessing": true,
        "sAjaxSource": "api/routers",
        "sAjaxDataProp": "data",
        "sPaginationType": "full_numbers",
        "bJQueryUI": false,
        "bStateSave": true,
        "aoColumns": [
            { "sTitle": "Name", "mData": "name" },
            { "sTitle": "State", "mData": "state" },
            { "sTitle": "Updated", "mData": "updated",
                "mRender": function (data, type, row) {
                    if(data == 0)
                        return "never";

                    var dur = new Date().getTime() - data;
                    return Math.round(dur / 1000) + "s ago";
                },
            },
            { "sTitle": "Peers", "mData": "peers" },
            { "sTitle": "Vendor", "mData": "hardware.vendor" },
            { "sTitle": "Serial", "mData": "hardware.serial" },
            { "sTitle": "Model", "mData": "hardware.model" }
        ],
        "fnDrawCallback" : function() {
            $('#routers p.status span').text('loaded at ' + new Date());
        }
    });
}

var g_progress = null;
    
function refresh() {
    var start = new Date().getTime();
   
    if(g_progress != null) {
        console.warn('already refreshing');
        return;
    }

    g_progress = setInterval(function() {
        var dur = new Date().getTime() - start;
        $('#refresh_status').text(
            'refreshing for ' + (dur / 1000) + ' seconds'); 
    }, 100);

    jQuery.ajax("api/refresh", {
        "cache": false,
    })
    .always(function() {
        clearInterval(g_progress);
        g_progress = null;
    })
    .done(function(data) {
        $('#refresh_status').text('refreshed at ' + new Date());
    })
    .fail(function(jqXHR, textStatus, errorThrown) {
        $('#refresh_status').text('ERROR refreshing');
    });
}

function look() {
    var start = new Date().getTime();
    var progress = setInterval(function() {
        var dur = new Date().getTime() - start;
        $('#look_status').text(
            'running for ' + (dur / 1000) + ' seconds'); 
    }, 100);

    var url = "api/look/" + $('#host').val() + "/" + $('#cmd').val();
    jQuery.ajax(url)
        .done(function(data) {
            $('#look textarea').empty();
            
            $.each(data.results, function(host, lines) {
                $.each(lines.split("\n"), function(_i, line) {
                    $('#look textarea').append("[" + host + "] " + line + "\n");
                })
            });
            
            clearInterval(progress);
            $('#look_status').text('done at ' + new Date());
        })
        .fail(function(jqXHR, textStatus, errorThrown) {
            clearInterval(progress);
            $('#look_status').text('ERROR');
        });
}

function reload_status() {
    jQuery.ajax("api/routers", { cache: false })
        .done(function(data) {
            $('#quick tbody').html('');
            
            $.each(data.data, function(_index, router) {
                $('#quick tbody').append('<tr><td>' + router.name + '</td><td>' + router.state + '</td></tr>');
            });
        })
        .fail(function(jqXHR, textStatus, errorThrown) {
            $('#quick tbody').html('');
        });

}

function setup() {
    $('#routers a.reload').click(function() {
        $('#routers table').dataTable().fnReloadAjax();
    });
    $('#peers a.reload').click(function() {
        $('#peers table').dataTable().fnReloadAjax();
    });
    $('#refresh').click(refresh);
    setInterval(reload_status, 1000);
}

$(document).ready(function() {
    setup();
    load_peers();
    load_routers();
});
