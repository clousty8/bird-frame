// Onglets Système sans session (contrat §2.2) : contrôles de modification désactivés, mention
// « Connexion requise » et lien qui ouvre la modale. Quand l'authentification est désactivée
// (serveur de dev sans mot de passe), tout reste actif sans connexion.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import RulesTab from '../src/lib/components/system/RulesTab.svelte';
import ReviewTab from '../src/lib/components/system/ReviewTab.svelte';
import FalseNegativesTab from '../src/lib/components/system/FalseNegativesTab.svelte';
import ThresholdsTab from '../src/lib/components/system/ThresholdsTab.svelte';
import { siteStore } from '../src/lib/stores/site.svelte';
import { authStore } from '../src/lib/stores/auth.svelte';
import * as client from '../src/lib/api/client';
import type { DynamicThreshold, ReviewDetection, SpeciesRule } from '../src/lib/api/types';

const RULE: SpeciesRule = {
  scientific_name: 'Columba livia',
  common_name_fr: 'Pigeon biset',
  rule: 'impossible',
  threshold_override: null,
  redirect_to_scientific_name: null,
  redirect_to_common_name_fr: null,
  reason: null,
  updated_at: '2026-09-27T15:00:00Z',
  sync_status: 'applied',
  commands: [],
};

const DETECTION: ReviewDetection = {
  detection_id: 1523,
  node_id: 1,
  node_local_id: 4627,
  detected_at_utc: '2026-09-27T14:39:01Z',
  local_date: '2026-09-27',
  scientific_name: 'Parus major',
  common_name_fr: 'Mésange charbonnière',
  effective_scientific_name: 'Parus major',
  effective_common_name_fr: 'Mésange charbonnière',
  confidence: 0.72,
  source_display_name: 'Sound Card 1',
  has_clip: true,
  kept_clip_id: 88,
  audio_url: '/api/v1/recordings/88/audio',
  spectrogram_url: '/api/v1/recordings/88/spectrogram',
  review: null,
  review_note: null,
  rule: null,
  predictions: [],
};

const THRESHOLD: DynamicThreshold = {
  node_id: 1,
  scientific_name: 'Prunella modularis',
  common_name_fr: 'Accenteur mouchet',
  node_species_name: 'accenteur mouchet',
  level: 3,
  current_value: 0.2,
  base_threshold: 0.6,
  high_conf_count: 19,
  trigger_count: 19,
  is_active: true,
  expires_at: '2026-09-28T14:26:19Z',
  last_triggered_at: '2026-09-27T14:39:38Z',
  first_created_at: '2026-09-27T14:39:38Z',
  reset_pending: false,
};

function mockSystemRoutes(): void {
  vi.spyOn(client, 'getSpeciesRules').mockResolvedValue({ site_slug: 'pornic', rules: [RULE] });
  vi.spyOn(client, 'getDetections').mockResolvedValue({ detections: [DETECTION], total: 1, limit: 25, offset: 0 });
  vi.spyOn(client, 'getFalseNegatives').mockResolvedValue({ false_negatives: [], total: 0, limit: 25, offset: 0 });
  vi.spyOn(client, 'getDynamicThresholds').mockResolvedValue({
    site_slug: 'pornic',
    snapshot_at: null,
    thresholds: [THRESHOLD],
  });
}

async function expectNoticeOpensModal(): Promise<void> {
  expect(screen.getByText('Connexion requise')).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'se connecter' }));
  expect(authStore.modalOpen).toBe(true);
}

describe('Système — déconnecté, authentification active', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    siteStore.select('pornic');
    authStore._resetForTests({ authEnabled: true, authenticated: false });
    mockSystemRoutes();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('Règles : formulaire et actions désactivés, mention et lien vers la modale', async () => {
    render(RulesTab);
    await screen.findByText('Pigeon biset');

    expect(screen.getByRole('button', { name: 'Enregistrer la règle' })).toBeDisabled();
    expect(screen.getByLabelText('Impossible ici')).toBeDisabled();
    expect(screen.getByLabelText('Raison (optionnel)')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Modifier' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Supprimer' })).toBeDisabled();
    await expectNoticeOpensModal();
  });

  it('Revue : boutons de revue et note désactivés, filtres toujours utilisables', async () => {
    render(ReviewTab);
    await screen.findByText('Mésange charbonnière');

    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Faux positif' })).toBeDisabled();
    expect(screen.getByPlaceholderText('Note (optionnel)')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Filtrer' })).toBeEnabled();
    await expectNoticeOpensModal();
  });

  it('Faux négatifs : formulaire désactivé', async () => {
    render(FalseNegativesTab);
    await screen.findByText('Aucun signalement');

    expect(screen.getByRole('button', { name: 'Signaler' })).toBeDisabled();
    expect(screen.getByLabelText('Notes (optionnel)')).toBeDisabled();
    await expectNoticeOpensModal();
  });

  it('Seuils dynamiques : réinitialisation désactivée', async () => {
    render(ThresholdsTab);
    await screen.findByText('Accenteur mouchet');

    expect(screen.getByRole('button', { name: 'Réinitialiser' })).toBeDisabled();
    await expectNoticeOpensModal();
  });

  it('les contrôles se réactivent dès la connexion', async () => {
    render(ThresholdsTab);
    await screen.findByText('Accenteur mouchet');
    expect(screen.getByRole('button', { name: 'Réinitialiser' })).toBeDisabled();

    authStore._resetForTests({ authEnabled: true, authenticated: true });

    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Réinitialiser' })).toBeEnabled());
    expect(screen.queryByText('Connexion requise')).not.toBeInTheDocument();
  });
});

describe('Système — authentification désactivée (serveur de dev sans mot de passe)', () => {
  beforeEach(() => {
    siteStore._resetForTests();
    siteStore.select('pornic');
    authStore._resetForTests({ authEnabled: false });
    mockSystemRoutes();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('tout est actif sans connexion, aucune mention', async () => {
    render(RulesTab);
    await screen.findByText('Pigeon biset');
    expect(screen.getByLabelText('Impossible ici')).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Supprimer' })).toBeEnabled();
    expect(screen.queryByText('Connexion requise')).not.toBeInTheDocument();
    cleanup();

    render(ReviewTab);
    await screen.findByText('Mésange charbonnière');
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeEnabled();
    cleanup();

    render(FalseNegativesTab);
    await screen.findByText('Aucun signalement');
    expect(screen.getByLabelText('Notes (optionnel)')).toBeEnabled();
    cleanup();

    render(ThresholdsTab);
    await screen.findByText('Accenteur mouchet');
    expect(screen.getByRole('button', { name: 'Réinitialiser' })).toBeEnabled();
  });
});
