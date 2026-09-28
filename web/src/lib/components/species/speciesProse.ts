// Mise en prose de la fiche rédactionnelle (contrat §6.9 / §8.3) pour la section « À propos » :
// introduction découpée en paragraphes, phrases pour le statut migratoire et le rythme de vie,
// et nettoyage des mentions techniques que les fiches générées glissent parfois (« score
// BirdNET maximal de 0,33 », « le modèle de zone ne franchit le seuil… ») — la fiche doit se
// lire sans rien connaître à BirdNET ni à l'informatique.

import type { ActivityPattern, MigrationStatut, SpeciesDetail } from '../../api/types';
import { capitalizeFirst, type SpeciesNoun } from './frenchGrammar';

// Mentions à retirer (le passage entier qui les contient disparaît).
const TECHNICAL_PASSAGE =
  /\bscores?\b|\bseuils?\b|modèles? de (zone|détection)|\bce modèle\b|modèle utilisé|couvert\w* par (le|ce) modèle/i;
// Mentions à reformuler : l'outil de détection devient « l'appareil ».
const DEVICE_MENTION = /\b(BirdNET(?:-Go)?|le modèle)\b/g;

/** Découpe un texte en phrases (le point final reste attaché à sa phrase). */
export function splitSentences(text: string): string[] {
  return text
    .trim()
    .split(/(?<=[.!?…])\s+(?=[«"A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŒ0-9])/u)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function ensureFinalPunctuation(sentence: string): string {
  return /[.!?…»]$/.test(sentence) ? sentence : `${sentence}.`;
}

function cleanSentence(sentence: string): string {
  const parts = sentence.split(/(\s*[;:]\s+)/);
  const kept: string[] = [];
  for (let i = 0; i < parts.length; i += 2) {
    const clause = parts[i] ?? '';
    if (!clause.trim() || TECHNICAL_PASSAGE.test(clause)) continue;
    if (kept.length > 0) kept.push(parts[i - 1] ?? ' ; ');
    kept.push(clause);
  }
  const rebuilt = kept.join('').trim();
  if (!rebuilt) return '';
  return ensureFinalPunctuation(capitalizeFirst(rebuilt.replace(/[,;:]\s*$/, '')));
}

/**
 * Retire d'un texte de fiche les passages techniques (scores, seuils, « modèle de zone ») et
 * remplace les mentions de BirdNET par « l'appareil ». Renvoie `''` s'il ne reste rien.
 */
export function plainFr(text: string | null | undefined): string {
  if (!text) return '';
  const withoutParentheses = text.replace(/\s*\(([^()]*)\)/g, (match, inner: string) =>
    TECHNICAL_PASSAGE.test(inner) || /birdnet/i.test(inner) ? '' : match,
  );
  const sentences = splitSentences(withoutParentheses)
    .map(cleanSentence)
    .filter(Boolean)
    .map((sentence) =>
      sentence
        .replace(DEVICE_MENTION, "l'appareil")
        .replace(/(^|[.!?]\s+)l'appareil/g, (_match, before: string) => `${before}L'appareil`),
    );
  return sentences.join(' ').trim();
}

export interface Introduction {
  /** Premier paragraphe, mis en valeur (1 ou 2 phrases). */
  lead: string;
  /** Paragraphes suivants (2 à 3 phrases chacun). */
  rest: string[];
}

const LEAD_MAX_CHARS = 230;
const PARAGRAPH_TARGET_CHARS = 320;

/** Transforme le résumé d'un seul bloc en une vraie introduction : chapeau + paragraphes. */
export function buildIntroduction(summary: string): Introduction {
  const sentences = splitSentences(plainFr(summary));
  const first = sentences.shift() ?? '';
  let lead = first;
  const second = sentences[0];
  if (second && lead.length + second.length + 1 <= LEAD_MAX_CHARS) {
    lead = `${lead} ${second}`;
    sentences.shift();
  }
  const rest: string[] = [];
  let current = '';
  for (const sentence of sentences) {
    current = current ? `${current} ${sentence}` : sentence;
    if (current.length >= PARAGRAPH_TARGET_CHARS) {
      rest.push(current);
      current = '';
    }
  }
  if (current) {
    // Une phrase orpheline en fin de texte rejoint le paragraphe précédent.
    if (rest.length > 0 && current.length < PARAGRAPH_TARGET_CHARS / 2) rest[rest.length - 1] += ` ${current}`;
    else rest.push(current);
  }
  return { lead, rest };
}

const STATUT_SENTENCES: Record<MigrationStatut, string> = {
  sédentaire: "En France, c'est un oiseau sédentaire : il reste toute l'année dans la même région.",
  'migrateur partiel':
    "En France, c'est un migrateur partiel : une partie des oiseaux reste toute l'année, les autres voyagent au fil des saisons.",
  migrateur: "C'est un oiseau migrateur : il ne passe qu'une partie de l'année en France.",
  hivernant: "En France, c'est surtout un visiteur d'hiver : il arrive à l'automne et repart au printemps.",
  estivant: "En France, c'est un visiteur d'été : il arrive au printemps pour nicher et repart à la fin de l'été.",
  'de passage': "En France, c'est surtout un oiseau de passage, que l'on croise pendant ses migrations.",
};

export function statutSentence(statut: MigrationStatut): string {
  return STATUT_SENTENCES[statut];
}

const ACTIVITY_SENTENCES: Record<ActivityPattern, string> = {
  diurne: "C'est un oiseau de jour : il est actif, et se fait entendre, surtout entre le lever et le coucher du soleil.",
  nocturne: "C'est un oiseau de nuit : il est actif, et se fait entendre, surtout après le coucher du soleil.",
  crépusculaire:
    "C'est un oiseau du crépuscule : il est surtout actif, et se fait surtout entendre, à l'aube et à la tombée de la nuit.",
  mixte: "C'est un oiseau actif de jour comme de nuit : on peut l'entendre à toute heure.",
};

export function activitySentence(pattern: ActivityPattern): string {
  return ACTIVITY_SENTENCES[pattern];
}

// Un texte de migration qui parle déjà de son sujet dans ses premiers mots se lit seul
// (« Hiverne en Afrique… », « Passages marqués en mars… ») ; sinon (« Afrique subsaharienne,
// au sud du Sahara ») on le fait précéder d'une question qui lui donne son sens.
const FIRST_WORDS = 8;
const SELF_EXPLANATORY = {
  hiverne: /hivern|hiver/i,
  niche: /nich|reprodu|nidif|couv/i,
  passage: /passage|migr|arriv|départ|retour|mouvement|dispersion|travers|halte|irruption|erratique|vagabond/i,
};

function firstWords(text: string): string {
  return text.split(/\s+/).slice(0, FIRST_WORDS).join(' ');
}

function migrationSentence(kind: keyof typeof SELF_EXPLANATORY, raw: string | null, noun: SpeciesNoun): string {
  const text = plainFr(raw);
  if (!text) return '';
  if (SELF_EXPLANATORY[kind].test(firstWords(text))) return text;
  const question =
    kind === 'hiverne'
      ? `Où passe-t-${noun.pronoun} l'hiver ?`
      : kind === 'niche'
        ? `Où et quand niche-t-${noun.pronoun} ?`
        : `Quand ${noun.object} voit-on passer ?`;
  return `${question} ${text}`;
}

export interface AboutLookalike {
  scientificName: string;
  name: string;
  why: string;
  hasPage: boolean;
}

/** Tout le texte de la section « À propos », déjà nettoyé ; une chaîne vide / un tableau vide
 *  = sous-section absente (la page s'en sert aussi pour le sommaire). */
export interface AboutContent {
  intro: Introduction | null;
  where: string;
  diet: string;
  activity: string;
  migration: string[];
  song: string;
  lookalikes: AboutLookalike[];
  facts: string[];
}

export function aboutContent(detail: SpeciesDetail, noun: SpeciesNoun): AboutContent {
  if (!detail.has_sheet) {
    return { intro: null, where: '', diet: '', activity: '', migration: [], song: '', lookalikes: [], facts: [] };
  }
  return {
    intro: detail.summary_fr ? buildIntroduction(detail.summary_fr) : null,
    where: [plainFr(detail.habitat), plainFr(detail.rarity_note)].filter(Boolean).join(' '),
    diet: plainFr(detail.diet),
    activity: detail.activity_pattern ? activitySentence(detail.activity_pattern) : '',
    migration: migrationParagraphs(detail, noun),
    song: plainFr(detail.song_fr),
    lookalikes: detail.lookalikes.map((lookalike) => ({
      scientificName: lookalike.scientific_name,
      name: lookalike.common_name_fr ?? lookalike.scientific_name,
      why: plainFr(lookalike.why_fr),
      hasPage: lookalike.has_page,
    })),
    facts: detail.fun_facts.map(plainFr).filter(Boolean),
  };
}

/** Section « Migration et saisons » en paragraphes (jamais d'étiquettes « Hiverne : … »). */
export function migrationParagraphs(detail: SpeciesDetail, noun: SpeciesNoun): string[] {
  const paragraphs: string[] = [];
  const first = [detail.migration ? statutSentence(detail.migration.statut) : '', plainFr(detail.seasonality_fr)]
    .filter(Boolean)
    .join(' ');
  if (first) paragraphs.push(first);
  if (detail.migration) {
    const second = [
      migrationSentence('hiverne', detail.migration.hiverne, noun),
      migrationSentence('niche', detail.migration.niche, noun),
      migrationSentence('passage', detail.migration.passage, noun),
    ]
      .filter(Boolean)
      .join(' ');
    if (second) paragraphs.push(second);
  }
  return paragraphs;
}
