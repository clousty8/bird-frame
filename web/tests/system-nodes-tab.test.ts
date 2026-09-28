import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/svelte';
import NodesTab from '../src/lib/components/system/NodesTab.svelte';
import * as client from '../src/lib/api/client';
import type { NodeStatus } from '../src/lib/api/types';

function makeNode(overrides: Partial<NodeStatus> = {}): NodeStatus {
  return {
    node_id: 1,
    node_name: 'Mac Armand — Pornic',
    site_slug: 'pornic',
    site_name: 'Pornic',
    online: true,
    last_seen_at: '2026-09-27T14:40:12Z',
    last_sync_at: '2026-09-27T14:40:05Z',
    last_heartbeat_at: '2026-09-27T14:38:10Z',
    last_detection_at: '2026-09-27T14:39:01Z',
    mic_device_name: 'HyperX QuadCast 2',
    mic_healthy: true,
    disk_free_pct: 62.4,
    birdnet_go_reachable: true,
    birdnet_go_pid_alive: true,
    birdnet_go_version: '20260823',
    bridge_version: '0.1.0',
    synced_up_to_id: 4627,
    node_db_max_id: 4627,
    sync_lag: 0,
    decommissioned_at: null,
    ...overrides,
  };
}

describe('NodesTab', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('affiche un indicateur de chargement puis les nœuds', async () => {
    vi.spyOn(client, 'getNodes').mockResolvedValue({ nodes: [makeNode()] });

    render(NodesTab);

    expect(screen.getByRole('status', { name: 'Chargement des nœuds…' })).toBeInTheDocument();

    expect(await screen.findByText('Mac Armand — Pornic')).toBeInTheDocument();
    expect(screen.getByText('Pornic')).toBeInTheDocument();
    expect(screen.getByText('En ligne')).toBeInTheDocument();
    expect(screen.getByText('HyperX QuadCast 2', { exact: false })).toBeInTheDocument();
  });

  it('affiche un état vide quand aucun nœud n\'est enregistré', async () => {
    vi.spyOn(client, 'getNodes').mockResolvedValue({ nodes: [] });

    render(NodesTab);

    expect(await screen.findByText('Aucun nœud enregistré')).toBeInTheDocument();
  });

  it('affiche une erreur exploitable (jamais avalée) avec un bouton pour réessayer', async () => {
    vi.spyOn(client, 'getNodes')
      .mockRejectedValueOnce(new client.ApiRequestError('internal_error', 'Le serveur a répondu 500.', 500))
      .mockResolvedValueOnce({ nodes: [makeNode()] });

    render(NodesTab);

    expect(await screen.findByText('Le serveur a répondu 500.')).toBeInTheDocument();
    const retry = screen.getByRole('button', { name: 'Réessayer' });

    await fireEvent.click(retry);

    expect(await screen.findByText('Mac Armand — Pornic')).toBeInTheDocument();
    expect(client.getNodes).toHaveBeenCalledTimes(2);
  });

  it('signale un micro en anomalie et un nœud hors ligne', async () => {
    vi.spyOn(client, 'getNodes').mockResolvedValue({
      nodes: [makeNode({ online: false, mic_healthy: false })],
    });

    render(NodesTab);

    await screen.findByText('Mac Armand — Pornic');
    expect(screen.getByText('Hors ligne')).toBeInTheDocument();
    expect(screen.getByText('anomalie')).toBeInTheDocument();
  });
});
