const { test, expect } = require('@playwright/test');

const record = (pseudo, score, hours) => ({ pseudo, score, Temps_Jeu_Heures: hours, 'Winrate_%': 50, KDA: 2, Elims_Moyenne: 4, Assists_Moyenne: 1, Degats_Moyenne: 1000, Soins_Moyenne: 10 });
const dataset = {
  'Résumé_Joueurs': { Alpha: { Temps_Jeu_Total_Heures: 12 }, Bravo: { Temps_Jeu_Total_Heures: 9 }, Charlie: { Temps_Jeu_Total_Heures: 4 } },
  Tank: { dva: [record('Alpha', 80, 12), record('Bravo', 60, 9), record('Charlie', 40, 4)] },
  Damage: { ashe: [] }, Support: {}
};
const meta = { generated_at: '2026-10-09T20:00:00Z', source_generated_at: '2026-10-09T20:00:00Z', is_stale: false, run_id: 'browser-test' };

async function mockData(page, metadata = meta) {
  await page.route('**/classement.json', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dataset) }));
  await page.route('**/data-meta.json', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(metadata) }));
}

test('loads role, search and canonical rank controls', async ({ page }) => {
  await mockData(page);
  await page.goto('./');
  await expect(page.locator('#status')).toHaveText('Ranking data loaded');
  await expect(page.locator('#hero-heading')).toHaveText('dva');
  await page.locator('#search').fill('Charlie');
  await expect(page.locator('#ranking-body tr td').first()).toHaveText('3');
  await page.locator('[data-sort="score"]').click();
  await expect(page.locator('#ranking-body tr td').first()).toHaveText('3');
  await page.locator('#role-select').selectOption('Damage');
  await expect(page.locator('#hero-heading')).toHaveText('ashe');
  await expect(page.locator('.empty-state')).toContainText('No generated heroes');
  await page.locator('#reset').click();
  await expect(page.locator('#role-select')).toHaveValue('Tank');
  await expect(page.locator('#search')).toHaveValue('');
  await expect(page.locator('#ranking-body tr').first().locator('td').first()).toHaveText('1');
});

test('renders summary keys and stale banner without recomputation', async ({ page }) => {
  await mockData(page, { ...meta, is_stale: true, source_generated_at: '2026-01-01T00:00:00Z' });
  await page.goto('./');
  await expect(page.locator('#stale-banner')).toBeVisible();
  await expect(page.locator('#summary-list')).toContainText('Alpha');
  await expect(page.locator('#ranking-body')).toContainText('80');
});

test('reports missing generated files', async ({ page }) => {
  await page.goto('./');
  await expect(page.locator('#error')).toContainText('run the next dataset update');
  await expect(page.locator('.empty-state')).toContainText('No statistics rendered');
});
