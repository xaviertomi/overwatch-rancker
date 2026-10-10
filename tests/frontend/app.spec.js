const { test, expect } = require('@playwright/test');

const record = (pseudo, score, hours) => ({
  pseudo,
  score,
  Temps_Jeu_Heures: hours,
  'Winrate_%': 50,
  KDA: 2,
  Elims_Moyenne: 4,
  Assists_Moyenne: 1,
  Degats_Moyenne: 1000,
  Soins_Moyenne: 10,
});
const dataset = {
  'Résumé_Joueurs': {
    Alpha: { Temps_Jeu_Total_Heures: 12 },
    Bravo: { Temps_Jeu_Total_Heures: 9 },
    Charlie: { Temps_Jeu_Total_Heures: 4 },
  },
  Tank: { dva: [record('Alpha', 80, 12), record('Bravo', 60, 9), record('Charlie', 40, 4)] },
  Damage: { ashe: [] },
  Support: {},
};
const meta = {
  generated_at: '2026-10-09T20:00:00Z',
  source_generated_at: '2026-10-09T20:00:00Z',
  is_stale: false,
  run_id: 'browser-test',
};

async function mockData(page, data = dataset, metadata = meta) {
  await page.route('**/classement.json', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(data),
  }));
  await page.route('**/data-meta.json', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(metadata),
  }));
}

test('search and visual sorting preserve producer canonical ranks', async ({ page }) => {
  await mockData(page);
  await page.goto('./');
  await expect(page.locator('#status')).toHaveText('Classement chargé');
  await expect(page.locator('#hero-heading')).toHaveText('dva');

  await page.locator('#search').fill('charlie');
  await expect(page.locator('#ranking-body tr td').first()).toHaveText('3');
  await page.locator('#search').fill('');
  const scoreButton = page.locator('[data-sort="score"]');
  await scoreButton.focus();
  await scoreButton.press('Enter');
  await expect(page.locator('#ranking-body tr').first()).toContainText('Charlie');
  await expect(page.locator('#ranking-body tr').first().locator('td').first()).toHaveText('3');
  await expect(scoreButton.locator('..')).toHaveAttribute('aria-sort', 'ascending');
  await scoreButton.press('Enter');
  await expect(page.locator('#ranking-body tr').first()).toContainText('Alpha');
  await expect(scoreButton.locator('..')).toHaveAttribute('aria-sort', 'descending');

  const role = page.locator('#role-select');
  await role.focus();
  await role.press('ArrowDown');
  await role.press('Enter');
  await expect(role).toHaveValue('Damage');
  await expect(page.locator('#hero-heading')).toHaveText('ashe');
  await expect(page.locator('.empty-state')).toContainText('Aucun joueur n’a été classé');

  await page.locator('#reset').focus();
  await page.locator('#reset').press('Enter');
  await expect(role).toHaveValue('Tank');
  await expect(page.locator('#hero-select')).toHaveValue('dva');
  await expect(page.locator('#search')).toHaveValue('');
  await expect(page.locator('#ranking-body tr').first().locator('td').first()).toHaveText('1');
});

test('renders pseudo-keyed summary and stale data without changing scores', async ({ page }) => {
  await mockData(page, dataset, {
    ...meta,
    is_stale: true,
    source_generated_at: '2026-01-01T00:00:00Z',
  });
  await page.goto('./');
  await expect(page.locator('#stale-banner')).toContainText('Les données sont anciennes');
  await expect(page.locator('#summary-list')).toContainText('Alpha');
  await expect(page.locator('#summary-list')).toContainText('12 h');
  await expect(page.locator('#freshness')).toContainText('Données générées le');
  await expect(page.locator('#ranking-body tr').first()).toContainText('80');
});

test('keeps empty roles usable and reports unavailable generated data', async ({ page }) => {
  await mockData(page, {
    'Résumé_Joueurs': { Empty: { Temps_Jeu_Total_Heures: 0 } },
    Tank: { dva: [] },
    Damage: {},
    Support: {},
  });
  await page.goto('./');
  await expect(page.locator('.empty-state')).toContainText('Aucun joueur n’a été classé');
  await page.locator('#role-select').selectOption('Support');
  await expect(page.locator('.empty-state')).toContainText('Aucun héros généré');
  await expect(page.locator('#role-select')).toBeEnabled();

  await page.unrouteAll();
  await page.route('**/classement.json', route => route.fulfill({ status: 404, body: '' }));
  await page.route('**/data-meta.json', route => route.fulfill({ status: 404, body: '' }));
  await page.goto('./');
  await expect(page.locator('#error')).toContainText('Fichiers générés introuvables');
  await expect(page.locator('.empty-state')).toHaveText('Aucune statistique affichée.');
});

