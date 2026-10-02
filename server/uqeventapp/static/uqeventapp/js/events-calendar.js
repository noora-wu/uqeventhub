/**
 * Discover calendar on events.html — month grid, offcanvas day panel.
 * Depends on Bootstrap 5 (Offcanvas). Load after bootstrap.bundle.min.js.
 */
(function () {
  var eventsDataEl = document.getElementById("uq-calendar-events-data");
  var EVENTS = [];
  if (eventsDataEl) {
    try {
      var parsed = JSON.parse(eventsDataEl.textContent || "[]");
      if (Array.isArray(parsed)) {
        EVENTS = parsed;
      }
    } catch (err) {
      EVENTS = [];
    }
  }

  var byDate = {};
  EVENTS.forEach(function (ev) {
    if (!byDate[ev.date]) byDate[ev.date] = [];
    byDate[ev.date].push(ev);
  });
  var grid = document.getElementById("uqCalGrid");
  var label = document.getElementById("uqCalMonthLabel");
  var btnPrev = document.getElementById("uqCalPrev");
  var btnNext = document.getElementById("uqCalNext");
  if (!grid || !label || !btnPrev || !btnNext) return;
  var shell = document.querySelector(".uq-cal-shell[data-cal-year][data-cal-month]");
  var y;
  var m;
  if (shell && shell.dataset.calYear && shell.dataset.calMonth) {
    y = parseInt(shell.dataset.calYear, 10);
    m = parseInt(shell.dataset.calMonth, 10) - 1;
  }
  if (typeof y !== "number" || typeof m !== "number" || isNaN(y) || isNaN(m) || m < 0 || m > 11) {
    var fallback = new Date();
    y = fallback.getFullYear();
    m = fallback.getMonth();
  }
  var monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  var offcanvasEl = document.getElementById("uqCalOffcanvas");
  var offTitle = document.getElementById("uqCalOffcanvasLabel");
  var offBody = document.getElementById("uqCalOffcanvasBody");
  var offcanvas = offcanvasEl && typeof bootstrap !== "undefined" ? new bootstrap.Offcanvas(offcanvasEl) : null;

  function pad(n) {
    return (n < 10 ? "0" : "") + n;
  }
  function iso(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }
  function longDate(isoStr) {
    var p = isoStr.split("-");
    var d = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
    return d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  }
  function openPanel(isoStr, list) {
    if (!offcanvas || !offTitle || !offBody) return;
    offTitle.textContent = longDate(isoStr);
    offBody.innerHTML = list
      .map(function (ev) {
        if (ev.href) {
          return (
            '<div class="border-bottom pb-3 mb-3">' +
            '<p class="fw-semibold mb-2">' +
            ev.title +
            "</p>" +
            '<p class="small text-secondary mb-2">Full event page with sessions and registration.</p>' +
            '<a class="btn btn-uq-gold w-100" href="' +
            ev.href +
            '">View event details</a></div>'
          );
        }
        return (
          '<div class="border-bottom pb-3 mb-3">' +
          '<p class="fw-semibold mb-1">' +
          ev.title +
          '</p><p class="small text-secondary mb-2">This event does not have a public detail link yet.</p>' +
          '<button type="button" class="btn btn-secondary w-100" disabled aria-disabled="true">View event details</button></div>'
        );
      })
      .join("");
    offcanvas.show();
  }
  function render() {
    label.textContent = monthNames[m] + " " + y;
    var first = new Date(y, m, 1);
    var startOffset = (first.getDay() + 6) % 7;
    var gridStart = new Date(y, m, 1 - startOffset);
    var html = "";
    var todayIso = iso(new Date());
    for (var i = 0; i < 42; i++) {
      var d = new Date(gridStart);
      d.setDate(gridStart.getDate() + i);
      var inMonth = d.getMonth() === m;
      var key = iso(d);
      var list = byDate[key] || [];
      var has = list.length > 0;
      var detail = list.some(function (e) {
        return e.href;
      });
      var classes = "uq-cal-day";
      if (!inMonth) classes += " uq-cal-day--outside";
      if (has) classes += detail ? " uq-cal-day--detail" : " uq-cal-day--listing";
      if (key === todayIso) classes += " uq-cal-day--today";
      var dayNum = d.getDate();
      if (list.length === 1 && list[0].href) {
        html +=
          '<a class="' +
          classes +
          '" role="gridcell" href="' +
          list[0].href +
          '"><span class="uq-cal-day__num">' +
          dayNum +
          '</span><span class="uq-cal-day__title">' +
          list[0].title +
          '</span><span class="uq-cal-day__go" aria-hidden="true"><i class="bi bi-arrow-up-right"></i></span></a>';
      } else if (has) {
        html +=
          '<button type="button" class="' +
          classes +
          '" role="gridcell" data-iso="' +
          key +
          '" aria-label="' +
          list.length +
          ' events this day, open schedule"><span class="uq-cal-day__num">' +
          dayNum +
          '</span><span class="uq-cal-day__dots">';
        list.forEach(function () {
          html += '<span class="uq-cal-dot"></span>';
        });
        html += '</span><span class="uq-cal-day__hint small">' + list.length + " event" + (list.length > 1 ? "s" : "") + "</span></button>";
      } else {
        html += '<div class="' + classes + '" role="gridcell"><span class="uq-cal-day__num">' + dayNum + "</span></div>";
      }
    }
    grid.innerHTML = html;
    grid.querySelectorAll("button.uq-cal-day[data-iso]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var k = btn.getAttribute("data-iso");
        openPanel(k, byDate[k] || []);
      });
    });
  }
  btnPrev.addEventListener("click", function () {
    m--;
    if (m < 0) {
      m = 11;
      y--;
    }
    render();
  });
  btnNext.addEventListener("click", function () {
    m++;
    if (m > 11) {
      m = 0;
      y++;
    }
    render();
  });
  render();
})();
