(function () {
  "use strict";

  // Main menu button on small screens.
  var menuBtn = document.querySelector(".menu-btn");
  var nav = document.getElementById("site-nav");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && nav.classList.contains("open")) {
        nav.classList.remove("open");
        menuBtn.setAttribute("aria-expanded", "false");
        menuBtn.focus();
      }
    });
  }

  // Back-to-top button on long pages.
  if (document.documentElement.scrollHeight > window.innerHeight * 3) {
    var top = document.createElement("a");
    top.href = "#top";
    top.className = "to-top";
    top.hidden = true;
    top.setAttribute("aria-label", "Back to top");
    top.innerHTML = '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10 16V4M4.5 9.5L10 4l5.5 5.5"/></svg>';
    document.body.appendChild(top);
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        top.hidden = window.pageYOffset < window.innerHeight * 1.5;
        ticking = false;
      });
    }, { passive: true });
  }

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
    var toggle = panel.querySelector(".filter-toggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var open = panel.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

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
      if (toggle) {
        var active = 0;
        for (var k in state) { if (state[k] !== "all") active++; }
        toggle.textContent = active ? "Filters (" + active + ")" : "Filters";
      }
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

  // Evidence map: choose a device, then tap a part to show its panel.
  var xpanels = document.querySelector(".xray-panels");
  if (xpanels) {
    var spots = Array.prototype.slice.call(document.querySelectorAll(".xray .spot"));
    var devs = Array.prototype.slice.call(document.querySelectorAll("svg.xdev"));
    var tabs = Array.prototype.slice.call(document.querySelectorAll(".xtab"));
    var intros = Array.prototype.slice.call(document.querySelectorAll(".xintro"));
    var showDevice = function (id) {
      devs.forEach(function (d) { d.classList.toggle("on", d.getAttribute("data-device") === id); });
      tabs.forEach(function (b) {
        var on = b.getAttribute("data-device") === id;
        b.classList.toggle("on", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      intros.forEach(function (p) { p.classList.toggle("on", p.getAttribute("data-device") === id); });
    };
    var showPart = function (id, scroll) {
      var found = false;
      xpanels.querySelectorAll(".xpanel").forEach(function (p) {
        var on = p.getAttribute("data-panel") === id;
        p.classList.toggle("on", on);
        if (on) found = p;
      });
      spots.forEach(function (sp) { sp.classList.toggle("on", sp.getAttribute("data-part") === id); });
      xpanels.classList.toggle("idle", !found);
      if (found) showDevice(found.getAttribute("data-device"));
      if (found && scroll && window.innerWidth < 900) found.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
    tabs.forEach(function (b) {
      b.addEventListener("click", function () {
        showDevice(b.getAttribute("data-device"));
        xpanels.querySelectorAll(".xpanel").forEach(function (p) { p.classList.remove("on"); });
        spots.forEach(function (sp) { sp.classList.remove("on"); });
        xpanels.classList.add("idle");
        try { window.history.replaceState(null, "", window.location.pathname + "#dev-" + b.getAttribute("data-device")); } catch (e) {}
      });
    });
    spots.forEach(function (sp) {
      sp.addEventListener("click", function (ev) {
        ev.preventDefault();
        var id = sp.getAttribute("data-part");
        try { window.history.replaceState(null, "", "#part-" + id); } catch (e) {}
        showPart(id, true);
      });
    });
    var hash = window.location.hash || "";
    if (hash.indexOf("#dev-") === 0) {
      showDevice(hash.replace("#dev-", ""));
    } else {
      showPart(hash.replace("#part-", ""), false);
    }
    if (!devs.some(function (d) { return d.classList.contains("on"); }) && devs.length) showDevice(devs[0].getAttribute("data-device"));
  }

  // Pocket toolbox: everything is computed locally.
  var tbTs = document.getElementById("tb-ts");
  if (tbTs && typeof BigInt === "function") {
    var tbFmt = document.getElementById("tb-fmt");
    var tbTsOut = document.getElementById("tb-ts-out");
    var EPOCH_1601 = BigInt("11644473600000");
    var EPOCH_2001 = BigInt("978307200000");
    var convert = function () {
      var raw = tbTs.value.replace(/[\s,_]/g, "");
      if (!raw) { tbTsOut.textContent = "The date will appear here."; return; }
      if (!/^-?\d+(\.\d+)?$/.test(raw)) { tbTsOut.textContent = "Please enter digits only."; return; }
      var ms;
      try {
        var whole = BigInt(raw.split(".")[0]);
        var f = tbFmt.value;
        if (f === "unix") ms = whole * BigInt(1000);
        else if (f === "unixms") ms = whole;
        else if (f === "prtime") ms = whole / BigInt(1000);
        else if (f === "webkit") ms = whole / BigInt(1000) - EPOCH_1601;
        else if (f === "filetime") ms = whole / BigInt(10000) - EPOCH_1601;
        else if (f === "mac") ms = whole * BigInt(1000) + EPOCH_2001;
        else ms = whole / BigInt(1000000) + EPOCH_2001;
      } catch (err) { tbTsOut.textContent = "That value could not be read."; return; }
      var d = new Date(Number(ms));
      if (isNaN(d.getTime())) { tbTsOut.textContent = "That value is outside the range of dates. Check the format."; return; }
      tbTsOut.textContent = "UTC:        " + d.toISOString().replace("T", " ").replace(".000Z", "").replace("Z", "") +
        "\nYour time:  " + d.toString() + "\n\nCheck important values with a second tool.";
    };
    tbTs.addEventListener("input", convert);
    tbFmt.addEventListener("change", convert);
  }
  var tbFile = document.getElementById("tb-file");
  if (tbFile) {
    var tbHashOut = document.getElementById("tb-hash-out");
    var hex = function (buf) {
      return Array.prototype.map.call(new Uint8Array(buf), function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
    };
    tbFile.addEventListener("change", function () {
      var file = tbFile.files && tbFile.files[0];
      if (!file) return;
      if (!(window.crypto && window.crypto.subtle)) { tbHashOut.textContent = "This browser cannot calculate hashes on this page."; return; }
      if (file.size > 300 * 1024 * 1024) { tbHashOut.textContent = "This file is larger than 300 MB. Use a desktop hashing tool."; return; }
      tbHashOut.textContent = "Calculating...";
      file.arrayBuffer().then(function (buf) {
        return Promise.all([window.crypto.subtle.digest("SHA-256", buf), window.crypto.subtle.digest("SHA-1", buf)]);
      }).then(function (r) {
        tbHashOut.textContent = "File:    " + file.name + "\nSize:    " + file.size + " bytes\nSHA-256: " + hex(r[0]) + "\nSHA-1:   " + hex(r[1]);
      }).catch(function () { tbHashOut.textContent = "The file could not be read."; });
    });
  }
  var tbRot = document.getElementById("tb-rot");
  if (tbRot) {
    var tbRotOut = document.getElementById("tb-rot-out");
    tbRot.addEventListener("input", function () {
      tbRotOut.textContent = tbRot.value ? tbRot.value.replace(/[a-zA-Z]/g, function (ch) {
        var base = ch <= "Z" ? 65 : 97;
        return String.fromCharCode((ch.charCodeAt(0) - base + 13) % 26 + base);
      }) : "The decoded text will appear here.";
    });
  }
  var tbB64 = document.getElementById("tb-b64");
  if (tbB64) {
    var tbB64Out = document.getElementById("tb-b64-out");
    tbB64.addEventListener("input", function () {
      var v = tbB64.value.replace(/\s+/g, "");
      if (!v) { tbB64Out.textContent = "The decoded text will appear here."; return; }
      try {
        var bytes;
        if (/^(0x)?([0-9a-fA-F]{2})+$/.test(v)) {
          v = v.replace(/^0x/, "");
          bytes = new Uint8Array(v.length / 2);
          for (var i = 0; i < bytes.length; i++) bytes[i] = parseInt(v.substr(i * 2, 2), 16);
        } else {
          var bin = window.atob(v.replace(/-/g, "+").replace(/_/g, "/"));
          bytes = new Uint8Array(bin.length);
          for (var k = 0; k < bin.length; k++) bytes[k] = bin.charCodeAt(k);
        }
        tbB64Out.textContent = new TextDecoder("utf-8").decode(bytes);
      } catch (err) { tbB64Out.textContent = "This is not valid Base64 or hex."; }
    });
  }

  // Compare page: two or three tools side by side, facts only.
  var cmp = document.getElementById("cmp");
  var cmpData = document.getElementById("cmp-data");
  if (cmp && cmpData) {
    var db = JSON.parse(cmpData.textContent);
    var byId = {};
    db.tools.forEach(function (t) { byId[t.id] = t; });
    var out = document.getElementById("cmp-out");
    var catSel = document.getElementById("cmp-cat");
    var sels = [document.getElementById("cmp-a"), document.getElementById("cmp-b"), document.getElementById("cmp-c")];
    var params = new URLSearchParams(window.location.search);
    var picked = (params.get("t") || "").split(",").filter(function (id) { return byId[id]; }).slice(0, 3);
    if (params.get("c") && db.cats[params.get("c")]) catSel.value = params.get("c");

    var esc = function (v) {
      return String(v).replace(/[&<>"]/g, function (ch) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]; });
    };
    function fillSelects() {
      var cat = catSel.value;
      sels.forEach(function (sel, i) {
        var keep = picked[i] || "";
        var html = '<option value="">' + (i === 2 ? "Third tool (optional)" : "Choose a tool") + "</option>";
        db.tools.forEach(function (t) {
          if (cat && t.cats.indexOf(cat) === -1 && t.id !== keep) return;
          html += '<option value="' + t.id + '"' + (t.id === keep ? " selected" : "") + ">" + esc(t.name) + "</option>";
        });
        sel.innerHTML = html;
      });
    }
    function row(label, cells, cls) {
      return '<tr' + (cls ? ' class="' + cls + '"' : "") + '><th scope="row">' + label + "</th>" +
        cells.map(function (c) { return "<td>" + c + "</td>"; }).join("") + "</tr>";
    }
    function head(label, n) { return '<tr class="grp"><th scope="colgroup" colspan="' + (n + 1) + '">' + label + "</th></tr>"; }
    function render() {
      var tools = picked.filter(Boolean).map(function (id) { return byId[id]; });
      var q = tools.map(function (t) { return t.id; }).join(",");
      var url = window.location.pathname + (q ? "?t=" + q : (catSel.value ? "?c=" + catSel.value : ""));
      try { window.history.replaceState(null, "", url); } catch (e) {}
      if (tools.length < 2) {
        out.innerHTML = '<p class="empty">Choose at least two tools to compare.</p>';
        return;
      }
      var n = tools.length;
      var dash = '<span class="no">Not available</span>';
      var h = '<div class="cmp-wrap"><table class="cmp"><thead><tr><td></td>' + tools.map(function (t) {
        return '<th scope="col"><a href="tools/' + t.id + '.html">' + esc(t.name) + '</a><span>by ' + esc(t.dev) + "</span></th>";
      }).join("") + "</tr></thead><tbody>";
      h += head("Basics", n);
      h += row("What it does", tools.map(function (t) { return esc(t.sum); }));
      h += row("Licence", tools.map(function (t) { return esc(t.lic); }));
      h += row("Interface", tools.map(function (t) { return esc(t.iface); }));
      h += row("Runs on", tools.map(function (t) { return esc(t.plat.join(", ")); }));
      h += row("Level", tools.map(function (t) { return esc(t.level); }));
      h += head("Functions it is listed under", n);
      var cats = [];
      Object.keys(db.cats).forEach(function (c) {
        if (tools.some(function (t) { return t.cats.indexOf(c) !== -1; })) cats.push(c);
      });
      cats.forEach(function (c) {
        h += row('<a href="categories/' + c + '.html">' + esc(db.cats[c]) + "</a>", tools.map(function (t) {
          return t.cats.indexOf(c) !== -1 ? '<span class="yes">Listed</span>' : '<span class="no">Not listed</span>';
        }));
      });
      h += head("Project activity" + (cmp.getAttribute("data-checked") ? " (checked " + esc(cmp.getAttribute("data-checked")) + ")" : ""), n);
      h += row("Latest release", tools.map(function (t) { return t.rel ? esc(t.rel) + (t.reldate ? "<br><small>" + esc(t.reldate) + "</small>" : "") : dash; }));
      h += row("Last code update", tools.map(function (t) { return t.upd ? esc(t.upd) : dash; }));
      h += row("GitHub stars", tools.map(function (t) { return t.stars ? esc(t.stars) : dash; }));
      h += row("Activity", tools.map(function (t) { return t.act ? esc(t.act) : dash; }));
      h += head("On this site", n);
      h += row("Does a similar job to", tools.map(function (t) { return t.sim.length ? esc(t.sim.join(", ")) : '<span class="no">None listed</span>'; }));
      h += row("Used in workflows", tools.map(function (t) {
        return t.wf.length ? t.wf.map(function (w) { return '<a href="workflows/' + w[0] + '.html">' + esc(w[1]) + "</a>"; }).join("<br>") : '<span class="no">None yet</span>';
      }));
      h += row("Full guide", tools.map(function (t) { return t.guide ? '<a href="tools/' + t.id + '.html">Read the guide</a>' : '<span class="no">Not yet</span>'; }));
      h += row("Download", tools.map(function (t) { return '<a href="tools/' + t.id + '.html">Open tool page</a>'; }));
      out.innerHTML = h + "</tbody></table></div>";
    }
    sels.forEach(function (sel, i) {
      sel.addEventListener("change", function () { picked[i] = sel.value; fillSelects(); render(); });
    });
    catSel.addEventListener("change", function () { fillSelects(); render(); });
    fillSelects();
    render();
  }

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
