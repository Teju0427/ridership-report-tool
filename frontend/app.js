// FRONTEND LOGIC
// The browser calls our API with fetch(), gets JSON back, and updates the page.
// Flow:  page loads -> loadOptions() -> loadDashboard() -> draw KPIs/charts

const $ = (id) => document.getElementById(id);
const charts = {};            // keep chart objects so we can destroy & redraw them
const fmt = (n) => (n ?? 0).toLocaleString();

// ---------- helpers ----------
async function api(url, options) {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

function currentFilters() {
  const p = new URLSearchParams();
  if ($("start").value) p.set("start", $("start").value);
  if ($("end").value) p.set("end", $("end").value);
  if ($("line").value) p.set("line", $("line").value);
  return p.toString();
}

// ---------- 1. filter options ----------
async function loadOptions() {
  const opt = await api("/api/options");
  const select = $("line");
  select.length = 1;                     // keep "All lines", remove the rest
  opt.lines.forEach((l) => select.add(new Option(l, l)));

  if (opt.max_date) {
    // default view = last 31 days of available data
    const end = new Date(opt.max_date);
    const start = new Date(end); start.setDate(end.getDate() - 30);
    const iso = (d) => d.toISOString().slice(0, 10);
    $("start").value = iso(start) < opt.min_date ? opt.min_date : iso(start);
    $("end").value = opt.max_date;
  }
}

// ---------- 2. dashboard ----------
async function loadDashboard() {
  try {
    const d = await api(`/api/dashboard?${currentFilters()}`);
    const s = d.summary;
    $("k-total").textContent = fmt(s.total);
    $("k-avg").textContent = fmt(s.avg_daily);
    $("k-station").textContent = s.busiest_station ?? "–";
    $("k-peak").textContent = s.peak_hour != null ? `${String(s.peak_hour).padStart(2, "0")}:00` : "–";
    const ch = $("k-change");
    ch.textContent = s.change_pct != null ? `${s.change_pct > 0 ? "▲" : "▼"} ${Math.abs(s.change_pct)}%` : "–";
    ch.className = s.change_pct > 0 ? "ok" : s.change_pct < 0 ? "err" : "";

    const ul = $("insights");
    ul.innerHTML = "";
    d.insights.forEach((t) => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });

    draw("c-daily", "line", d.daily.map((r) => r.date), d.daily.map((r) => r.passengers), "Passengers");
    draw("c-station", "bar", d.stations.map((r) => r.station), d.stations.map((r) => r.passengers), "Passengers", true);
    draw("c-hour", "bar", d.hours.map((r) => `${r.hour}:00`), d.hours.map((r) => r.avg_passengers), "Avg passengers");

    $("download").href = `/api/report.xlsx?${currentFilters()}`;
  } catch (e) {
    alert(e.message);
  }
}

function draw(id, type, labels, values, label, horizontal = false) {
  charts[id]?.destroy();               // remove old chart before drawing new one
  charts[id] = new Chart($(id), {
    type,
    data: { labels, datasets: [{ label, data: values, backgroundColor: "#1f4e79", borderColor: "#1f4e79", pointRadius: 0, tension: 0.25 }] },
    options: {
      indexAxis: horizontal ? "y" : "x",
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { [horizontal ? "x" : "y"]: { beginAtZero: true } },
    },
  });
}

// ---------- 3. upload ----------
$("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();                  // stop the browser reloading the page
  const out = $("upload-result");
  const form = new FormData();
  form.append("file", $("file").files[0]);
  out.textContent = "Uploading...";
  try {
    const r = await api("/api/upload", { method: "POST", body: form });
    out.innerHTML = "";
    const msg = document.createElement("div");
    msg.className = r.rejected_rows ? "err" : "ok";
    msg.textContent = `${r.filename}: ${fmt(r.saved_rows)} rows saved, ${r.rejected_rows} rejected.`;
    out.appendChild(msg);
    if (r.errors.length) {
      const ul = document.createElement("ul");
      r.errors.forEach((er) => { const li = document.createElement("li"); li.textContent = `Row ${er.row}: ${er.reason}`; ul.appendChild(li); });
      out.appendChild(ul);
    }
    await loadOptions();
    await loadDashboard();
  } catch (err) {
    out.innerHTML = "";
    const m = document.createElement("div"); m.className = "err"; m.textContent = err.message; out.appendChild(m);
  }
});

$("reset").addEventListener("click", async () => {
  if (!confirm("Delete ALL ridership data?")) return;
  await api("/api/data", { method: "DELETE" });
  $("upload-result").textContent = "All data cleared.";
  await loadOptions();
  await loadDashboard();
});

$("apply").addEventListener("click", loadDashboard);

// ---------- start ----------
loadOptions().then(loadDashboard);
