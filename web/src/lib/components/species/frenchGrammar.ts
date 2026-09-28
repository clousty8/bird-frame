// Petite grammaire française pour les phrases générées de la fiche espèce (« À Pornic, la Pie
// bavarde est très courante toute l'année », « Au Mans, … », « d'avril à août »…).
//
// Le genre d'un nom d'oiseau est celui de son premier mot (« Pie » dans « Pie bavarde »,
// « Martinet » dans « Martinet noir »). Les listes ci-dessous couvrent tous les premiers mots
// des 368 noms de l'univers France (species-data/species_universe_fr.json, 28/09/2026). Un
// premier mot inconnu (espèce hors univers) retombe sur « cette espèce » : jamais de faute
// d'accord inventée.

import { MONTH_NAMES } from './months';

const FEMININE_HEADS = new Set([
  'Aigrette', 'Alouette', 'Avocette', 'Barge', 'Bergeronnette', 'Bernache', 'Bondrée', 'Bouscarle',
  'Buse', 'Bécasse', 'Bécassine', 'Caille', 'Chevêche', 'Chevêchette', 'Chouette', 'Cigogne',
  'Cisticole', 'Conure', 'Corneille', 'Effraie', 'Fauvette', 'Foulque', 'Gallinule', 'Glaréole',
  'Gorgebleue', 'Grande', 'Grive', 'Grue', 'Guifette', 'Gélinotte', 'Harelde', 'Hirondelle', 'Huppe',
  'Hypolaïs', 'Linotte', 'Locustelle', 'Lusciniole', 'Macreuse', 'Marouette', 'Mouette', 'Mésange',
  'Nette', 'Niverolle', 'Nyctale', 'Océanite', 'Oie', 'Orite', 'Ouette', 'Outarde', 'Panure',
  'Paruline', 'Perdrix', 'Perruche', 'Petite', 'Pie', 'Pie-grièche', 'Rousserolle', 'Rémiz',
  'Sarcelle', 'Sittelle', 'Spatule', 'Sterne', 'Talève', 'Tourterelle', 'Échasse', 'Érismature',
]);

const MASCULINE_HEADS = new Set([
  'Accenteur', 'Aigle', 'Autour', 'Balbuzard', 'Bec-croisé', 'Bihoreau', 'Blongios', 'Bouvreuil',
  'Bruant', 'Busard', 'Butor', 'Bécasseau', 'Bécassin', 'Canard', 'Capucin', 'Cassenoix',
  'Chardonneret', 'Chevalier', 'Chocard', 'Choucas', 'Cincle', 'Circaète', 'Cochevis', 'Colin',
  'Combattant', 'Corbeau', 'Cormoran', 'Coucou', 'Courlis', 'Crabier', 'Crave', 'Cygne', 'Eider',
  'Engoulevent', 'Faisan', 'Faucon', 'Flamant', 'Fou', 'Fuligule', 'Fulmar', 'Garrot', 'Geai',
  'Gobemouche', 'Goéland', 'Grand', 'Grand-duc', 'Gravelot', 'Grimpereau', 'Gros-bec', 'Grèbe',
  'Guillemot', 'Guêpier', 'Harle', 'Hibou', 'Huîtrier', 'Héron', 'Ibis', 'Jaseur', 'Junco', 'Labbe',
  'Loriot', 'Léiothrix', 'Macareux', 'Martin-pêcheur', 'Martinet', 'Merle', 'Milan', 'Moineau',
  'Monticole', 'Oedicnème', 'Petit', 'Petit-duc', 'Phalarope', 'Phragmite', 'Pic', 'Pigeon',
  'Pinson', 'Pipit', 'Plectrophane', 'Plongeon', 'Pluvier', 'Pouillot', 'Puffin', 'Pygargue',
  'Roitelet', 'Rollier', 'Rossignol', 'Rougegorge', 'Rougequeue', 'Râle', 'Serin', 'Sizerin',
  'Tadorne', 'Tarier', 'Tarin', 'Tichodrome', 'Torcol', 'Tournepierre', 'Traquet', 'Troglodyte',
  'Tétras', 'Vanneau', 'Vautour', 'Venturon', 'Verdier', 'Élanion', 'Épervier', 'Étourneau',
]);

