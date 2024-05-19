$(document).ready(function() {
    let path = window.location.pathname;
    $('form[name="admin_editor"]').on('submit', function(e) {
        e.preventDefault();
        $.ajax({
            url: path,
            method: 'POST',
            data: $(this).serialize(),
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
