// src/lib/root-path-preprocess.js

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\\/]/g, '\\$&');
}

export function rootPathPreprocess() {
  return {
    name: 'root-path-preprocess',

    script({ content, filename, attributes }) {
      if (!content) return;

      let modified = content;
      let needsBase = false;
      const isModuleScript = attributes && attributes.context === 'module';

      const hasBaseImport = /import\s*\{[^}]*base[^}]*\}\s*from\s*['"]\$app\/paths['"]/.test(modified);

      // 1a. Transform goto('/...'), goto("/...") — simple string args.
      // Also handles goto('/...', { ... }) with a second argument (e.g.
      // { replaceState: true }), used for admin/workspace navigation.
      modified = modified.replace(
        /\bgoto\(\s*(['"])(\/[^'"]*)\1(\s*,[^)]*)?\)/g,
        (match, quote, path, secondArg) => {
          needsBase = true;
          return `goto(\`\${base}${path}\`${secondArg || ''})`;
        }
      );

      // 1b. Transform goto(`/...`) — template literal args starting with /
      // Matches goto(`/path...`) and goto(`/path${var}...`)
      // Inserts ${base} after the opening backtick so the path becomes ${base}/path...
      modified = modified.replace(
        /\bgoto\(\s*\x60(\/[a-z])/g,
        (match, pathStart) => {
          needsBase = true;
          return `goto(\`\${base}${pathStart}`;
        }
      );

      // 2. Transform location.href = '/...' and location.href = `/...`
      modified = modified.replace(
        /\blocation\.href\s*=\s*(['"])(\/[^'"]*)\1/g,
        (match, quote, path) => {
          needsBase = true;
          return `location.href = \`\${base}${path}\``;
        }
      );

      // 2b. Transform location.href = `/path...` (template literal starting with /)
      modified = modified.replace(
        /\blocation\.href\s*=\s*\x60(\/[a-z])/g,
        (match, pathStart) => {
          needsBase = true;
          return `location.href = \`\${base}${pathStart}`;
        }
      );

      // 3. Transform location.href = expr ?? '/...'
      modified = modified.replace(
        /\blocation\.href\s*=\s*([^{]+?)\s*\?\?\s*(['"\x60])(\/[^'"\x60]*)\2/g,
        (match, fallback, quote, path) => {
          needsBase = true;
          return `location.href = ${fallback} ?? \`\${base}${path}\``;
        }
      );

      // 4. Transform window.history.replaceState(..., '', '/...') and with template literals
      modified = modified.replace(
        /window\.history\.replaceState\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*(['"])(\/[^'"]*)\3\s*\)/g,
        (match, state, title, quote, path) => {
          needsBase = true;
          return `window\.history\.replaceState(${state}, ${title}, \`\${base}${path}\`)`;
        }
      );

      // 4b. Transform window.history.replaceState(..., '', `/path...`) (template literal)
      modified = modified.replace(
        /window\.history\.replaceState\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*\x60(\/[a-z])/g,
        (match, state, title, pathStart) => {
          needsBase = true;
          return `window.history.replaceState(${state}, ${title}, \`\${base}${pathStart}`;
        }
      );

      // 5. Transform Socket.IO: strip namespace arg and fix path
      // io(`${getBasePath()}` || undefined, { path: '/ws/socket.io', ... })
      // becomes: io(undefined, { path: `${base}/ws/socket.io`, ... })
      // Socket.IO treats the first arg as a namespace, so the root path
      // must NOT be passed as the first argument — only the path option
      // needs the prefix. Uses \x60 for backtick in regex (JS regex
      // literal escaping doesn't support \`).
      modified = modified.replace(
        /\bio\(\s*\x60\$\{[^}]+\}\x60\s*\|\|\s*undefined\s*,/g,
        (match) => {
          needsBase = true;
          return 'io(undefined,';
        }
      );
      // Also handle minified form: io(`${...}` || void 0,
      modified = modified.replace(
        /\bio\(\s*\x60\$\{[^}]+\}\x60\s*\|\|\s*void\s+0\s*,/g,
        (match) => {
          needsBase = true;
          return 'io(undefined,';
        }
      );

      // 7. Transform new Audio('/...') and new Audio(`/...`)
      modified = modified.replace(
        /\bnew\s+Audio\(\s*(['"\x60])(\/[^'"\x60]*)\1\s*\)/g,
        (match, quote, path) => {
          needsBase = true;
          return `new Audio(\`\${base}${path}\`)`;
        }
      );

      // 8. Transform href: '/path' in object literals (e.g. navigation menu items)
      modified = modified.replace(
        /\bhref:\s*(['"])(\/[a-z][a-z0-9/._-]*)\1/g,
        (match, quote, path) => {
          needsBase = true;
          return `href: \`\${base}${path}\``;
        }
      );

      // 8b. Transform href: `/path...` in object literals (template literals)
      modified = modified.replace(
        /\bhref:\s*\x60(\/[a-z])/g,
        (match, pathStart) => {
          needsBase = true;
          return `href: \`\${base}${pathStart}`;
        }
      );

      // 9. Transform route: '/path' in object literals (navigation menu items)
      modified = modified.replace(
        /\broute:\s*(['"])(\/[a-z][a-z0-9/._-]*)\1/g,
        (match, quote, path) => {
          needsBase = true;
          return `route: \`\${base}${path}\``;
        }
      );

      // 10. Catch-all: transform template literals starting with /path
      // Handles patterns like: condition ? `/path/${var}` : `/other/${var}`
      // and standalone: `/c/${id}`, `/admin/settings/models?id=${...}`, etc.
      // Transforms backtick+slash+letter to backtick+${base}+slash+letter
      // But only in contexts where the backtick opens a template literal
      // (not inside already-transformed ${base}` expressions)
      modified = modified.replace(
        /\x60(\/[a-z])/g,
        (match, pathStart) => {
          // Check if this is already preceded by ${base} — avoid double-transforming
          // The previous transformations produce patterns like: `${base}/path`
          // which are: backtick + ${base} + /path + backtick
          // A raw backtick+/ is a new template literal that needs transformation
          needsBase = true;
          return `\`\${base}${pathStart}`;
        }
      );

      // 11. Inject base import if transformations were made
      if (needsBase && !hasBaseImport && !isModuleScript) {
        modified = `import { base } from '$app/paths';\n${modified}`;
      }

      if (!needsBase) return undefined;

      return { code: modified };
    },

    markup({ content, filename }) {
      if (!content) return;

      let modified = content;
      let needsBase = false;

      // Transform href="/..." — skip external URLs, anchors, mailto
      modified = modified.replace(
        /\bhref="([^"]+)"/g,
        (match, path) => {
          if (path.startsWith('/') && !path.startsWith('//')) {
            needsBase = true;
            return `href="{base}${path}"`;
          }
          return match;
        }
      );

      modified = modified.replace(
        /\bhref='([^']+)'/g,
        (match, path) => {
          if (path.startsWith('/') && !path.startsWith('//')) {
            needsBase = true;
            return `href='{base}${path}'`;
          }
          return match;
        }
      );

      // Transform href={`/path...`} in Svelte expressions
      modified = modified.replace(
        /\bhref=\{\x60(\/[a-z])/g,
        (match, pathStart) => {
          needsBase = true;
          return `href={\`\${base}${pathStart}`;
        }
      );

      // Transform goto('/...') in inline event handlers in markup.
      // Also handles goto('/...', { ... }) with a second argument.
      modified = modified.replace(
        /\bgoto\(\s*(['"])(\/[^'"]*)\1(\s*,[^)]*)?\)/g,
        (match, quote, path, secondArg) => {
          needsBase = true;
          return `goto(\`\${base}${path}\`${secondArg || ''})`;
        }
      );

      // Transform goto(`/...`) in inline event handlers in markup (template literal)
      modified = modified.replace(
        /\bgoto\(\s*\x60(\/[a-z])/g,
        (match, pathStart) => {
          needsBase = true;
          return `goto(\`\${base}${pathStart}`;
        }
      );

      // Transform location.href = '/...' inside inline event handlers in markup
      modified = modified.replace(
        /\blocation\.href\s*=\s*(['"])(\/[^'"]*)\1/g,
        (match, quote, path) => {
          needsBase = true;
          return `location.href = \`\${base}${path}\``;
        }
      );

      // Transform location.href = expr ?? '/...' in markup
      modified = modified.replace(
        /\blocation\.href\s*=\s*([^{]+?)\s*\?\?\s*(['"\x60])(\/[^'"\x60]*)\2/g,
        (match, fallback, quote, path) => {
          needsBase = true;
          return `location.href = ${fallback} ?? \`\${base}${path}\``;
        }
      );

      // Transform window.history.replaceState with template literals in markup
      modified = modified.replace(
        /window\.history\.replaceState\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*\x60(\/[a-z])/g,
        (match, state, title, pathStart) => {
          needsBase = true;
          return `window.history.replaceState(${state}, ${title}, \`\${base}${pathStart}`;
        }
      );

      // Transform on:error image fallback handlers in markup
      // Handles: on:error={(e) => { e.currentTarget.src = '/favicon.png'; }}
      // Handles: on:error={(e) => { e.target.src = '/favicon.png'; }}
      // Handles: on:error={(e) => (e.target.src = '/user.png')}
      for (const target of ['currentTarget', 'target']) {
        for (const [origPath, newPath] of [
          ['/favicon.png', '/static/favicon.png'],
          ['/user.png', '/static/user.png']
        ]) {
          // Multi-line form: on:error={(e) => { e.currentTarget.src = '/favicon.png'; }}
          const multiLineRegex = new RegExp(
            `on:error=\\{\\(e\\)\\s*=>\\s*\\{\\s*e\\.${target}\\.src\\s*=\\s*(['"])${escapeRegex(origPath)}\\1\\s*;?\\s*\\}\\}`,
            'g'
          );
          modified = modified.replace(multiLineRegex, () => {
            needsBase = true;
            return `on:error={(e) => { e.${target}.src = \`\${base}${newPath}\`; }}`;
          });

          // Inline parenthesized form: on:error={(e) => (e.target.src = '/user.png')}
          const inlineRegex = new RegExp(
            `on:error=\\{\\(e\\)\\s*=>\\s*\\(e\\.${target}\\.src\\s*=\\s*(['"])${escapeRegex(origPath)}\\1\\)\\}`,
            'g'
          );
          modified = modified.replace(inlineRegex, () => {
            needsBase = true;
            return `on:error={(e) => (e.${target}.src = \`\${base}${newPath}\`)}`;
          });
        }
      }

      // Catch-all: transform template literals starting with /path in markup
      // Handles patterns like: condition ? `/path/${var}` : `/other/${var}`
      // and href={...`/path/...`...}, ternary expressions in Svelte markup
      // Must run BEFORE the needsBase check so files with only template-literal
      // paths (no href="/..." or goto('/...')) are still transformed.
      modified = modified.replace(
        /\x60(\/[a-z])/g,
        (match, pathStart) => {
          needsBase = true;
          return `\`\${base}${pathStart}`;
        }
      );

      if (!needsBase) return undefined;

      // Inject base import into <script> tag
      const hasBaseImport = /import\s*\{[^}]*base[^}]*\}\s*from\s*['"]\$app\/paths['"]/.test(modified);
      if (!hasBaseImport) {
        let replaced = false;
        modified = modified.replace(
          /<script(?![^>]*\bcontext\s*=\s*["']module["'])([^>]*)>\n/,
          (match, attrs) => {
            replaced = true;
            return `<script${attrs}>\n\timport { base } from '$app/paths';\n`;
          }
        );
        if (!replaced) {
          modified = modified.replace(
            /<script([^>]*)>\n/,
            (match, attrs) => {
              return `<script${attrs}>\n\timport { base } from '$app/paths';\n`;
            }
          );
        }
      }

      return { code: modified };
    }
  };
}