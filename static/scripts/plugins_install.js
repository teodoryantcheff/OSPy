
jQuery(document).ready(function(){
    jQuery(".collapsible h4").click(function(event){
        jQuery(this).parent(".category").toggleClass("expanded").toggleClass("collapsed");
    });

    jQuery(".collapsible h4").first().parent(".category").toggleClass("expanded").toggleClass("collapsed");
    jQuery(".collapsible h5").click(function(event){
        jQuery(this).parent(".category").toggleClass("expanded").toggleClass("collapsed");
    });

    $(".collapsible a").click(function(e) { e.stopPropagation(); });
});
