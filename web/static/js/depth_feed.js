// ToDo: Move to a js file for types and shared config values
var colors = {
                 "feed": {
                     'asks': '#e74c3c',
                     'bids': '#2ecc71'
                 },
                 'status': {
                     'alive': '#27ae60',
                     'dead': '#c0392b'
                 },
                 "price": {
                     'asks': '#e74c3c',
                     'bids': '#468966'
                 },
                 "logging": {
                     'bad': '#e74c3c',
                     'good': '#468960',
                     'neutral': '#1e2b34'
                 }
             };

var short_hand = {
                     'bids': 'b',
                     'asks': 'a'
                 };

// Helper functions
function set_conn_status(is_alive) {
    if(is_alive) {
        $('#statusId').css('background-color', colors.status.alive);
    } else {
        $('#statusId').css('background-color', colors.status.alive);
    }
}

function init_depth_feed(feed_depth)
{
    add_ask_rows(feed_depth, colors.feed.asks);
    add_spread_row();
    add_bid_rows(feed_depth, colors.feed.bids);
}

function update_depth_feed(book, feed_depth)
{
    update_side(short_hand.asks, book.asks, colors.feed.asks, feed_depth);
    update_side(short_hand.bids, book.bids, colors.feed.bids, feed_depth);
}

function add_bid_rows(depth, color) {
    for(var i = 0; i < depth; i++) {
        $('#bids').append(
            '<tr>'+
            '    <td style="color: '+color            +'; text-align: right;"  id="'+short_hand.bids+'o'+i+'"></td>'+
            '    <td style="color: '+color            +'; text-align: right;"  id="'+short_hand.bids+'q'+i+'"></td>'+
            '    <td style="color: '+colors.price.bids+'; text-align: center; font-weight: bold;" id="'+short_hand.bids+'p'+i+'"></td>'+
            '    <td></td>' +
            '    <td></td>' +
            '    <td align="left"                                              id="'+short_hand.bids+'delta'+i+'"></td>'+
            '</tr>'
        );
    }
}

function add_spread_row() {
    $('#spread').append(
        '<tr>'+
        '    <td></td>' +
        '    <td></td>' +
        '    <td id="spread_value" style="text-align: center;">'+0.0+'</td>' +
        '    <td><b>USD Spread</b></td>' +
        '    <td></td>' +
        '    <td></td>' +
        '</tr>'
    );
}

function add_ask_rows(depth, color) {
    for(var i = 0; i < depth; i++) {
        $('#asks').append(
            '<tr>'+
            '    <td></td>' +
            '    <td></td>' +
            '    <td style="color: '+colors.price.asks+'; text-align: center; font-weight: bold;" id="'+short_hand.asks+'p'+i+'"></td>'+
            '    <td style="color: '+color            +'"                      id="'+short_hand.asks+'q'+i+'"></td>'+
            '    <td style="color: '+color            +'"                      id="'+short_hand.asks+'o'+i+'"></td>'+
            '    <td align="left"                                              id="'+short_hand.asks+'delta'+i+'"></td>'+
            '</tr>'
        );
    }
}

function update_delta(price_tag, delta_tag, price)
{
    var priceT = $(price_tag);
    var deltaT = $(delta_tag);
    var deltaO = parseFloat(deltaT.text());
    if (isNaN(deltaO)) {
        deltaO = 0.0;
    }
    var priceN = parseFloat(price);
    var priceO = parseFloat(priceT.text());
    if (isNaN(priceO)) {
        priceO = priceN;
    }
    var deltaN = parseFloat(deltaO + priceN - priceO);
    deltaT.text(deltaN.toFixed(4));
}

function update_level(tag, value, color, animate) {
    var div_tag = $(tag);
    if (div_tag.text() != value) {
        if (tag.indexOf('q') > -1) {
            div_tag.text(value.toFixed(6));
        } else if (tag.indexOf('p') > -1) {
            div_tag.text(value.toFixed(2));
        } else if (tag.indexOf('o') > -1) {
            div_tag.text(parseInt(value));
        } else {
            div_tag.text(value);
        }

        if (animate) {
            if ((div_tag.is(':animated'))) {
                div_tag.stop();
            }
            div_tag.css('color', color);
            div_tag.animate({color: '#ecf0f1'}, 1000);
        }
    }
}

function update_side(side_str, feed, color, feed_depth) {
    $(feed).each(
        function(index, level) {
            var i = index;
            if (side_str == short_hand.asks) {
                i = (feed_depth-1) - index;
            }
            update_level('#'+side_str+'o'+i, level.orders, color, true);
            update_level('#'+side_str+'q'+i, level.qty, color, true);
            update_delta('#'+side_str+'p'+i, '#'+side_str+'delta'+index, level.price);
            update_level('#'+side_str+'p'+i, level.price, color, false);

            var bid_price = parseFloat($('#bp'+'0').text());
            var ask_price = parseFloat($('#ap'+(feed_depth-1)).text());
            $('#spread_value').text((ask_price - bid_price).toFixed(2));
        }
    );
}


