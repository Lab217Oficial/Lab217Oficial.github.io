#!/usr/bin/env python3
"""
lab217.py — herramienta local para escribir y publicar el blog de Lab217.

Filosofía: transparente y segura.
  - Todo son archivos de texto planos + git. Nada mágico.
  - Escribes en Markdown dentro de posts/src/*.md.
  - `build` genera el HTML y reconstruye los índices (blog.html + preview del index).
  - `publish` prepara el commit pero NUNCA hace push. El contenido sólo llega a
    GitHub Pages cuando la cuenta dueña del repo ejecuta el push a mano.

Uso:
  python3 tools/lab217.py new "Título del post"     # crea un .md nuevo
  python3 tools/lab217.py build                      # genera HTML + índices
  python3 tools/lab217.py serve [puerto]             # previsualiza en localhost
  python3 tools/lab217.py publish [-m "mensaje"]     # build + commit (sin push)
  python3 tools/lab217.py list                       # lista los posts

Sin dependencias externas: sólo la librería estándar de Python 3.
"""

import sys, os, re, html, subprocess, datetime, http.server, socketserver, functools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "posts", "src")
POSTS_DIR = os.path.join(ROOT, "posts")
BLOG_HTML = os.path.join(ROOT, "blog.html")
INDEX_HTML = os.path.join(ROOT, "index.html")
INDEX_PREVIEW_COUNT = 2

# ----------------------------------------------------------------------------
# Markdown mínimo (subconjunto suficiente para un blog de taller)
# ----------------------------------------------------------------------------
def _inline(text):
    """Convierte inline markdown a HTML, escapando lo demás."""
    # Proteger spans de código `...`
    codes = []
    def stash(m):
        codes.append(html.escape(m.group(1)))
        return "\x00%d\x00" % (len(codes) - 1)
    text = re.sub(r"`([^`]+)`", stash, text)

    text = html.escape(text)

    # Imágenes ![alt](src)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                  r'<img src="\2" alt="\1">', text)
    # Enlaces [texto](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  r'<a href="\2">\1</a>', text)
    # Negrita **...**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Cursiva *...*
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)

    # Restaurar código
    def unstash(m):
        return "<code>%s</code>" % codes[int(m.group(1))]
    text = re.sub(r"\x00(\d+)\x00", unstash, text)
    return text


