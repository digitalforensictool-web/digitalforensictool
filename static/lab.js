(function () {
  "use strict";
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function hex(b) { return ("0" + b.toString(16)).slice(-2); }
  function readBuf(file, max) {
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onload = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
      r.readAsArrayBuffer(max ? file.slice(0, max) : file);
    });
  }
  function fmtSize(n) { return n < 1024 ? n + " bytes" : n < 1048576 ? (n / 1024).toFixed(1) + " KB" : (n / 1048576).toFixed(1) + " MB"; }
  function table(rows) {
    return '<table class="lab-table"><tbody>' + rows.map(function (r) {
      return "<tr><th scope=\"row\">" + esc(r[0]) + "</th><td>" + esc(r[1]) + "</td></tr>";
    }).join("") + "</tbody></table>";
  }

  // ---------- EXIF reader (JPEG and PNG eXIf) ----------
  var TYPES = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8 };
  function readIfd(dv, tiff, off, le, names, out, sub) {
    if (off + 2 > dv.byteLength) return;
    var n = dv.getUint16(off, le);
    for (var i = 0; i < n; i++) {
      var e = off + 2 + i * 12;
      if (e + 12 > dv.byteLength) break;
      var tag = dv.getUint16(e, le), type = dv.getUint16(e + 2, le), cnt = dv.getUint32(e + 4, le);
      var size = (TYPES[type] || 1) * cnt;
      var vo = size <= 4 ? e + 8 : tiff + dv.getUint32(e + 8, le);
      if (vo + size > dv.byteLength) continue;
      var val = null;
      if (type === 2) {
        var s = "";
        for (var k = 0; k < cnt; k++) { var c = dv.getUint8(vo + k); if (c === 0) break; s += String.fromCharCode(c); }
        val = s.trim();
      } else if (type === 3) {
        val = []; for (var a = 0; a < cnt; a++) val.push(dv.getUint16(vo + a * 2, le));
      } else if (type === 4) {
        val = []; for (var b = 0; b < cnt; b++) val.push(dv.getUint32(vo + b * 4, le));
      } else if (type === 5 || type === 10) {
        val = [];
        for (var d = 0; d < cnt; d++) {
          var nu = type === 5 ? dv.getUint32(vo + d * 8, le) : dv.getInt32(vo + d * 8, le);
          var de = type === 5 ? dv.getUint32(vo + d * 8 + 4, le) : dv.getInt32(vo + d * 8 + 4, le);
          val.push(de ? nu / de : 0);
        }
      } else if (type === 1 || type === 7) {
        val = []; for (var m = 0; m < Math.min(cnt, 8); m++) val.push(dv.getUint8(vo + m));
      }
      if (sub && sub[tag] !== undefined) { sub[tag](val); continue; }
      if (names[tag]) out[names[tag]] = val;
    }
  }
  function parseTiff(buf, start) {
    var dv = new DataView(buf);
    var le = dv.getUint16(start) === 0x4949;
    if (dv.getUint16(start + 2, le) !== 42) return null;
    var out = { main: {}, exif: {}, gps: {} };
    var ifd0 = start + dv.getUint32(start + 4, le), exifOff = 0, gpsOff = 0;
    var M = { 0x010F: "Make", 0x0110: "Model", 0x0112: "Orientation", 0x0131: "Software", 0x0132: "DateTime", 0x013B: "Artist", 0x8298: "Copyright" };
    var X = { 0x9003: "DateTimeOriginal", 0x9004: "DateTimeDigitized", 0xA002: "Width", 0xA003: "Height", 0x829A: "ExposureTime", 0x829D: "FNumber",
      0x8827: "ISO", 0x920A: "FocalLength", 0xA434: "LensModel", 0xA431: "BodySerialNumber", 0xA430: "CameraOwnerName", 0xA433: "LensMake" };
    var G = { 0x0001: "LatRef", 0x0002: "Lat", 0x0003: "LonRef", 0x0004: "Lon", 0x0005: "AltRef", 0x0006: "Alt", 0x0007: "Time", 0x001D: "Date" };
    readIfd(dv, start, ifd0, le, M, out.main, { 0x8769: function (v) { exifOff = v[0]; }, 0x8825: function (v) { gpsOff = v[0]; } });
    if (exifOff) readIfd(dv, start, start + exifOff, le, X, out.exif);
    if (gpsOff) readIfd(dv, start, start + gpsOff, le, G, out.gps);
    return out;
  }
  function jpegInfo(buf) {
    var u = new Uint8Array(buf), dv = new DataView(buf), p = 2, info = { exif: null, width: 0, height: 0, segments: [] };
    if (u[0] !== 0xFF || u[1] !== 0xD8) return null;
    while (p + 4 <= u.length) {
      if (u[p] !== 0xFF) break;
      var mk = u[p + 1];
      if (mk === 0xD8 || (mk >= 0xD0 && mk <= 0xD7) || mk === 0x01) { p += 2; continue; }
      if (mk === 0xD9 || mk === 0xDA) break;
      var len = dv.getUint16(p + 2);
      if (mk === 0xE1 && u[p + 4] === 69 && u[p + 5] === 120 && u[p + 6] === 105 && u[p + 7] === 102) {
        info.segments.push("EXIF (APP1)");
        try { info.exif = parseTiff(buf, p + 10); } catch (e) { info.exif = null; }
      } else if (mk === 0xE0) info.segments.push("JFIF (APP0)");
      else if (mk === 0xE1) info.segments.push("XMP or other (APP1)");
      else if (mk === 0xED) info.segments.push("Photoshop IRB (APP13)");
      else if (mk === 0xFE) info.segments.push("Comment");
      if ((mk >= 0xC0 && mk <= 0xCF) && mk !== 0xC4 && mk !== 0xC8 && mk !== 0xCC) { info.height = dv.getUint16(p + 5); info.width = dv.getUint16(p + 7); }
      p += 2 + len;
    }
    return info;
  }
  function pngInfo(buf) {
    var u = new Uint8Array(buf), dv = new DataView(buf), p = 8, info = { exif: null, width: dv.getUint32(16), height: dv.getUint32(20), text: [] };
    while (p + 12 <= u.length) {
      var len = dv.getUint32(p), type = String.fromCharCode(u[p + 4], u[p + 5], u[p + 6], u[p + 7]);
      if (type === "eXIf") { try { info.exif = parseTiff(buf, p + 8); } catch (e) {} }
      if (type === "tEXt") {
        var s = ""; for (var i = 0; i < Math.min(len, 200); i++) s += String.fromCharCode(u[p + 8 + i] || 32);
        info.text.push(s.replace(/\0/g, ": "));
      }
      if (type === "IEND") break;
      p += 12 + len;
    }
    return info;
  }
  function dms(v, ref) {
    if (!v || v.length < 3) return null;
    var d = v[0] + v[1] / 60 + v[2] / 3600;
    return (ref === "S" || ref === "W") ? -d : d;
  }
  function describeImage(buf, name) {
    var u = new Uint8Array(buf), kind = "", info = null;
    if (u[0] === 0xFF && u[1] === 0xD8) { kind = "JPEG"; info = jpegInfo(buf); }
    else if (u[0] === 0x89 && u[1] === 0x50 && u[2] === 0x4E && u[3] === 0x47) { kind = "PNG"; info = pngInfo(buf); }
    else return '<p class="lab-warn">This tool reads JPEG and PNG photos. The file does not start like either. For HEIC, TIFF, RAW or video, use ExifTool on your own computer.</p>';
    var rows = [["File name", name], ["Detected type", kind], ["Picture size", info.width ? info.width + " x " + info.height + " pixels" : "not found"]];
    var flags = [];
    var ex = info.exif;
    if (!ex) {
      flags.push("No EXIF block found. The photo may have been stripped by a messaging app, a website or an editor, or it may never have had one.");
    } else {
      var m = ex.main, x = ex.exif, g = ex.gps;
      function add(label, v) { if (v !== undefined && v !== null && v !== "") rows.push([label, Array.isArray(v) ? v.join(", ") : v]); }
      add("Camera make", m.Make); add("Camera model", m.Model); add("Software", m.Software);
      add("Modified (DateTime)", m.DateTime); add("Taken (DateTimeOriginal)", x.DateTimeOriginal); add("Digitized", x.DateTimeDigitized);
      add("Artist", m.Artist); add("Copyright", m.Copyright); add("Owner name", x.CameraOwnerName); add("Body serial number", x.BodySerialNumber);
      add("Lens", x.LensModel);
      if (x.ExposureTime) add("Exposure time", "1/" + Math.round(1 / x.ExposureTime[0]) + " s");
      if (x.FNumber) add("Aperture", "f/" + x.FNumber[0].toFixed(1));
      if (x.ISO) add("ISO", x.ISO);
      if (x.FocalLength) add("Focal length", x.FocalLength[0].toFixed(1) + " mm");
      if (g.Lat && g.Lon) {
        var la = dms(g.Lat, g.LatRef), lo = dms(g.Lon, g.LonRef);
        rows.push(["GPS position", la.toFixed(5) + ", " + lo.toFixed(5)]);
        flags.push("This photo contains a GPS position. Check on a map whether it fits the story. GPS in a file is a clue, not proof of where the person was.");
      }
      if (m.Software) flags.push("A Software tag is present. It may name the camera firmware, the phone system or an editing program. If it names an editor, the file was probably saved again after it was taken.");
      if (m.DateTime && x.DateTimeOriginal && m.DateTime !== x.DateTimeOriginal) flags.push("The 'modified' time differs from the 'taken' time. The file was probably saved again later.");
      flags.push("Camera clocks can be wrong and can be changed. Compare these times with the file system times and with other evidence.");
    }
    if (info.segments && info.segments.length) rows.push(["Metadata blocks", info.segments.join(", ")]);
    if (info.text && info.text.length) rows.push(["PNG text chunks", info.text.join(" | ")]);
    return table(rows) + (flags.length ? '<ul class="lab-flags">' + flags.map(function (f) { return "<li>" + esc(f) + "</li>"; }).join("") + "</ul>" : "");
  }

  // ---------- sample photo with EXIF (built in the browser) ----------
  function asc(s) { var a = []; for (var i = 0; i < s.length; i++) a.push(s.charCodeAt(i)); a.push(0); return a; }
  function u16(v) { return [(v >> 8) & 255, v & 255]; }
  function u32(v) { return [(v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255]; }
  function rat(n, d) { return u32(n).concat(u32(d)); }
  function ifdBytes(entries, base, nextZero) {
    entries.sort(function (a, b) { return a.tag - b.tag; });
    var head = 2 + entries.length * 12 + 4, data = [], out = u16(entries.length);
    entries.forEach(function (en) {
      var bytes = en.bytes, cnt = en.count;
      out = out.concat(u16(en.tag), u16(en.type), u32(cnt));
      if (bytes.length <= 4) { var pad = bytes.slice(); while (pad.length < 4) pad.push(0); out = out.concat(pad); }
      else { out = out.concat(u32(base + head + data.length)); data = data.concat(bytes); if (data.length % 2) data.push(0); }
    });
    out = out.concat(u32(0));
    return out.concat(data);
  }
  function buildSampleExif() {
    var A = function (tag, s) { var b = asc(s); return { tag: tag, type: 2, count: b.length, bytes: b }; };
    var exifE = [A(0x9003, "2026:03:14 09:12:55"), A(0x9004, "2026:03:14 09:12:55"),
      { tag: 0x829A, type: 5, count: 1, bytes: rat(1, 250) }, { tag: 0x829D, type: 5, count: 1, bytes: rat(18, 10) },
      { tag: 0x8827, type: 3, count: 1, bytes: u16(200).concat([0, 0]) }, { tag: 0x920A, type: 5, count: 1, bytes: rat(60, 10) }, A(0xA434, "Example 26mm f/1.8")];
    var gpsE = [A(0x0001, "N"), { tag: 0x0002, type: 5, count: 3, bytes: rat(28, 1).concat(rat(36, 1), rat(4644, 100)) },
      A(0x0003, "E"), { tag: 0x0004, type: 5, count: 3, bytes: rat(77, 1).concat(rat(13, 1), rat(4620, 100)) }];
    var main0 = function (exOff, gpsOff) {
      return [A(0x010F, "ExampleCam"), A(0x0110, "EC-100"), { tag: 0x0112, type: 3, count: 1, bytes: u16(1).concat([0, 0]) },
        A(0x0131, "Example Photo Editor 2.1"), A(0x0132, "2026:03:14 18:30:02"),
        { tag: 0x8769, type: 4, count: 1, bytes: u32(exOff) }, { tag: 0x8825, type: 4, count: 1, bytes: u32(gpsOff) }];
    };
    var size0 = ifdBytes(main0(0, 0), 8).length;
    var exOff = 8 + size0, sizeX = ifdBytes(exifE.slice(), exOff).length, gpsOff = exOff + sizeX;
    var tiff = [0x4D, 0x4D, 0, 42].concat(u32(8), ifdBytes(main0(exOff, gpsOff), 8), ifdBytes(exifE, exOff), ifdBytes(gpsE, gpsOff));
    var body = [69, 120, 105, 102, 0, 0].concat(tiff);
    return [0xFF, 0xE1].concat(u16(body.length + 2), body);
  }
  function makeSample(cb) {
    var c = document.createElement("canvas"); c.width = 480; c.height = 300;
    var x = c.getContext("2d"), g = x.createLinearGradient(0, 0, 480, 300);
    g.addColorStop(0, "#1437C8"); g.addColorStop(1, "#FFD84A");
    x.fillStyle = g; x.fillRect(0, 0, 480, 300);
    x.fillStyle = "#fff"; x.font = "bold 44px sans-serif"; x.fillText("SAMPLE PHOTO", 56, 160);
    x.font = "20px sans-serif"; x.fillText("made in your browser for practice", 62, 200);
    c.toBlob(function (blob) {
      readBuf(blob).then(function (buf) {
        var u = new Uint8Array(buf), seg = buildSampleExif(), out = new Uint8Array(u.length + seg.length);
        out.set(u.subarray(0, 2), 0); out.set(seg, 2); out.set(u.subarray(2), 2 + seg.length);
        cb(new File([out], "sample-photo.jpg", { type: "image/jpeg" }), out.buffer);
      });
    }, "image/jpeg", 0.9);
  }

  var imgIn = $("lab-img");
  if (imgIn) {
    var imgOut = $("lab-img-out"), imgPrev = $("lab-img-prev");
    var show = function (file, buf) {
      imgOut.innerHTML = describeImage(buf, file.name) + '<p class="muted" style="font-size:13px">File size: ' + fmtSize(file.size) + ". Nothing was uploaded.</p>";
      try { var url = URL.createObjectURL(new Blob([buf], { type: file.type || "image/jpeg" })); imgPrev.innerHTML = '<img alt="Preview of the chosen picture" src="' + url + '">'; } catch (e) {}
    };
    imgIn.addEventListener("change", function () {
      var f = imgIn.files && imgIn.files[0]; if (!f) return;
      if (f.size > 60 * 1048576) { imgOut.textContent = "Please choose a file under 60 MB."; return; }
      readBuf(f).then(function (b) { show(f, b); });
    });
    var sb = $("lab-img-sample");
    if (sb) sb.addEventListener("click", function () { makeSample(function (f, b) { show(f, b); }); });
    var sd = $("lab-img-dl");
    if (sd) sd.addEventListener("click", function () {
      makeSample(function (f) { var a = document.createElement("a"); a.href = URL.createObjectURL(f); a.download = "sample-photo.jpg"; document.body.appendChild(a); a.click(); a.remove(); });
    });
  }

  // ---------- file signature checker ----------
  var SIGS = [
    ["FFD8FF", "JPEG image", ["jpg", "jpeg", "jpe"]], ["89504E470D0A1A0A", "PNG image", ["png"]], ["47494638", "GIF image", ["gif"]],
    ["25504446", "PDF document", ["pdf"]], ["504B0304", "ZIP container (also DOCX, XLSX, PPTX, JAR, APK)", ["zip", "docx", "xlsx", "pptx", "jar", "apk", "odt", "ods", "epub"]],
    ["52617221", "RAR archive", ["rar"]], ["377ABCAF271C", "7-Zip archive", ["7z"]], ["1F8B08", "GZIP data", ["gz", "tgz"]],
    ["4D5A", "Windows program (MZ: EXE, DLL, SYS)", ["exe", "dll", "sys", "scr", "ocx"]], ["7F454C46", "ELF program (Linux)", ["elf", "so", "bin", ""]],
    ["53514C69746520666F726D6174203300", "SQLite database", ["db", "sqlite", "sqlite3", "db3"]], ["D0CF11E0A1B11AE1", "Old Office / OLE2 file (DOC, XLS, PPT, MSG)", ["doc", "xls", "ppt", "msg"]],
    ["49443303", "MP3 audio (ID3 tag)", ["mp3"]], ["FFFB", "MP3 audio", ["mp3"]], ["4F676753", "Ogg media", ["ogg", "oga", "ogv"]], ["664C6143", "FLAC audio", ["flac"]],
    ["1A45DFA3", "Matroska or WebM video", ["mkv", "webm"]], ["4D534346", "Microsoft cabinet (CAB)", ["cab"]], ["EVF", "", []], ["255044462D", "PDF document", ["pdf"]],
    ["EB52904E544653", "NTFS volume boot record", ["img", "dd", "raw"]], ["4C0000000114020000000000C000000000000046", "Windows shortcut (LNK)", ["lnk"]],
    ["7B5C72746631", "RTF document", ["rtf"]], ["3C3F786D6C", "XML text", ["xml", "plist"]], ["62706C697374", "Apple binary plist", ["plist"]],
    ["4344303031", "ISO 9660 image", ["iso"]], ["5B5A6F6E65", "Windows zone identifier text", ["ini"]]
  ];
  function detect(u) {
    var h = ""; for (var i = 0; i < Math.min(u.length, 32); i++) h += hex(u[i]).toUpperCase();
    var t4 = String.fromCharCode(u[4], u[5], u[6], u[7]), t8 = String.fromCharCode(u[8], u[9], u[10], u[11]), s3 = String.fromCharCode(u[0], u[1], u[2], u[3]);
    if (s3 === "RIFF") return t8 === "WAVE" ? ["WAV audio", ["wav"]] : t8 === "AVI " ? ["AVI video", ["avi"]] : t8 === "WEBP" ? ["WebP image", ["webp"]] : ["RIFF container", []];
    if (t4 === "ftyp") {
      var br = t8;
      if (br === "heic" || br === "heix" || br === "mif1") return ["HEIC / HEIF image", ["heic", "heif"]];
      if (br === "qt  ") return ["QuickTime video (MOV)", ["mov"]];
      if (br === "M4A ") return ["M4A audio", ["m4a"]];
      return ["MPEG-4 media (brand " + br.trim() + ")", ["mp4", "m4v", "m4a", "3gp"]];
    }
    if (s3 === "EVF\t") return ["EnCase E01 evidence file", ["e01", "ex01"]];
    for (var k = 0; k < SIGS.length; k++) { if (SIGS[k][1] && h.indexOf(SIGS[k][0]) === 0) return [SIGS[k][1], SIGS[k][2]]; }
    return null;
  }
  var sigIn = $("lab-sig");
  if (sigIn) {
    sigIn.addEventListener("change", function () {
      var f = sigIn.files && sigIn.files[0]; if (!f) return;
      readBuf(f, 64).then(function (b) {
        var u = new Uint8Array(b), line = [], txt = "";
        for (var i = 0; i < Math.min(u.length, 32); i++) { line.push(hex(u[i])); txt += (u[i] > 31 && u[i] < 127) ? String.fromCharCode(u[i]) : "."; }
        var ext = (f.name.indexOf(".") > -1 ? f.name.split(".").pop() : "").toLowerCase();
        var d = detect(u), verdict;
        if (!d) verdict = '<p class="lab-warn">Signature not in this small table. It may be plain text or a type this lab does not know. Try a larger tool such as TrID or the file command.</p>';
        else if (d[1].length && d[1].indexOf(ext) === -1) verdict = '<p class="lab-warn"><strong>The name and the content do not match.</strong> The extension is ".' + esc(ext) + '", but the content looks like: ' + esc(d[0]) + ". This can be an honest mistake or a disguised file. Look closer.</p>";
        else verdict = '<p class="lab-ok">The extension and the content agree: ' + esc(d[0]) + ".</p>";
        $("lab-sig-out").innerHTML = table([["File name", f.name], ["Size", fmtSize(f.size)], ["First bytes (hex)", line.join(" ")], ["As text", txt]]) + verdict;
      });
    });
  }

  // ---------- compare two files ----------
  function sha256(buf) {
    return crypto.subtle.digest("SHA-256", buf).then(function (d) {
      return Array.prototype.map.call(new Uint8Array(d), hex).join("");
    });
  }
  var ca = $("lab-cmp-a"), cb2 = $("lab-cmp-b");
  if (ca && cb2 && window.crypto && crypto.subtle) {
    var run = function () {
      var a = ca.files && ca.files[0], b = cb2.files && cb2.files[0];
      if (!a || !b) return;
      var out = $("lab-cmp-out");
      if (a.size > 300 * 1048576 || b.size > 300 * 1048576) { out.textContent = "Please use files under 300 MB. Larger images need a desktop hashing tool."; return; }
      out.textContent = "Calculating...";
      Promise.all([readBuf(a).then(sha256), readBuf(b).then(sha256)]).then(function (h) {
        var same = h[0] === h[1];
        out.innerHTML = table([["File A", a.name + " (" + fmtSize(a.size) + ")"], ["SHA-256 of A", h[0]], ["File B", b.name + " (" + fmtSize(b.size) + ")"], ["SHA-256 of B", h[1]]]) +
          (same ? '<p class="lab-ok"><strong>The hash values match.</strong> The two files are identical, byte for byte.</p>'
                : '<p class="lab-warn"><strong>The hash values are different.</strong> The files are not identical. Even one changed byte gives a completely different value.</p>');
      });
    };
    ca.addEventListener("change", run); cb2.addEventListener("change", run);
  }

  // ---------- strings ----------
  var stIn = $("lab-str");
  if (stIn) {
    var all = [];
    var draw = function () {
      var q = ($("lab-str-q").value || "").toLowerCase(), shown = all.filter(function (s) { return !q || s.toLowerCase().indexOf(q) > -1; });
      $("lab-str-out").innerHTML = '<p class="muted">' + shown.length + " of " + all.length + ' strings shown (first 300).</p><pre class="lab-pre">' + esc(shown.slice(0, 300).join("\n")) + "</pre>";
    };
    var extract = function (u, min, wide) {
      var res = [], cur = "", i;
      for (i = 0; i < u.length; i++) {
        var c = u[i];
        if (c > 31 && c < 127) cur += String.fromCharCode(c);
        else { if (cur.length >= min) res.push(cur); cur = ""; }
      }
      if (cur.length >= min) res.push(cur);
      if (wide) {
        cur = "";
        for (i = 0; i + 1 < u.length; i += 2) {
          if (u[i] > 31 && u[i] < 127 && u[i + 1] === 0) cur += String.fromCharCode(u[i]);
          else { if (cur.length >= min) res.push("[UTF-16] " + cur); cur = ""; }
        }
        if (cur.length >= min) res.push("[UTF-16] " + cur);
      }
      return res;
    };
    var go = function () {
      var f = stIn.files && stIn.files[0]; if (!f) return;
      readBuf(f, 4 * 1048576).then(function (b) {
        all = extract(new Uint8Array(b), Math.max(4, parseInt($("lab-str-min").value, 10) || 8), $("lab-str-wide").checked);
        draw();
      });
    };
    stIn.addEventListener("change", go);
    $("lab-str-min").addEventListener("change", go); $("lab-str-wide").addEventListener("change", go);
    $("lab-str-q").addEventListener("input", draw);
  }
})();
