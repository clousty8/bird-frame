// Fiche espèce v0.2 : grammaire des phrases générées, présence locale en mots, mise en prose
// de la fiche rédactionnelle (sans jargon).
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { LocalPresence, PresenceLevel } from '../src/lib/api/types';
import {
  atPlace,
  monthRangePhrase,
  ofPlace,
  speciesNoun,
} from '../src/lib/components/species/frenchGrammar';
import {
  describeLocalPresence,
  monthRuns,
  presencePeriodLabel,
} from '../src/lib/components/species/localPresence';
import {
  buildIntroduction,
  plainFr,
  splitSentences,
} from '../src/lib/components/species/speciesProse';

function presence(levels: PresenceLevel[], currentMonth = 9, distanceKm = 0, city = 'Pornic'): LocalPresence {
  return {
    site_slug: 'pornic',
    site_name: 'Pornic',
    reference_city: { name: city, distance_km: distanceKm },
    monthly_levels: levels,
    current_month: currentMonth,
    current_month_level: levels[currentMonth - 1] ?? 'absent',
  };
}

const ALL = (level: PresenceLevel): PresenceLevel[] => new Array<PresenceLevel>(12).fill(level);

describe('frenchGrammar', () => {
  it('donne l’article, le genre et les pronoms du nom d’oiseau', () => {
    expect(speciesNoun('Martinet noir')).toMatchObject({ withArticle: 'le Martinet noir', pronoun: 'il', object: 'le' });
    expect(speciesNoun('Pie bavarde')).toMatchObject({ withArticle: 'la Pie bavarde', pronoun: 'elle', feminine: true });
    expect(speciesNoun('Effraie des clochers').withArticle).toBe("l'Effraie des clochers");
    expect(speciesNoun('Étourneau sansonnet').withArticle).toBe("l'Étourneau sansonnet");
    expect(speciesNoun('Hirondelle rustique').withArticle).toBe("l'Hirondelle rustique");
    expect(speciesNoun('Héron cendré').withArticle).toBe('le Héron cendré');
    expect(speciesNoun('Huppe fasciée').withArticle).toBe('la Huppe fasciée');
    expect(speciesNoun('Grande Aigrette').withArticle).toBe('la Grande Aigrette');
    expect(speciesNoun('Pie-grièche écorcheur').feminine).toBe(true);
  });

  it('retombe sur « cette espèce » quand le genre est inconnu (jamais de faute inventée)', () => {
    expect(speciesNoun('Zzz inconnu').withArticle).toBe('cette espèce');
    expect(speciesNoun(null).withArticle).toBe('cette espèce');
  });

  it('connaît le genre de tous les noms de l’univers France', () => {
    const universePath = path.resolve(process.cwd(), '..', 'species-data', 'species_universe_fr.json');
    const universe = JSON.parse(readFileSync(universePath, 'utf-8')) as { commonName: string }[];
    const unknown = universe.map((entry) => entry.commonName).filter((name) => speciesNoun(name).withArticle === 'cette espèce');
    expect(unknown).toEqual([]);
  });

  it('accorde les prépositions de lieu et de mois', () => {
    expect(atPlace('Pornic')).toBe('à Pornic');
    expect(atPlace('Le Mans')).toBe('au Mans');
    expect(ofPlace('Le Mans')).toBe('du Mans');
    expect(ofPlace('Ajaccio')).toBe("d'Ajaccio");
    expect(ofPlace('Nantes')).toBe('de Nantes');
    expect(monthRangePhrase(3, 7)).toBe("d'avril à août");
    expect(monthRangePhrase(9, 2)).toBe("d'octobre à mars");
    expect(monthRangePhrase(4, 4)).toBe('en mai');
  });
});

