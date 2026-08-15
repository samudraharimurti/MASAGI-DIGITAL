/* ============================================================
   MASAGI Digital — landing page behavior
   Carousel · dark/light mode · EN/ID · navbar · reveal · form
   ============================================================ */
(function () {
  "use strict";



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
  var SWIPER_OPTS = {
    loop: true,
    speed: 700,
    autoplay: { delay: 5000, disableOnInteraction: false },
    pagination: { el: ".swiper-pagination", clickable: true },
    navigation: { nextEl: ".swiper-button-next", prevEl: ".swiper-button-prev" },
    keyboard: { enabled: true },
  };
  var heroSwiper = new Swiper(".hero-swiper", SWIPER_OPTS);

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
        if (slide.image) {
          // photo behind a navy overlay so the white slide text stays legible;
          // covers the original slide and its Swiper loop-duplicate(s)
          document.querySelectorAll(".hero-swiper .slide.s" + n).forEach(function (el) {
            el.style.backgroundImage =
              "linear-gradient(130deg, rgba(16,29,56,.82), rgba(27,42,74,.72)), url('" + slide.image + "')";
            el.style.backgroundSize = "cover";
            el.style.backgroundPosition = "center";
          });
        }
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
      if (c.case) {
        mergeLangField("case.eyebrow", c.case, "eyebrow_en", "eyebrow_id");
        mergeLangField("case.heading", c.case, "heading_en", "heading_id");
        mergeLangField("case.sub", c.case, "sub_en", "sub_id");
        mergeLangField("case.role", c.case, "role_en", "role_id");
        mergeLangField("case.org", c.case, "org_en", "org_id");
        mergeLangField("case.link", c.case, "link_en", "link_id");
      }
      if (c.media) {
        mergeLangField("media.eyebrow", c.media, "eyebrow_en", "eyebrow_id");
        mergeLangField("media.title", c.media, "title_en", "title_id");
        mergeLangField("media.lead", c.media, "lead_en", "lead_id");
      }
      applyLang(currentLang); // re-render with the freshly merged copy
    })
    .catch(function () { /* portal unreachable — keep the built-in defaults */ });

  /* ---------- hero slides from the CMS (blog.masagi.io) ----------
     Each slide may carry a picture or a video beside its copy. When the CMS is
     unreachable the three built-in slides above stay exactly as they are. */
  var CMS_BASE = "https://blog.masagi.io";
  function esc(s) {
    return (s == null ? "" : String(s)).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function ytId(u) { var m = u.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|shorts\/))([\w-]{6,})/); return m && m[1]; }
  function vimeoId(u) { var m = u.match(/vimeo\.com\/(?:video\/)?(\d+)/); return m && m[1]; }

  function slideMediaHtml(s) {
    var u = (s.media_url || "").trim();
    if (!u || s.media_type === "none") return "";
    if (s.media_type === "video") {
      var yt = ytId(u), vi = vimeoId(u);
      if (yt) return '<iframe src="https://www.youtube.com/embed/' + esc(yt) +
        '?rel=0" title="MASAGI" allow="encrypted-media; fullscreen" allowfullscreen loading="lazy"></iframe>';
      if (vi) return '<iframe src="https://player.vimeo.com/video/' + esc(vi) +
        '" title="MASAGI" allow="fullscreen" allowfullscreen loading="lazy"></iframe>';
      return '<video controls playsinline preload="metadata"' +
        (s.poster ? ' poster="' + esc(s.poster) + '"' : "") + ' src="' + esc(u) + '"></video>';
    }
    return '<img src="' + esc(u) + '" alt="" loading="lazy">';
  }

  function buildHero(slides) {
    var wrap = document.querySelector(".hero-swiper .swiper-wrapper");
    if (!wrap || !slides.length) return;
    if (heroSwiper && heroSwiper.destroy) heroSwiper.destroy(true, true);
    wrap.innerHTML = slides.map(function (s, i) {
      var k = "hero.cms" + i;
      TRANSLATIONS.en[k + ".eyebrow"] = s.eyebrow_en || "";
      TRANSLATIONS.id[k + ".eyebrow"] = s.eyebrow_id || s.eyebrow_en || "";
      TRANSLATIONS.en[k + ".title"] = s.title_en || "";
      TRANSLATIONS.id[k + ".title"] = s.title_id || s.title_en || "";
      TRANSLATIONS.en[k + ".sub"] = s.sub_en || "";
      TRANSLATIONS.id[k + ".sub"] = s.sub_id || s.sub_en || "";
      TRANSLATIONS.en[k + ".cta"] = s.cta_label_en || "";
      TRANSLATIONS.id[k + ".cta"] = s.cta_label_id || s.cta_label_en || "";
      var media = slideMediaHtml(s);
      var text = '<div class="slide-text">' +
        ((s.eyebrow_en || s.eyebrow_id) ? '<span class="eyebrow" data-i18n="' + k + '.eyebrow"></span>' : "") +
        // only the first slide carries the <h1>; the rest are h2 styled identically,
        // so the page exposes exactly one level-1 heading to assistive tech
        '<' + (i === 0 ? 'h1' : 'h2') + ' class="slide-h" data-i18n="' + k + '.title"></' +
          (i === 0 ? 'h1' : 'h2') + '>' +
        ((s.sub_en || s.sub_id) ? '<p data-i18n="' + k + '.sub"></p>' : "") +
        (((s.cta_label_en || s.cta_label_id) && s.cta_href)
          ? '<div class="cta-row"><a class="btn btn-accent" href="' + esc(s.cta_href) +
            '" data-i18n="' + k + '.cta"></a></div>' : "") + '</div>';
      var inner = media
        ? '<div class="slide-grid' + (s.media_side === "left" ? " media-left" : "") + '">' +
          text + '<div class="slide-media">' + media + "</div></div>"
        : text;
      return '<div class="swiper-slide slide s' + ((i % 3) + 1) + '">' +
        '<div class="slide-inner">' + inner + "</div></div>";
    }).join("");
    heroSwiper = new Swiper(".hero-swiper", SWIPER_OPTS);
    applyLang(currentLang); // fill the data-i18n placeholders (incl. Swiper's loop clones)
  }

  fetchWithTimeout(CMS_BASE + "/api/public/carousel", 6000)
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (c) {
      // The hero IS the carousel now, so whatever the CMS holds drives it
      // directly — there is no static hero left to fall back to.
      var slides = (c && c.slides) || [];
      if (slides.length) buildHero(slides);
    })
    .catch(function () { /* CMS unreachable — keep the built-in hero slides */ });

  /* ---------- Media cards ----------
     Articles come from the CMS (blog.masagi.io). Until that subdomain's DNS is
     live we fall back to the older MASAGI HV feed, and to the three static
     cards in the markup if neither answers — the page always renders. */
  var MEDIA_COVER_CLASSES = ["c1", "c2", "c3"];
  function renderMediaCards(posts) {
    var grid = document.querySelector(".media-grid");
    if (!posts.length || !grid) return;
    grid.innerHTML = posts.map(function (p, i) {
      var base = "media.dyn" + i;
      TRANSLATIONS.en[base + ".tag"] = p.tag_en || "Insight";
      TRANSLATIONS.id[base + ".tag"] = p.tag_id || p.tag_en || "Wawasan";
      TRANSLATIONS.en[base + ".title"] = p.title_en || "";
      TRANSLATIONS.id[base + ".title"] = p.title_id || p.title_en || "";
      TRANSLATIONS.en[base + ".excerpt"] = p.excerpt_en || "";
      TRANSLATIONS.id[base + ".excerpt"] = p.excerpt_id || p.excerpt_en || "";
      var cover = p.image ? ' style="background-image:url(\'' + esc(p.image) + '\')"' : "";
      var coverClass = p.image ? "" : MEDIA_COVER_CLASSES[i % 3];
      return '<a class="m-card reveal visible" href="' + esc(p.url) + '" target="_blank" rel="noopener">' +
        '<div class="m-cover ' + coverClass + '"' + cover + "></div>" +
        '<div class="m-body"><div class="m-meta"><span class="tag" data-i18n="' + base + '.tag"></span>' +
        "<span>" + esc(p.date || "") + "</span></div>" +
        '<h3 data-i18n="' + base + '.title"></h3>' +
        '<p data-i18n="' + base + '.excerpt"></p>' +
        '<span class="m-read" data-i18n="media.read"></span></div></a>';
    }).join("");
    applyLang(currentLang); // fill in the data-i18n placeholders just inserted
  }

  function loadMediaFromHv() {
    fetchWithTimeout("https://hv.masagi.io/api/site-content", 6000)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (c) {
        renderMediaCards(((c && c.insights) || []).slice(0, 3).map(function (p) {
          return {
            url: "https://hv.masagi.io/blog/" + encodeURIComponent(p.slug || ""),
            tag_en: p.tag, tag_id: p.tag, title_en: p.title, title_id: p.title_id,
            excerpt_en: p.excerpt, excerpt_id: p.excerpt_id, date: p.date, image: p.image,
          };
        }));
      })
      .catch(function () { /* neither feed answered — the static cards stay */ });
  }

  fetchWithTimeout(CMS_BASE + "/api/public/posts?limit=3", 6000)
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (c) {
      var posts = (c && c.posts) || [];
      if (!posts.length) { loadMediaFromHv(); return; }
      renderMediaCards(posts.map(function (p) {
        return {
          url: p.url, tag_en: p.type_label_en, tag_id: p.type_label_id,
          title_en: p.title_en, title_id: p.title_id,
          excerpt_en: p.excerpt_en, excerpt_id: p.excerpt_id,
          date: p.published_at, image: p.cover_image,
        };
      }));
    })
    .catch(loadMediaFromHv);

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
