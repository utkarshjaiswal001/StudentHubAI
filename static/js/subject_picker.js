// Upload/edit note form: list the official AKTU subjects for the chosen
// branch, year and semester. "Other" lets the owner type any subject.
(function () {
    var data = document.getElementById("subject-choices");
    var pick = document.getElementById("note-subject-pick");
    var input = document.getElementById("note-subject");
    var fields = ["note-branch", "note-year", "note-semester"].map(function (id) {
        return document.getElementById(id);
    });
    if (!data || !pick || !input || fields.indexOf(null) !== -1) return;
    var choices = JSON.parse(data.textContent);
    var OTHER = "__other__";

    function option(value, text) {
        var el = document.createElement("option");
        el.value = value;
        el.textContent = text;
        return el;
    }

    function showInput(show) {
        input.hidden = !show;
        pick.required = !show;
    }

    function refresh() {
        var key = fields.map(function (field) { return field.value; }).join("|");
        var subjects = choices[key] || [];
        pick.innerHTML = "";
        if (!subjects.length) {
            pick.hidden = true;
            showInput(true);
            return;
        }
        pick.appendChild(option("", "Select subject"));
        var current = input.value.trim().toLowerCase();
        var matched = false;
        subjects.forEach(function (subject) {
            var el = option(subject.name, subject.code + " · " + subject.name);
            if (subject.name.toLowerCase() === current) {
                el.selected = true;
                matched = true;
            }
            pick.appendChild(el);
        });
        var other = option(OTHER, "Other (type the subject name)");
        pick.appendChild(other);
        pick.hidden = false;
        if (matched) {
            showInput(false);
        } else if (current) {
            other.selected = true;
            showInput(true);
        } else {
            showInput(false);
        }
    }

    pick.addEventListener("change", function () {
        if (pick.value === OTHER) {
            input.value = "";
            showInput(true);
            input.focus();
        } else {
            input.value = pick.value;
            showInput(false);
        }
    });
    fields.forEach(function (field) { field.addEventListener("change", refresh); });
    refresh();
})();
