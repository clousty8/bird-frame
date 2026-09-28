<script lang="ts">
  // Sous-onglet « Règles par espèce » (contrat §6.20-§6.22). Composant neuf.
  import { siteStore } from '../../stores/site.svelte';
  import { authStore } from '../../stores/auth.svelte';
  import { getSpeciesRules, putSpeciesRule, deleteSpeciesRule, ApiRequestError } from '../../api/client';
  import type { SpeciesRule, SpeciesRuleKind, UniverseSpecies } from '../../api/types';
  import Badge from '../ui/Badge.svelte';
  import Button from '../ui/Button.svelte';
  import LoadingSpinner from '../ui/LoadingSpinner.svelte';
  import EmptyState from '../ui/EmptyState.svelte';
  import ErrorAlert from '../ui/ErrorAlert.svelte';
  import CollapsibleSection from '../ui/CollapsibleSection.svelte';
  import AuthRequiredNotice from '../AuthRequiredNotice.svelte';
  import SpeciesSearchInput from './SpeciesSearchInput.svelte';
  import { formatInstant } from './format';

  let rules = $state<SpeciesRule[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let pollTimer: ReturnType<typeof setInterval> | undefined;

  // ---- Formulaire d'ajout / modification -------------------------------------
  let formSpeciesName = $state<string | null>(null);
  let formSpeciesCommon = $state<string | null>(null);
  let formKind = $state<SpeciesRuleKind>('present');
  let formThreshold = $state(''); // champ texte : vide = pas de seuil personnalisé
  let formRedirectName = $state<string | null>(null);
  let formRedirectCommon = $state<string | null>(null);
  let formReason = $state('');
  let formSubmitting = $state(false);
  let formError = $state<string | null>(null);
  let formSuccess = $state<string | null>(null);

  // ---- Suppression (confirmation en deux temps, pas de window.confirm) ------
  let confirmingDeleteFor = $state<string | null>(null);
  let deletingFor = $state<string | null>(null);
  let deleteError = $state<string | null>(null);

  async function load(): Promise<void> {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    loading = true;
    loadError = null;
    try {
      const response = await getSpeciesRules(slug);
      rules = response.rules;
    } catch (err) {
      loadError = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors du chargement des règles.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    // Dépendance explicite au slug courant : recharge à chaque changement de site.
    const slug = siteStore.selectedSlug;
    if (slug) void load();
  });

  // Contrat §6.20 : « Le frontend rafraîchit cette liste toutes les 5 s tant qu'une
  // règle est en pending. »
  $effect(() => {
    const hasPending = rules.some((rule) => rule.sync_status === 'pending');
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = undefined;
    }
    if (hasPending) {
      pollTimer = setInterval(() => void load(), 5000);
    }
    return () => {
      if (pollTimer) clearInterval(pollTimer);
    };
  });

  function resetForm(): void {
    formSpeciesName = null;
    formSpeciesCommon = null;
    formKind = 'present';
    formThreshold = '';
    formRedirectName = null;
    formRedirectCommon = null;
    formReason = '';
    formError = null;
  }

  function selectFormSpecies(species: UniverseSpecies): void {
    formSpeciesName = species.scientific_name;
    formSpeciesCommon = species.common_name_fr;
    formError = null;
    // Une règle existe déjà pour cette espèce : on pré-remplit le formulaire (édition).
    const existing = rules.find((rule) => rule.scientific_name === species.scientific_name);
    if (existing) {
      formKind = existing.rule;
      formThreshold = existing.threshold_override !== null ? String(existing.threshold_override) : '';
      formRedirectName = existing.redirect_to_scientific_name;
      formRedirectCommon = existing.redirect_to_common_name_fr;
      formReason = existing.reason ?? '';
    }
  }

  function startEdit(rule: SpeciesRule): void {
    formSpeciesName = rule.scientific_name;
    formSpeciesCommon = rule.common_name_fr;
    formKind = rule.rule;
    formThreshold = rule.threshold_override !== null ? String(rule.threshold_override) : '';
    formRedirectName = rule.redirect_to_scientific_name;
    formRedirectCommon = rule.redirect_to_common_name_fr;
    formReason = rule.reason ?? '';
    formError = null;
    formSuccess = null;
    try {
      // Environnement sans scrollTo (jsdom des tests, navigateurs anciens) : pas bloquant.
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      // Rien à faire : le formulaire reste pré-rempli, seul le défilement automatique manque.
    }
  }

  function selectRedirectTarget(species: UniverseSpecies): void {
    formRedirectName = species.scientific_name;
    formRedirectCommon = species.common_name_fr;
  }

  async function submitForm(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const slug = siteStore.selectedSlug;
    if (!slug || !formSpeciesName) {
      formError = "Choisissez d'abord une espèce.";
      return;
    }
    if (formKind === 'redirect' && !formRedirectName) {
      formError = 'Choisissez une espèce cible pour la redirection.';
      return;
    }

    let threshold: number | null = null;
    if (formKind === 'present' && formThreshold.trim() !== '') {
      const parsed = Number(formThreshold);
      if (Number.isNaN(parsed) || parsed < 0.01 || parsed > 1) {
        formError = 'Le seuil doit être un nombre entre 0.01 et 1 (laissez vide pour garder le seuil par défaut).';
        return;
      }
      threshold = parsed;
    }

    formSubmitting = true;
    formError = null;
    formSuccess = null;
    try {
      await putSpeciesRule(slug, formSpeciesName, {
        rule: formKind,
        threshold_override: formKind === 'present' ? threshold : null,
        redirect_to_scientific_name: formKind === 'redirect' ? formRedirectName : null,
        reason: formReason.trim() !== '' ? formReason.trim() : null,
      });
      formSuccess = `Règle enregistrée pour ${formSpeciesCommon ?? formSpeciesName}.`;
      resetForm();
      await load();
    } catch (err) {
      formError =
        err instanceof ApiRequestError ? err.message : "Erreur inconnue lors de l'enregistrement de la règle.";
    } finally {
      formSubmitting = false;
    }
  }

  async function confirmDelete(scientificName: string): Promise<void> {
    const slug = siteStore.selectedSlug;
    if (!slug) return;
    deletingFor = scientificName;
    deleteError = null;
    try {
      await deleteSpeciesRule(slug, scientificName);
      confirmingDeleteFor = null;
      await load();
    } catch (err) {
      deleteError = err instanceof ApiRequestError ? err.message : 'Erreur inconnue lors de la suppression.';
    } finally {
      deletingFor = null;
    }
  }

  const SYNC_BADGE: Record<SpeciesRule['sync_status'], { variant: 'neutral' | 'warning' | 'success' | 'error'; label: string }> = {
    none: { variant: 'neutral', label: 'aucune commande' },
    pending: { variant: 'warning', label: 'en attente…' },
    applied: { variant: 'success', label: 'appliquée' },
    failed: { variant: 'error', label: 'échec' },
  };

  const RULE_BADGE: Record<SpeciesRuleKind, { variant: 'success' | 'error' | 'info'; label: string }> = {
    present: { variant: 'success', label: 'présente ici' },
    impossible: { variant: 'error', label: 'impossible ici' },
    redirect: { variant: 'info', label: 'redirigée' },
  };
