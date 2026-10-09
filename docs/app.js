(() => {
  "use strict";
  const roles = ["Tank", "Damage", "Support"];
  const recordKeys = ["pseudo", "score", "Temps_Jeu_Heures", "Winrate_%", "KDA", "Elims_Moyenne", "Assists_Moyenne", "Degats_Moyenne", "Soins_Moyenne"];
  const state = { data: null, meta: null, role: "Tank", hero: "", query: "", sortKey: "score", sortDirection: "desc" };
  const $ = (id) => document.getElementById(id);
  const status = $("status"), error = $("error"), stale = $("stale-banner"), roleSelect = $("role-select"), heroSelect = $("hero-select"), search = $("search"), body = $("ranking-body"), summaryList = $("summary-list");
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const fail = (message) => { error.textContent = message; error.hidden = false; status.textContent = "Ranking unavailable"; body.innerHTML = '<tr><td colspan="10" class="empty-state">No statistics rendered.</td></tr>'; summaryList.innerHTML = ""; };
  const validDataset = (data) => {
    if (!data || typeof data !== "object" || Object.keys(data).sort().join() !== ["Damage", "Résumé_Joueurs", "Support", "Tank"].join()) return false;
    if (!data["Résumé_Joueurs"] || typeof data["Résumé_Joueurs"] !== "object" || Array.isArray(data["Résumé_Joueurs"])) return false;
    let ranked = 0;
    for (const [pseudo, entry] of Object.entries(data["Résumé_Joueurs"])) if (!pseudo.trim() || !entry || Object.keys(entry).length !== 1 || !finite(entry.Temps_Jeu_Total_Heures)) return false;
    for (const role of roles) {
      if (!data[role] || typeof data[role] !== "object" || Array.isArray(data[role])) return false;
      for (const records of Object.values(data[role])) {
        if (!Array.isArray(records)) return false;
        const seen = new Set();
        for (const record of records) { ranked++; if (!record || Object.keys(record).sort().join() !== recordKeys.slice().sort().join() || typeof record.pseudo !== "string" || !record.pseudo.trim() || seen.has(record.pseudo) || !finite(record.score) || record.score < 0 || record.score > 100 || recordKeys.slice(2).some((key) => !finite(record[key]))) return false; seen.add(record.pseudo); }
      }
    }
    return Object.keys(data["Résumé_Joueurs"]).length > 0 || ranked > 0;
  };
  const validMeta = (meta) => meta && typeof meta.generated_at === "string" && typeof meta.source_generated_at === "string" && typeof meta.run_id === "string" && meta.run_id.trim() && typeof meta.is_stale === "boolean" && !Number.isNaN(Date.parse(meta.generated_at)) && !Number.isNaN(Date.parse(meta.source_generated_at)) && Object.keys(meta).sort().join() === ["generated_at", "is_stale", "run_id", "source_generated_at"].join();
  const heroesForRole = () => Object.keys(state.data?.[state.role] || {}).sort((a, b) => a.localeCompare(b));
  const display = (value) => typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—";
  const renderSummary = () => { const query = state.query.toLowerCase(); summaryList.innerHTML = ""; for (const [pseudo, entry] of Object.entries(state.data["Résumé_Joueurs"])) if (pseudo.toLowerCase().includes(query)) { const item = document.createElement("li"); item.innerHTML = `<span>${escapeHtml(pseudo)}</span><span class="summary-hours">${display(entry.Temps_Jeu_Total_Heures)} h</span>`; summaryList.append(item); } if (!summaryList.children.length) summaryList.innerHTML = '<li class="muted">No matching player summary.</li>'; };
  const escapeHtml = (value) => { const node = document.createElement("span"); node.textContent = value; return node.innerHTML; };
  const renderHeroOptions = () => { const available = heroesForRole(); heroSelect.innerHTML = ""; available.forEach((hero) => { const option = document.createElement("option"); option.value = hero; option.textContent = hero; heroSelect.append(option); }); if (!available.includes(state.hero)) state.hero = available[0] || ""; heroSelect.value = state.hero; };
  const updatePortrait = () => { const portrait = $("hero-portrait"); portrait.innerHTML = "<span>OW</span>"; if (!state.hero) return; const image = document.createElement("img"); image.alt = `${state.hero} portrait`; image.src = new URL(`./assets/heroes/${encodeURIComponent(state.hero)}.png`, document.baseURI).href; image.onerror = () => { image.remove(); }; portrait.append(image); };
  const compare = (a, b) => { const av = a.record[state.sortKey], bv = b.record[state.sortKey]; const direction = state.sortDirection === "asc" ? 1 : -1; if (av !== bv) return (av - bv) * direction; if (a.canonicalRank !== b.canonicalRank) return a.canonicalRank - b.canonicalRank; return a.record.pseudo.localeCompare(b.record.pseudo); };
  const renderTable = () => { $("hero-heading").textContent = state.hero || "No hero selected"; $("hero-role").textContent = state.role; $("hero-description").textContent = state.hero ? "Canonical producer rank; local controls change only visual order." : "This role has no generated heroes."; $("table-caption").textContent = state.hero ? `Canonical ranking for ${state.hero}` : "No hero ranking available"; updatePortrait(); body.innerHTML = ""; if (!state.hero) { body.innerHTML = '<tr><td colspan="10" class="empty-state">No generated heroes are available for this role.</td></tr>'; return; } const query = state.query.toLowerCase(); const records = state.data[state.role][state.hero].map((record, index) => ({ record, canonicalRank: index + 1 })).filter((item) => item.record.pseudo.toLowerCase().includes(query)).sort(compare); if (!records.length) { body.innerHTML = '<tr><td colspan="10" class="empty-state">No matching players.</td></tr>'; return; } for (const item of records) { const cells = [item.canonicalRank, item.record.pseudo, display(item.record.score), display(item.record.Temps_Jeu_Heures), `${display(item.record["Winrate_%"])}%`, display(item.record.KDA), display(item.record.Elims_Moyenne), display(item.record.Assists_Moyenne), display(item.record.Degats_Moyenne), display(item.record.Soins_Moyenne)]; const row = document.createElement("tr"); cells.forEach((value, index) => { const cell = document.createElement("td"); cell.textContent = value; if (index === 0) cell.className = "canonical"; row.append(cell); }); body.append(row); } };
  const updateAriaSort = () => document.querySelectorAll("[data-sort]").forEach((button) => { button.parentElement.setAttribute("aria-sort", button.dataset.sort === state.sortKey ? (state.sortDirection === "asc" ? "ascending" : "descending") : "none"); });
  const render = () => { roleSelect.value = state.role; renderHeroOptions(); renderSummary(); renderTable(); updateAriaSort(); };
  roleSelect.addEventListener("change", () => { state.role = roleSelect.value; state.hero = heroesForRole()[0] || ""; render(); });
  heroSelect.addEventListener("change", () => { state.hero = heroSelect.value; renderTable(); });
  search.addEventListener("input", () => { state.query = search.value; render(); });
  $("reset").addEventListener("click", () => { state.role = "Tank"; state.hero = ""; state.query = ""; state.sortKey = "score"; state.sortDirection = "desc"; search.value = ""; render(); });
  document.querySelectorAll("[data-sort]").forEach((button) => button.addEventListener("click", () => { if (state.sortKey === button.dataset.sort) state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc"; else { state.sortKey = button.dataset.sort; state.sortDirection = "desc"; } renderTable(); updateAriaSort(); }));
  const load = async () => { try { const base = document.baseURI; const [dataResponse, metaResponse] = await Promise.all([fetch(new URL("./classement.json", base)), fetch(new URL("./data-meta.json", base))]); if (!dataResponse.ok || !metaResponse.ok) throw new Error("Generated files are missing or not reachable; run the next dataset update."); const [data, meta] = await Promise.all([dataResponse.json(), metaResponse.json()]); if (!validDataset(data) || !validMeta(meta)) throw new Error("Generated data is malformed or incompatible; run the next dataset update."); state.data = data; state.meta = meta; status.textContent = "Ranking data loaded"; freshness.textContent = `Source generated ${new Date(meta.source_generated_at).toLocaleString()}`; stale.hidden = !meta.is_stale; render(); } catch (caught) { fail(caught.message || "Generated data could not be loaded; run the next dataset update."); } };
  const freshness = $("freshness");
  load();
})();
