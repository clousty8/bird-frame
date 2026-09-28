import { describe, it, expect } from 'vitest';
import { formatCount, formatNumber, pluralize } from '../src/lib/format';

describe('pluralize — règle française', () => {
  it('singulier pour 0 et 1', () => {
    expect(pluralize(0, 'détection')).toBe('détection');
    expect(pluralize(1, 'détection')).toBe('détection');
  });

  it('pluriel à partir de 2', () => {
    expect(pluralize(2, 'détection')).toBe('détections');
    expect(pluralize(2436, 'jour')).toBe('jours');
  });

  it('accepte un pluriel irrégulier', () => {
    expect(pluralize(3, 'nouvel oiseau', 'nouveaux oiseaux')).toBe('nouveaux oiseaux');
    expect(pluralize(1, 'nouvel oiseau', 'nouveaux oiseaux')).toBe('nouvel oiseau');
  });

  it('singulier sous 2 en valeur absolue (1,5 kilo, −1 degré)', () => {
    expect(pluralize(1.5, 'kilo')).toBe('kilo');
    expect(pluralize(-1, 'degré')).toBe('degré');
    expect(pluralize(-3, 'degré')).toBe('degrés');
  });
});

describe('formatCount', () => {
  it('« 1 détection » et non « 1 détections »', () => {
    expect(formatCount(1, 'détection')).toBe('1 détection');
  });

  it('formate le nombre à la française (espace fine insécable)', () => {
    expect(formatCount(2438, 'détection')).toBe(`${formatNumber(2438)} détections`);
    expect(formatNumber(2438)).toMatch(/^2\s438$/u);
  });
});
