
jQuery(document).ready(function(){

    jQuery("#cSubmit").click(function() {
        jQuery("#stationsForm").submit();
    });

    jQuery("#cResetNames").click(function(){
        jQuery("input[type='text']").each(function () {
            var num = parseInt(jQuery(this).attr("name").split('_')[0]) + 1;
            jQuery(this).val("Station " + (num<10 ? "0" : "") + num);
        });
        jQuery(".stationShow input").each(function () {
            jQuery(this).prop('checked', true);
        });
    });

});