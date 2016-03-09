tinymce.init({
    selector: 'textarea',
    plugins: "autosave contextmenu image",
    toolbar: "undo redo | bold italic underline | subscript superscript | alignleft aligncenter alignright | bullist numlist | outdent indent | image | fullscreen",
    menubar: false,
    statusbar: false,
    convert_urls: false,
    height: 200,

    browser_spellcheck: true,

    block_formats: 'Header 1=h1;Header 2=h2',

    image_description: true,

    contextmenu: "bold italic underline | subscript superscript",

    file_browser_callback: function(field_name, url, type, win) {
        if (type == 'image') {
            $('#image_form input').click();
        }
    }

});
