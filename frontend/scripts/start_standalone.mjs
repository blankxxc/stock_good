import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const standaloneRoot = path.join(frontendRoot, '.next', 'standalone');
const serverPath = path.join(standaloneRoot, 'server.js');

if (!fs.existsSync(serverPath)) {
  console.error('Standalone server not found. Run `npm run build` before `npm start`.');
  process.exit(1);
}

function replaceDirectory(source, destination) {
  if (!fs.existsSync(source)) return;
  fs.rmSync(destination, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, { recursive: true, force: true });
}

// Next standalone output intentionally omits public assets and .next/static.
// Copy them beside server.js so CSS, client chunks, and public files are served.
replaceDirectory(
  path.join(frontendRoot, '.next', 'static'),
  path.join(standaloneRoot, '.next', 'static'),
);
replaceDirectory(
  path.join(frontendRoot, 'public'),
  path.join(standaloneRoot, 'public'),
);

process.env.HOSTNAME ||= '0.0.0.0';
process.env.PORT ||= '3000';

await import(pathToFileURL(serverPath).href);
