/* animate-core.js — lightweight, dependency-free UI motion primitives:
   count-up numbers, text-scramble, click ripple, cursor-tracked card tilt,
   particle burst, and skeleton-shimmer toggling. Vanilla JS/CSS only —
   this app has no React/build step, so these stay framework-free and are
   applied by adding data-attributes to existing server-rendered markup
   rather than mounting any component tree. */
(function (window, document) {
  'use strict';

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // ── Count-up numbers ──
  // Animates the first number found in an element's text from 0 up to its
  // own current value. Leaves any prefix/suffix text intact, so "92%" ->
  // counts "0%".."92%", and "34h 12m" -> counts "0h 12m".."34h 12m".
  function animateCounters(root) {
    var els = (root || document).querySelectorAll('[data-animate-counter]');
    if (!els.length || prefersReducedMotion()) return;

    els.forEach(function (el) {
      if (el.__acCounterDone) return;
      el.__acCounterDone = true;

      var text = el.textContent;
      var match = text.match(/-?\d+(\.\d+)?/);
      if (!match) return;

      var target = parseFloat(match[0]);
      var decimals = (match[0].split('.')[1] || '').length;
      var prefix = text.slice(0, match.index);
      var suffix = text.slice(match.index + match[0].length);
      var duration = parseInt(el.getAttribute('data-duration'), 10) || 900;
      var start = null;

      function frame(ts) {
        if (start === null) start = ts;
        var progress = Math.min(1, (ts - start) / duration);
        var eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        el.textContent = prefix + (target * eased).toFixed(decimals) + suffix;
        if (progress < 1) {
          requestAnimationFrame(frame);
        } else {
          el.textContent = prefix + target.toFixed(decimals) + suffix;
        }
      }
      requestAnimationFrame(frame);
    });
  }

  // ── Text scramble ──
  // Cycles random characters before settling into the element's own text.
  var SCRAMBLE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  function scrambleText(el, opts) {
    if (prefersReducedMotion()) return;
    opts = opts || {};
    var finalText = el.getAttribute('data-scramble-text') || el.textContent;
    var duration = opts.duration || 700;
    var frameDelay = opts.frameDelay || 35;
    var frame = 0;
    var totalFrames = Math.round(duration / frameDelay);

    function render() {
      var progress = frame / totalFrames;
      var revealCount = Math.floor(progress * finalText.length);
      var out = '';
      for (var i = 0; i < finalText.length; i++) {
        var ch = finalText[i];
        out += (i < revealCount || ch === ' ') ? ch : SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
      }
      el.textContent = out;
      frame++;
      if (frame <= totalFrames) {
        setTimeout(render, frameDelay);
      } else {
        el.textContent = finalText;
      }
    }
    render();
  }

  function initScrambles(root) {
    (root || document).querySelectorAll('[data-scramble]').forEach(function (el) {
      if (el.__acScrambled) return;
      el.__acScrambled = true;
      scrambleText(el);
    });
  }

  // ── Ripple click effect ──
  // Delegated at the document level (so it works on elements added after
  // page load) for anything matching [data-ripple] or .sb-item — the
  // portal sidebar's nav-item class, ripple'd by default since it's the
  // one "menu item click" surface every page in this app already has.
  function initRipple() {
    document.addEventListener('click', function (e) {
      if (prefersReducedMotion()) return;
      var target = e.target.closest('[data-ripple], .sb-item');
      if (!target) return;

      var rect = target.getBoundingClientRect();
      var size = Math.max(rect.width, rect.height) * 1.6;
      var ripple = document.createElement('span');
      ripple.className = 'ac-ripple';
      ripple.style.width = ripple.style.height = size + 'px';
      ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
      ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';

      if (window.getComputedStyle(target).position === 'static') {
        target.style.position = 'relative';
      }
      target.classList.add('ac-ripple-host');
      target.appendChild(ripple);
      ripple.addEventListener('animationend', function () { ripple.remove(); });
    });
  }

  // ── Particle burst ──
  // Spawns N small colored dots that fly outward from an element's center
  // and fade out — for celebratory moments (badge earned, milestone hit).
  // Triggered manually: AnimateCore.particleBurst(el).
  function particleBurst(el, opts) {
    if (prefersReducedMotion()) return;
    opts = opts || {};
    var count = opts.count || 14;
    var colors = opts.colors || ['#38bdf8', '#a78bfa', '#fbbf24', '#34d399', '#f472b6'];
    var rect = el.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;

    for (var i = 0; i < count; i++) {
      var p = document.createElement('span');
      p.className = 'ac-particle';
      var angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
      var distance = 40 + Math.random() * 40;
      p.style.setProperty('--ac-dx', (Math.cos(angle) * distance) + 'px');
      p.style.setProperty('--ac-dy', (Math.sin(angle) * distance) + 'px');
      p.style.background = colors[i % colors.length];
      p.style.left = cx + 'px';
      p.style.top = cy + 'px';
      document.body.appendChild(p);
      p.addEventListener('animationend', function () { this.remove(); });
    }
  }

  // ── Parallax card tilt ──
  // Subtle rotateX/rotateY based on cursor position relative to the card.
  // Skipped on touch devices (pointer: coarse) since there's no hover.
  function initTilt(root) {
    var els = (root || document).querySelectorAll('[data-tilt]');
    if (!els.length || prefersReducedMotion()) return;
    if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) return;

    els.forEach(function (card) {
      if (card.__acTiltBound) return;
      card.__acTiltBound = true;
      var maxDeg = parseFloat(card.getAttribute('data-tilt-max')) || 6;
      card.classList.add('ac-tilt');
      card.addEventListener('mousemove', function (e) {
        var rect = card.getBoundingClientRect();
        var px = (e.clientX - rect.left) / rect.width;
        var py = (e.clientY - rect.top) / rect.height;
        var rotateY = (px - 0.5) * 2 * maxDeg;
        var rotateX = (0.5 - py) * 2 * maxDeg;
        card.style.transform = 'perspective(600px) rotateX(' + rotateX.toFixed(2) + 'deg) rotateY(' + rotateY.toFixed(2) + 'deg) translateZ(0)';
      });
      card.addEventListener('mouseleave', function () { card.style.transform = ''; });
    });
  }

  // ── Skeleton shimmer ──
  // Toggle placeholders (data-skeleton-for="<key>") vs. real content
  // (data-skeleton-target="<key>") while a fetch-driven section loads, so
  // it never pops in with a layout shift. Usage:
  //   <div class="ac-skeleton ..." data-skeleton-for="breaks">...</div>
  //   <div data-skeleton-target="breaks" class="u-d-none">...</div>
  //   AnimateCore.hideSkeleton('breaks') once the fetch resolves.
  function showSkeleton(key) {
    document.querySelectorAll('[data-skeleton-for="' + key + '"]').forEach(function (el) { el.classList.remove('u-d-none'); });
    document.querySelectorAll('[data-skeleton-target="' + key + '"]').forEach(function (el) { el.classList.add('u-d-none'); });
  }
  function hideSkeleton(key) {
    document.querySelectorAll('[data-skeleton-for="' + key + '"]').forEach(function (el) { el.classList.add('u-d-none'); });
    document.querySelectorAll('[data-skeleton-target="' + key + '"]').forEach(function (el) { el.classList.remove('u-d-none'); });
  }

  function init(root) {
    animateCounters(root);
    initScrambles(root);
    initTilt(root);
  }

  initRipple();
  document.addEventListener('DOMContentLoaded', function () { init(document); });

  window.AnimateCore = {
    init: init,
    animateCounters: animateCounters,
    scrambleText: scrambleText,
    particleBurst: particleBurst,
    showSkeleton: showSkeleton,
    hideSkeleton: hideSkeleton,
  };
})(window, document);
