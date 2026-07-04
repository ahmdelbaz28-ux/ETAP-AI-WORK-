const { execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const BASE_URL = 'http://localhost:5173';
const OUTPUT_DIR = path.join(__dirname, '..', 'docs', 'screenshots', 'ui');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

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

if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

for (const p of pages) {
  const filePath = path.join(OUTPUT_DIR, `${p.name}.png`);
  const url = `${BASE_URL}${p.path}`;
  try {
    execSync(
      `"${EDGE}" --headless=new --disable-gpu --screenshot="${filePath}" --window-size=1400,900 --hide-scrollbars --virtual-time-budget=5000 "${url}"`,
      { timeout: 30000, stdio: 'pipe' },
    );
    if (fs.existsSync(filePath)) {
      const size = fs.statSync(filePath).size;
      console.log(`${p.name}.png — ${Math.round(size / 1024)}KB`);
    }
  } catch (_e) {
    console.log(`Failed: ${p.name}`);
  }
}
console.log('Done');
