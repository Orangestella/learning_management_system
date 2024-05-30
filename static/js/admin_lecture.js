$(document).ready(function() {
    let path = window.location.pathname;
    $('form[name="admin_editor"]').on('submit', function(e) {
        e.preventDefault();
        let formData = new FormData($(this).get(0));
        $.ajax({
            url: path,
            method: 'POST',
            data: formData,
            processData: false,  // Don't process the files
            contentType: false,  // Set content type to false as jQuery will tell the server its a query string request
            success: function(data) {
                alert(data.message)
                if (data.status === 'success') {
                   window.close()
                }
            }
        });
    });

    $('a.delete_link').on('click', function (e) {
        let r = confirm("Are you sure you want to perform this operation?");
        if (r !== true) {
            e.preventDefault();
        }
    });
});
