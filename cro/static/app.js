// MASAGI CROM - theme toggle, confirms, invoice line-item editor.
(function () {
  "use strict";

  // Theme toggle (attribute set pre-paint by inline script in <head>)
  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", cur);
      localStorage.setItem("theme", cur);
    });
  }

  // Confirm dialogs on forms with data-confirm
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  // Auto-hide success flashes
  setTimeout(function () {
    document.querySelectorAll(".flash-ok").forEach(function (el) {
      el.style.transition = "opacity .6s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 700);
    });
  }, 4000);

  // ---- Invoice editor ----
  var form = document.getElementById("invoice-form");
  if (!form) return;

  var table = document.getElementById("items-table").querySelector("tbody");
  var taxInput = document.getElementById("inv-tax");
  var taxMode = document.getElementById("inv-taxmode");
  var taxRow = document.getElementById("pv-tax-row");
  var taxLabel = document.getElementById("pv-tax-label");

  function rp(n) { return "Rp " + Math.round(n).toLocaleString("id-ID"); }

  function recalc() {
    var subtotal = 0;
    table.querySelectorAll(".item-row").forEach(function (row) {
      var qty = parseFloat(row.querySelector(".qty").value) || 0;
      var price = parseFloat(row.querySelector(".price").value) || 0;
      var tot = qty * price;
      row.querySelector(".row-total").textContent = rp(tot);
      subtotal += tot;
    });
    var mode = taxMode ? taxMode.value : "PPh";
    var taxPct = mode === "NONE" ? 0 : (parseFloat(taxInput.value) || 0);
    var tax = subtotal * taxPct / 100;
    // PPh is withheld (subtracted); PPN is added; NONE leaves the subtotal unchanged.
    var total = mode === "PPN" ? subtotal + tax : mode === "PPh" ? subtotal - tax : subtotal;
    if (taxRow) taxRow.style.display = mode === "NONE" ? "none" : "";
    if (taxLabel && taxMode) taxLabel.textContent = taxMode.options[taxMode.selectedIndex].text;
    document.getElementById("pv-sub").textContent = rp(subtotal);
    document.getElementById("pv-tax").textContent =
      (mode === "PPh" ? "- " : mode === "PPN" ? "+ " : "") + rp(tax);
    document.getElementById("pv-total").textContent = rp(total);
  }

  function bindRow(row) {
    row.querySelectorAll("input").forEach(function (inp) {
      inp.addEventListener("input", recalc);
    });
    row.querySelector(".remove-row").addEventListener("click", function () {
      if (table.querySelectorAll(".item-row").length > 1) {
        row.remove();
        recalc();
      }
    });
  }

  document.getElementById("add-row").addEventListener("click", function () {
    var first = table.querySelector(".item-row");
    var clone = first.cloneNode(true);
    clone.querySelectorAll("input").forEach(function (inp) {
      inp.value = inp.classList.contains("qty") ? "1" : inp.classList.contains("price") ? "0" : "";
    });
    clone.querySelector(".row-total").textContent = "Rp 0";
    table.appendChild(clone);
    bindRow(clone);
    recalc();
  });

  table.querySelectorAll(".item-row").forEach(bindRow);
  taxInput.addEventListener("input", recalc);
  if (taxMode) {
    taxMode.addEventListener("change", function () {
      var m = taxMode.value;
      if (m === "PPN") taxInput.value = taxMode.getAttribute("data-ppn") || taxInput.value;
      else if (m === "PPh") taxInput.value = taxMode.getAttribute("data-pph") || taxInput.value;
      taxInput.disabled = (m === "NONE");
      recalc();
    });
  }
  recalc();

  // Filter submissions by selected client
  var clientSel = document.getElementById("inv-client");
  var subSel = document.getElementById("inv-sub");
  function filterSubs() {
    var cid = clientSel.value;
    var selectedVisible = false;
    Array.prototype.forEach.call(subSel.options, function (opt) {
      if (!opt.value) return;
      var show = !cid || opt.getAttribute("data-client") === cid;
      opt.hidden = !show;
      if (opt.selected && show) selectedVisible = true;
      if (opt.selected && !show) opt.selected = false;
    });
    if (!selectedVisible && !subSel.value) subSel.selectedIndex = 0;
  }
  clientSel.addEventListener("change", filterSubs);
  filterSubs();
})();
