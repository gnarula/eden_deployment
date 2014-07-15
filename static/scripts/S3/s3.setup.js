function update_prepop_list() {
    data = {"template": $("#setup_deploy_template option:selected").text()};
    $.ajax({
        type: 'POST',
        url: S3.Ap.concat('/setup/prepop_setting'),
        data: data,
        dataType: "json"
    })
    .done(function(prepop_options) {
        $('#setup_deploy_prepop_options').html('');
        $.each(prepop_options, function(key, value) {
            $('#setup_deploy_prepop_options')
                .append($("<option></option>")
                .attr("value", "template:" + value)
                .text(value));
            });
    });
}
$(document).ready(function() {
    update_prepop_list();
    $("#setup_deploy_template").change(update_prepop_list);
});