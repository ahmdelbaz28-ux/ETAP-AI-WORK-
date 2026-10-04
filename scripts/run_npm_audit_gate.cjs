const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const targetDir = process.argv[2] || '.';
const exceptionsFile = process.env.EXCEPTIONS_FILE || path.resolve(__dirname, '../.github/npm-audit-exceptions.txt');

let exceptions = [];
if (fs.existsSync(exceptionsFile)) {
  exceptions = fs.readFileSync(exceptionsFile, 'utf8')
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#') && line.startsWith('GHSA-'));
}

console.log(`[npm-audit-gate] Scanning directory: ${targetDir}`);
console.log(`[npm-audit-gate] Loaded ${exceptions.length} exceptions from ${exceptionsFile}`);

let stdout = '';
try {
  stdout = execSync('pnpm audit --audit-level=high --json', {
    cwd: targetDir,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
    maxBuffer: 20 * 1024 * 1024
  });
} catch (err) {
  // pnpm audit exits with non-zero when vulnerabilities are found
  stdout = err.stdout || '';
}

if (!stdout.trim()) {
  console.log('[npm-audit-gate] No audit output or clean audit.');
  process.exit(0);
}

let report;
try {
  report = JSON.parse(stdout);
} catch (parseErr) {
  console.error('[npm-audit-gate] Failed to parse pnpm audit JSON:', parseErr.message);
  process.exit(1);
}

const BLOCKING_LEVELS = new Set(['high', 'critical']);
const vulns = report.vulnerabilities || {};
const advisories = report.advisories || {};
const blocking = [];
const excepted = [];

function ghsaFromUrl(url) {
  if (!url || typeof url !== 'string') return null;
  const last = url.split('/').filter(Boolean).pop();
  return last && last.startsWith('GHSA-') ? last : null;
}

// Handle npm-style vulnerabilities
for (const [pkg, info] of Object.entries(vulns)) {
  const via = Array.isArray(info.via) ? info.via : [];
  for (const v of via) {
    if (typeof v === 'string') continue;
    const sev = v && typeof v.severity === 'string' ? v.severity.toLowerCase() : 'unknown';
    if (!BLOCKING_LEVELS.has(sev)) continue;
    const ghsa = ghsaFromUrl(v && v.url);
    if (!ghsa) continue;
    const entry = { pkg, ghsa, severity: sev, title: v.title, url: v.url };
    if (exceptions.includes(ghsa)) {
      excepted.push(entry);
    } else {
      blocking.push(entry);
    }
  }
}

// Handle pnpm-style advisories
for (const adv of Object.values(advisories)) {
  const sev = adv && typeof adv.severity === 'string' ? adv.severity.toLowerCase() : 'unknown';
  const pkgName = adv.module_name || adv.name || 'unknown';
  if (!BLOCKING_LEVELS.has(sev)) continue;
  const ghsa = ghsaFromUrl(adv.url);
  if (!ghsa) continue;
  const entry = { pkg: pkgName, ghsa, severity: sev, title: adv.title, url: adv.url };
  if (exceptions.includes(ghsa)) {
    excepted.push(entry);
  } else {
    blocking.push(entry);
  }
}

console.log(`[npm-audit-gate] Summary: ${excepted.length} excepted, ${blocking.length} blocking.`);

if (blocking.length > 0) {
  console.error('[npm-audit-gate] ::error::Blocking unexcepted high/critical advisories:');
  for (const b of blocking) {
    console.error(`  - ${b.pkg} [${b.severity}] ${b.ghsa}: ${b.title} (${b.url})`);
  }
  process.exit(1);
}

console.log('[npm-audit-gate] Gate passed cleanly — no unexcepted vulnerabilities.');
process.exit(0);
