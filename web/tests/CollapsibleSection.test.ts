// CollapsibleSection (bien commun, src/lib/components/ui/). Deux défauts corrigés :
// 1. la classe « ouvert » n'était jamais posée selon isOpen, alors que le CSS
//    (src/styles/tailwind.css) n'affiche le contenu qu'avec elle ;
// 2. la racine portait la classe `collapse`, qui est AUSSI un utilitaire Tailwind v4
//    (`visibility: collapse`) : tout le bloc, en-tête compris, était invisible.
// jsdom ne calcule pas le CSS Tailwind : on vérifie donc (a) le comportement du composant
// et (b) que chaque classe dont il dépend est bien définie dans tailwind.css.
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import CollapsibleSection from '../src/lib/components/ui/CollapsibleSection.svelte';

const content = createRawSnippet(() => ({ render: () => '<p>Contenu du déplié</p>' }));

// Svelte pose `inert` par la propriété DOM (reflétée en attribut par les navigateurs,
// pas par jsdom) : on accepte l'une ou l'autre.
function isInert(element: HTMLElement | null): boolean {
  return element !== null && (element.inert === true || element.hasAttribute('inert'));
}

function rootOf(button: HTMLElement): HTMLElement {
  const root = button.parentElement;
  if (!root) throw new Error('racine introuvable');
  return root;
}

describe('CollapsibleSection', () => {
  afterEach(() => cleanup());

  it("affiche toujours l'en-tête (titre + flèche) et reste replié par défaut", () => {
    render(CollapsibleSection, { title: 'Spectrogramme en direct', children: content });

    const button = screen.getByRole('button', { name: /Spectrogramme en direct/ });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button.querySelector('svg')).not.toBeNull();

    const root = rootOf(button);
    expect(root).not.toHaveClass('collapsible-open');
    const region = document.getElementById(button.getAttribute('aria-controls') ?? '');
    expect(region).not.toBeNull();
    expect(region).toHaveAttribute('aria-hidden', 'true');
    expect(isInert(region)).toBe(true);
  });

  it("n'utilise jamais la classe `collapse` (utilitaire Tailwind visibility: collapse)", () => {
    render(CollapsibleSection, { title: 'Titre', children: content });
    const root = rootOf(screen.getByRole('button', { name: /Titre/ }));
    expect(root).not.toHaveClass('collapse');
    for (const element of root.querySelectorAll('*')) {
      expect(element.classList.contains('collapse')).toBe(false);
    }
  });

  it('pose la classe « ouvert » et rend le contenu accessible au clic, puis la retire', async () => {
    render(CollapsibleSection, { title: 'Commandes (2)', children: content });
    const button = screen.getByRole('button', { name: /Commandes \(2\)/ });
    const root = rootOf(button);
    const region = document.getElementById(button.getAttribute('aria-controls') ?? '');

    await fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(root).toHaveClass('collapsible-open');
    expect(region).toHaveAttribute('aria-hidden', 'false');
    expect(isInert(region)).toBe(false);
    expect(screen.getByText('Contenu du déplié')).toBeInTheDocument();

    await fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(root).not.toHaveClass('collapsible-open');
  });

  it('respecte defaultOpen', () => {
    render(CollapsibleSection, { title: 'Ouvert', defaultOpen: true, children: content });
    const button = screen.getByRole('button', { name: /Ouvert/ });
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(rootOf(button)).toHaveClass('collapsible-open');
  });

  it('donne un identifiant de contenu unique à deux sections de même titre', () => {
    render(CollapsibleSection, { title: 'Commandes (1)', children: content });
    render(CollapsibleSection, { title: 'Commandes (1)', children: content });
    const ids = screen.getAllByRole('button', { name: /Commandes \(1\)/ }).map((b) => b.getAttribute('aria-controls'));
    expect(ids).toHaveLength(2);
    expect(ids[0]).not.toBe(ids[1]);
  });

  it('chaque classe utilisée par le composant est définie dans tailwind.css, contenu affiché seulement ouvert', () => {
    const css = readFileSync(path.join(process.cwd(), 'src/styles/tailwind.css'), 'utf-8');
    expect(css).toMatch(/\.collapsible\s*\{/);
    expect(css).toMatch(/\.collapsible-title\s*\{/);
    const closed = /\.collapsible-content\s*\{([^}]*)\}/.exec(css)?.[1] ?? '';
    const open = /\.collapsible-open \.collapsible-content\s*\{([^}]*)\}/.exec(css)?.[1] ?? '';
    expect(closed).toMatch(/max-height:\s*0/);
    expect(open).toMatch(/max-height:\s*(?!0)[\d.]+/);
    // Aucune règle composant `.collapse {` : elle serait écrasée par l'utilitaire Tailwind.
    expect(css).not.toMatch(/^\s*\.collapse\s*\{/m);
  });
});
