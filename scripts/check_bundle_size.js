/**
 * scripts/check_bundle_size.js
 * Verifies production UI bundle size against documented 5MB baseline.
 */

import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, '..');
const UI_DIST_DIR = path.join(ROOT_DIR, 'ui', 'dist');
const ASSETS_DIR = path.join(UI_DIST_DIR, 'assets');
const MAX_BUNDLE_SIZE_MB = 5.0;

function checkBundleSize() {
  if (!fs.existsSync(ASSETS_DIR)) {
    console.log('📦 UI dist/assets not found. Building UI production bundle...');
    execSync('pnpm --dir ui build', { stdio: 'inherit', cwd: ROOT_DIR });
  }

  if (!fs.existsSync(ASSETS_DIR)) {
    console.error('❌ Error: UI dist/assets does not exist after build.');
    process.exit(1);
  }

  const files = fs.readdirSync(ASSETS_DIR);
  let totalBytes = 0;
  const jsFiles = [];

  for (const file of files) {
    if (file.endsWith('.js')) {
      const filePath = path.join(ASSETS_DIR, file);
      const stat = fs.statSync(filePath);
      totalBytes += stat.size;
      jsFiles.push({ file, sizeKB: (stat.size / 1024).toFixed(2), bytes: stat.size });
    }
  }

  const totalMB = (totalBytes / (1024 * 1024)).toFixed(2);
  console.log(`\n📊 Total Production JS Bundle Size: ${totalMB} MB (${jsFiles.length} files)`);
  console.log(`🎯 Configured Baseline Threshold: ${MAX_BUNDLE_SIZE_MB} MB`);

  // Sort and print top 5 largest bundles
  jsFiles.sort((a, b) => b.bytes - a.bytes);
  console.log('\nTop JS assets:');
  for (const item of jsFiles.slice(0, 5)) {
    console.log(`  - ${item.file}: ${item.sizeKB} KB`);
  }

  if (totalBytes > MAX_BUNDLE_SIZE_MB * 1024 * 1024) {
    console.error(`\n❌ BLOCKED: Bundle size ${totalMB} MB exceeds threshold of ${MAX_BUNDLE_SIZE_MB} MB.`);
    process.exit(1);
  }

  console.log(`\n✅ Bundle size verification PASSED: ${totalMB} MB <= ${MAX_BUNDLE_SIZE_MB} MB\n`);
}

checkBundleSize();
