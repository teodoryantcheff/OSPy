
function load_doc(e) {
    if(window.location.hash) {
        jQuery("#help_contents").load("/help?id=" + window.location.hash.substring(1));
    } else {
        jQuery("#help_contents").load("/help?id=1");
    }
}

jQuery(document).ready(load_doc);
jQuery(window).bind('hashchange', load_doc);
