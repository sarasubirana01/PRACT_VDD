from pathlib import Path
import json
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parents[1]
CSV  = BASE / "data" / "spotify.csv"

OUT_SAMPLE = BASE / "data" / "sample.json"
OUT_GENRES = BASE / "data" / "genre_stats.json"
OUT_CORR   = BASE / "data" / "corr.json"
OUT_HTML   = BASE / "index.html"

NUM_COLS = [
    "popularity","danceability","energy","valence","tempo",
    "acousticness","speechiness","instrumentalness","liveness"
]

FEATURES = ["danceability","energy","valence","tempo","acousticness","speechiness","instrumentalness","liveness"]

def main():
    print("📥 Llegint dataset...")
    df = pd.read_csv(CSV)

    needed = NUM_COLS + ["track_genre","track_name","artists"]
    df = df.dropna(subset=needed).copy()

    # Tipos
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=NUM_COLS + ["track_genre"])

    # Muestra para scatter (para que sea rápido y no sea “mancha negra”)
    n_sample = min(25000, len(df))
    sample = df.sample(n=n_sample, random_state=42)[
        ["track_name","artists","track_genre","popularity","valence","energy"] + FEATURES
    ].copy()

    # Guardar sample.json (lista de dicts)
    OUT_SAMPLE.write_text(json.dumps(sample.to_dict(orient="records"), ensure_ascii=False), encoding="utf-8")

    print(f"✅ sample.json ({n_sample:,} filas)")

    # Stats por género (para bar + storytelling)
    g = df.groupby("track_genre").agg(
        n=("track_genre","size"),
        popularity_mean=("popularity","mean"),
        valence_mean=("valence","mean"),
        energy_mean=("energy","mean")
    ).reset_index()

    # ordenar por popularidad media
    g = g.sort_values("popularity_mean", ascending=False)
    OUT_GENRES.write_text(json.dumps(g.to_dict(orient="records"), ensure_ascii=False), encoding="utf-8")
    print("✅ genre_stats.json")

    # Matriz de correlación (features)
    corr = df[FEATURES + ["popularity"]].corr(numeric_only=True).round(3)
    OUT_CORR.write_text(json.dumps({
        "cols": corr.columns.tolist(),
        "matrix": corr.values.tolist()
    }, ensure_ascii=False), encoding="utf-8")
    print("✅ corr.json")

    # Generar index.html (dashboard + controles + storytelling)
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print(f"✅ index.html generat a: {OUT_HTML}")

