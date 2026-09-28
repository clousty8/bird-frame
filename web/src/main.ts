import { mount } from 'svelte';
import App from './App.svelte';
import './styles/tailwind.css';

const target = document.getElementById('app');
if (!target) {
  throw new Error('Élément #app introuvable dans index.html.');
}

const app = mount(App, { target });

export default app;
