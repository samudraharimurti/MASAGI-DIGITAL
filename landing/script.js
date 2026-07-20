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
  var currentLang = "en";
  function applyLang(lang) {
    if (!TRANSLATIONS[lang]) lang = "en";
    currentLang = lang;
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

  /* ---------- live content: portal CMS (hero/about/services/contact) +
     HV insights (Media cards). The hardcoded copy above is the fallback —
     used as-is if either fetch fails, is slow, or the account/HV is down,
     so the page never depends on another service to render correctly. ---- */
  function fetchWithTimeout(url, ms) {
    var ctrl = ("AbortController" in window) ? new AbortController() : null;
    var id = ctrl && setTimeout(function () { ctrl.abort(); }, ms);
    return fetch(url, ctrl ? { signal: ctrl.signal } : {}).finally(function () {
      if (id) clearTimeout(id);
    });
  }
  function mergeLangField(key, obj, enField, idField) {
    if (obj[enField]) TRANSLATIONS.en[key] = obj[enField];
    if (obj[idField]) TRANSLATIONS.id[key] = obj[idField];
  }

  fetchWithTimeout("https://account.masagi.io/api/public/landing-content", 6000)
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (c) {
      if (!c) return;
      (c.hero || []).slice(0, 3).forEach(function (slide, i) {
        var n = i + 1;
        mergeLangField("hero.s" + n + ".eyebrow", slide, "eyebrow_en", "eyebrow_id");
        mergeLangField("hero.s" + n + ".title", slide, "title_en", "title_id");
        mergeLangField("hero.s" + n + ".sub", slide, "sub_en", "sub_id");
      });
      if (c.about) {
        mergeLangField("about.lead", c.about, "lead_en", "lead_id");
        mergeLangField("about.mission.text", c.about, "mission_en", "mission_id");
        mergeLangField("about.vision.text", c.about, "vision_en", "vision_id");
      }
      if (c.services) {
        mergeLangField("services.hv.desc", c.services, "hv_desc_en", "hv_desc_id");
        mergeLangField("services.crom.desc", c.services, "crom_desc_en", "crom_desc_id");
      }
      if (c.contact) {
        mergeLangField("contact.hq.value", c.contact, "hq_en", "hq_id");
        mergeLangField("contact.hours.value", c.contact, "hours_en", "hours_id");
        if (c.contact.email) {
          var link = document.getElementById("contactEmailLink");
          if (link) { link.href = "mailto:" + c.contact.email; link.textContent = c.contact.email; }
        }
      }
      applyLang(currentLang); // re-render with the freshly merged copy
    })
    .catch(function () { /* portal unreachable — keep the built-in defaults */ });

  /* Media cards: pull real insight articles from MASAGI HV's own CMS, so the
     landing page always shows (and links to) whatever is actually published
     there, instead of maintaining a second copy of the same content. */
  var MEDIA_COVER_CLASSES = ["c1", "c2", "c3"];
  fetchWithTimeout("https://hv.masagi.io/api/site-content", 6000)
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (c) {
      var posts = ((c && c.insights) || []).slice(0, 3);
      var grid = document.querySelector(".media-grid");
      if (!posts.length || !grid) return;
      grid.innerHTML = posts.map(function (p, i) {
        var base = "media.dyn" + i;
        TRANSLATIONS.en[base + ".tag"] = p.tag || "Insight";
        TRANSLATIONS.id[base + ".tag"] = p.tag || "Wawasan";
        TRANSLATIONS.en[base + ".title"] = p.title || "";
        TRANSLATIONS.id[base + ".title"] = p.title_id || p.title || "";
        TRANSLATIONS.en[base + ".excerpt"] = p.excerpt || "";
        TRANSLATIONS.id[base + ".excerpt"] = p.excerpt_id || p.excerpt || "";
        var cover = p.image ? ' style="background-image:url(\'' + p.image + '\')"' : "";
        var coverClass = p.image ? "" : MEDIA_COVER_CLASSES[i % 3];
        return '<a class="m-card reveal visible" href="https://hv.masagi.io/blog/' +
          encodeURIComponent(p.slug || "") + '" target="_blank" rel="noopener">' +
          '<div class="m-cover ' + coverClass + '"' + cover + '></div>' +
          '<div class="m-body"><div class="m-meta"><span class="tag" data-i18n="' + base + '.tag"></span>' +
          '<span>' + (p.date || "") + '</span></div>' +
          '<h3 data-i18n="' + base + '.title"></h3>' +
          '<p data-i18n="' + base + '.excerpt"></p>' +
          '<span class="m-read" data-i18n="media.read"></span></div></a>';
      }).join("");
      applyLang(currentLang); // fill in the data-i18n placeholders just inserted
    })
    .catch(function () { /* HV unreachable — keep the 3 static demo cards */ });

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
