// Vérifie la mécanique de licence décrite dans docs/architecture.md §0.3 : chaque fichier
// listé dans NOTICE.md existe bien et porte l'en-tête de licence attendu. Empêche toute
// dérive silencieuse (fichier copié puis renommé/supprimé sans mettre à jour NOTICE.md,
// ou en-tête oublié).
import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';

// process.cwd() = racine de web/ (là où tourne `npm run test`, cf. vite.config.ts).
const WEB_ROOT = process.cwd();
const REPO_ROOT = path.resolve(WEB_ROOT, '..');

function listedFilesFromNotice(): string[] {
  const noticeContent = readFileSync(path.join(WEB_ROOT, 'NOTICE.md'), 'utf-8');
  const rows = noticeContent
    .split('\n')
    .filter((line) => line.startsWith('| `web/'))
    .map((line) => {
      const match = line.match(/^\|\s*`([^`]+)`/);
      return match?.[1];
    })
    .filter((value): value is string => value !== undefined);
  return rows;
}

describe('NOTICE.md — conformité licence (architecture.md §0.3)', () => {
  const files = listedFilesFromNotice();

  it('liste au moins un fichier', () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it.each(files)('%s existe et porte l\'en-tête de licence CC BY-NC-SA 4.0', (relativePath) => {
    const absolutePath = path.join(REPO_ROOT, relativePath);
    expect(existsSync(absolutePath)).toBe(true);

    const content = readFileSync(absolutePath, 'utf-8');
    const head = content.split('\n').slice(0, 6).join('\n');
    expect(head).toMatch(/Adapté de BirdNET-Go/);
    expect(head).toMatch(/CC BY-NC-SA 4\.0/);
    expect(head).toMatch(/NOTICE\.md/);
  });
});