test('keeps the site frames aligned and adds three visible characters without page overflow', async ({ page }) => {
  const dmonRows = [
    {
      ...record('Jhonasse', 73.33, 26.88),
      'Winrate_%': 57.38,
      KDA: 4.54,
      Elims_Moyenne: 21.06,
      Assists_Moyenne: 3.39,
      Degats_Moyenne: 12441.39,
      Soins_Moyenne: 276.71,
    },
    {
      ...record('Thieuthieu', 26.67, 6.71),
      'Winrate_%': 69.57,
      KDA: 4.25,
      Elims_Moyenne: 19.28,
      Assists_Moyenne: 3.95,
      Degats_Moyenne: 10773.79,
      Soins_Moyenne: 527.29,
    },
  ];
  await mockData(page, { ...dataset, Tank: { ...dataset.Tank, dmon: dmonRows } });
  const baselineTableWidths = new Map([[320, 262], [390, 332], [768, 468], [1280, 885], [1568, 885]]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('./');
  await expect(page.locator('#status')).toHaveText('Classement chargé');
  await expect(page.locator('#hero-heading')).toHaveText('dmon');

  for (const [width, baselineWidth] of baselineTableWidths) {
    await page.setViewportSize({ width, height: 900 });
    const dimensions = await page.evaluate(() => {
      const main = document.querySelector('main.shell').getBoundingClientRect();
      const selectors = ['.site-header .shell', 'main.shell', '.content-grid', '.site-footer .shell'];
      const frames = selectors.map(selector => {
        const rect = document.querySelector(selector).getBoundingClientRect();
        return { left: rect.left, right: rect.right };
      });
      const wrap = document.querySelector('.table-wrap');
      const probe = document.createElement('span');
      probe.style.cssText = `position:fixed;visibility:hidden;width:3ch;font:${getComputedStyle(document.querySelector('main.shell')).font};white-space:nowrap;`;
      document.body.append(probe);
      const threeCh = probe.getBoundingClientRect().width;
      probe.remove();
      return {
        viewportWidth: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        tableVisibleWidth: wrap.getBoundingClientRect().width,
        tableClientWidth: wrap.clientWidth,
        tableScrollWidth: wrap.scrollWidth,
        threeCh,
        framesAligned: frames.every(frame =>
          Math.abs(frame.left - main.left) < 0.5 && Math.abs(frame.right - main.right) < 0.5),
      };
    });
    expect(dimensions.documentWidth).toBe(width);
    expect(dimensions.tableVisibleWidth).toBeGreaterThanOrEqual(baselineWidth + dimensions.threeCh);
    expect(dimensions.tableScrollWidth).toBeGreaterThan(dimensions.tableClientWidth);
    expect(dimensions.framesAligned).toBeTruthy();

    if (width === 1568) {
      await expect(page.locator('#ranking-body tr td:last-child')).toHaveText(['276,71', '527,29']);
      const statsVisible = await page.evaluate(() => {
        const wrap = document.querySelector('.table-wrap').getBoundingClientRect();
        return [...document.querySelectorAll('#ranking-body tr td:last-child')].every(cell => {
          const range = document.createRange();
          range.selectNodeContents(cell);
          const text = range.getBoundingClientRect();
          return text.left >= wrap.left && text.right <= wrap.right;
        });
      });
      expect(statsVisible).toBeTruthy();
    }
  }
});

test('renders French interface copy and French number formatting', async ({ page }) => {
  await mockData(page, dataset, { ...meta, source_generated_at: new Date().toISOString() });
  await page.goto('./');
  await page.reload();

  await expect(page).toHaveTitle('Classement Overwatch');
  await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
  await expect(page.locator('#status')).toHaveText('Classement chargé');
  await expect(page.locator('#role-select option')).toHaveText(['Tank', 'Dégâts', 'Soutien']);
  await expect(page.locator('#role-select')).toHaveAttribute('aria-label', 'Rôle');
  await expect(page.locator('#hero-select')).toHaveAttribute('aria-label', 'Héros');
  await expect(page.locator('#search')).toHaveAttribute('placeholder', 'Filtrer par pseudo');
  await expect(page.locator('#reset')).toHaveText('Réinitialiser la vue');
  await expect(page.locator('#controls-title')).toHaveText('Explorer les classements');
  await expect(page.locator('#summary-title')).toHaveText('Résumé des joueurs');
  await expect(page.locator('[data-sort="Winrate_%"]')).toHaveAttribute('aria-label', 'Taux de victoire');
  await expect(page.locator('thead')).toContainText('Victoire (%)');
  await expect(page.locator('thead')).toContainText('Élim. / 10 min');
  await expect(page.locator('thead')).toContainText('Assist. / 10 min');
  await expect(page.locator('thead')).toContainText('Dégâts / 10 min');
  await expect(page.locator('.methodology summary')).toHaveText('Méthodologie et limites');
  await expect(page.locator('.site-footer')).toContainText('Données générées uniquement');
  await expect(page.locator('#freshness')).toContainText('Données générées le');
  await expect(page.locator('#freshness')).toContainText('à l’instant');
  const frenchDamage = await page.evaluate(() =>
    new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(1000));
  await expect(page.locator('#ranking-body tr').first().locator('td').nth(8)).toHaveText(frenchDamage);
  await expect(page.locator('#hero-description')).toContainText('Classement canonique établi par le générateur.');
  await expect(page.locator('#table-caption')).toHaveText('Classement canonique pour dva');
});
