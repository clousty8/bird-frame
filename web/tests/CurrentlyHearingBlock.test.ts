import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, within } from '@testing-library/svelte';
import CurrentlyHearingBlock from '../src/lib/components/dashboard/CurrentlyHearingBlock.svelte';
import * as client from '../src/lib/api/client';
import { ApiRequestError } from '../src/lib/api/client';
import type { NowResponse, PendingItem, RecentDetection } from '../src/lib/api/types';

function makePending(overrides: Partial<PendingItem> = {}): PendingItem {
  return {
    node_id: 1,
    scientific_name: 'Erithacus rubecula',
    common_name_fr: 'Rougegorge familier',
    status: 'active',
    hit_count: 3,
    confidence_hint: null,
    first_detected_unix: 1790519938,
    last_updated_unix: 1790519944,
    source_id: 'audio_card_881db84a',
    photo_url: '/api/v1/species/Erithacus%20rubecula/photo?size=320',
    ...overrides,
  };
}

function makeRecent(overrides: Partial<RecentDetection> = {}): RecentDetection {
  return {
    detection_id: 1523,
    scientific_name: 'Parus major',
    common_name_fr: 'Mésange charbonnière',
    confidence: 0.72,
    detected_at_utc: '2026-09-27T14:39:01Z',
    photo_url: '/api/v1/species/Parus%20major/photo?size=320',
    ...overrides,
  };
}

function makeNow(overrides: Partial<NowResponse> = {}): NowResponse {
  return {
    site_slug: 'pornic',
    server_time_utc: '2026-09-27T14:39:05Z',
    pending: [],
    node_status: null,
    recent: [],
    ...overrides,
  };
}

// Même mock d'EventSource que tests/api-client.test.ts, pour piloter le flux SSE à la main.
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  listeners = new Map<string, ((event: MessageEvent) => void)[]>();
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void): void {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, data: unknown): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data: JSON.stringify(data) } as MessageEvent);
    }
  }
}

describe('CurrentlyHearingBlock', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('affiche un état de chargement puis les espèces en écoute', async () => {
    vi.spyOn(client, 'getSiteNow').mockResolvedValue(makeNow({ pending: [makePending()] }));

    render(CurrentlyHearingBlock, { slug: 'pornic' });

    expect(screen.getByText('Chargement du bloc « en écoute »…')).toBeInTheDocument();

    expect(await screen.findByText('Rougegorge familier')).toBeInTheDocument();
    expect(screen.getByText('en écoute')).toBeInTheDocument();
    expect(screen.getByText('3 coups')).toBeInTheDocument();
  });

  it("affiche un état vide quand rien n'est en cours d'écoute", async () => {
    vi.spyOn(client, 'getSiteNow').mockResolvedValue(makeNow());

    render(CurrentlyHearingBlock, { slug: 'pornic' });

    expect(await screen.findByText("Rien en cours d'écoute pour l'instant.")).toBeInTheDocument();
  });

  it('affiche une erreur lisible sans planter si /now échoue', async () => {
    vi.spyOn(client, 'getSiteNow').mockRejectedValue(
      new ApiRequestError('network_error', 'Impossible de joindre le serveur bird-frame.', 0)
    );

    render(CurrentlyHearingBlock, { slug: 'pornic' });

    expect(await screen.findByText('Impossible de joindre le serveur bird-frame.')).toBeInTheDocument();
  });

  it('affiche les 10 dernières détections confirmées en petites puces (pas un grand bloc séparé)', async () => {
    vi.spyOn(client, 'getSiteNow').mockResolvedValue(makeNow({ recent: [makeRecent()] }));

    render(CurrentlyHearingBlock, { slug: 'pornic' });

    expect(await screen.findByText('Dernières détections confirmées')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /Mésange charbonnière/ });
    expect(link).toHaveAttribute('href', '/species/Parus%20major');
  });

  it('affiche le message de repli du spectrogramme live, replié par défaut (WP-19)', async () => {
    vi.spyOn(client, 'getSiteNow').mockResolvedValue(makeNow());

    render(CurrentlyHearingBlock, { slug: 'pornic' });
    await screen.findByText("Rien en cours d'écoute pour l'instant.");

    const toggle = screen.getByRole('button', { name: /Spectrogramme en direct/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.getByText('Spectrogramme en direct : disponible quand le relais audio sera branché (WP-19).')
    ).toBeInTheDocument();
  });

  it('se connecte au SSE pending et met à jour la liste « en écoute » en direct', async () => {
    vi.spyOn(client, 'getSiteNow').mockResolvedValue(makeNow());

    render(CurrentlyHearingBlock, { slug: 'pornic' });
    await screen.findByText("Rien en cours d'écoute pour l'instant.");

    const source = FakeEventSource.instances[0];
    expect(source?.url).toBe('/api/v1/sites/pornic/pending/stream');

    source?.emit('pending', {
      site_slug: 'pornic',
      updated_at_utc: '2026-09-27T14:40:00Z',
      pending: [makePending({ scientific_name: 'Turdus merula', common_name_fr: 'Merle noir' })],
    });

    expect(await screen.findByText('Merle noir')).toBeInTheDocument();
  });

  it('ajoute une nouvelle détection confirmée reçue par SSE en tête des puces récentes', async () => {
    vi.spyOn(client, 'getSiteNow').mockResolvedValue(makeNow({ recent: [makeRecent()] }));

    render(CurrentlyHearingBlock, { slug: 'pornic' });
    await screen.findByText('Dernières détections confirmées');

    const source = FakeEventSource.instances[0];
    source?.emit('detection', makeRecent({ detection_id: 1524, scientific_name: 'Turdus merula', common_name_fr: 'Merle noir' }));

    await screen.findByText(/Merle noir/);
    const list = screen.getByText('Dernières détections confirmées').closest('div') as HTMLElement;
    const firstChip = within(list).getAllByRole('link')[0];
    expect(firstChip).toHaveTextContent('Merle noir');
  });

  it('se réabonne et recharge le snapshot quand le site change', async () => {
    const getSiteNowSpy = vi.spyOn(client, 'getSiteNow').mockResolvedValue(makeNow());

    const { rerender } = render(CurrentlyHearingBlock, { slug: 'pornic' });
    await screen.findByText("Rien en cours d'écoute pour l'instant.");
    expect(getSiteNowSpy).toHaveBeenCalledWith('pornic');
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]?.closed).toBe(false);

    await rerender({ slug: 'le-mans' });

    expect(getSiteNowSpy).toHaveBeenCalledWith('le-mans');
    expect(FakeEventSource.instances[0]?.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1]?.url).toBe('/api/v1/sites/le-mans/pending/stream');
  });
});
