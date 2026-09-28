// Section « Peut-on l'entendre à … ? » de la fiche espèce : traduit `local_presence` (contrat
// §6.9 — un niveau qualitatif par mois, d'après les observations naturalistes autour de la
// ville de référence la plus proche du site) en phrases simples, pour quelqu'un qui ne
// connaît ni les oiseaux, ni BirdNET, ni l'informatique : aucun score, aucun pourcentage,
// aucun terme technique.

import type { LocalPresence, PresenceLevel } from '../../api/types';
import {
  agree,
  atPlace,
  capitalizeFirst,
  joinWithEt,
  monthName,
  monthRangePhrase,
  ofPlace,
  type SpeciesNoun,
} from './frenchGrammar';

/** Du plus fréquent au moins fréquent (ordre de la légende). */
export const PRESENCE_LEVELS: readonly PresenceLevel[] = ['tres_courant', 'courant', 'peu_frequent', 'rare', 'absent'];

export const PRESENCE_LEVEL_LABELS: Record<PresenceLevel, string> = {
  tres_courant: 'Très courant',
  courant: 'Courant',
  peu_frequent: 'Peu fréquent',
  rare: 'Rare',
  absent: 'Absent',
};

const RANK: Record<PresenceLevel, number> = { absent: 0, rare: 1, peu_frequent: 2, courant: 3, tres_courant: 4 };

/** Au-delà, la phrase précise de quelle ville viennent les observations. */
export const FAR_REFERENCE_KM = 80;

/**
 * Suites de mois consécutifs (le calendrier boucle : octobre → mars est une seule suite) pour
 * lesquels `flags[i]` est vrai. Chaque suite = [premier mois, dernier mois] (index 0-11), triées
 * par premier mois. Tous vrais → [[0, 11]] ; aucun → [].
 */
export function monthRuns(flags: readonly boolean[]): [number, number][] {
  if (flags.length !== 12) return [];
  if (flags.every(Boolean)) return [[0, 11]];
  const firstOff = flags.findIndex((flag) => !flag);
  if (firstOff === -1) return [[0, 11]];
  const runs: [number, number][] = [];
  let start: number | null = null;
  for (let step = 1; step <= 12; step += 1) {
    const index = (firstOff + step) % 12;
    if (flags[index]) {
      if (start === null) start = index;
    } else if (start !== null) {
      runs.push([start, (index + 11) % 12]);
      start = null;
    }
  }
  return runs.sort((a, b) => a[0] - b[0]);
}

/** « de mai à juillet », « en mai et d'août à septembre ». */
export function runsPhrase(runs: readonly [number, number][]): string {
  return joinWithEt(runs.map(([start, end]) => monthRangePhrase(start, end)));
}

function adviceAfterColon(level: PresenceLevel, noun: SpeciesNoun): string {
  const heard = agree('entendu', noun.feminine);
  switch (level) {
    case 'tres_courant':
      return 'une détection est tout à fait normale';
    case 'courant':
      return 'une détection est normale';
    case 'peu_frequent':
      return "une détection reste possible, mais réécoutez l'enregistrement en cas de doute";
    case 'rare':
      return `si l'appareil dit l'avoir ${heard}, réécoutez l'enregistrement pour vérifier`;
    case 'absent':
      return `si l'appareil dit l'avoir ${heard}, c'est sans doute une confusion avec un autre oiseau ; réécoutez l'enregistrement pour vérifier`;
  }
}

function currentMonthClause(level: PresenceLevel, noun: SpeciesNoun): string {
  const f = noun.feminine;
  switch (level) {
    case 'tres_courant':
      return `${noun.pronoun} est ${agree('très courant', f)}`;
    case 'courant':
      return `${noun.pronoun} est ${agree('courant', f)}`;
    case 'peu_frequent':
      return `${noun.pronoun} est ${agree('peu fréquent', f)}`;
    case 'rare':
      return `on ne ${noun.object} croise que très rarement`;
    case 'absent':
      return `on ne ${noun.object} croise pour ainsi dire jamais`;
  }
}

