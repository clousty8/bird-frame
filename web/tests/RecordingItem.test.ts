import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import RecordingItem from '../src/lib/components/species/RecordingItem.svelte';
import type { TopClip } from '../src/lib/api/types';
import { authStore } from '../src/lib/stores/auth.svelte';

function makeClip(overrides: Partial<TopClip> = {}): TopClip {
  return {
    kept_clip_id: 88,
    detection_id: 1523,
    detected_at_utc: '2026-09-27T14:39:01Z',
    confidence: 0.72,
    rank: 1,
    audio_available: true,
    audio_url: '/api/v1/recordings/88/audio',
    spectrogram_url: '/api/v1/recordings/88/spectrogram',
    duration_s: 15,
    review: null,
    missing: false,
    predictions: [
      { scientific_name: 'Parus major', common_name_fr: 'Mésange charbonnière', confidence: 0.72, is_primary: true },
    ],
    ...overrides,
  };
}

describe('RecordingItem — lecture audio', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("affiche un message visible quand la lecture échoue (404/clip supprimé/format non lisible), pas seulement en console", async () => {
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockRejectedValue(
      new DOMException('Impossible de lire ce fichier.', 'NotSupportedError')
    );
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(RecordingItem, { clip: makeClip() });

    await fireEvent.click(screen.getByRole('button', { name: "Lire l'enregistrement" }));

    // Avant ce correctif, seul console.error était appelé : rien n'était visible pour
    // l'utilisateur et le bouton restait silencieusement sur « Lire ».
    expect(await screen.findByText('Lecture impossible.')).toBeInTheDocument();
    expect(consoleSpy).toHaveBeenCalled();
    // Le bouton reste bien sur « Lire » (playing n'est jamais passé à true), mais désormais
    // avec un message d'erreur affiché à côté.
    expect(screen.getByRole('button', { name: "Lire l'enregistrement" })).toBeInTheDocument();
  });

  it("n'affiche aucun message d'erreur avant toute tentative de lecture", () => {
    render(RecordingItem, { clip: makeClip() });
    expect(screen.queryByText('Lecture impossible.')).not.toBeInTheDocument();
  });

  it("efface le message d'erreur si une nouvelle tentative de lecture réussit", async () => {
    const playSpy = vi
      .spyOn(HTMLMediaElement.prototype, 'play')
      .mockRejectedValueOnce(new DOMException('échec', 'NotSupportedError'))
      .mockImplementationOnce(function (this: HTMLMediaElement) {
        this.dispatchEvent(new Event('play'));
        return Promise.resolve();
      });
    vi.spyOn(console, 'error').mockImplementation(() => {});

    render(RecordingItem, { clip: makeClip() });
    const button = screen.getByRole('button', { name: "Lire l'enregistrement" });

    await fireEvent.click(button);
    expect(await screen.findByText('Lecture impossible.')).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: /Lire|Mettre en pause/ }));
    expect(playSpy).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('Lecture impossible.')).not.toBeInTheDocument();
  });
});

describe('RecordingItem — écoute réservée à une session (contrat §2.2)', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('déconnecté : cadenas « Connecte-toi pour écouter », spectrogramme visible, aucun <audio>', async () => {
    authStore._resetForTests({ authEnabled: true, authenticated: false });
    const { container } = render(RecordingItem, { clip: makeClip() });

    expect(screen.getByRole('img', { name: "Spectrogramme de l'enregistrement" })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: "Lire l'enregistrement" })).not.toBeInTheDocument();
    // Pas d'élément audio : il préchargerait l'URL protégée et récolterait des 401.
    expect(container.querySelector('audio')).toBeNull();

    await fireEvent.click(screen.getByRole('button', { name: 'Connecte-toi pour écouter' }));
    expect(authStore.modalOpen).toBe(true);
  });

  it('connecté : bouton de lecture et <audio> normaux', () => {
    authStore._resetForTests({ authEnabled: true, authenticated: true });
    const { container } = render(RecordingItem, { clip: makeClip() });

    expect(screen.getByRole('button', { name: "Lire l'enregistrement" })).toBeInTheDocument();
    expect(screen.queryByText('Connecte-toi pour écouter')).not.toBeInTheDocument();
    expect(container.querySelector('audio')?.getAttribute('src')).toBe('/api/v1/recordings/88/audio');
  });

  it('bascule vers le cadenas à la déconnexion', async () => {
    authStore._resetForTests({ authEnabled: true, authenticated: true });
    render(RecordingItem, { clip: makeClip() });
    expect(screen.getByRole('button', { name: "Lire l'enregistrement" })).toBeInTheDocument();

    authStore._resetForTests({ authEnabled: true, authenticated: false });

    expect(await screen.findByRole('button', { name: 'Connecte-toi pour écouter' })).toBeInTheDocument();
  });
});
