/* LAB217 — interacciones base compartidas por todas las páginas */
(function () {
  // Año dinámico en el footer
  var y = document.getElementById("y");
  if (y) y.textContent = new Date().getFullYear();

  // Menú móvil
  var burger = document.getElementById("burger");
  var menu = document.getElementById("menu");
  if (burger && menu) {
    var closeMenu = function () {
      menu.classList.remove("open");
      burger.setAttribute("aria-expanded", "false");
      burger.textContent = "[ menú ]";
    };
    burger.addEventListener("click", function () {
      var open = menu.classList.toggle("open");
      burger.setAttribute("aria-expanded", open ? "true" : "false");
      burger.textContent = open ? "[ cerrar ]" : "[ menú ]";
    });
    // Cerrar al navegar
    menu.addEventListener("click", function (e) {
      if (e.target.tagName === "A") closeMenu();
    });
    // Cerrar con Escape y devolver el foco al botón
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && menu.classList.contains("open")) {
        closeMenu();
        burger.focus();
      }
    });
  }

  // Marca la sección/página activa en el nav
  var path = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav__links a").forEach(function (a) {
    var href = a.getAttribute("href") || "";
    if (href === path) a.setAttribute("aria-current", "page");
  });
})();
