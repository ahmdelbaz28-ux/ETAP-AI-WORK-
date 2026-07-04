import { chromium } from 'playwright';
import { mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const BASE_URL = 'http://localhost:5173';
const OUTPUT_DIR = join(process.cwd(), 'docs', 'screenshots', 'ui');

const pages = [
  { name: 'dashboard-dark', path: '/dashboard' },
  { name: 'studies', path: '/studies' },
  { name: 'ai-assistant', path: '/assistant' },
  { name: 'projects', path: '/projects' },
  { name: 'settings', path: '/settings' },
  { name: 'diagnostics', path: '/diagnostics' },
  { name: 'digital-twin', path: '/digital-twin' },
  { name: 'reports', path: '/reports' },
  { name: 'asset-management', path: '/asset-management' },
  { name: 'etap-integration', path: '/etap' },
];

if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1400, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: 'dark',
});

for (const p of pages) {
  const page = await context.newPage();
  try {
    await page.goto(`${BASE_URL}${p.path}`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(3000);
    const filePath = join(OUTPUT_DIR, `${p.name}.png`);
    await page.screenshot({ path: filePath, fullPage: false });
    const size = (await import('node:fs')).statSync(filePath).size;
    console.log(`${p.name}.png — ${Math.round(size / 1024)}KB`);
  } catch (err) {
    console.log(`Failed: ${p.name} — ${err.message?.slice(0, 60)}`);
  }
  await page.close();
}

await browser.close();
console.log('Done');
