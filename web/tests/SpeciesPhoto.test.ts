import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import SpeciesPhoto from '../src/lib/components/SpeciesPhoto.svelte';

describe('SpeciesPhoto — repli et nouvel essai après échec de chargement', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('réessaie avec une URL cassant le cache après un échec de chargement', async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0);

    render(SpeciesPhoto, { src: '/photo/a.jpg', alt: 'Espèce A' });
    const img = screen.getByRole('img', { name: 'Espèce A' }) as HTMLImageElement;

    await fireEvent.error(img);
    await vi.advanceTimersByTimeAsync(500);

    expect(img.src).toContain('/photo/a.jpg?retry=1');
  });

  it("annule le retry programmé pour l'ancienne URL quand `src` change avant son déclenchement", async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0);

    const { rerender } = render(SpeciesPhoto, { src: '/photo/a.jpg', alt: 'Espèce A' });
    const img = screen.getByRole('img', { name: 'Espèce A' }) as HTMLImageElement;
    expect(img.src).toContain('/photo/a.jpg');

    // Échec de chargement pour l'espèce A : un retry est programmé (425 ms avec ce jitter figé).
    await fireEvent.error(img);

    // Avant que ce retry ne se déclenche, le composant reçoit une nouvelle espèce (ex. un
    // nouvel item poussé par CurrentlyHearingBlock dans la même instance du composant).
    await rerender({ src: '/photo/b.jpg', alt: 'Espèce B' });

    await vi.advanceTimersByTimeAsync(1000);

    const currentImg = screen.getByRole('img', { name: 'Espèce B' }) as HTMLImageElement;
    // Avant le correctif, le $effect ne retournait aucune fonction de nettoyage : le retry
    // de l'ancienne URL se déclenchait quand même après coup et réécrivait `displaySrc` avec
    // l'URL de l'espèce A, remplaçant la photo de l'espèce B affichée à l'écran.
    expect(currentImg.src).toContain('/photo/b.jpg');
    expect(currentImg.src).not.toContain('retry=');
  });

  it("n'affiche pas d'icône de repli avant tout échec de chargement", () => {
    render(SpeciesPhoto, { src: '/photo/a.jpg', alt: 'Espèce A' });
    expect(screen.getByRole('img', { name: 'Espèce A' })).toBeInTheDocument();
  });
});