describe('localPresence', () => {
  it('regroupe les mois consécutifs, y compris par-dessus le changement d’année', () => {
    const flags = [true, true, false, false, false, false, false, false, false, true, true, true];
    expect(monthRuns(flags)).toEqual([[9, 1]]);
    expect(monthRuns(new Array<boolean>(12).fill(true))).toEqual([[0, 11]]);
    expect(monthRuns(new Array<boolean>(12).fill(false))).toEqual([]);
  });

  it('résume en une phrase une espèce très courante toute l’année', () => {
    expect(describeLocalPresence(presence(ALL('tres_courant')), speciesNoun('Pie bavarde'), 'Pornic')).toEqual([
      "À Pornic, la Pie bavarde est très courante toute l'année : une détection est tout à fait normale.",
    ]);
  });

  it('décrit la saison puis conseille selon le mois en cours', () => {
    const swift: PresenceLevel[] = [
      'absent', 'absent', 'rare', 'courant', 'tres_courant', 'tres_courant',
      'tres_courant', 'peu_frequent', 'rare', 'absent', 'absent', 'absent',
    ];
    const noun = speciesNoun('Martinet noir');
    expect(describeLocalPresence(presence(swift, 6), noun, 'Pornic')).toEqual([
      "À Pornic, le Martinet noir est présent d'avril à août, surtout de mai à juillet.",
      'En juin, il est très courant : une détection est tout à fait normale.',
    ]);
    expect(describeLocalPresence(presence(swift, 1), noun, 'Pornic')[1]).toBe(
      "En janvier, on ne le croise pour ainsi dire jamais : si l'appareil dit l'avoir entendu, c'est sans doute une confusion avec un autre oiseau ; réécoutez l'enregistrement pour vérifier."
    );
    expect(presencePeriodLabel(presence(swift), noun)).toBe("D'avril à août");
  });

  it('accorde au féminin et précise la ville d’observation quand elle est loin', () => {
    const levels: PresenceLevel[] = [
      'courant', 'courant', 'peu_frequent', 'rare', 'absent', 'absent',
      'absent', 'absent', 'absent', 'courant', 'courant', 'courant',
    ];
    const lines = describeLocalPresence(presence(levels, 9, 120, 'Le Mans'), speciesNoun('Grive mauvis'), 'Tours');
    expect(lines[0]).toBe(
      "À Tours, d'après les observations autour du Mans, la Grive mauvis est présente d'octobre à mars, surtout d'octobre à février."
    );
    expect(lines[1]).toBe(
      "En septembre, on ne la croise pour ainsi dire jamais : si l'appareil dit l'avoir entendue, c'est sans doute une confusion avec un autre oiseau ; réécoutez l'enregistrement pour vérifier."
    );
  });

  it('distingue « courant toute l’année, et même très courant … » et « présent toute l’année, surtout … »', () => {
    const chaffinch: PresenceLevel[] = [...ALL('tres_courant')];
    chaffinch[7] = 'courant';
    chaffinch[8] = 'courant';
    expect(describeLocalPresence(presence(chaffinch), speciesNoun('Pinson des arbres'), 'Pornic')[0]).toBe(
      "À Pornic, le Pinson des arbres est courant toute l'année, et même très courant d'octobre à juillet."
    );
    const blackcap: PresenceLevel[] = [
      'peu_frequent', 'peu_frequent', 'courant', 'tres_courant', 'tres_courant', 'tres_courant',
      'tres_courant', 'tres_courant', 'courant', 'courant', 'peu_frequent', 'peu_frequent',
    ];
    expect(describeLocalPresence(presence(blackcap), speciesNoun('Fauvette à tête noire'), 'Pornic')[0]).toBe(
      "À Pornic, la Fauvette à tête noire est présente toute l'année, surtout de mars à octobre."
    );
  });
});

describe('speciesProse', () => {
  it('retire les passages techniques et parle de « l’appareil » plutôt que de BirdNET', () => {
    expect(plainFr('Régulier et commun en France. Score BirdNET maximal de 0,33 indique une espèce plausible.')).toBe(
      'Régulier et commun en France.'
    );
    expect(plainFr('Espèce commune et régulière en France (score max BirdNET 0,52). Nicheur localisé.')).toBe(
      'Espèce commune et régulière en France. Nicheur localisé.'
    );
    expect(plainFr("Exceptionnel en France, visiteur très rare ; score de détection BirdNET maximal 0,012 (Ajaccio).")).toBe(
      'Exceptionnel en France, visiteur très rare.'
    );
    expect(plainFr('Cris proches ; BirdNET confond parfois en environnement bruyant.')).toBe(
      "Cris proches ; l'appareil confond parfois en environnement bruyant."
    );
    expect(plainFr('BirdNET peut confondre les cris en vol.')).toBe("L'appareil peut confondre les cris en vol.");
    // « modèle » au sens courant reste intact.
    expect(plainFr('Son nid a servi de modèle pour les pantoufles.')).toBe('Son nid a servi de modèle pour les pantoufles.');
    expect(plainFr(null)).toBe('');
  });

  it('fait du résumé une introduction : chapeau court puis paragraphes', () => {
    const summary = [
      'Petit passereau au plastron orange vif, le Rougegorge familier est très connu.',
      'Il appartient à la famille des gobemouches.',
      "Son allure ronde et ses grands yeux noirs en font un compagnon du jardinier, qu'il suit pour saisir les vers mis au jour par la bêche.",
      'Territorial toute l’année, il défend farouchement son domaine contre ses congénères, au point que les combats peuvent être violents.',
      'Mâle et femelle chantent, ce qui est rare chez les passereaux.',
      "En France, les nicheurs sont en partie sédentaires, rejoints à l'automne par des migrateurs du nord.",
    ].join(' ');
    const intro = buildIntroduction(summary);
    expect(intro.lead).toBe(
      'Petit passereau au plastron orange vif, le Rougegorge familier est très connu. Il appartient à la famille des gobemouches.'
    );
    expect(intro.rest.length).toBeGreaterThanOrEqual(1);
    expect(intro.rest.join(' ')).toContain('Mâle et femelle chantent');
    expect(splitSentences(summary)).toHaveLength(6);
  });
});
