/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base des routes API navigateur, sans slash final. Défaut : "/api/v1" (contrat §2.3). */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