def build_html():
    # HTML + JS: carga JSONs y renderiza con Plotly.js
    return """<!doctype html>
<html lang="ca">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Spotify: Emocionalitat i Popularitat</title>

  <script src="https://cdn.plot.ly/plotly-3.3.1.min.js"></script>

  <style>
    :root { --border:#e8e8e8; --muted:#666; --bg:#fff; --text:#111; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin:0; background:var(--bg); color:var(--text); }
    header { padding:18px 20px; border-bottom:1px solid #eee; }
    h1 { margin:0 0 6px; font-size:20px; }
    header p { margin:0; color:#555; font-size:13px; line-height:1.35; }

    main { padding:16px 20px 26px; }
    .row { display:flex; gap:12px; flex-wrap:wrap; align-items:flex-end; margin-bottom:12px; }
    .ctl { display:flex; flex-direction:column; gap:6px; }
    label { font-size:12px; color:#333; }
    select, input[type="range"], input[type="number"] { font-size:13px; padding:6px 8px; border:1px solid var(--border); border-radius:10px; }
    .small { font-size:12px; color:var(--muted); }

    .story { border:1px solid var(--border); border-radius:12px; padding:12px 14px; margin-bottom:14px; }
    .story h2 { margin:0 0 6px; font-size:15px; }
    .story ul { margin:8px 0 0; padding-left:18px; }
    .story li { margin:6px 0; font-size:13px; line-height:1.35; }

    .grid { display:grid; grid-template-columns: 1.15fr 0.85fr; gap:14px; }
    .card { border:1px solid var(--border); border-radius:12px; padding:10px; background:#fff; }
    .card h2 { margin:4px 6px 10px; font-size:14px; }
    .plot { width:100%; height:460px; }
    #plot_scatter { height:560px; }

    @media (max-width:1100px){ .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Spotify: Emocionalitat i Popularitat</h1>
    <p>Dashboard interactiu per explorar com varien emoció (valence/energy), gènere i popularitat. Filtra i compara per descobrir patrons.</p>
  </header>

  <main>
    <div class="row">
      <div class="ctl">
        <label>Gènere (multi)</label>
        <select id="genreSelect" multiple size="6" style="min-width:260px;"></select>
        <span class="small">Ctrl (Windows) / ⌘ (Mac) per seleccionar múltiples.</span>
      </div>

      <div class="ctl" style="min-width:240px;">
        <label>Popularitat mínima: <span id="popVal">50</span></label>
        <input id="popSlider" type="range" min="0" max="100" step="1" value="50"/>
      </div>

      <div class="ctl">
        <label>Top N gèneres (si no selecciones manualment)</label>
        <input id="topN" type="number" min="5" max="50" value="15"/>
      </div>

      <div class="ctl">
        <button id="btnClear" style="padding:8px 10px; border:1px solid var(--border); border-radius:12px; background:#fff; cursor:pointer;">
          Netejar selecció
        </button>
      </div>
    </div>

    <div class="story">
      <h2>Història en 4 idees (amb els teus filtres)</h2>
      <ul>
        <li id="s1"></li>
        <li id="s2"></li>
        <li id="s3"></li>
        <li id="s4"></li>
      </ul>
      <div class="small" style="margin-top:8px;">
        Tip: passa el ratolí pels punts per veure track, artista i valors.
      </div>
    </div>

    <div class="card">
      <h2>1) Mapa emocional: valence vs energy</h2>
      <div id="plot_scatter" class="plot"></div>
    </div>

    <div class="grid" style="margin-top:14px;">
      <div class="card">
        <h2>2) Distribució de valence per gènere (comparació real)</h2>
        <div id="plot_valence_box" class="plot"></div>
      </div>

      <div class="card">
        <h2>3) Top gèneres per popularitat mitjana</h2>
        <div id="plot_top_genres" class="plot"></div>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h2>4) Heatmap de correlacions (features vs popularitat i entre features)</h2>
      <div id="plot_corr" class="plot" style="height:520px;"></div>
    </div>
  </main>

<script>
let SAMPLE = [];
let GENRES = [];
let CORR = null;

const genreSelect = document.getElementById("genreSelect");
const popSlider = document.getElementById("popSlider");
const popVal = document.getElementById("popVal");
const topN = document.getElementById("topN");

function selectedGenres(){
  return Array.from(genreSelect.selectedOptions).map(o => o.value);
}

function topGenresByPopularity(n){
  return GENRES
    .slice()
    .sort((a,b)=> b.popularity_mean - a.popularity_mean)
    .slice(0,n)
    .map(d => d.track_genre);
}

function filterRows(){
  const minPop = Number(popSlider.value);
  const sel = selectedGenres();
  const allowed = (sel.length > 0) ? sel : topGenresByPopularity(Number(topN.value || 15));

  const rows = SAMPLE.filter(r => r.popularity >= minPop && allowed.includes(r.track_genre));
  return { rows, allowed };
}

function renderScatter(rows){
  const trace = {
    type: "scattergl",
    mode: "markers",
    x: rows.map(r=>r.valence),
    y: rows.map(r=>r.energy),
    text: rows.map(r=>`${r.track_name} — ${r.artists}`),
    customdata: rows.map(r=>[r.track_genre, r.popularity]),
    hovertemplate:
      "<b>%{text}</b><br>" +
      "Gènere: %{customdata[0]}<br>" +
      "Popularitat: %{customdata[1]}<br>" +
      "Valence: %{x:.3f}<br>" +
      "Energy: %{y:.3f}<extra></extra>",
    marker: { size: rows.map(r=>Math.max(4, Math.min(18, r.popularity/4))), opacity: 0.45 }
  };

  const layout = {
    margin:{l:50,r:20,t:10,b:50},
    xaxis:{title:"Valence (positivitat)", range:[0,1]},
    yaxis:{title:"Energy (intensitat)", range:[0,1]},
    height: 560
  };

  Plotly.react("plot_scatter", [trace], layout, {displayModeBar:false});
}

function renderValenceBox(rows, allowed){
  // box por género
  const traces = allowed.map(g => {
    const vals = rows.filter(r=>r.track_genre===g).map(r=>r.valence);
    return { type:"box", name:g, y:vals, boxpoints:false };
  });

  const layout = {
    margin:{l:50,r:20,t:10,b:120},
    yaxis:{title:"Valence"},
    height: 460
  };
  Plotly.react("plot_valence_box", traces, layout, {displayModeBar:false});
}

function renderTopGenres(minPop){
  const stats = GENRES
    .filter(d => d.n > 50) // evita gèneres amb poques cançons
    .sort((a,b)=> b.popularity_mean - a.popularity_mean)
    .slice(0, 15);

  const trace = {
    type:"bar",
    x: stats.map(d=>d.track_genre),
    y: stats.map(d=>d.popularity_mean),
  };

  const layout = {
    margin:{l:50,r:20,t:10,b:120},
    yaxis:{title:"Popularitat mitjana"},
    height: 460
  };

  Plotly.react("plot_top_genres", [trace], layout, {displayModeBar:false});
}

function renderCorr(){
  const cols = CORR.cols;
  const z = CORR.matrix;

  const trace = {
    type: "heatmap",
    x: cols,
    y: cols,
    z: z,
    zmin: -1, zmax: 1,
    hovertemplate: "%{y} vs %{x}<br>r=%{z:.3f}<extra></extra>"
  };

  const layout = {
    margin:{l:120,r:20,t:10,b:120},
    height: 520
  };

  Plotly.react("plot_corr", [trace], layout, {displayModeBar:false});
}

function renderStory(rows, allowed){
  const n = rows.length;
  const avgPop = n ? (rows.reduce((s,r)=>s+r.popularity,0)/n) : 0;

  // género más “feliz” por valence media
  const byG = {};
  for (const g of allowed) byG[g] = {sumV:0,sumE:0,c:0,sumP:0};
  for (const r of rows){
    const o = byG[r.track_genre];
    if (!o) continue;
    o.sumV += r.valence; o.sumE += r.energy; o.sumP += r.popularity; o.c += 1;
  }
  const arr = Object.entries(byG)
    .filter(([g,o])=>o.c>0)
    .map(([g,o])=>({g, v:o.sumV/o.c, e:o.sumE/o.c, p:o.sumP/o.c, c:o.c}))
    .sort((a,b)=> b.p - a.p);

  const topByPop = arr.slice(0,3).map(d=>`${d.g} (${d.p.toFixed(1)})`).join(", ");
  const happiest = arr.slice().sort((a,b)=>b.v-a.v)[0];
  const intense  = arr.slice().sort((a,b)=>b.e-a.e)[0];

  document.getElementById("s1").textContent = `Mostra actual: ${n.toLocaleString()} cançons (popularitat mitjana ${avgPop.toFixed(1)}).`;
  document.getElementById("s2").textContent = `Top gèneres per popularitat mitjana (dins la selecció): ${topByPop || "—"}.`;
  document.getElementById("s3").textContent = happiest ? `Gènere més “optimista” (valence mitjana): ${happiest.g} (${happiest.v.toFixed(2)}).` : "—";
  document.getElementById("s4").textContent = intense ? `Gènere més intens (energy mitjana): ${intense.g} (${intense.e.toFixed(2)}).` : "—";
}

function renderAll(){
  popVal.textContent = popSlider.value;
  const minPop = Number(popSlider.value);

  const { rows, allowed } = filterRows();

  renderScatter(rows);
  renderValenceBox(rows, allowed);
  renderTopGenres(minPop);
  renderCorr();
  renderStory(rows, allowed);
}

async function init(){
  const [sample, genres, corr] = await Promise.all([
    fetch("data/sample.json").then(r=>r.json()),
    fetch("data/genre_stats.json").then(r=>r.json()),
    fetch("data/corr.json").then(r=>r.json()),
  ]);

  SAMPLE = sample;
  GENRES = genres;
  CORR = corr;

  // fill genres selector
  const allGenres = Array.from(new Set(GENRES.map(d=>d.track_genre))).sort();
  genreSelect.innerHTML = "";
  for (const g of allGenres){
    const opt = document.createElement("option");
    opt.value = g;
    opt.textContent = g;
    genreSelect.appendChild(opt);
  }

  document.getElementById("btnClear").addEventListener("click", ()=>{
    Array.from(genreSelect.options).forEach(o=>o.selected=false);
    renderAll();
  });

  popSlider.addEventListener("input", renderAll);
  topN.addEventListener("input", renderAll);
  genreSelect.addEventListener("change", renderAll);

  renderAll();
}

init().catch(err=>{
  console.error(err);
  alert("Error carregant dades. Revisa que existeixin data/sample.json, data/genre_stats.json i data/corr.json.");
});
</script>

</body>
</html>
"""

if __name__ == "__main__":
    main()