</script>

<div class="space-y-6">
  <div class="rounded-lg border border-[var(--color-info)]/30 bg-[var(--color-info)]/10 p-4 text-sm space-y-2 max-w-3xl">
    <p class="font-medium">Comment ça marche</p>
    <p>
      BirdNET-Go abaisse tout seul, pendant <strong>24 h</strong>, le seuil de confiance d'une
      espèce qu'il vient de détecter plusieurs fois avec une forte confiance (« seuil dynamique »,
      voir l'onglet <em>Seuils dynamiques</em>). Les règles ci-dessous s'ajoutent à ce mécanisme,
      par site :
    </p>
    <ul class="list-disc list-inside space-y-1">
      <li><strong>Présente ici</strong> — inclut l'espèce même si le filtre de zone l'exclurait, avec un seuil bas optionnel et permanent.</li>
      <li><strong>Impossible ici</strong> — exclut l'espèce, même si son seuil dynamique s'est abaissé entre-temps.</li>
      <li><strong>Rediriger vers…</strong> — n'agit que sur l'affichage côté serveur (une confusion connue avec une autre espèce) ; la détection brute n'est jamais modifiée.</li>
    </ul>
  </div>

  {#if !siteStore.selectedSlug}
    <EmptyState title="Aucun site sélectionné" description="Choisissez un site en haut de page pour gérer ses règles." />
  {:else}
    <AuthRequiredNotice action="ajouter, modifier ou supprimer des règles" />

    <!-- Déconnecté (contrat §2.2) : le <fieldset disabled> désactive tout le formulaire. -->
    <form class="max-w-xl" onsubmit={submitForm}>
      <fieldset class="space-y-3 min-w-0" disabled={!authStore.unlocked}>
        <h2 class="text-lg font-semibold">Ajouter ou modifier une règle</h2>

        {#if formSpeciesName}
          <SpeciesSearchInput
            id="rule-species"
            label="Espèce"
            selectedScientificName={formSpeciesName}
            selectedCommonName={formSpeciesCommon}
            onSelect={selectFormSpecies}
            onClear={() => {
              formSpeciesName = null;
              formSpeciesCommon = null;
            }}
          />
        {:else}
          <SpeciesSearchInput id="rule-species" label="Espèce" onSelect={selectFormSpecies} />
        {/if}

        <fieldset class="space-y-1.5">
          <legend class="text-sm font-medium mb-1">Règle</legend>
          <label class="flex items-center gap-2 text-sm">
            <input type="radio" class="radio" name="rule-kind" value="present" bind:group={formKind} />
            Présente ici → seuil abaissé
          </label>
          <label class="flex items-center gap-2 text-sm">
            <input type="radio" class="radio" name="rule-kind" value="impossible" bind:group={formKind} />
            Impossible ici
          </label>
          <label class="flex items-center gap-2 text-sm">
            <input type="radio" class="radio" name="rule-kind" value="redirect" bind:group={formKind} />
            Rediriger vers…
          </label>
      </fieldset>

      {#if formKind === 'present'}
        <div>
          <label for="rule-threshold" class="block text-sm font-medium mb-1">
            Seuil personnalisé (0,01 à 1, optionnel)
          </label>
          <input
            id="rule-threshold"
            type="number"
            step="0.01"
            min="0.01"
            max="1"
            class="input input-bordered w-32"
            bind:value={formThreshold}
            placeholder="ex. 0.35"
          />
        </div>
      {:else if formKind === 'redirect'}
        {#if formRedirectName}
          <SpeciesSearchInput
            id="rule-redirect-target"
            label="Rediriger vers"
            selectedScientificName={formRedirectName}
            selectedCommonName={formRedirectCommon}
            onSelect={selectRedirectTarget}
            excludeScientificName={formSpeciesName}
            onClear={() => {
              formRedirectName = null;
              formRedirectCommon = null;
            }}
          />
        {:else}
          <SpeciesSearchInput
            id="rule-redirect-target"
            label="Rediriger vers"
            onSelect={selectRedirectTarget}
            excludeScientificName={formSpeciesName}
          />
        {/if}
      {/if}

      <div>
        <label for="rule-reason" class="block text-sm font-medium mb-1">Raison (optionnel)</label>
        <textarea
          id="rule-reason"
          class="textarea textarea-bordered w-full"
          rows="2"
          maxlength="500"
          bind:value={formReason}
          placeholder="ex. Pas de pigeons bisets ici, confusion avec le ramier"
        ></textarea>
      </div>

      {#if formError}
        <ErrorAlert type="error" message={formError} />
      {/if}
      {#if formSuccess}
        <p role="status" class="text-sm text-[var(--color-success)]">{formSuccess}</p>
      {/if}

      <div class="flex items-center gap-2">
        <Button type="submit" variant="primary" disabled={formSubmitting || !formSpeciesName}>
          {formSubmitting ? 'Enregistrement…' : 'Enregistrer la règle'}
        </Button>
        {#if formSpeciesName}
          <Button type="button" variant="ghost" onclick={resetForm} disabled={formSubmitting}>Annuler</Button>
        {/if}
      </div>
      </fieldset>
    </form>

    <div>
      <h2 class="text-lg font-semibold mb-3">Règles existantes</h2>

      {#if deleteError}
        <ErrorAlert type="error" message={deleteError} dismissible onDismiss={() => (deleteError = null)} />
      {/if}

      {#if loading}
        <LoadingSpinner label="Chargement des règles…" />
      {:else if loadError}
        <div class="space-y-2">
          <ErrorAlert type="error" message={loadError} />
          <Button variant="default" onclick={load}>Réessayer</Button>
        </div>
      {:else if rules.length === 0}
        <EmptyState title="Aucune règle" description="Ce site n'a encore aucune règle par espèce." />
      {:else}
        <div class="overflow-x-auto">
          <table class="table table-zebra w-full">
            <thead>
              <tr>
                <th>Espèce</th>
                <th>Règle</th>
                <th>Détail</th>
                <th>Raison</th>
                <th>Propagation</th>
                <th>Mise à jour</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each rules as rule (rule.scientific_name)}
                <tr>
                  <td>
                    <div class="font-medium">{rule.common_name_fr ?? rule.scientific_name}</div>
                    <div class="text-xs text-muted italic">{rule.scientific_name}</div>
                  </td>
                  <td><Badge variant={RULE_BADGE[rule.rule].variant} text={RULE_BADGE[rule.rule].label} /></td>
                  <td class="text-sm">
                    {#if rule.rule === 'present'}
                      {rule.threshold_override !== null ? `seuil ${rule.threshold_override}` : 'seuil par défaut'}
                    {:else if rule.rule === 'redirect'}
                      → {rule.redirect_to_common_name_fr ?? rule.redirect_to_scientific_name}
                    {:else}
                      —
                    {/if}
                  </td>
                  <td class="text-sm max-w-[16rem]">{rule.reason ?? '—'}</td>
                  <td>
                    <Badge variant={SYNC_BADGE[rule.sync_status].variant} text={SYNC_BADGE[rule.sync_status].label} />
                    {#if rule.commands.length > 0}
                      <div class="mt-1">
                        <CollapsibleSection
                          title="Commandes ({rule.commands.length})"
                          titleClass="text-sm px-3 py-2"
                          contentClass="px-3"
                        >
                          <ul class="text-xs space-y-1">
                            {#each rule.commands as command (command.command_id)}
                              <li>
                                <span class="font-mono">{command.kind}</span> —
                                <Badge
                                  size="xs"
                                  variant={command.status === 'applied'
                                    ? 'success'
                                    : command.status === 'failed' || command.status === 'expired'
                                      ? 'error'
                                      : 'warning'}
                                  text={command.status}
                                />
                                {#if command.error_message}
                                  <span class="text-error">— {command.error_message}</span>
                                {/if}
                              </li>
                            {/each}
                          </ul>
                        </CollapsibleSection>
                      </div>
                    {/if}
                  </td>
                  <td class="text-sm whitespace-nowrap">{formatInstant(rule.updated_at)}</td>
                  <td class="whitespace-nowrap">
                    <div class="flex items-center gap-1.5 justify-end">
                      <Button variant="ghost" size="xs" disabled={!authStore.unlocked} onclick={() => startEdit(rule)}>
                        Modifier
                      </Button>
                      {#if confirmingDeleteFor === rule.scientific_name}
                        <Button
                          variant="error"
                          size="xs"
                          disabled={deletingFor === rule.scientific_name || !authStore.unlocked}
                          onclick={() => confirmDelete(rule.scientific_name)}
                        >
                          {deletingFor === rule.scientific_name ? 'Suppression…' : 'Confirmer'}
                        </Button>
                        <Button variant="ghost" size="xs" onclick={() => (confirmingDeleteFor = null)}>Annuler</Button>
                      {:else}
                        <Button
                          variant="ghost"
                          size="xs"
                          disabled={!authStore.unlocked}
                          onclick={() => (confirmingDeleteFor = rule.scientific_name)}
                        >
                          Supprimer
                        </Button>
                      {/if}
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>
