/* ════════════════════════════════════════════════════════
   LU2COHOUSE — app.js
   Standard scroll with GSAP entrance + section reveals
════════════════════════════════════════════════════════ */

const IS_PREVIEW = location.search.includes('preview');

/* ── Elements ── */
const loader    = document.getElementById('loader');
const loaderBar = document.querySelector('.loader-bar');
const nav       = document.getElementById('nav');

/* ── Lenis smooth scroll ── */
let lenis = null;
try {
  lenis = new Lenis({
    duration: 0.9,
    easing: t => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    smoothWheel: true
  });
  lenis.on('scroll', ScrollTrigger.update);
  gsap.ticker.add(time => lenis.raf(time * 1000));
} catch(e) {
  window.addEventListener('scroll', ScrollTrigger.update, { passive: true });
}
gsap.ticker.lagSmoothing(0);

/* ── Nav scrolled state ── */
ScrollTrigger.create({
  start: 'top -80',
  onUpdate: self => nav.classList.toggle('scrolled', self.progress > 0)
});

/* ── Hero entrance animation ── */
function runEntrance() {
  if (!IS_PREVIEW) {
    gsap.set(nav,            { opacity: 0 });
    gsap.set('.hero-char',   { yPercent: 110 });
    gsap.set('.t-word',      { opacity: 0, y: 30, rotationX: -45 });
    gsap.set('#hero-sub',    { opacity: 0, y: 40 });
    gsap.set('#hero-scroll', { opacity: 0, y: 20 });
  } else {
    gsap.set('.hero-char', { yPercent: 0 });
  }

  const dur = IS_PREVIEW ? 0 : 1;

  // Sequence: image is already visible (CSS bg) → nav fades in slowly → then texts
  gsap.timeline({ defaults: { ease: 'power3.out' } })
    .to(nav,            { opacity: 1, duration: IS_PREVIEW ? 0 : 1.6, ease: 'power2.inOut' }, IS_PREVIEW ? 0 : 0.6)
    .to('.hero-char',   { yPercent: 0, duration: dur * 1.4, stagger: 0.04 },                  IS_PREVIEW ? 0 : 1.8)
    .to('.t-word',      { opacity: 1, y: 0, rotationX: 0, duration: dur, stagger: 0.14 },     IS_PREVIEW ? 0 : 2.8)
    .to('#hero-sub',    { opacity: 1, y: 0, duration: dur * 1.2 },                            IS_PREVIEW ? 0 : 3.6)
    .to('#hero-scroll', { opacity: 1, y: 0, duration: dur * 0.9 },                            IS_PREVIEW ? 0 : 4.3);
}

/* ── Stat counter animation ── */
function animateCounter(el) {
  const target = parseInt(el.dataset.target, 10);
  const obj = { val: 0 };
  gsap.to(obj, {
    val: target,
    duration: 2,
    ease: 'power2.out',
    onUpdate() { el.textContent = Math.round(obj.val); }
  });
}

/* ── Scroll section reveals ── */
function initScrollReveals() {

  // Timeless
  ScrollTrigger.create({
    trigger: '#timeless',
    start: 'top 78%',
    once: true,
    onEnter() {
      gsap.from('.timeless-heading, .timeless-body', {
        opacity: 0, y: 40, duration: 1, stagger: 0.14, ease: 'power3.out'
      });
      gsap.from('.stats-row', { opacity: 0, y: 24, duration: 1, delay: 0.3, ease: 'power3.out' });
      document.querySelectorAll('.stat-num[data-target]').forEach(el => {
        animateCounter(el);
      });
    }
  });

  // Always (24/7)
  gsap.from('.always-num', {
    opacity: 0, y: 50, duration: 1.2, ease: 'power3.out',
    scrollTrigger: { trigger: '#always', start: 'top 78%', once: true }
  });
  gsap.from('.always-heading, .always-body', {
    opacity: 0, y: 36, duration: 1, stagger: 0.14, ease: 'power3.out',
    scrollTrigger: { trigger: '#always', start: 'top 78%', once: true }
  });

  // Lumière
  gsap.from('.lumiere-heading, .lumiere-body, .lumiere-cta', {
    opacity: 0, y: 36, duration: 1, stagger: 0.12, ease: 'power3.out',
    scrollTrigger: { trigger: '#lumiere', start: 'top 78%', once: true }
  });

  // Quote
  gsap.from('.quote-text', {
    opacity: 0, y: 28, duration: 1.2, ease: 'power3.out',
    scrollTrigger: { trigger: '#quote', start: 'top 78%', once: true }
  });

  // Made for Every Body
  gsap.from('.made-heading, .made-body, .made-cta', {
    opacity: 0, y: 36, duration: 1, stagger: 0.12, ease: 'power3.out',
    scrollTrigger: { trigger: '#made-for', start: 'top 78%', once: true }
  });

  // Image reveals
  gsap.utils.toArray('.reveal-img').forEach(el => {
    gsap.from(el, {
      opacity: 0, scale: 1.06, duration: 1.4, ease: 'power3.out',
      scrollTrigger: { trigger: el, start: 'top 85%', once: true }
    });
  });

  // Global Stats
  ScrollTrigger.create({
    trigger: '#global-stats',
    start: 'top 80%',
    once: true,
    onEnter() {
      gsap.from('.global-eyebrow', { opacity: 0, y: 16, duration: 0.8, ease: 'power3.out' });
      gsap.from('.global-num', { opacity: 0, y: 40, duration: 1.1, stagger: 0.1, ease: 'power3.out', delay: 0.1 });
      gsap.from('.global-lbl', { opacity: 0, y: 16, duration: 0.8, stagger: 0.1, ease: 'power3.out', delay: 0.3 });
    }
  });
}

/* ── Boot ── */
function boot() {
  if (!IS_PREVIEW && loader) {
    let progress = 0;
    const interval = setInterval(() => {
      progress = Math.min(progress + Math.random() * 18, 100);
      if (loaderBar) loaderBar.style.width = progress + '%';
      if (progress >= 100) {
        clearInterval(interval);
        setTimeout(() => {
          loader.classList.add('hidden');
          runEntrance();
          initScrollReveals();
        }, 400);
      }
    }, 80);
  } else {
    if (loader) loader.classList.add('hidden');
    runEntrance();
    initScrollReveals();
  }
}

boot();