function levelAdjective(level: PresenceLevel, feminine: boolean): string {
  return agree(PRESENCE_LEVEL_LABELS[level].toLowerCase(), feminine);
}

/**
 * Phrases de conclusion, par ex. :
 * - « À Pornic, le Rougegorge familier est très courant toute l'année : une détection est tout à fait normale. »
 * - « À Pornic, le Martinet noir est présent d'avril à août, surtout de mai à juillet. En septembre, on ne le
 *   croise que très rarement : si l'appareil dit l'avoir entendu, réécoutez l'enregistrement pour vérifier. »
 */
export function describeLocalPresence(presence: LocalPresence, noun: SpeciesNoun, siteName: string): string[] {
  const levels = presence.monthly_levels;
  const ranks = levels.map((level) => RANK[level]);
  const minRank = Math.min(...ranks);
  const maxRank = Math.max(...ranks);
  const f = noun.feminine;

  const source =
    presence.reference_city.distance_km > FAR_REFERENCE_KM
      ? `, d'après les observations autour ${ofPlace(presence.reference_city.name)},`
      : ',';
  const opening = `${capitalizeFirst(atPlace(siteName))}${source} ${noun.withArticle}`;
  const runsWhere = (predicate: (rank: number) => boolean) => runsPhrase(monthRuns(ranks.map(predicate)));

  // Même niveau toute l'année : une seule phrase, conseil compris.
  if (minRank === maxRank) {
    const level = levels[0] ?? 'absent';
    const state =
      level === 'absent'
        ? `n'est pour ainsi dire jamais ${agree('observé', f)}`
        : `est ${levelAdjective(level, f)} toute l'année`;
    return [`${opening} ${state} : ${adviceAfterColon(level, noun)}.`];
  }

  let summary: string;
  if (maxRank <= RANK.rare) {
    summary = `${opening} est très rarement ${agree('observé', f)}, surtout ${runsWhere((r) => r >= RANK.rare)}.`;
  } else if (minRank >= RANK.courant) {
    summary = `${opening} est ${agree('courant', f)} toute l'année, et même ${agree('très courant', f)} ${runsWhere((r) => r === RANK.tres_courant)}.`;
  } else if (minRank === RANK.peu_frequent) {
    summary = `${opening} est ${agree('présent', f)} toute l'année, surtout ${runsWhere((r) => r >= RANK.courant)}.`;
  } else {
    // Saisonnier : présent (≥ peu fréquent) une partie de l'année seulement.
    const presentRanks = ranks.filter((r) => r >= RANK.peu_frequent);
    const presentPhrase = runsWhere((r) => r >= RANK.peu_frequent);
    if (presentRanks.every((r) => r === presentRanks[0])) {
      const level = levels.find((l) => RANK[l] >= RANK.peu_frequent) ?? 'peu_frequent';
      summary = `${opening} est ${levelAdjective(level, f)} ${presentPhrase}.`;
    } else {
      summary = `${opening} est ${agree('présent', f)} ${presentPhrase}, surtout ${runsWhere((r) => r === maxRank)}.`;
    }
  }

  const current = presence.current_month_level;
  const advice = `En ${monthName(presence.current_month - 1)}, ${currentMonthClause(current, noun)} : ${adviceAfterColon(current, noun)}.`;
  return [summary, advice];
}

/** Période de présence en quelques mots, pour l'encadré « En bref » : « Toute l'année »,
 *  « D'avril à août », « Rarement observé ». */
export function presencePeriodLabel(presence: LocalPresence, noun: SpeciesNoun): string {
  const flags = presence.monthly_levels.map((level) => RANK[level] >= RANK.peu_frequent);
  if (flags.every(Boolean)) return "Toute l'année";
  if (!flags.some(Boolean)) return capitalizeFirst(`rarement ${agree('observé', noun.feminine)}`);
  return capitalizeFirst(runsPhrase(monthRuns(flags)));
}
