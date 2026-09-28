import { describe, it, expect } from 'vitest';
import { presetToRange, isValidLocalDate, formatLocalDateFr, utcInstantToLocalDate } from '../src/lib/components/stats/period';

describe('isValidLocalDate', () => {
  it('accepte une date calendaire réelle', () => {
    expect(isValidLocalDate('2026-09-27')).toBe(true);
  });

  it('rejette un format incorrect', () => {
    expect(isValidLocalDate('27/09/2026')).toBe(false);
    expect(isValidLocalDate('2026-9-27')).toBe(false);
    expect(isValidLocalDate('')).toBe(false);
  });

  it('rejette une date qui déborde (ex. 30 février)', () => {
    expect(isValidLocalDate('2026-02-30')).toBe(false);
  });
});

describe('presetToRange', () => {
  const today = '2026-09-27';

  it('7d : 7 jours inclusifs se terminant aujourd\'hui', () => {
    expect(presetToRange('7d', today)).toEqual({ start: '2026-09-21', end: '2026-09-27' });
  });

  it('30d : 30 jours inclusifs se terminant aujourd\'hui', () => {
    expect(presetToRange('30d', today)).toEqual({ start: '2026-08-29', end: '2026-09-27' });
  });

  it('90d : 90 jours inclusifs se terminant aujourd\'hui', () => {
    expect(presetToRange('90d', today)).toEqual({ start: '2026-06-30', end: '2026-09-27' });
  });

  it('year : du 1er janvier de l\'année courante à aujourd\'hui', () => {
    expect(presetToRange('year', today)).toEqual({ start: '2026-01-01', end: '2026-09-27' });
  });

  it('custom : renvoie la plage fournie si valide', () => {
    const custom = { start: '2026-01-05', end: '2026-01-10' };
    expect(presetToRange('custom', today, custom)).toEqual(custom);
  });

  it('custom : se replie sur 30 jours si la plage fournie est invalide ou absente', () => {
    expect(presetToRange('custom', today, null)).toEqual({ start: '2026-08-29', end: '2026-09-27' });
    expect(presetToRange('custom', today, { start: '2026-09-10', end: '2026-09-01' })).toEqual({
      start: '2026-08-29',
      end: '2026-09-27',
    });
  });

  it('gère un changement de mois/année dans le calcul (arithmétique de calendrier, pas de fuseau)', () => {
    expect(presetToRange('7d', '2026-01-02')).toEqual({ start: '2025-12-27', end: '2026-01-02' });
  });
});

describe('formatLocalDateFr', () => {
  it('formate une date locale en français', () => {
    expect(formatLocalDateFr('2026-09-27')).toBe('27 sept. 2026');
  });

  it('renvoie la valeur telle quelle si elle est invalide', () => {
    expect(formatLocalDateFr('pas une date')).toBe('pas une date');
  });
});

describe('utcInstantToLocalDate — contrat §1.3-§1.4 : jamais le jour calendaire UTC', () => {
  it('convertit vers le jour local du site quand celui-ci diffère du jour UTC (soirée)', () => {
    // 22h30 UTC fin septembre = 00h30 le LENDEMAIN à Pornic (Europe/Paris, UTC+2 l'été).
    expect(utcInstantToLocalDate('2026-09-25T22:30:00Z', 'Europe/Paris')).toBe('2026-09-26');
  });

  it("convertit vers l'année locale du site quand celle-ci diffère de l'année UTC (réveillon)", () => {
    // 23h15 UTC le 31 décembre = 00h15 le 1er janvier suivant à Pornic (UTC+1 l'hiver).
    expect(utcInstantToLocalDate('2026-12-31T23:15:00Z', 'Europe/Paris')).toBe('2027-01-01');
  });

  it('ne change rien quand le jour local et le jour UTC coïncident', () => {
    expect(utcInstantToLocalDate('2026-09-27T10:00:00Z', 'Europe/Paris')).toBe('2026-09-27');
  });

  it('se replie sur le jour calendaire UTC pour un fuseau inconnu, sans planter', () => {
    expect(utcInstantToLocalDate('2026-09-25T22:30:00Z', 'Pas/UnFuseau')).toBe('2026-09-25');
  });
});
