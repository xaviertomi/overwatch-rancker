(() => {
  "use strict";

  const roles = ["Tank", "Damage", "Support"];
  const roleLabels = { Tank: "Tank", Damage: "Dégâts", Support: "Soutien" };
  const heroRoles = {
    dva: "Tank", doomfist: "Tank", "junker-queen": "Tank", mauga: "Tank",
    orisa: "Tank", ramattra: "Tank", reinhardt: "Tank", roadhog: "Tank",
    sigma: "Tank", winston: "Tank", "wrecking-ball": "Tank", zarya: "Tank",
    hazard: "Tank", dmon: "Tank", domina: "Tank",
    anran: "Damage", ashe: "Damage", bastion: "Damage", cassidy: "Damage",
    echo: "Damage", genji: "Damage", hanzo: "Damage", junkrat: "Damage",
    mei: "Damage", pharah: "Damage", reaper: "Damage", sierra: "Damage",
    sojourn: "Damage", "soldier-76": "Damage", sombra: "Damage", symmetra: "Damage",
    torbjorn: "Damage", tracer: "Damage", venture: "Damage", widowmaker: "Damage",
    freja: "Damage", vendetta: "Damage", emre: "Damage", shion: "Damage",
    ana: "Support", baptiste: "Support", brigitte: "Support", doctrine: "Support",
    illari: "Support", juno: "Support", kiriko: "Support", lifeweaver: "Support",
    lucio: "Support", mercy: "Support", moira: "Support", zenyatta: "Support",
    mizuki: "Support", wuyang: "Support", "jetpack-cat": "Support",
  };
  const recordKeys = [
    "pseudo", "score", "Temps_Jeu_Heures", "Winrate_%", "KDA",
    "Elims_Moyenne", "Assists_Moyenne", "Degats_Moyenne", "Soins_Moyenne",
  ];
  const numericKeys = recordKeys.filter((key) => key !== "pseudo");
  const state = {
    data: null,
    meta: null,
    role: "Tank",
    hero: "",
    initialRole: "Tank",
    initialHero: "",
    query: "",
    sortKey: "score",
    sortDirection: "desc",
  };
  const $ = (id) => document.getElementById(id);
  const status = $("status");
  const error = $("error");
  const staleBanner = $("stale-banner");
  const freshness = $("freshness");
  const roleSelect = $("role-select");
  const heroSelect = $("hero-select");
  const search = $("search");
  const reset = $("reset");
  const body = $("ranking-body");
  const summaryList = $("summary-list");
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const sortedKeys = (object) => Object.keys(object).sort();

  function setControlsEnabled(enabled) {
    roleSelect.disabled = !enabled;
    heroSelect.disabled = !enabled || heroSelect.options.length === 0;
    search.disabled = !enabled;
    reset.disabled = !enabled;
    document.querySelectorAll("[data-sort]").forEach((button) => {
      button.disabled = !enabled;
    });
  }

  function fail(message) {
    error.textContent = message;
    error.hidden = false;
    staleBanner.hidden = true;
    status.textContent = "Classement indisponible";
    freshness.textContent = "";
    body.innerHTML = '<tr><td colspan="10" class="empty-state">Aucune statistique affichée.</td></tr>';
    summaryList.replaceChildren();
    setControlsEnabled(false);
  }

  function validDataset(data) {
    const expectedRootKeys = ["Damage", "Résumé_Joueurs", "Support", "Tank"];
    if (!data || typeof data !== "object" || Array.isArray(data) ||
        sortedKeys(data).join("\0") !== expectedRootKeys.join("\0")) return false;

    const summary = data["Résumé_Joueurs"];
    if (!summary || typeof summary !== "object" || Array.isArray(summary)) return false;
    for (const [pseudo, entry] of Object.entries(summary)) {
      if (!pseudo.trim() || !entry || typeof entry !== "object" || Array.isArray(entry) ||
          sortedKeys(entry).join("\0") !== "Temps_Jeu_Total_Heures" ||
          !finite(entry.Temps_Jeu_Total_Heures)) return false;
    }

    let rankedCount = 0;
    for (const role of roles) {
      const roleData = data[role];
      if (!roleData || typeof roleData !== "object" || Array.isArray(roleData)) return false;
      for (const [hero, records] of Object.entries(roleData)) {
        if (heroRoles[hero] !== role || !Array.isArray(records)) return false;
        const seen = new Set();
        for (const record of records) {
          rankedCount += 1;
          if (!record || typeof record !== "object" || Array.isArray(record) ||
              sortedKeys(record).join("\0") !== recordKeys.slice().sort().join("\0") ||
              typeof record.pseudo !== "string" || !record.pseudo.trim() ||
              seen.has(record.pseudo) || !finite(record.score) ||
              record.score < 0 || record.score > 100 ||
              numericKeys.some((key) => !finite(record[key]))) return false;
          seen.add(record.pseudo);
        }
      }
    }
    return Object.keys(summary).length > 0 || rankedCount > 0;
  }

  function validUtcTimestamp(value) {
    return typeof value === "string" &&
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(value) &&
      Number.isFinite(Date.parse(value));
  }

  function validMetadata(meta) {
    const expected = ["generated_at", "is_stale", "run_id", "source_generated_at"];
    return meta && typeof meta === "object" && !Array.isArray(meta) &&
      sortedKeys(meta).join("\0") === expected.join("\0") &&
      validUtcTimestamp(meta.generated_at) && validUtcTimestamp(meta.source_generated_at) &&
      typeof meta.is_stale === "boolean" &&
      typeof meta.run_id === "string" && meta.run_id.trim().length > 0;
  }

  roles.forEach((role) => {
    const option = document.createElement("option");
    option.value = role;
    option.textContent = roleLabels[role];
    roleSelect.append(option);
  });

  function heroesForRole() {
    return sortedKeys(state.data?.[state.role] || {});
  }

  function formatNumber(value) {
    return finite(value) ? value.toLocaleString("fr-FR", { maximumFractionDigits: 2 }) : "—";
  }

  function renderSummary() {
    const query = state.query.toLocaleLowerCase();
    summaryList.replaceChildren();
    for (const [pseudo, entry] of Object.entries(state.data["Résumé_Joueurs"])) {
      if (!pseudo.toLocaleLowerCase().includes(query)) continue;
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = pseudo;
      const hours = document.createElement("span");
      hours.className = "summary-hours";
      hours.textContent = `${formatNumber(entry.Temps_Jeu_Total_Heures)} h`;
      item.append(name, hours);
      summaryList.append(item);
    }
    if (!summaryList.children.length) {
      const item = document.createElement("li");
      item.className = "muted";
      item.textContent = "Aucun joueur ne correspond à la recherche.";
      summaryList.append(item);
    }
  }

  function renderHeroOptions() {
    const available = heroesForRole();
    heroSelect.replaceChildren();
    for (const hero of available) {
      const option = document.createElement("option");
      option.value = hero;
      option.textContent = hero;
      heroSelect.append(option);
    }
    if (!available.includes(state.hero)) state.hero = available[0] || "";
    heroSelect.value = state.hero;
    heroSelect.disabled = available.length === 0;
  }

  function updatePortrait() {
    const portrait = $("hero-portrait");
    portrait.replaceChildren();
    if (!state.hero) {
      const placeholder = document.createElement("span");
      placeholder.textContent = "OW";
      portrait.append(placeholder);
      return;
    }
    const image = document.createElement("img");
    image.alt = `${state.hero}, portrait`;
    image.src = new URL(`./assets/heroes/${encodeURIComponent(state.hero)}.png`, document.baseURI).href;
    image.onerror = () => {
      image.remove();
      const placeholder = document.createElement("span");
      placeholder.textContent = "OW";
      portrait.append(placeholder);
    };
    portrait.append(image);
  }

  function compareRows(left, right) {
    const leftValue = left.record[state.sortKey];
    const rightValue = right.record[state.sortKey];
    const direction = state.sortDirection === "asc" ? 1 : -1;
    if (leftValue !== rightValue) return (leftValue - rightValue) * direction;
    if (left.canonicalRank !== right.canonicalRank) {
      return left.canonicalRank - right.canonicalRank;
    }
    return left.record.pseudo.localeCompare(right.record.pseudo);
  }

  function emptyRow(message) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 10;
    cell.className = "empty-state";
    cell.textContent = message;
    row.append(cell);
    body.append(row);
  }

  function renderTable() {
    $("hero-heading").textContent = state.hero || "Aucun héros sélectionné";
    $("hero-role").textContent = roleLabels[state.role];
    $("hero-description").textContent = state.hero
      ? "Classement canonique établi par le générateur. Le nombre de parties et certaines moyennes peuvent être estimés ou reconstitués à partir des moyennes de l’API source."
      : "Ce rôle ne contient aucun héros dans les données générées.";
    $("table-caption").textContent = state.hero
      ? `Classement canonique pour ${state.hero}`
      : "Aucun classement de héros disponible";
    updatePortrait();
    body.replaceChildren();

    if (!state.hero) {
      emptyRow("Aucun héros généré n’est disponible pour ce rôle.");
      return;
    }

    const sourceRecords = state.data[state.role][state.hero];
    if (sourceRecords.length === 0) {
      emptyRow("Aucun joueur n’a été classé pour ce héros.");
      return;
    }

    const query = state.query.toLocaleLowerCase();
    const visibleRecords = sourceRecords
      .map((record, index) => ({ record, canonicalRank: index + 1 }))
      .filter((item) => item.record.pseudo.toLocaleLowerCase().includes(query))
      .sort(compareRows);
    if (!visibleRecords.length) {
      emptyRow("Aucun joueur ne correspond à la recherche.");
      return;
    }

    for (const item of visibleRecords) {
      const values = [
        item.canonicalRank,
        item.record.pseudo,
        formatNumber(item.record.score),
        formatNumber(item.record.Temps_Jeu_Heures),
        `${formatNumber(item.record["Winrate_%"])}%`,
        formatNumber(item.record.KDA),
        formatNumber(item.record.Elims_Moyenne),
        formatNumber(item.record.Assists_Moyenne),
        formatNumber(item.record.Degats_Moyenne),
        formatNumber(item.record.Soins_Moyenne),
      ];
      const row = document.createElement("tr");
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        cell.textContent = String(value);
        if (index === 0) cell.className = "canonical";
        row.append(cell);
      });
      body.append(row);
    }
  }

  function updateAriaSort() {
    document.querySelectorAll("[data-sort]").forEach((button) => {
      const value = button.dataset.sort === state.sortKey
        ? (state.sortDirection === "asc" ? "ascending" : "descending")
        : "none";
      button.parentElement.setAttribute("aria-sort", value);
    });
  }

  function render() {
    roleSelect.value = state.role;
    renderHeroOptions();
    renderSummary();
    renderTable();
    updateAriaSort();
    setControlsEnabled(true);
  }

  roleSelect.addEventListener("change", () => {
    state.role = roleSelect.value;
    state.hero = heroesForRole()[0] || "";
    render();
  });
  heroSelect.addEventListener("change", () => {
    state.hero = heroSelect.value;
    renderTable();
  });
  search.addEventListener("input", () => {
    state.query = search.value;
    render();
  });
  reset.addEventListener("click", () => {
    state.role = state.initialRole;
    state.hero = state.initialHero;
    state.query = "";
    state.sortKey = "score";
    state.sortDirection = "desc";
    search.value = "";
    render();
  });
  document.querySelectorAll("[data-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      if (state.sortKey === button.dataset.sort) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = button.dataset.sort;
        state.sortDirection = "desc";
      }
      renderTable();
      updateAriaSort();
    });
  });

  async function load() {
    setControlsEnabled(false);
    try {
      const base = document.baseURI;
      const [datasetResponse, metadataResponse] = await Promise.all([
        fetch(new URL("./classement.json", base)),
        fetch(new URL("./data-meta.json", base)),
      ]);
      if (!datasetResponse.ok || !metadataResponse.ok) {
        throw new Error("Fichiers générés introuvables ou inaccessibles ; exécutez la prochaine mise à jour des données.");
      }
      const [data, meta] = await Promise.all([
        datasetResponse.json(),
        metadataResponse.json(),
      ]);
      if (!validDataset(data) || !validMetadata(meta)) {
        throw new Error("Données générées mal formées ou incompatibles ; exécutez la prochaine mise à jour des données.");
      }

      state.data = data;
      state.meta = meta;
      state.initialRole = Object.keys(data.Tank).length > 0
        ? "Tank"
        : roles.find((role) => Object.keys(data[role]).length > 0) || "Tank";
      state.role = state.initialRole;
      state.initialHero = sortedKeys(data[state.initialRole])[0] || "";
      state.hero = state.initialHero;
      status.textContent = "Classement chargé";
      const generatedDate = new Date(meta.source_generated_at);
      const ageMs = Math.max(0, Date.now() - generatedDate.getTime());
      const ageHours = Math.floor(ageMs / 3_600_000);
      const ageDays = Math.floor(ageHours / 24);
      const ageText = ageHours < 24
        ? `il y a ${ageHours} ${ageHours === 1 ? "heure" : "heures"}`
        : `il y a ${ageDays} ${ageDays === 1 ? "jour" : "jours"}`;
      freshness.textContent = `Données générées le ${generatedDate.toLocaleString("fr-FR")} (${ageText})`;
      staleBanner.hidden = !meta.is_stale;
      error.hidden = true;
      render();
    } catch (caught) {
      fail(caught instanceof Error &&
        (caught.message.startsWith("Fichiers générés") || caught.message.startsWith("Données générées"))
        ? caught.message
        : "Les données générées n’ont pas pu être chargées. Réessayez après la prochaine mise à jour.");
    }
  }

  load();
})();
