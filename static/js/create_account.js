$(document).ready(function() {
    $('form[name="create_account"]').on('submit', function(e) {
        e.preventDefault();

        $.ajax({
            url: '/account/create_account',
            method: 'POST',
            data: $(this).serialize(),
            success: function(response) {
                if (response.status === 'success') {
                    window.close()
                } else {
                    swal("Fail to create", response.message, "error");
                }
            },
            error: function(error) {
                console.log(error);
                alert('An error occurred, please try again.');
            }
        });
    });
});
