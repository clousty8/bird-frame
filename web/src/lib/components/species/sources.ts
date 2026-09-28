// Liste « Sources » de la fiche espèce (contrat §6.9 : `wikipedia.{fr,en}` + `sources`).
//
// Les fiches rédactionnelles citent presque toujours les mêmes pages Wikipédia que la base :
// afficher les deux listes bout à bout répétait chaque URL (une fois libellée « Wikipédia
// (FR) », une fois en brut). On construit donc une liste unique : Wikipédia FR puis EN en
// tête, avec libellé, puis seulement les AUTRES sources, dédoublonnées, libellées par leur
// nom d'hôte. Les sources viennent de fiches générées par IA : seules les URLs http(s)
// deviennent des liens (une autre valeur reste affichée en texte, jamais cliquable).

import type { WikiRef } from '../../api/types';

export interface SourceLink {
  /** URL cliquable, ou `null` si la valeur n'est pas une URL http(s) valide. */
  href: string | null;
  /** Texte affiché. */
  label: string;
  /** Texte d'infobulle (URL complète). */
  title: string;
}

function parseHttpUrl(raw: string): URL | null {
  try {
    const url = new URL(raw.trim());
    return url.protocol === 'http:' || url.protocol === 'https:' ? url : null;
  } catch {
    return null;
  }
}

function decodeSafe(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** Clé de comparaison : insensible au schéma, à `www.`/`m.` (Wikipédia mobile), à la casse
 *  de l'hôte, au fragment, à la barre finale, à l'encodage et à `_` vs espace. */
export function sourceKey(raw: string): string {
  const url = parseHttpUrl(raw);
  if (!url) return raw.trim();
  const host = url.hostname.toLowerCase().replace(/^www\./, '').replace(/\.m\.wikipedia\.org$/, '.wikipedia.org');
  const path = decodeSafe(url.pathname).replace(/_/g, ' ').replace(/\/+$/, '');
  return `${host}${path}${url.search}`;
}

function hostLabel(url: URL): string {
  return url.hostname.toLowerCase().replace(/^www\./, '');
}

function wikipediaLabel(url: URL): string | null {
  const match = /^([a-z-]+)\.(?:m\.)?wikipedia\.org$/.exec(url.hostname.toLowerCase());
  if (!match || !match[1]) return null;
  const title = decodeSafe(url.pathname.replace(/^\/wiki\//, '')).replace(/_/g, ' ');
  return `Wikipédia (${match[1].toUpperCase()}) — ${title}`;
}

export function buildSourceLinks(
  wikipedia: { fr: WikiRef | null; en: WikiRef | null },
  sources: readonly string[],
): SourceLink[] {
  const links: SourceLink[] = [];
  const seen = new Set<string>();

  const wikiEntries: [WikiRef | null, string][] = [
    [wikipedia.fr, 'Wikipédia (FR)'],
    [wikipedia.en, 'Wikipédia (EN)'],
  ];
  for (const [ref, label] of wikiEntries) {
    const url = ref?.url ? parseHttpUrl(ref.url) : null;
    if (!url || !ref?.url) continue;
    const key = sourceKey(ref.url);
    if (seen.has(key)) continue;
    seen.add(key);
    links.push({ href: url.href, label, title: ref.url });
  }

  for (const raw of sources) {
    const trimmed = raw.trim();
    if (!trimmed) continue;
    const key = sourceKey(trimmed);
    if (seen.has(key)) continue;
    seen.add(key);
    const url = parseHttpUrl(trimmed);
    if (!url) {
      links.push({ href: null, label: trimmed, title: trimmed });
      continue;
    }
    links.push({ href: url.href, label: wikipediaLabel(url) ?? hostLabel(url), title: trimmed });
  }

  // Deux autres sources sur le même hôte (ex. deux pages oiseaux.net) : on complète le
  // libellé par le chemin pour les distinguer.
  const labelCounts = new Map<string, number>();
  for (const link of links) labelCounts.set(link.label, (labelCounts.get(link.label) ?? 0) + 1);
  return links.map((link) => {
    if (!link.href || (labelCounts.get(link.label) ?? 0) < 2) return link;
    const url = new URL(link.href);
    const detail = decodeSafe(`${url.pathname}${url.search}`).replace(/^\/+/, '');
    return detail ? { ...link, label: `${link.label} — ${detail}` } : link;
  });
}