def md_to_html(md):
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]

        # Bloque de código ```
        if line.strip().startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            i += 1  # saltar cierre
            out.append("<pre><code>%s</code></pre>" % "\n".join(buf))
            continue

        # Línea en blanco
        if not line.strip():
            i += 1
            continue

        # Regla horizontal
        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # Encabezados
        m = re.match(r"^(#{2,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (level, _inline(m.group(2).strip()), level))
            i += 1
            continue

        # Cita
        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>%s</blockquote>" % _inline(" ".join(buf)))
            continue

        # Lista sin orden
        if re.match(r"^\s*[-*]\s+", line):
            buf = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append("<li>%s</li>" % _inline(re.sub(r"^\s*[-*]\s+", "", lines[i])))
                i += 1
            out.append("<ul>%s</ul>" % "".join(buf))
            continue

        # Lista ordenada
        if re.match(r"^\s*\d+\.\s+", line):
            buf = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                buf.append("<li>%s</li>" % _inline(re.sub(r"^\s*\d+\.\s+", "", lines[i])))
                i += 1
            out.append("<ol>%s</ol>" % "".join(buf))
            continue

        # Párrafo (junta líneas consecutivas)
        buf = []
        while i < n and lines[i].strip() and not re.match(
                r"^\s*(#{2,4}\s|>|[-*]\s|\d+\.\s|```)", lines[i]) and not re.match(
                r"^\s*([-*_])\1{2,}\s*$", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % _inline(" ".join(buf)))
    return "\n      ".join(out)


# ----------------------------------------------------------------------------
# Front matter + carga de posts
# ----------------------------------------------------------------------------
def parse_post(path):
    raw = open(path, encoding="utf-8").read()
    meta, body = {}, raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            header = raw[3:end].strip()
            body = raw[end + 4:].lstrip("\n")
            for ln in header.split("\n"):
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    slug = os.path.splitext(os.path.basename(path))[0]
    meta.setdefault("title", slug)
    meta.setdefault("date", "1970-01-01")
    meta.setdefault("author", "Lab217")
    meta.setdefault("summary", "")
    meta["slug"] = slug
    meta["body_md"] = body
    return meta


def load_posts():
    if not os.path.isdir(SRC_DIR):
        return []
    posts = [parse_post(os.path.join(SRC_DIR, f))
             for f in os.listdir(SRC_DIR) if f.endswith(".md")]
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def fmt_date(d):
    return d.replace("-", ".")


# ----------------------------------------------------------------------------
# Plantillas
# ----------------------------------------------------------------------------
POST_TEMPLATE = """<!DOCTYPE html>
<html lang="es" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} — Blog LAB217</title>
  <meta name="description" content="{summary}">
  <meta name="color-scheme" content="dark">
  <link rel="icon" href="../assets/img/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>

  <header class="nav">
    <div class="container nav__row">
      <a class="brand" href="../index.html" aria-label="Lab217 inicio">
        <img src="../assets/img/lab217-logo.svg" alt="Lab217">
      </a>
      <button class="nav__burger" id="burger" aria-expanded="false" aria-controls="menu">[ menú ]</button>
      <nav class="nav__links" id="menu" aria-label="Principal">
        <a href="../index.html#nosotros">Nosotros</a>
        <a href="../index.html#hacemos">Qué hacemos</a>
        <a href="../proyectos.html">Proyectos</a>
        <a href="../tienda.html">Tienda</a>
        <a href="../blog.html">Blog</a>
        <a href="../index.html#contacto">Contacto</a>
        <a href="../flasher.html">Flasher</a>
      </nav>
    </div>
  </header>

  <main>
  <div class="container">
    <article class="article">
      <div class="breadcrumb"><a href="../index.html">inicio</a> / <a href="../blog.html">blog</a> / {slug}</div>
      <h1>{title}</h1>
      <div class="meta">{date_disp} · por {author}</div>

      {body}

      <p style="margin-top:34px"><a class="btn btn--ghost" href="../blog.html">← Volver al blog</a></p>
    </article>
  </div>
  </main>

  <div class="hazard" aria-hidden="true"></div>
  <footer>
    <div class="container">
      <div class="foot-bar" style="border-top:none">
        <span>© <span id="y"></span> LAB217 · Hecho en México</span>
        <span>[ status: online ] · CC BY-SA / GPL</span>
      </div>
    </div>
  </footer>

  <script src="../assets/js/main.js"></script>
</body>
</html>
"""

ROW_TEMPLATE = """        <a class="post-row" href="posts/{slug}.html">
          <time datetime="{date}">{date_disp}</time>
          <div>
            <h3>{title}</h3>
            <p class="muted">{summary}</p>
          </div>
          <span class="arrow">→</span>
        </a>"""


def render_rows(posts):
    return "\n".join(ROW_TEMPLATE.format(
        slug=p["slug"], date=p["date"], date_disp=fmt_date(p["date"]),
        title=html.escape(p["title"]), summary=html.escape(p["summary"])) for p in posts)


def replace_between(path, block):
    txt = open(path, encoding="utf-8").read()
    pat = re.compile(r"(<!-- POSTS:START.*?-->)(.*?)(<!-- POSTS:END -->)", re.DOTALL)
    if not pat.search(txt):
        print("  ! aviso: no encontré los marcadores POSTS en %s" % os.path.basename(path))
        return
    new = pat.sub(lambda m: m.group(1) + "\n" + block + "\n        " + m.group(3), txt)
    open(path, "w", encoding="utf-8").write(new)


# ----------------------------------------------------------------------------
# Comandos
# ----------------------------------------------------------------------------
def cmd_build(args=None):
    posts = load_posts()
    if not posts:
        print("No hay posts en posts/src/. Crea uno con:  python3 tools/lab217.py new \"Mi título\"")
        return
    for p in posts:
        out = POST_TEMPLATE.format(
            title=html.escape(p["title"]), summary=html.escape(p["summary"]),
            slug=p["slug"], date_disp=fmt_date(p["date"]),
            author=html.escape(p["author"]), body=md_to_html(p["body_md"]))
        open(os.path.join(POSTS_DIR, p["slug"] + ".html"), "w", encoding="utf-8").write(out)
        print("  ✓ posts/%s.html" % p["slug"])
    replace_between(BLOG_HTML, render_rows(posts))
    replace_between(INDEX_HTML, render_rows(posts[:INDEX_PREVIEW_COUNT]))
    print("Índices actualizados: blog.html y index.html (%d posts)." % len(posts))


def cmd_new(args):
    if not args:
        print("Uso: python3 tools/lab217.py new \"Título del post\"")
        return
    title = " ".join(args)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    today = datetime.date.today().isoformat()
    fname = "%s-%s.md" % (today, slug)
    path = os.path.join(SRC_DIR, fname)
    os.makedirs(SRC_DIR, exist_ok=True)
    if os.path.exists(path):
        print("Ya existe: %s" % path)
        return
    skeleton = (
        "---\n"
        "title: %s\n"
        "date: %s\n"
        "author: el colectivo Lab217\n"
        "summary: Resumen corto que aparece en la lista del blog.\n"
        "---\n\n"
        "Primer párrafo. Escribe en Markdown normal.\n\n"
        "## Un subtítulo\n\n"
        "Texto con **negrita**, *cursiva*, `código` y [enlaces](https://example.com).\n\n"
        "> Una cita punk.\n\n"
        "- viñeta uno\n- viñeta dos\n"
    ) % (title, today)
    open(path, "w", encoding="utf-8").write(skeleton)
    print("Creado: posts/src/%s" % fname)
    print("Edítalo y luego corre:  python3 tools/lab217.py build")


def cmd_list(args=None):
    posts = load_posts()
    if not posts:
        print("(sin posts)")
        return
    for p in posts:
        print("  %s  %s" % (p["date"], p["title"]))


def cmd_serve(args):
    port = int(args[0]) if args else 8217
    os.chdir(ROOT)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler)
    with socketserver.TCPServer(("", port), handler) as httpd:
        print("Sirviendo en http://localhost:%d  (Ctrl+C para parar)" % port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


def _git(*a):
    return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True)


