$(document).ready(function() {
    $('form').on('submit', function(e) {
        e.preventDefault();
        $.ajax({
            url: '/login',
            method: 'POST',
            data: $(this).serialize(),
            success: function(data) {
                if (data.status === 'error') {
                   swal("Fail to login", data.message, "error");
                } else {
                    window.location.href = '/';
                }
            }
        });
    });
});
