function checkPasswordMatch() {
    var password = $("#newPassword").val();
    var confirmPassword = $("#confirmNewPassword").val();

    if (password == "" || confirmPassword == "") {
        $("#passwordAlerts").html("");
        return;
    }

    if (password != confirmPassword) {
        $("#passwordAlerts").html('<div class="alert alert-warning alert-dismissible" role="alert"> \
        <button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="true">\
        &times;</span></button> Passwords do not match! </div>');
    }
    else {
        $("#passwordAlerts").html("");
    }
}

$(document).ready(function () {
    $("#confirmNewPassword, #newPassword").keyup(checkPasswordMatch);

});

// http://stackoverflow.com/a/133997/4466589 by Rakesh Pai
    function post(path, params, method) {
    method = method || "post"; // Set method to post by default if not specified.

    // The rest of this code assumes you are not using a library.
    // It can be made less wordy if you use one.
    var form = document.createElement("form");
    form.setAttribute("method", method);
    form.setAttribute("action", path);

    for(var key in params) {
        if(params.hasOwnProperty(key)) {
            var hiddenField = document.createElement("input");
            hiddenField.setAttribute("type", "hidden");
            hiddenField.setAttribute("name", key);
            hiddenField.setAttribute("value", params[key]);

            form.appendChild(hiddenField);
         }
    }

    document.body.appendChild(form);
    form.submit();
}


function delete_wish(wish_id) {
    post("/delete-wish/", {wish_id: wish_id});
}

function accept_wish(to_whom, title, author, wish_id) {
    window.location.href = "mailto:" + to_whom + "?subject=Your request for '" + encodeURIComponent(title) + " - " + encodeURIComponent(author) + "' has been accepted" + "&body=" + encodeURIComponent("This is an automated e-mail. Please contact with a librarian for details.\n\nUWC Dilijan Library");
    if (confirm("Do you want to delete this request?")) {
        delete_wish(wish_id);
    }
}

function decline_wish(to_whom, title, author, wish_id) {
    window.location.href = "mailto:" + to_whom + "?subject=Your request for '" + encodeURIComponent(title) + " - " + encodeURIComponent(author) + "' has been declined" + "&body=" + encodeURIComponent("This is an automated e-mail. Please contact with a librarian for details.\n\nUWC Dilijan Library");
    if (confirm("Do you want to delete this request?")) {
        delete_wish(wish_id);
    }
}

function delete_interrupt(id) {
    post("/delete-interrupt/", {interrupt_id: id})
}