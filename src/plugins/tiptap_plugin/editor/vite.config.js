import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Builds a single self-contained index.html with all JS and CSS inlined.
// The output file is loaded offline by QWebEngineView — no CDN, no internet.
export default defineConfig({
  root: 'src',
  plugins: [viteSingleFile()],
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    // Inline everything so the output is truly a single file
    assetsInlineLimit: 100_000_000,
    cssCodeSplit: false,
  },
})
