import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const repoContractsPath = path.resolve(currentDir, '../contracts/config.json');
const fallbackContractsPath = path.resolve(currentDir, 'src/config/contracts-fallback.json');

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: {
      allow: ['..']
    }
  },
  resolve: {
    preserveSymlinks: true,
    alias: [
      {
        find: /^\/contracts\/config\.json$/,
        replacement: fs.existsSync(repoContractsPath) ? repoContractsPath : fallbackContractsPath
      }
    ]
  }
});
