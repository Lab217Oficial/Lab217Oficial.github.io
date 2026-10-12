# Lab217 · sitio oficial

Sitio estático (HTML/CSS/JS, sin build) para **Lab217** — hardware y software open source,
punk y orgullosamente mexicano. Pensado para GitHub Pages.

> Hardware libre desde México para todo el mundo · *Romper para fortalecer*

## Estructura

```
index.html            Landing: hero, nosotros, qué hacemos, proyectos, flasher, blog, contacto
proyectos.html        Catálogo completo de proyectos
tienda.html           Tienda (próximamente) — estructura lista para vender kits
blog.html             Índice del blog
flasher.html          Flasher de firmware por navegador (Web Serial / UF2)
posts/                Entradas del blog (HTML generado — no editar a mano)
  src/                Fuente en Markdown de cada post (esto SÍ lo editas)
tools/
  lab217.py           Herramienta local: escribe, genera y publica el blog
assets/
  css/style.css       Estilos (monocromo + acento rojo #FF2A1A)
  js/main.js          Nav móvil + año del footer
  js/flasher.js       Detección de compatibilidad Web Serial
  fonts/              Quadaptor (display) + Roboto (cuerpo)
  img/                Logo + favicon de marca
  firmware/           Binarios .bin + manifests para el flasher
.nojekyll             Evita que GitHub Pages ignore archivos con "_"
```

## Desarrollo local

Necesitas un servidor (el flasher requiere contexto seguro: `localhost` cuenta):

```bash
python3 -m http.server 8217
# abre http://localhost:8217
```

## Marca

- **Colores:** `#000000` `#FFFFFF` `#A5A5A5` `#EFEFEF` + acento rojo señal `#FF2A1A`
- **Tipografías:** Quadaptor (títulos display / logo) · Roboto y Roboto Condensed (cuerpo/encabezados)
- Estética: punk / industrial / brutalista monocromo. Bordes duros, hazard tape, scanlines, glitch.

## Flasher de firmware

El flasher es **universal**: al abrirlo consulta en vivo los releases oficiales de la org
[`Lab217MX`](https://github.com/Lab217MX) en GitHub y arma el catálogo solo. Todo proyecto
nuevo debe publicar su firmware como release oficial; la convención es:

- **ESP32 / ESP8266 — flasheable por Web Serial.** En el repo del proyecto, en la carpeta
  `firmware/` **del tag del release**: un `manifest.json` (formato
  [esp-web-tools](https://esphome.github.io/esp-web-tools/)) junto a los `.bin` que referencia.
  Las rutas `path` de las parts son relativas a la carpeta del manifest.
  Ejemplo mínimo:
  ```json
  { "name": "Mi Firmware",
    "builds": [ { "chipFamily": "ESP32-S3",
                  "parts": [ { "path": "mi-firmware.bin", "offset": 0 } ] } ] }
  ```
  La página lo detecta, muestra su tarjeta con botón **Instalar** y lo escribe vía Web Serial.
- **RP2040 / RP2350 (Pico) — descargable.** Adjunta el `.uf2` al release de GitHub; aparece como tarjeta
  de descarga junto a las instrucciones de modo `BOOTSEL` (las placas RP2040 y RP2350 no usan Web Serial).
- **Kraken Kit:** su firmware base es el ESP32 Bit Pirate; se flashea desde el
  [webflasher oficial del proyecto](https://geo-tp.github.io/ESP32-Bit-Pirate/webflasher/).
- El catálogo se cachea 30 min en `localStorage` para no agotar el límite de la API de GitHub.
- Requiere Chrome / Edge / Opera de escritorio y servir por HTTPS o `localhost`.
- **WiFi Monitor** vive como ejemplo local en `assets/firmware/` mientras no tenga repo propio.

## Cómo agregar contenido

- **Proyecto nuevo:** duplica un `<article class="card">` en `proyectos.html` (y opcional en el
  preview de `index.html`).
- **Tienda:** `tienda.html` ya está lista para cuando abras la store. Cada tarjeta de producto
  usa `<span class="buy soon">Comprar · pronto</span>`; para activarla, cámbiala por un enlace
  real: `<a class="buy" href="URL-del-producto">Comprar $XXX</a>` y añade el precio con
  `<span class="price">$XXX</span>` en el `card__foot`.
- **Post nuevo (con la herramienta):**
  ```bash
  python3 tools/lab217.py new "Mi título"   # crea posts/src/AAAA-MM-DD-mi-titulo.md
  # edita ese .md en Markdown
  python3 tools/lab217.py build             # genera el HTML y actualiza los índices
  python3 tools/lab217.py serve             # previsualiza en http://localhost:8217
  ```
  Cuando estés conforme, publica (esto **no** hace push, sólo prepara el commit):
  ```bash
  python3 tools/lab217.py publish -m "nuevo post"
  git push origin main                      # SÓLO la cuenta dueña; aquí se hace público
  ```
  Transparente y seguro: todo son archivos + git, y nada llega a internet hasta que
  la cuenta con permisos hace el `git push` a mano.
- **Firmware nuevo:** publica el release oficial en GitHub siguiendo la convención de la sección
  *Flasher de firmware* (más arriba). La tarjeta aparece sola en `flasher.html`; no hay que
  tocar la página.
