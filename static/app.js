(function () {
  "use strict";

  // Filterable lists: a [data-list] container holds [data-item] cards.
  document.querySelectorAll("[data-filters]").forEach(function (panel) {
    var list = document.querySelector(panel.getAttribute("data-filters"));
    if (!list) return;
    var items = Array.prototype.slice.call(list.querySelectorAll("[data-item]"));
    var input = panel.querySelector("input[type=search]");
    var count = document.querySelector("[data-count]");
    var empty = document.querySelector("[data-empty]");
    var sortSel = panel.querySelector("select[data-sort]");
    var state = {};

    function apply() {
      var q = input ? input.value.toLowerCase().trim() : "";
      var words = q ? q.split(/\s+/) : [];
      var shown = 0;
      items.forEach(function (el) {
        var ok = true;
        var text = el.getAttribute("data-text") || "";
        for (var i = 0; i < words.length; i++) {
          if (text.indexOf(words[i]) === -1) { ok = false; break; }
        }
        if (ok) {
          for (var key in state) {
            if (state[key] === "all") continue;
            var have = " " + (el.getAttribute("data-" + key) || "") + " ";
            if (have.indexOf(" " + state[key] + " ") === -1) { ok = false; break; }
          }
        }
        el.hidden = !ok;
        if (ok) shown++;
      });
      if (count) count.textContent = shown + (shown === 1 ? " tool shown" : " tools shown");
      if (empty) empty.hidden = shown !== 0;
    }

    panel.querySelectorAll("[data-group]").forEach(function (group) {
      var key = group.getAttribute("data-group");
      state[key] = "all";
      group.querySelectorAll("button").forEach(function (btn) {
        btn.addEventListener("click", function () {
          state[key] = btn.getAttribute("data-value");
          group.querySelectorAll("button").forEach(function (b) {
            b.setAttribute("aria-pressed", b === btn ? "true" : "false");
          });
          apply();
        });
      });
    });

    if (sortSel) {
      sortSel.addEventListener("change", function () {
        var mode = sortSel.value;
        var sorted = items.slice().sort(function (a, b) {
          if (mode === "stars") return (+b.getAttribute("data-stars") || 0) - (+a.getAttribute("data-stars") || 0);
          if (mode === "updated") return (b.getAttribute("data-updated") || "").localeCompare(a.getAttribute("data-updated") || "");
          return (a.getAttribute("data-name") || "").localeCompare(b.getAttribute("data-name") || "");
        });
        sorted.forEach(function (el) { list.appendChild(el); });
      });
    }

    if (input) {
      var params = new URLSearchParams(window.location.search);
      if (params.get("q")) input.value = params.get("q");
      input.addEventListener("input", apply);
    }
    apply();
  });

  // Simple section filter (alternative finder): hides [data-section] blocks that do not match.
  document.querySelectorAll("[data-section-filter]").forEach(function (input) {
    var sections = Array.prototype.slice.call(document.querySelectorAll("[data-section]"));
    var empty = document.querySelector("[data-empty]");
    function apply() {
      var q = input.value.toLowerCase().trim();
      var shown = 0;
      sections.forEach(function (s) {
        var ok = !q || (s.getAttribute("data-section") || "").indexOf(q) !== -1;
        s.hidden = !ok;
        if (ok) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    }
    input.addEventListener("input", apply);
    apply();
  });

  // Copy buttons for install commands.
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      var done = function () {
        var old = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = old; }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      } else {
        var ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); done(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
  });
})();
