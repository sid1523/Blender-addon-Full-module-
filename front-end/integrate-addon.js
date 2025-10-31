#!/usr/bin/env node
import { execSync } from 'child_process';
import fs from 'fs';
import path, { dirname } from 'path';
import { fileURLToPath } from 'url';

// Emulate __dirname in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function run(cmd, cwd) {
  console.log(`> ${cmd}`);
  execSync(cmd, { cwd, stdio: 'inherit' });
}

async function main() {
  const root = path.resolve(__dirname);
  console.log('Installing front-end dependencies');
  run('npm install', root);
  console.log('Building front-end');
  run('npm run build', root);
  const distDir = path.join(root, 'dist');
  const dest = path.join(root, '..', 'canvas3d', 'ui', 'frontend');
  console.log(`Integrating into add-on at ${dest}`);
  if (fs.existsSync(dest)) fs.rmSync(dest, { recursive: true, force: true });
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(distDir)) {
    const src = path.join(distDir, entry);
    const dst = path.join(dest, entry);
    fs.cpSync(src, dst, { recursive: true });
  }
  console.log('Front-end assets integrated successfully.');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
