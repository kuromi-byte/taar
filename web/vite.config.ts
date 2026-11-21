import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import fs from 'fs';

const repoContractsPath = path.resolve(__dirname, '../contracts/config.json');
const fallbackContractsPath = path.resolve(__dirname, 'src/config/contracts-fallback.json');

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
