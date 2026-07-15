/* ============================================================
   MASAGI Digital — landing page behavior
   Carousel · dark/light mode · EN/ID · navbar · reveal · form
   ============================================================ */
(function () {
  "use strict";

  /* ---------- dark / light mode (persisted) ---------- */
  var themeBtn = document.getElementById("themeBtn");

  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    themeBtn.textContent = t === "dark" ? "☀" : "☾";
    try { localStorage.setItem("masagi-theme", t); } catch (e) {}
  }
  themeBtn.addEventListener("click", function () {
    applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });

  var savedTheme = null;
  try { savedTheme = localStorage.getItem("masagi-theme"); } catch (e) {}
  applyTheme(savedTheme ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));

  /* ---------- EN / ID language (persisted) ---------- */
  function applyLang(lang) {
    if (!TRANSLATIONS[lang]) lang = "en";
    var dict = TRANSLATIONS[lang];
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (dict[key] !== undefined) el.innerHTML = dict[key];
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-ph");
      if (dict[key] !== undefined) el.setAttribute("placeholder", dict[key]);
    });
    document.querySelectorAll(".lang-btn").forEach(function (b) {
      b.classList.toggle("on", b.getAttribute("data-lang") === lang);
    });
    try { localStorage.setItem("masagi-lang", lang); } catch (e) {}
  }
  document.querySelectorAll(".lang-btn").forEach(function (b) {
    b.addEventListener("click", function () { applyLang(b.getAttribute("data-lang")); });
  });

  var savedLang = null;
  try { savedLang = localStorage.getItem("masagi-lang"); } catch (e) {}
  applyLang(savedLang ||
    ((navigator.language || "").toLowerCase().indexOf("id") === 0 ? "id" : "en"));

  /* ---------- hero carousel (Swiper) ---------- */
  new Swiper(".hero-swiper", {
    loop: true,
    speed: 700,
    autoplay: { delay: 5000, disableOnInteraction: false },
    pagination: { el: ".swiper-pagination", clickable: true },
    navigation: { nextEl: ".swiper-button-next", prevEl: ".swiper-button-prev" },
    keyboard: { enabled: true },
  });

  /* ---------- navbar: transparent over hero → solid on scroll ---------- */
  var navbar = document.getElementById("navbar");
  function onScroll() {
    navbar.classList.toggle("scrolled", window.scrollY > 40);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- mobile hamburger menu ---------- */
  var hamburger = document.getElementById("hamburger");
  var menu = document.getElementById("menu");
  hamburger.addEventListener("click", function () {
    var open = menu.classList.toggle("mobile-open");
    hamburger.classList.toggle("open", open);
    hamburger.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) navbar.classList.add("scrolled");   /* readable menu over the hero */
    else onScroll();
  });
  /* close the mobile menu after tapping a link */
  menu.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () {
      menu.classList.remove("mobile-open");
      hamburger.classList.remove("open");
      hamburger.setAttribute("aria-expanded", "false");
      onScroll();
    });
  });

  /* ---------- scroll-reveal animations ---------- */
  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    document.querySelectorAll(".reveal").forEach(function (el) { observer.observe(el); });
  } else {
    /* no observer support -> never hide content */
    document.querySelectorAll(".reveal").forEach(function (el) { el.classList.add("visible"); });
  }

  /* ---------- contact form → pre-filled email ---------- */
  document.getElementById("contactForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var name = document.getElementById("fName").value.trim();
    var email = document.getElementById("fEmail").value.trim();
    var company = document.getElementById("fCompany").value.trim();
    var msg = document.getElementById("fMsg").value.trim();
    if (!name || !email || !msg) return;
    var subject = "MASAGI Digital — inquiry from " + name + (company ? " (" + company + ")" : "");
    var body = msg + "\n\n—\n" + name + (company ? "\n" + company : "") + "\n" + email;
    window.location.href = "mailto:samudra@masagi.io?subject=" +
      encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
  });
})();
