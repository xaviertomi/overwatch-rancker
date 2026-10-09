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
  await expect(page.locator('#status')).toHaveText('Ranking data loaded');
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
  await expect(page.locator('.empty-state')).toContainText('No players have been ranked');

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
  await expect(page.locator('#stale-banner')).toBeVisible();
  await expect(page.locator('#summary-list')).toContainText('Alpha');
  await expect(page.locator('#summary-list')).toContainText('12 h');
  await expect(page.locator('#freshness')).toContainText('2026');
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
  await expect(page.locator('.empty-state')).toContainText('No players have been ranked');
  await page.locator('#role-select').selectOption('Support');
  await expect(page.locator('.empty-state')).toContainText('No generated heroes');
  await expect(page.locator('#role-select')).toBeEnabled();

  await page.unrouteAll();
  await page.goto('./');
  await expect(page.locator('#error')).toContainText('run the next dataset update');
  await expect(page.locator('.empty-state')).toContainText('No statistics rendered');
});

test('keeps ranking table horizontally scrollable on mobile', async ({ page }) => {
  await mockData(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('./');
  await expect(page.locator('#status')).toHaveText('Ranking data loaded');
  const dimensions = await page.locator('.table-wrap').evaluate((node) => ({
    clientWidth: node.clientWidth,
    scrollWidth: node.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth);
  await expect(page.locator('#reset')).toBeVisible();
});
