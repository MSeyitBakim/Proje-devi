// Fails the build early, with a clear message, when project files are missing from the
// deployed folder (a bare `vite build` without vite.config.* fails with "Could not resolve
// entry module index.html" because the SvelteKit plugin is never loaded).
import { existsSync } from 'node:fs';

const required = [
  ['vite.config.ts', 'vite.config.js'],
  ['svelte.config.js'],
  ['src/app.html'],
  ['src/routes/+layout.svelte'],
  ['src/routes/+page.svelte']
];
const missing = required.filter((alternatives) => !alternatives.some((file) => existsSync(file)));

if (missing.length) {
  console.error(`\nMissing files in ${process.cwd()}:`);
  for (const alternatives of missing) console.error(`  - ${alternatives.join(' or ')}`);
  console.error('\nCommit the complete apps/web folder (check with: git ls-files apps/web).\n');
  process.exit(1);
}
console.log('apps/web layout OK');