def cmd_publish(args):
    msg = "blog: actualizar contenido"
    if args and args[0] in ("-m", "--message") and len(args) > 1:
        msg = " ".join(args[1:])

    print("== 1) Generando el sitio ==")
    cmd_build()

    if not os.path.isdir(os.path.join(ROOT, ".git")):
        print("\nEste directorio no es un repo git. Inicialízalo antes de publicar.")
        return

    print("\n== 2) Cambios detectados ==")
    status = _git("status", "--short")
    print(status.stdout or "  (sin cambios)")
    if not status.stdout.strip():
        print("Nada que publicar.")
        return

    resp = input("\n¿Crear el commit con estos cambios? [y/N] ").strip().lower()
    if resp != "y":
        print("Cancelado. No se tocó nada en git.")
        return

    _git("add", "-A")
    commit = _git("commit", "-m", msg)
    print(commit.stdout + commit.stderr)

    branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"
    print("=" * 60)
    print("Commit listo en la rama '%s'." % branch)
    print("NADA se ha subido todavía. Para publicar en GitHub Pages,")
    print("la cuenta dueña del repo debe ejecutar el push a mano:")
    print()
    print("    git push origin %s" % branch)
    print()
    print("Sólo entonces el contenido se hará público. (Transparente y seguro.)")
    print("=" * 60)


COMMANDS = {
    "new": cmd_new, "build": cmd_build, "serve": cmd_serve,
    "publish": cmd_publish, "list": cmd_list,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
