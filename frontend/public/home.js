document.addEventListener('DOMContentLoaded', () => {
  renderTopNav('home');
  document.getElementById('hero-cta').onclick = () => goToGeneration();
});
