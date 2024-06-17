$(document).ready(function() {
    let path = window.location.pathname;
    $('form[name="submission_form"]').on('submit', function(e) {
        e.preventDefault();
        let formData = new FormData($(this).get(0));
        $.ajax({
            url: path,
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                alert(data.message)
                if (data.status === 'success') {
                   window.location.href='/';
                }
            }
        });
    });
});
