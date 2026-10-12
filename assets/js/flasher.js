/* LAB217 — flasher universal.
   1. Detecta si el navegador soporta Web Serial (estado en la cabecera).
   2. Consulta los releases oficiales de la org en GitHub y arma el catálogo:
      - firmware/manifest.json en la raíz del tag  -> flasheable por Web Serial (ESP)
      - assets .uf2 adjuntos al release            -> descarga para modo BOOTSEL (RP2040)
   Convención de publicación (ver README):
     ESP:   firmware/manifest.json + firmware/*.bin en el repo, en el tag del release.
     RP2040: adjuntar el .uf2 al release de GitHub.
   Catálogo cacheado en localStorage 30 min para no agotar el límite de la API. */
(function () {
  var ORG = "Lab217MX";
  var MANIFEST_PATH = "firmware/manifest.json";
  var CACHE_KEY = "lab217-flasher-catalog";
  var CACHE_TTL = 30 * 60 * 1000;

  // ---------- 1. Estado de compatibilidad (cabecera) ----------
  var dot = document.getElementById("serial-dot");
  var status = document.getElementById("serial-status");
  var unsupported = document.getElementById("unsupported");

  var hasSerial = "serial" in navigator;
  var secure = window.isSecureContext;

  if (hasSerial && secure) {
    if (dot) dot.classList.add("ok");
    if (status) status.innerHTML =
      "Navegador compatible con Web Serial. Elige un firmware y pulsa <b>Instalar</b>.";
  } else if (hasSerial && !secure) {
    if (dot) dot.classList.add("no");
    if (status) status.innerHTML =
      "Web Serial disponible, pero la página debe servirse por <b>HTTPS</b> o <b>localhost</b>.";
    if (unsupported) unsupported.style.display = "block";
  } else {
    if (dot) dot.classList.add("no");
    if (status) status.innerHTML =
      "Este navegador no soporta Web Serial. Usa <b>Chrome, Edge u Opera</b> de escritorio.";
    if (unsupported) unsupported.style.display = "block";
  }

  // ---------- 2. Catálogo desde releases de GitHub ----------
  var catalogStatus = document.getElementById("catalog-status");

  function gh(url) {
    return fetch(url, { headers: { Accept: "application/vnd.github+json" } }).then(function (r) {
      if (r.status === 404) return null;
      if (!r.ok) throw new Error("GitHub respondió " + r.status);
      return r.json();
    });
  }

  function rawUrl(repo, tag, path) {
    return "https://raw.githubusercontent.com/" + ORG + "/" + repo + "/" + tag + "/" + path;
  }

  function loadReleases() {
    try {
      var cached = JSON.parse(localStorage.getItem(CACHE_KEY));
      if (cached && Date.now() - cached.ts < CACHE_TTL) return Promise.resolve(cached.data);
    } catch (e) { /* caché inválido, seguir */ }

    return gh("https://api.github.com/orgs/" + ORG + "/repos?per_page=100")
      .then(function (repos) {
        if (!repos) return [];
        return Promise.all(repos.map(function (r) {
          return gh("https://api.github.com/repos/" + ORG + "/" + r.name + "/releases/latest")
            .then(function (rel) {
              if (!rel || !rel.tag_name) return null;
              return {
                repo: r.name,
                repoUrl: r.html_url,
                tag: rel.tag_name,
                releaseName: rel.name || rel.tag_name,
                releaseUrl: rel.html_url,
                uf2: (rel.assets || [])
                  .filter(function (a) { return /\.uf2$/i.test(a.name); })
                  .map(function (a) { return { name: a.name, url: a.browser_download_url, size: a.size }; })
              };
            });
        }));
      })
      .then(function (items) {
        var data = items.filter(Boolean);
        try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: data })); } catch (e) {}
        return data;
      });
  }

  // Un release es flasheable si trae firmware/manifest.json en el tag (raw tiene CORS abierto)
  function withManifest(entry) {
    var url = rawUrl(entry.repo, entry.tag, MANIFEST_PATH);
    return fetch(url).then(function (r) {
      if (!r.ok) return null;
      return r.json().then(function (m) {
        var build = m.builds && m.builds[0];
        if (!build || !build.chipFamily) return null;
        return {
          repo: entry.repo, tag: entry.tag, releaseUrl: entry.releaseUrl,
          manifestUrl: url, fwName: m.name || entry.repo, chipFamily: build.chipFamily
        };
      });
    }).catch(function () { return null; });
  }

  function fmtSize(bytes) {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  var canFlash = hasSerial && secure &&
    window.customElements && typeof customElements.whenDefined === "function";

  function espCard(fw) {
    var div = document.createElement("div");
    div.className = "fw";
    var label = "[ CHIP: " + fw.chipFamily + " · " + fw.tag + " ]";
    var controls;
    if (customElements.get("esp-web-install-button")) {
      controls = '<esp-web-install-button manifest="' + fw.manifestUrl + '">' +
        '<button slot="activate" class="btn btn--red">Instalar ' + fw.fwName + '</button>' +
        '<span slot="unsupported">Navegador no compatible — usa el método manual.</span>' +
        '<span slot="not-allowed">Necesitas servir la página por HTTPS o localhost.</span>' +
        "</esp-web-install-button>";
    } else {
      controls = '<a class="btn btn--red" href="' + fw.releaseUrl + '" target="_blank" rel="noopener">' +
        "Descargar firmware ↗</a>";
    }
    div.innerHTML =
      '<span class="chip">' + label + "</span>" +
      "<h3>" + fw.fwName + "</h3>" +
      '<p class="muted">Release oficial <b>' + fw.tag + "</b> del repo <code>" + fw.repo + "</code>.</p>" +
      '<div class="fw__actions">' + controls +
      '<a class="red" href="' + fw.releaseUrl + '" target="_blank" rel="noopener">Ver release ↗</a></div>';
    return div;
  }

  function uf2Card(entry, asset) {
    var div = document.createElement("div");
    div.className = "fw";
    div.innerHTML =
      '<span class="chip">[ CHIP: RP2040 / RP2350 · ' + entry.tag + " ]</span>" +
      "<h3>" + entry.repo + "</h3>" +
      '<p class="muted">Release oficial <b>' + entry.tag + "</b>. Entra en modo BOOTSEL y arrastra " +
      "el archivo a la unidad <code>RPI-RP2</code>.</p>" +
      '<div class="fw__actions">' +
      '<a class="btn btn--red" href="' + asset.url + '" download>Descargar ' + asset.name + "</a>" +
      '<span class="muted" style="font-size:13px">' + fmtSize(asset.size) + "</span>" +
      '<a class="red" href="' + entry.releaseUrl + '" target="_blank" rel="noopener">Ver release ↗</a></div>';
    return div;
  }

  function render(items) {
    var espList = document.getElementById("esp-list");
    var uf2List = document.getElementById("uf2-list");
    var espEmpty = document.getElementById("esp-empty");
    var uf2Empty = document.getElementById("uf2-empty");

    var dynamic = 0;
    items.forEach(function (entry) {
      entry.uf2.forEach(function (asset) {
        if (uf2List) { uf2List.appendChild(uf2Card(entry, asset)); dynamic++; }
      });
    });

    return Promise.all(items.map(withManifest)).then(function (esp) {
      esp.filter(Boolean).forEach(function (fw) {
        if (espList) { espList.appendChild(espCard(fw)); dynamic++; }
      });

      var espCount = esp.filter(Boolean).length;
      var uf2Count = items.reduce(function (n, e) { return n + e.uf2.length; }, 0);

      if (espEmpty) espEmpty.style.display = espCount ? "none" : "block";
      if (uf2Empty) uf2Empty.style.display = uf2Count ? "none" : "block";
      if (catalogStatus) {
        var total = espCount + uf2Count;
        catalogStatus.textContent = total
          ? "Catálogo oficial: " + total + " firmware" + (total === 1 ? "" : "s") +
            " en " + items.length + " release" + (items.length === 1 ? "" : "s") + " de GitHub."
          : "Aún no hay firmwares publicados en los releases de GitHub.";
      }
    });
  }

  // Esperar a que esp-web-tools defina su componente (CDN) antes de armar las tarjetas
  var ready = canFlash
    ? Promise.race([
        customElements.whenDefined("esp-web-install-button"),
        new Promise(function (r) { setTimeout(r, 4000); })
      ])
    : Promise.resolve();

  ready.then(loadReleases).then(render).catch(function (err) {
    if (catalogStatus) {
      catalogStatus.textContent =
        "No pude consultar los releases de GitHub (" + err.message +
        "). Revisa tu conexión o recarga en unos minutos; el firmware local de abajo sigue disponible.";
    }
    var espEmpty = document.getElementById("esp-empty");
    if (espEmpty) espEmpty.style.display = "block";
  });
})();