// « le Héron », « la Huppe » : h aspiré, pas d'élision. Les autres h sont muets (« l'Hirondelle »).
const ASPIRATED_H = new Set(['Harelde', 'Harfang', 'Harle', 'Hibou', 'Huppe', 'Héron']);

const VOWEL_START = /^[aeiouyàâäéèêëîïôöùûüœæ]/i;

export interface SpeciesNoun {
  /** Groupe nominal avec article défini : « le Martinet noir », « l'Effraie des clochers »,
   *  ou « cette espèce » quand le genre du nom est inconnu. */
  withArticle: string;
  feminine: boolean;
  /** Pronom sujet : « il » / « elle ». */
  pronoun: 'il' | 'elle';
  /** Pronom complément devant consonne : « le » / « la » (« on ne le croise que… »). */
  object: 'le' | 'la';
}

const FALLBACK_NOUN: SpeciesNoun = { withArticle: 'cette espèce', feminine: true, pronoun: 'elle', object: 'la' };

function startsWithElision(word: string): boolean {
  if (VOWEL_START.test(word)) return true;
  return /^h/i.test(word) && !ASPIRATED_H.has(word);
}

/** Article, genre et pronoms d'un nom d'oiseau français (voir l'en-tête du fichier). */
export function speciesNoun(commonName: string | null): SpeciesNoun {
  const name = commonName?.trim();
  if (!name) return FALLBACK_NOUN;
  const head = name.split(/\s+/)[0] ?? '';
  const feminine = FEMININE_HEADS.has(head);
  if (!feminine && !MASCULINE_HEADS.has(head)) return FALLBACK_NOUN;
  const article = startsWithElision(head) ? "l'" : feminine ? 'la ' : 'le ';
  return {
    withArticle: `${article}${name}`,
    feminine,
    pronoun: feminine ? 'elle' : 'il',
    object: feminine ? 'la' : 'le',
  };
}

/** Accorde un adjectif ou participe régulier : « courant » → « courante », « rare » → « rare ». */
export function agree(word: string, feminine: boolean): string {
  if (!feminine || word.endsWith('e')) return word;
  return `${word}e`;
}

export function capitalizeFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** « à Pornic », « au Mans », « aux Sables-d'Olonne ». */
export function atPlace(name: string): string {
  const trimmed = name.trim();
  if (/^Le\s+/.test(trimmed)) return `au ${trimmed.replace(/^Le\s+/, '')}`;
  if (/^Les\s+/.test(trimmed)) return `aux ${trimmed.replace(/^Les\s+/, '')}`;
  return `à ${trimmed}`;
}

/** « de Pornic », « du Mans », « des Sables-d'Olonne », « d'Ajaccio ». */
export function ofPlace(name: string): string {
  const trimmed = name.trim();
  if (/^Le\s+/.test(trimmed)) return `du ${trimmed.replace(/^Le\s+/, '')}`;
  if (/^Les\s+/.test(trimmed)) return `des ${trimmed.replace(/^Les\s+/, '')}`;
  return startsWithElision(trimmed) ? `d'${trimmed}` : `de ${trimmed}`;
}

/** Nom du mois (index 0 = janvier), en minuscules. */
export function monthName(index: number): string {
  return MONTH_NAMES[((index % 12) + 12) % 12] ?? '';
}

/** « en mai », « de mai à juillet », « d'avril à août », « d'octobre à mars ». */
export function monthRangePhrase(start: number, end: number): string {
  const first = monthName(start);
  if (start === end) return `en ${first}`;
  const from = VOWEL_START.test(first) ? `d'${first}` : `de ${first}`;
  return `${from} à ${monthName(end)}`;
}

/** Relie des éléments : « a », « a et b », « a, b et c ». */
export function joinWithEt(parts: readonly string[]): string {
  if (parts.length <= 1) return parts[0] ?? '';
  return `${parts.slice(0, -1).join(', ')} et ${parts[parts.length - 1]}`;
}
