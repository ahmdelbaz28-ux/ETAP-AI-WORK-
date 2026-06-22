import { readFileSync, writeFileSync } from 'fs';

// Read lockfile
const lock = readFileSync('pnpm-lock.yaml', 'utf-8');

function extractVersion(name) {
  const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp("'" + esc + "@([0-9]+\\.[0-9]+\\.[0-9]+[^'\\n:]*?)'", 'i');
  const match = lock.match(regex);
  if (match) {
    let v = match[1];
    v = v.replace(/[\s_]/, '').trim();
    return v;
  }
  return null;
}

// Read both package.json files
const root = JSON.parse(readFileSync('package.json', 'utf-8'));
const ui = JSON.parse(readFileSync('ui/package.json', 'utf-8'));

console.log('=== RESOLVED VERSIONS ===');

for (const [label, pkg] of [['ROOT', root], ['UI', ui]]) {
  for (const section of ['dependencies', 'devDependencies']) {
    if (pkg[section]) {
      for (const name of Object.keys(pkg[section])) {
        const exact = extractVersion(name);
        const old = pkg[section][name];
        if (exact) {
          pkg[section][name] = exact;
          console.log(label + ' ' + section + ' ' + name + ': ' + old + ' -> ' + exact);
        } else {
          const fallback = old.replace(/^[~^]/, '');
          pkg[section][name] = fallback;
          console.log(label + ' ' + section + ' ' + name + ': ' + old + ' -> ' + fallback + ' (LOCKFILE FALLBACK)');
        }
      }
    }
  }
}

writeFileSync('package.json', JSON.stringify(root, null, 2) + '\n');
writeFileSync('ui/package.json', JSON.stringify(ui, null, 2) + '\n');
console.log('\nDone! Both package.json files updated.');
