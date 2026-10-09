const { test, expect } = require('@playwright/test');

test('loads all application resources below the project path', async ({ page }) => {
  const requests = [];
  page.on('request', request => requests.push(request.url()));
  await page.route('**/classement.json', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ 'Résumé_Joueurs': { A: { Temps_Jeu_Total_Heures: 1 } }, Tank: { dva: [] }, Damage: {}, Support: {} }) }));
  await page.route('**/data-meta.json', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ generated_at: '2026-10-09T20:00:00Z', source_generated_at: '2026-10-09T20:00:00Z', is_stale: false, run_id: 'path-test' }) }));
  await page.goto('./');
  await expect(page.locator('#status')).toHaveText('Ranking data loaded');
  expect(requests.filter(url => /\/(style\.css|app\.js|classement\.json|data-meta\.json)$/.test(new URL(url).pathname)).every(url => new URL(url).pathname.startsWith('/overwatch-rancker/'))).toBeTruthy();
});
