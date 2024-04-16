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
                    window.location.href = '/';  // 或者你想要跳转的页面
                }
            }
        });
    });
});
