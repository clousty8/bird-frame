// Densité des graduations des axes X de la page Statistiques selon la largeur (mobile).
import { describe, it, expect } from 'vitest';
import { hourTickStep, isCompactBandAxis, maxTicksForWidth, sampleTicks } from '../src/lib/components/stats/axisDensity';

describe('maxTicksForWidth', () => {
  it('garde le maximum sur grand écran', () => {
    expect(maxTicksForWidth(1000, 60, 8)).toBe(8);
  });

  it('réduit sur mobile (≈ 190 px utiles à 375 px de large)', () => {
    expect(maxTicksForWidth(190, 60, 8)).toBe(3);
  });

  it('jamais moins de 2 graduations', () => {
    expect(maxTicksForWidth(10, 60, 8)).toBe(2);
  });
});

describe('hourTickStep', () => {
  it('pas de 3 h minimum sur grand écran', () => {
    expect(hourTickStep(1000, 44, 3)).toBe(3);
  });

  it('pas élargi sur mobile pour ne pas chevaucher les libellés', () => {
    const step = hourTickStep(230, 44, 3);
    expect(step).toBe(6);
    expect(Math.ceil(24 / step) * 44).toBeLessThanOrEqual(230);
  });
});

describe('isCompactBandAxis', () => {
  it('libellés complets inclinés quand chaque tranche a la place', () => {
    expect(isCompactBandAxis(800, 10)).toBe(false);
  });

  it('libellés courts sur mobile (10 tranches dans ≈ 220 px)', () => {
    expect(isCompactBandAxis(220, 10)).toBe(true);
  });
});

describe('sampleTicks', () => {
  const days = Array.from({ length: 30 }, (_, i) => i);

  it('renvoie tout le domaine quand il tient', () => {
    expect(sampleTicks([1, 2, 3], 8)).toEqual([1, 2, 3]);
  });

  it('respecte le maximum et garde première et dernière valeur', () => {
    const ticks = sampleTicks(days, 8);
    expect(ticks.length).toBeLessThanOrEqual(8);
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]).toBe(29);
  });

  it("n'accole jamais la dernière graduation à la précédente (ancien « 26 sept.27 sept. »)", () => {
    for (const max of [3, 4, 5, 6, 7, 8]) {
      const ticks = sampleTicks(days, max);
      const gaps = ticks.slice(1).map((value, i) => value - (ticks[i] as number));
      const step = Math.ceil(days.length / (max - 1));
      expect(Math.min(...gaps)).toBeGreaterThanOrEqual(step / 2);
    }
  });
});
