<script lang="ts">
  // Coquille de l'application : en-tête (4 sections + SiteSelector + ThemeToggle + connexion)
  // qui monte la page de la route courante, et la modale de connexion partagée (contrat §2.2).
  // Voir web/README.md pour la carte des dossiers.
  import { onMount } from 'svelte';
  import { DEFAULT_SYSTEM_TAB, getCurrentRoute, onRouteChange, type RouteName } from './lib/router';
  import { themeStore, applyThemeToDocument } from './lib/stores/theme.svelte';
  import { authStore } from './lib/stores/auth.svelte';
  import Link from './lib/Link.svelte';
  import SiteSelector from './lib/components/SiteSelector.svelte';
  import ThemeToggle from './lib/components/ThemeToggle.svelte';
  import AuthButton from './lib/components/AuthButton.svelte';
  import LoginModal from './lib/components/LoginModal.svelte';
  import DashboardPage from './routes/DashboardPage.svelte';
  import SpeciesPage from './routes/SpeciesPage.svelte';
  import SpeciesDetailPage from './routes/SpeciesDetailPage.svelte';
  import StatsPage from './routes/StatsPage.svelte';
  import SystemPage from './routes/SystemPage.svelte';

  let route = $state(getCurrentRoute());
  let mobileNavOpen = $state(false);

  onMount(() => {
    void authStore.load();
  });

  $effect(() => {
    return onRouteChange((match) => {
      route = match;
      mobileNavOpen = false;
    });
  });

  // Réagit aussi bien à un changement de préférence (bouton) qu'à un changement de la
  // préférence système en mode "automatique".
  $effect(() => {
    applyThemeToDocument(themeStore.effective);
  });

  interface NavItem {
    label: string;
    path: string;
    matches: (name: RouteName) => boolean;
  }

  const NAV_ITEMS: NavItem[] = [
    { label: 'Tableau de bord', path: '/dashboard', matches: (name) => name === 'dashboard' },
    {
      label: 'Espèces',
      path: '/species',
      matches: (name) => name === 'species-list' || name === 'species-detail',
    },
    { label: 'Statistiques', path: '/stats', matches: (name) => name === 'stats' },
    { label: 'Système', path: '/system', matches: (name) => name === 'system' },
  ];
</script>

<div class="min-h-screen flex flex-col bg-base-200 text-base-content">
  <header class="border-b border-border-100 bg-base-100">
    <div class="flex items-center justify-between gap-3 px-4 py-3 max-w-6xl mx-auto">
      <div class="flex items-center gap-3">
        <span class="text-lg font-semibold whitespace-nowrap">bird-frame</span>
        <button
          type="button"
          class="btn btn-ghost btn-sm md:hidden"
          onclick={() => (mobileNavOpen = !mobileNavOpen)}
          aria-expanded={mobileNavOpen}
          aria-controls="main-nav-mobile"
          aria-label="Basculer le menu de navigation"
        >
          <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
      </div>

      <nav class="hidden md:flex items-center gap-1" aria-label="Navigation principale">
        {#each NAV_ITEMS as item (item.path)}
          <Link to={item.path} class="tab {item.matches(route.name) ? 'tab-active' : ''}">
            {item.label}
          </Link>
        {/each}
      </nav>

      <div class="flex items-center gap-2 shrink-0">
        <SiteSelector />
        <AuthButton />
        <ThemeToggle />
      </div>
    </div>

    {#if mobileNavOpen}
      <nav id="main-nav-mobile" class="md:hidden flex flex-col gap-1 px-4 pb-3" aria-label="Navigation principale (mobile)">
        {#each NAV_ITEMS as item (item.path)}
          <Link to={item.path} class="tab justify-start {item.matches(route.name) ? 'tab-active' : ''}">
            {item.label}
          </Link>
        {/each}
      </nav>
    {/if}
  </header>

  <main class="flex-1 px-4 py-6 max-w-6xl mx-auto w-full">
    {#if route.name === 'dashboard'}
      <DashboardPage />
    {:else if route.name === 'species-list'}
      <SpeciesPage />
    {:else if route.name === 'species-detail'}
      <SpeciesDetailPage scientificName={route.params.name ?? ''} />
    {:else if route.name === 'stats'}
      <StatsPage />
    {:else if route.name === 'system'}
      <SystemPage tab={route.params.tab ?? DEFAULT_SYSTEM_TAB} />
    {:else}
      <div class="text-center py-16">
        <h1 class="text-2xl font-semibold">Page introuvable</h1>
        <p class="text-muted mt-2">Cette page n'existe pas.</p>
        <Link to="/dashboard" class="btn btn-primary mt-4 inline-flex">Retour au tableau de bord</Link>
      </div>
    {/if}
  </main>
</div>

<LoginModal />
