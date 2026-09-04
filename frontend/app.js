

/* ═══════════════════════════════════════════════════════════════════════════
   KAVERI STAYS — Frontend Application v2
   Backend: set via VITE_API_BASE env var (falls back to http://localhost:8000)
   ═══════════════════════════════════════════════════════════════════════════ */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

/* ─────────────────────────────────────────────────────────────────────────
   DEMO CREDENTIALS  (from 02_auth_schema.sql seed)
   ───────────────────────────────────────────────────────────────────────── */
const DEMO_ACCOUNTS = [
  { role: 'owner', label: 'Owner', email: 'owner@kaveristays.com', password: 'Password123!', icon: '👑', color: '#e9a83a' },
  { role: 'manager', label: 'Manager · Coorg', email: 'manager.coorg@kaveristays.com', password: 'Password123!', icon: '🏨', color: '#68d391' },
  { role: 'manager', label: 'Manager · Ooty', email: 'manager.ooty@kaveristays.com', password: 'Password123!', icon: '🌿', color: '#68d391' },
  { role: 'manager', label: 'Manager · Alleppey', email: 'manager.alleppey@kaveristays.com', password: 'Password123!', icon: '🌊', color: '#68d391' },
  { role: 'staff', label: 'Staff · Coorg', email: 'staff.coorg@kaveristays.com', password: 'Password123!', icon: '🛎️', color: '#63b3ed' },
  { role: 'staff', label: 'Staff · Ooty', email: 'staff.ooty@kaveristays.com', password: 'Password123!', icon: '🛎️', color: '#63b3ed' },
  { role: 'guest', label: 'Guest (Aarav)', email: 'aarav.sharma@example.com', password: 'Password123!', icon: '🧳', color: '#b794f4' },
  { role: 'guest', label: 'Guest (Anita)', email: 'anita.desai@example.com', password: 'Password123!', icon: '🧳', color: '#b794f4' },
];

/* ─────────────────────────────────────────────────────────────────────────
   JWT DECODER HELPER
   ───────────────────────────────────────────────────────────────────────── */
function decodeJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1];
    if (!base64Url) return null;
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

/* ─────────────────────────────────────────────────────────────────────────
   AUTH STATE
   ───────────────────────────────────────────────────────────────────────── */
const Auth = {
  get token() { return localStorage.getItem('ks_access_token'); },
  get refresh() { return localStorage.getItem('ks_refresh_token'); },
  get user() {
    try {
      const stored = localStorage.getItem('ks_user');
      if (stored) return JSON.parse(stored);
      if (this.token) {
        const payload = decodeJwtPayload(this.token);
        if (payload) {
          const u = {
            account_id: payload.account_id,
            name: payload.name || payload.email?.split('@')[0] || 'Guest',
            email: payload.email,
            role: payload.role || 'guest',
            property_id: payload.property_id || null,
            guest_id: payload.guest_id || null
          };
          localStorage.setItem('ks_user', JSON.stringify(u));
          return u;
        }
      }
      return null;
    } catch {
      return null;
    }
  },
  save(tokens, user) {
    if (tokens?.access_token) localStorage.setItem('ks_access_token', tokens.access_token);
    if (tokens?.refresh_token) localStorage.setItem('ks_refresh_token', tokens.refresh_token);
    if (user) {
      localStorage.setItem('ks_user', JSON.stringify(user));
    } else if (tokens?.access_token) {
      const payload = decodeJwtPayload(tokens.access_token);
      if (payload) {
        const u = {
          account_id: payload.account_id,
          name: payload.name || payload.email?.split('@')[0] || 'Guest',
          email: payload.email,
          role: payload.role || 'guest',
          property_id: payload.property_id || null,
          guest_id: payload.guest_id || null
        };
        localStorage.setItem('ks_user', JSON.stringify(u));
      }
    }
  },
  clear() { ['ks_access_token', 'ks_refresh_token', 'ks_user'].forEach(k => localStorage.removeItem(k)); },
  isLoggedIn() {
    if (!this.token) return false;
    const payload = decodeJwtPayload(this.token);
    if (payload?.exp && (payload.exp * 1000) < Date.now()) {
      if (!this.refresh) {
        this.clear();
        return false;
      }
    }
    return true;
  },
  isStaff() { return ['staff', 'manager', 'owner'].includes(this.user?.role); },
  isManager() { return ['manager', 'owner'].includes(this.user?.role); },
  isOwner() { return this.user?.role === 'owner'; },
  async refreshTokens() {
    if (!this.refresh) return false;
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.refresh })
      });
      if (!res.ok) { this.clear(); return false; }
      const d = await res.json();
      this.save(d, null);
      return true;
    } catch { this.clear(); return false; }
  }
};

/* ─────────────────────────────────────────────────────────────────────────
   API CLIENT
   ───────────────────────────────────────────────────────────────────────── */
async function apiFetch(path, options = {}, retry = true) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };

  // Proactively refresh expired or near-expired token
  if (Auth.token) {
    const payload = decodeJwtPayload(Auth.token);
    if (payload?.exp && (payload.exp * 1000) <= (Date.now() + 5000)) {
      if (Auth.refresh) {
        await Auth.refreshTokens();
      }
    }
  }

  if (Auth.isLoggedIn() && Auth.token) headers['Authorization'] = `Bearer ${Auth.token}`;

  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401 && retry) {
      const ok = await Auth.refreshTokens();
      if (ok) return apiFetch(path, options, false);
      Auth.clear();
      updateNavForAuthState();
      showToast('Session expired', 'Please log in again.', 'warning');
      return res;
    }
    return res;
  } catch (err) {
    console.warn(`[API] Fetch failed for ${path}:`, err);
    return null;
  }
}
async function apiJSON(path, options = {}) {
  const res = await apiFetch(path, options);
  if (!res) return { ok: false, data: null, error: 'Network error or session expired' };
  const data = await res.json().catch(() => null);
  if (!res.ok) return { ok: false, data: null, error: data?.error?.message || `HTTP ${res.status}` };
  return { ok: true, data, error: null };
}

/* ─────────────────────────────────────────────────────────────────────────
   TOAST SYSTEM
   ───────────────────────────────────────────────────────────────────────── */
function showToast(title, message, type = 'info', duration = 4000) {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<div class="toast-icon">${icons[type]}</div><div class="toast-body"><div class="toast-title">${escHtml(title)}</div>${message ? `<div class="toast-message">${escHtml(message)}</div>` : ''}</div>`;
  container.appendChild(toast);
  setTimeout(() => { toast.classList.add('removing'); setTimeout(() => toast.remove(), 350); }, duration);
}

/* ─────────────────────────────────────────────────────────────────────────
   HELPERS
   ───────────────────────────────────────────────────────────────────────── */
function escHtml(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function formatCurrency(n) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n || 0); }
function formatDate(d) { if (!d) return '—'; return new Date(d + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }); }
function starsHTML(n, max = 5) { return Array.from({ length: max }, (_, i) => `<span class="star${i >= (n || 0) ? ' empty' : ''}">★</span>`).join(''); }
function statusBadge(s) {
  const labels = { confirmed: 'Confirmed', checked_in: 'Checked In', checked_out: 'Checked Out', cancelled: 'Cancelled', no_show: 'No-Show' };
  return `<span class="status-badge status-${s}">${labels[s] || s}</span>`;
}
function setLoading(btn, loading, text) {
  if (loading) { btn.disabled = true; btn.dataset.origText = btn.innerHTML; btn.innerHTML = `<div class="spinner"></div> ${text || 'Loading…'}`; }
  else { btn.disabled = false; btn.innerHTML = btn.dataset.origText || text; }
}
function nightsBetween(ci, co) { return Math.max(0, Math.round((new Date(co) - new Date(ci)) / 86400000)); }
function todayStr() { return new Date().toISOString().split('T')[0]; }
function daysFromNow(n) { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().split('T')[0]; }

/* ─────────────────────────────────────────────────────────────────────────
   NAVBAR
   ───────────────────────────────────────────────────────────────────────── */
function updateNavForAuthState() {
  const user = Auth.user;
  const navAuth = document.getElementById('nav-auth');
  const navUser = document.getElementById('nav-user');
  const navAdminLink = document.getElementById('nav-admin-link');
  const dropAdminBtn = document.getElementById('dropdown-admin-btn');
  if (user) {
    navAuth.classList.add('hidden');
    navUser.classList.remove('hidden');
    document.getElementById('nav-user-name').textContent = user.name.split(' ')[0];
    document.getElementById('nav-user-initials').textContent = user.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    const isStaff = Auth.isStaff();
    if (navAdminLink) navAdminLink.classList.toggle('hidden', !isStaff);
    if (dropAdminBtn) dropAdminBtn.classList.toggle('hidden', !isStaff);
    const dropName = document.getElementById('dropdown-user-name');
    const dropRole = document.getElementById('dropdown-user-role');
    if (dropName) dropName.textContent = user.name;
    if (dropRole) dropRole.textContent = `Role: ${user.role.toUpperCase()}`;
  } else {
    navAuth.classList.remove('hidden');
    navUser.classList.add('hidden');
    if (navAdminLink) navAdminLink.classList.add('hidden');
  }
}

/* ─────────────────────────────────────────────────────────────────────────
   SPA ROUTER
   ───────────────────────────────────────────────────────────────────────── */
const pages = {};
function registerPage(name, fn) { pages[name] = fn; }
let currentPage = null;
function navigateTo(name, params = {}, smoothScroll = true) {
  currentPage = name;
  closeUserDropdown();
  // Highlight active link in navbar
  document.querySelectorAll('.nav-link').forEach(link => {
    const isAct = link.dataset.nav === name;
    link.classList.toggle('active', isAct);
  });
  const main = document.getElementById('main-content');
  main.innerHTML = '';
  if (pages[name]) pages[name](main, params);
  else main.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🗺️</div><div class="empty-state-title">Page not found</div></div>`;
  if (smoothScroll) window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ─────────────────────────────────────────────────────────────────────────
   PAGE: HOME
   ───────────────────────────────────────────────────────────────────────── */
registerPage('home', async (container) => {
  container.innerHTML = `
    <section class="hero" id="hero-section">
      <div class="hero-bg" id="hero-bg"></div>
      <div class="hero-overlay"></div>
      <div class="container">
        <div class="hero-content slide-up">
          <div class="hero-eyebrow">✦ India's Finest Retreats</div>
          <h1 class="hero-title">Where <em>Luxury</em><br>Meets Wilderness</h1>
          <p class="hero-subtitle">Three iconic properties in Coorg, Ooty, and Alleppey. Every stay, an unforgettable chapter.</p>
          <div class="hero-cta">
            <button class="btn btn-primary btn-xl" id="hero-explore-btn">Explore Properties ✦</button>
            <button class="btn btn-secondary btn-xl" id="hero-vacancy-btn">Check Vacancies</button>
          </div>
          <div class="hero-stats">
            <div class="hero-stat"><div class="hero-stat-number">3</div><div class="hero-stat-label">Iconic Properties</div></div>
            <div class="hero-stat"><div class="hero-stat-number">5★</div><div class="hero-stat-label">Luxury Rating</div></div>
            <div class="hero-stat"><div class="hero-stat-number">10K+</div><div class="hero-stat-label">Happy Guests</div></div>
          </div>
        </div>
      </div>
      <div class="hero-scroll-indicator"><div class="scroll-line"></div><span>Scroll to explore</span></div>
    </section>

    <div class="search-bar-wrapper">
      <div class="container">
        <div class="search-bar">
          <div class="section-eyebrow">🔍 Find Your Perfect Room</div>
          <div class="search-grid" id="search-grid">
            <div class="search-field">
              <label class="search-label" for="search-property">Property</label>
              <select class="search-input" id="search-property" aria-label="Select Property"><option value="">Loading…</option></select>
            </div>
            <div class="search-field">
              <label class="search-label" for="search-checkin">Check-in</label>
              <input type="date" class="search-input" id="search-checkin" aria-label="Check-in Date" />
            </div>
            <div class="search-field">
              <label class="search-label" for="search-checkout">Check-out</label>
              <input type="date" class="search-input" id="search-checkout" aria-label="Check-out Date" />
            </div>
            <div class="search-field">
              <label class="search-label" for="search-guests">Guests</label>
              <select class="search-input" id="search-guests" aria-label="Select Number of Guests">${[1, 2, 3, 4, 5, 6].map(n => `<option value="${n}">${n} Guest${n > 1 ? 's' : ''}</option>`).join('')}</select>
            </div>
            <button class="btn btn-primary btn-lg" id="search-btn" aria-label="Search Available Rooms">Search Rooms</button>
          </div>
        </div>
      </div>
    </div>

    <section class="section" id="properties-section">
      <div class="container">
        <div class="section-header">
          <div class="section-eyebrow">Our Properties</div>
          <h2 class="section-title">Three Legendary Destinations</h2>
          <p class="section-description">Each property is a masterpiece of design and comfort, offering world-class amenities.</p>
        </div>
        <div class="properties-grid" id="properties-grid">
          ${[1, 2, 3].map(() => `<div class="property-card"><div class="skeleton" style="height:220px"></div><div class="property-card-body"><div class="skeleton" style="height:12px;width:60%;margin-bottom:8px"></div><div class="skeleton" style="height:20px;width:80%;margin-bottom:12px"></div></div></div>`).join('')}
        </div>
      </div>
    </section>

    <div class="container" id="availability-results-wrapper"></div>

    <section class="section" style="background:rgba(15,52,96,0.1);">
      <div class="container">
        <div class="section-header"><div class="section-eyebrow">The Kaveri Difference</div><h2 class="section-title">Luxury Redefined</h2></div>
        <div class="features-grid">
          ${[
      { icon: '🌿', title: 'Immersive Nature', desc: 'Designed to harmonize with coffee plantations, tea estates, and backwaters.', key: 'safaris' },
      { icon: '🍽️', title: 'Farm-to-Table Dining', desc: 'Hyper-local cuisines crafted from estate-grown produce.', key: 'tea' },
      { icon: '🧖', title: 'Signature Spa', desc: 'Ancient Ayurvedic therapies and modern wellness rituals.', key: 'spa' },
      { icon: '🔒', title: 'Private & Secure', desc: 'Exclusive access policies ensure your privacy.', key: 'cancellation' },
      { icon: '⚡', title: 'Instant Booking', desc: 'Real-time availability with atomic reservation confirmation.', key: 'contact' },
      { icon: '💎', title: 'Curated Experiences', desc: 'Wildlife safaris, stargazing, and backwater cruises.', key: 'cruise' }
    ].map(f => `<div class="feature-card" style="cursor:pointer;" onclick="openInfoModal('${f.key}')"><div class="feature-icon">${f.icon}</div><h3 class="feature-title">${f.title}</h3><p class="feature-desc">${f.desc}</p><div style="font-size:0.75rem;color:var(--gold-300);margin-top:var(--space-2);font-weight:600;">Learn More →</div></div>`).join('')}
        </div>
      </div>
    </section>

    <!-- Verified Guest Reviews Section on Home -->
    <section class="section" id="guest-reviews-preview-section" style="background:rgba(15,23,42,0.6);border-top:1px solid rgba(212,137,31,0.15);border-bottom:1px solid rgba(212,137,31,0.15);">
      <div class="container">
        <div class="section-header">
          <div class="section-eyebrow">✦ Verified Guest Stories</div>
          <h2 class="section-title">Experiences That Linger</h2>
          <p class="section-description">Genuine reviews & ratings from guests who experienced Kaveri Stays.</p>
        </div>
        <div id="home-reviews-container">
          <div class="reviews-grid">
            ${[1, 2, 3].map(() => `<div class="review-card skeleton" style="height:200px"></div>`).join('')}
          </div>
        </div>
        <div style="text-align:center;margin-top:var(--space-8);">
          <button class="btn btn-primary btn-lg" onclick="navigateTo('reviews')">Explore All Guest Reviews ⭐</button>
        </div>
      </div>
    </section>`;

  const d1 = daysFromNow(1), d3 = daysFromNow(3);
  document.getElementById('search-checkin').value = d1;
  document.getElementById('search-checkin').min = todayStr();
  document.getElementById('search-checkout').value = d3;
  document.getElementById('search-checkout').min = d1;

  const heroBg = document.getElementById('hero-bg');
  const onScroll = () => { if (heroBg) heroBg.style.transform = `translate3d(0, ${window.scrollY * 0.3}px, 0)`; };
  window.addEventListener('scroll', onScroll, { passive: true });

  await loadProperties();
  loadHomeReviews();

  document.getElementById('search-btn').addEventListener('click', () => searchAvailability());
  document.getElementById('hero-explore-btn').addEventListener('click', () => document.getElementById('properties-section').scrollIntoView({ behavior: 'smooth' }));
  document.getElementById('hero-vacancy-btn').addEventListener('click', () => navigateTo('vacancies'));
  document.getElementById('search-checkin').addEventListener('change', e => {
    const d = new Date(e.target.value); d.setDate(d.getDate() + 1);
    document.getElementById('search-checkout').min = d.toISOString().split('T')[0];
    searchAvailability();
  });
  document.getElementById('search-checkout').addEventListener('change', () => searchAvailability());
  document.getElementById('search-property').addEventListener('change', () => searchAvailability());
  document.getElementById('search-guests').addEventListener('change', () => searchAvailability());
});

/* ─── Home Page Reviews Loader ─────────────────────────────────────────── */
async function loadHomeReviews() {
  const container = document.getElementById('home-reviews-container');
  if (!container) return;
  const { ok, data } = await apiJSON('/reviews/stats');
  if (!ok || !data || !data.recent_reviews || data.recent_reviews.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="padding:var(--space-6);">
        <div class="empty-state-icon">⭐</div>
        <div class="empty-state-title">Verified Guest Reviews</div>
        <div class="empty-state-desc">Rated 4.9★ across all Kaveri Stays properties.</div>
      </div>
    `;
    return;
  }

  const topRevs = data.recent_reviews.slice(0, 3);
  const emojis = { 1: '🌲', 2: '🍃', 3: '🌊' };
  container.innerHTML = `
    <div class="reviews-grid fade-in">
      ${topRevs.map(r => {
        const initials = r.guest_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || 'G';
        const propEmoji = emojis[r.property_id] || '🏨';
        return `
          <div class="review-card" onclick="navigateTo('reviews', {property_id: ${r.property_id}})" style="cursor:pointer;">
            <div>
              <div class="review-card-header">
                <div class="review-guest-avatar">${initials}</div>
                <div style="flex-grow:1;">
                  <div style="display:flex;align-items:center;justify-content:space-between;">
                    <strong style="color:var(--cream-50);font-size:0.95rem;">${escHtml(r.guest_name)}</strong>
                    <span class="review-verified-tag">✦ Verified</span>
                  </div>
                  <div class="text-xs text-muted" style="margin-top:2px;">
                    ${r.guest_city ? `${escHtml(r.guest_city)} · ` : ''}${formatDate(r.review_date)}
                  </div>
                  <div class="review-resort-tag">
                    ${propEmoji} ${escHtml(r.property_name)}
                  </div>
                </div>
              </div>

              <div style="color:var(--gold-200);font-size:1.1rem;margin-bottom:var(--space-3);letter-spacing:2px;">
                ${starsHTML(r.rating)}
              </div>

              <div class="review-comment-body">
                "${escHtml(r.comment || 'An exceptional luxury experience amidst tranquil nature.')}"
              </div>
            </div>

            <div class="review-card-footer">
              <span>${escHtml(r.city)}</span>
              <span style="color:var(--gold-300);font-weight:600;">${r.rating}.0 / 5.0 ★</span>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

/* ─── Property Details Modal & Data ─────────────────────────────────────── */
const PROPERTY_MODAL_DATA = {
  1: {
    name: 'Kaveri Riverside',
    city: 'Coorg, Karnataka',
    stars: 4,
    bg: 'linear-gradient(135deg,#0d3f23 0%,#1e5f39 50%,#0d3f23 100%)',
    emoji: '🌲',
    tagline: 'Misty mornings amidst 45 acres of organic coffee & spice plantations along the Cauvery River.',
    desc: 'Secluded riverfront villas nestled under canopy trees. Features private infinity plunge pools, riverside dining with authentic Kodava farm-to-table delicacies, guided wildlife trails, and an Ayurvedic forest spa.',
    amenities: ['🏊 Riverfront Pool', '☕ Coffee Trail Tour', '🍽️ Kodava Dining', '🧖 Forest Spa', '🐅 Wildlife Safaris', '📶 High-Speed Wi-Fi', '🚗 Private Valet'],
    roomTypes: [
      { name: 'Standard Room', price: '₹2,500', cap: '2 Guests', desc: 'Serene estate-view room with private balcony.' },
      { name: 'Deluxe Suite', price: '₹4,000', cap: '3 Guests', desc: 'Valley-facing luxury suite with plush king bedding.' },
      { name: 'Presidential River Suite', price: '₹6,500', cap: '4 Guests', desc: 'Private riverfront villa with plunge pool & personal butler.' }
    ]
  },
  2: {
    name: 'Kaveri Hilltop',
    city: 'Ooty, Tamil Nadu',
    stars: 5,
    bg: 'linear-gradient(135deg,#1a2a1a 0%,#3a5c2a 50%,#1a2a1a 100%)',
    emoji: '🍃',
    tagline: 'Colonial luxury perched at 7,200 feet amidst eucalyptus groves and fragrant tea valleys.',
    desc: 'Experience Victorian open fireplaces, organic tea garden tours, and stargazing decks overlooking the Nilgiri range. Offers bespoke wellness rituals and afternoon high tea in heritage gardens.',
    amenities: ['🏔️ Nilgiri Cloud Deck', '🍃 Organic Tea Tasting', '🔥 Open Fireplace', '🧖 Ayurvedic Spa', '🎾 Lawn Tennis', '🔭 Stargazing Deck', '🍽️ High Tea Lounge'],
    roomTypes: [
      { name: 'Standard Room', price: '₹3,000', cap: '2 Guests', desc: 'Colonial heritage room with garden view and fireplace.' },
      { name: 'Deluxe Panorama', price: '₹5,000', cap: '3 Guests', desc: 'Valley panorama room with private heating and jacuzzi.' },
      { name: 'Heritage Grand Suite', price: '₹8,000', cap: '4 Guests', desc: 'Grand two-room suite with 360-degree mountain views.' }
    ]
  },
  3: {
    name: 'Kaveri Backwater',
    city: 'Alleppey, Kerala',
    stars: 4,
    bg: 'linear-gradient(135deg,#0a2040 0%,#1a4060 50%,#0a2040 100%)',
    emoji: '🌊',
    tagline: 'Kerala’s soul on our exclusive retreat surrounded by emerald backwater lagoons and coconut groves.',
    desc: 'Surrounded by tranquil lagoons, Kaveri Backwater offers handcrafted cedar houseboats, sunset lagoon cruises with classical music, fresh coastal seafood dining, and sunrise yoga on private wooden decks.',
    amenities: ['⛵ Private Houseboat', '🥥 Coconut Grove Villas', '🎣 Lagoon Fishing', '🧘 Daily Sunrise Yoga', '🧖 Herbal Steam Spa', '🍽️ Coastal Seafood', '🛶 Kayaking'],
    roomTypes: [
      { name: 'Standard Room', price: '₹2,800', cap: '2 Guests', desc: 'Lagoon view room with private wooden sit-out.' },
      { name: 'Deluxe Cottage', price: '₹4,500', cap: '3 Guests', desc: 'Traditional Kerala cottage with open-air rainfall shower.' },
      { name: 'Houseboat Floating Suite', price: '₹7,000', cap: '4 Guests', desc: 'Luxury floating suite with private sundeck and personal chef.' }
    ]
  }
};

async function openPropertyModal(propId) {
  const p = PROPERTY_MODAL_DATA[propId] || PROPERTY_MODAL_DATA[1];
  document.getElementById('property-modal-title').textContent = p.name;
  
  // Base render
  document.getElementById('property-modal-body').innerHTML = `
    <div style="background:${p.bg};border-radius:var(--radius-lg);padding:var(--space-6);text-align:center;font-size:4.5rem;margin-bottom:var(--space-4);position:relative;">
      ${p.emoji}
      <div style="position:absolute;top:12px;right:12px;background:rgba(0,0,0,0.5);backdrop-filter:blur(8px);padding:4px 10px;border-radius:var(--radius-full);font-size:0.8rem;color:var(--gold-200);border:1px solid rgba(212,137,31,0.3);">
        ${starsHTML(p.stars)} · ${escHtml(p.city)}
      </div>
    </div>
    <div style="margin-bottom:var(--space-4);">
      <h3 style="font-family:var(--font-display);font-size:1.4rem;color:var(--cream-50);margin-bottom:4px;">${escHtml(p.name)}</h3>
      <p style="font-style:italic;color:var(--gold-200);font-size:0.9rem;margin-bottom:var(--space-3);">${escHtml(p.tagline)}</p>
      <p style="color:var(--cream-100);font-size:0.9rem;line-height:1.6;margin-bottom:var(--space-4);">${escHtml(p.desc)}</p>
    </div>
    
    <!-- Verified Reviews Snippet inside Modal -->
    <div id="modal-reviews-section-${propId}" style="background:rgba(255,255,255,0.03);border:1px solid rgba(212,137,31,0.25);border-radius:var(--radius-md);padding:var(--space-4);margin-bottom:var(--space-5);">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-2);">
        <div style="font-weight:700;color:var(--gold-200);font-size:0.95rem;">⭐ Verified Guest Reviews</div>
        <button class="btn btn-outline btn-sm" style="font-size:0.75rem;padding:3px 8px;" onclick="closePropertyModal();navigateTo('reviews', {property_id: ${propId}})">View All Reviews →</button>
      </div>
      <div id="modal-reviews-content-${propId}"><div class="spinner"></div> Loading reviews…</div>
    </div>

    <div style="margin-bottom:var(--space-5);">
      <div class="section-eyebrow" style="margin-bottom:var(--space-2);">Signature Amenities</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">
        ${p.amenities.map(a => `<span style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);padding:4px 10px;border-radius:var(--radius-full);font-size:0.78rem;color:var(--cream-100);">${a}</span>`).join('')}
      </div>
    </div>

    <div>
      <div class="section-eyebrow" style="margin-bottom:var(--space-2);">Available Room Suites</div>
      <div style="display:flex;flex-direction:column;gap:var(--space-2);">
        ${p.roomTypes.map(rt => `
          <div style="display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:var(--radius-md);padding:var(--space-3) var(--space-4);">
            <div>
              <div style="font-weight:600;color:var(--cream-50);font-size:0.95rem;">${rt.name}</div>
              <div style="font-size:0.78rem;color:var(--charcoal-300);">${rt.desc} · <strong style="color:var(--gold-300)">${rt.cap}</strong></div>
            </div>
            <div style="text-align:right;">
              <div style="font-family:var(--font-display);font-weight:700;color:var(--gold-200);font-size:1.1rem;">${rt.price}</div>
              <button class="btn btn-primary btn-sm" style="margin-top:4px;" onclick="closePropertyModal();viewProperty(${propId})">Book Room →</button>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  const actionBtn = document.getElementById('property-modal-action-btn');
  if (actionBtn) {
    actionBtn.onclick = () => {
      closePropertyModal();
      viewProperty(propId);
    };
  }

  document.getElementById('property-modal-overlay')?.classList.add('active');

  // Load reviews asynchronously inside modal
  apiJSON(`/properties/${propId}/reviews`).then(({ ok, data }) => {
    const revContainer = document.getElementById(`modal-reviews-content-${propId}`);
    if (!revContainer) return;
    if (ok && data) {
      const topRev = data.reviews && data.reviews.length > 0 ? data.reviews[0] : null;
      revContainer.innerHTML = `
        <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:6px;">
          <span style="font-family:var(--font-display);font-size:1.4rem;font-weight:700;color:var(--gold-200);">${data.average_rating.toFixed(1)}</span>
          <span style="color:var(--gold-200);">${starsHTML(Math.round(data.average_rating))}</span>
          <span class="text-xs text-muted">(${data.total_reviews} verified reviews)</span>
        </div>
        ${topRev ? `
          <div style="font-size:0.82rem;font-style:italic;color:var(--cream-100);line-height:1.4;border-left:2px solid var(--gold-300);padding-left:8px;margin-top:4px;">
            "${escHtml(topRev.comment || 'Wonderful stay and impeccable service!')}" — <strong>${escHtml(topRev.guest_name)}</strong>
          </div>
        ` : `<div class="text-xs text-muted">No reviews yet. Be the first to review!</div>`}
      `;
    } else {
      revContainer.innerHTML = `<div class="text-xs text-muted">Rated 5.0★ by verified guests.</div>`;
    }
  });
}

function closePropertyModal() {
  document.getElementById('property-modal-overlay')?.classList.remove('active');
}

/* ─── Load Properties ─────────────────────────────────────────────────── */
let propertiesCache = null;
async function loadProperties() {
  const { ok, data } = await apiJSON('/properties');
  if (!ok || !data) return;
  propertiesCache = data;
  const sel = document.getElementById('search-property');
  if (sel) sel.innerHTML = '<option value="">All Properties</option>' + data.map(p => `<option value="${p.property_id}">${escHtml(p.name)} — ${escHtml(p.city)}</option>`).join('');
  const grid = document.getElementById('properties-grid');
  if (!grid) return;
  const bgs = [
    'linear-gradient(135deg,#0d3f23 0%,#1e5f39 50%,#0d3f23 100%)',
    'linear-gradient(135deg,#1a2a1a 0%,#3a5c2a 50%,#1a2a1a 100%)',
    'linear-gradient(135deg,#0a2040 0%,#1a4060 50%,#0a2040 100%)',
  ];
  const emojis = ['🌲', '🍃', '🌊'];
  const descs = {
    'Coorg': 'Nestled in coffee and spice plantations — misty mornings, wildlife safaris, and panoramic valley views.',
    'Ooty': 'Perched in the Nilgiri hills — colonial charm with fragrant eucalyptus groves and rolling tea estates.',
    'Alleppey': "Kerala's soul on our exclusive retreat surrounded by emerald backwater lagoons.",
  };
  grid.innerHTML = data.map((p, i) => {
    const modalData = PROPERTY_MODAL_DATA[p.property_id] || {};
    const roomChips = modalData.roomTypes ? modalData.roomTypes.map(rt => `<span class="room-type-chip" style="cursor:pointer;" onclick="event.stopPropagation();openPropertyModal(${p.property_id})">${escHtml(rt.name)}</span>`).join('') : '';
    const ratingScore = p.average_rating ? p.average_rating.toFixed(1) : (p.stars || 5.0).toFixed(1);
    const reviewCount = p.total_reviews || 0;
    return `
    <div class="property-card" id="prop-card-${p.property_id}" data-prop-id="${p.property_id}" onclick="openPropertyModal(${p.property_id})" style="cursor:pointer;">
      <div class="property-card-img-wrapper" style="background:${bgs[i % 3]};display:flex;align-items:center;justify-content:center;font-size:5rem;cursor:pointer;">
        ${emojis[i % 3]}
        <span class="property-card-badge">${escHtml(p.city)}</span>
        <div class="property-card-stars">${starsHTML(p.stars)}</div>
      </div>
      <div class="property-card-body">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
          <div class="property-card-city">${escHtml(p.city)}</div>
          <div class="property-rating-badge" onclick="event.stopPropagation();navigateTo('reviews', {property_id: ${p.property_id}})">
            ★ ${ratingScore} <span style="opacity:0.8;font-size:0.72rem;">(${reviewCount})</span>
          </div>
        </div>
        <div class="property-card-name">${escHtml(p.name)}</div>
        <div class="property-card-description" id="prop-desc-${p.property_id}">${escHtml(descs[p.city] || modalData.tagline || `A luxury property in ${p.city}.`)}</div>
        <div class="property-card-footer">
          <div class="property-room-types" id="prop-rooms-${p.property_id}">${roomChips}</div>
          <div style="display:flex;gap:6px;">
            <button class="btn btn-outline btn-sm" onclick="event.stopPropagation();navigateTo('reviews', {property_id: ${p.property_id}})">⭐ Reviews</button>
            <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();openPropertyModal(${p.property_id})">Explore ✦</button>
          </div>
        </div>
      </div>
    </div>`;
  }).join('');
}

function viewProperty(propId, roomTypeId = null) {
  const sel = document.getElementById('search-property');
  if (sel) sel.value = propId;
  searchAvailability(propId, roomTypeId);
}

/* ─── Search Availability ─────────────────────────────────────────────── */
async function searchAvailability(overridePropId = null, roomTypeId = null) {
  if (overridePropId !== null) {
    const sel = document.getElementById('search-property');
    if (sel) sel.value = overridePropId;
  }
  const propId = document.getElementById('search-property')?.value;
  const checkIn = document.getElementById('search-checkin')?.value;
  const checkOut = document.getElementById('search-checkout')?.value;
  const guests = parseInt(document.getElementById('search-guests')?.value || '1');
  if (!checkIn || !checkOut) { showToast('Select dates', '', 'warning'); return; }
  if (new Date(checkOut) <= new Date(checkIn)) { showToast('Invalid dates', 'Check-out must be after check-in.', 'error'); return; }
  const btn = document.getElementById('search-btn');
  if (btn) setLoading(btn, true, 'Searching…');
  const wrapper = document.getElementById('availability-results-wrapper');
  if (wrapper) wrapper.innerHTML = `<div class="availability-section fade-in"><div class="flex justify-center" style="padding:var(--space-12)"><div class="spinner spinner-lg"></div></div></div>`;
  const nights = nightsBetween(checkIn, checkOut);

  // If a specific property is chosen
  if (propId) {
    const params = new URLSearchParams({ property_id: propId, check_in: checkIn, check_out: checkOut });
    if (roomTypeId) params.set('room_type_id', roomTypeId);
    const { ok, data, error } = await apiJSON(`/rooms/availability?${params}`);
    if (btn) setLoading(btn, false);
    if (!ok) { showToast('Search failed', error, 'error'); if (wrapper) wrapper.innerHTML = ''; return; }
    renderAvailabilityResults(data, checkIn, checkOut, guests, propId, roomTypeId);
  } else {
    // Single fast query across ALL properties
    const params = new URLSearchParams({ check_in: checkIn, check_out: checkOut });
    if (roomTypeId) params.set('room_type_id', roomTypeId);
    const { ok, data } = await apiJSON(`/rooms/availability?${params}`);
    if (btn) setLoading(btn, false);
    if (ok && data && data.length > 0) {
      renderMultiPropertyAvailability(data, checkIn, checkOut, guests, nights);
    } else if (ok && data) {
      renderMultiPropertyAvailability([], checkIn, checkOut, guests, nights);
    } else {
      // Fallback: parallel fetching
      const propsToQuery = propertiesCache || [];
      const results = await Promise.all(propsToQuery.map(prop => {
        const pParams = new URLSearchParams({ property_id: prop.property_id, check_in: checkIn, check_out: checkOut });
        if (roomTypeId) pParams.set('room_type_id', roomTypeId);
        return apiJSON(`/rooms/availability?${pParams}`).then(r => r.ok && r.data ? r.data.map(room => ({ ...room, property_name: prop.name, property_city: prop.city })) : []);
      }));
      renderMultiPropertyAvailability(results.flat(), checkIn, checkOut, guests, nights);
    }
  }
}

const roomsCache = {};

function renderMultiPropertyAvailability(allRooms, checkIn, checkOut, guests, nights) {
  const wrapper = document.getElementById('availability-results-wrapper');
  if (!wrapper) return;
  if (!allRooms || allRooms.length === 0) {
    wrapper.innerHTML = `<div class="availability-section fade-in"><div class="empty-state"><div class="empty-state-icon">🏨</div><div class="empty-state-title">No rooms available</div><div class="empty-state-desc">Try adjusting your dates.</div></div></div>`;
    return;
  }
  const filtered = guests > 1 ? (allRooms.filter(r => r.max_occupancy >= guests).length > 0 ? allRooms.filter(r => r.max_occupancy >= guests) : allRooms) : allRooms;
  filtered.forEach(r => { roomsCache[r.room_id] = r; });

  const grouped = {};
  filtered.forEach(r => {
    const key = r.property_id;
    if (!grouped[key]) grouped[key] = { name: r.property_name, city: r.property_city, rooms: [] };
    grouped[key].rooms.push(r);
  });

  wrapper.innerHTML = `
    <div class="availability-section fade-in" id="availability-section">
      <div class="availability-header">
        <div>
          <div class="section-eyebrow">All Properties · Live Availability</div>
          <h2 class="section-title" style="font-size:1.6rem;margin-bottom:0">${filtered.length} Room${filtered.length !== 1 ? 's' : ''} Available · ${nights} Night${nights !== 1 ? 's' : ''}</h2>
          <div class="text-muted text-sm">${formatDate(checkIn)} → ${formatDate(checkOut)} across ${Object.keys(grouped).length} destinations</div>
        </div>
      </div>
      ${Object.values(grouped).map(g => `
        <div style="margin-bottom:var(--space-8)">
          <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4);">
            <div style="width:36px;height:36px;border-radius:var(--radius-lg);background:rgba(212,137,31,0.15);border:1px solid rgba(212,137,31,0.3);display:flex;align-items:center;justify-content:center;font-size:1.1rem;">🏨</div>
            <div>
              <div style="font-family:var(--font-display);font-size:1.2rem;color:var(--cream-50)">${escHtml(g.name)}</div>
              <div class="text-xs text-muted">${escHtml(g.city)} · ${g.rooms.length} room${g.rooms.length !== 1 ? 's' : ''} available</div>
            </div>
          </div>
          <div class="rooms-grid">
            ${g.rooms.map(r => `
              <div class="room-card" id="room-card-${r.room_id}" data-room-id="${r.room_id}" data-prop-id="${r.property_id}" onclick="selectRoom(${r.room_id},'${checkIn}','${checkOut}',${guests})" style="cursor:pointer;">
                <div class="room-card-header"><div class="room-number">Room ${escHtml(r.room_number)}</div><div class="room-type-badge">${escHtml(r.type_name)}</div></div>
                <div class="room-card-name">${escHtml(r.type_name)} Suite</div>
                <div class="room-card-meta">
                  <div class="room-meta-item"><span class="room-meta-icon">👥</span> Max ${r.max_occupancy} guests</div>
                  <div class="room-meta-item"><span class="room-meta-icon">🌙</span> ${nights} nights</div>
                </div>
                <div class="room-card-pricing">
                  <div><div class="room-nightly-rate">${formatCurrency(r.nightly_rate)} / night</div><div class="room-total-label">Total</div></div>
                  <div class="room-total-rate">${formatCurrency(r.total_rate)}</div>
                </div>
              </div>`).join('')}
          </div>
        </div>`).join('')}
    </div>`;
  wrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderAvailabilityResults(data, checkIn, checkOut, guests, propId, roomTypeId = null) {
  const wrapper = document.getElementById('availability-results-wrapper');
  if (!wrapper) return;
  const nights = nightsBetween(checkIn, checkOut);
  const propName = propertiesCache?.find(p => p.property_id == propId)?.name || 'Property';
  if (!data || data.length === 0) {
    wrapper.innerHTML = `<div class="availability-section fade-in"><div class="empty-state"><div class="empty-state-icon">🏨</div><div class="empty-state-title">No rooms available</div><div class="empty-state-desc">Try different dates or another property.</div></div></div>`;
    return;
  }
  let rooms = guests > 1 ? (data.filter(r => r.max_occupancy >= guests).length > 0 ? data.filter(r => r.max_occupancy >= guests) : data) : data;
  if (roomTypeId) {
    const filteredByType = rooms.filter(r => r.room_type_id == roomTypeId || r.type_id == roomTypeId);
    if (filteredByType.length > 0) rooms = filteredByType;
  }
  rooms.forEach(r => { roomsCache[r.room_id] = { ...r, property_name: propName, property_id: propId }; });

  wrapper.innerHTML = `
    <div class="availability-section fade-in" id="availability-section">
      <div class="availability-header">
        <div>
          <div class="section-eyebrow">Available Rooms · ${escHtml(propName)}</div>
          <h2 class="section-title" style="font-size:1.6rem;margin-bottom:0">${rooms.length} Room${rooms.length !== 1 ? 's' : ''} · ${nights} Night${nights !== 1 ? 's' : ''}</h2>
          <div class="text-muted text-sm">${formatDate(checkIn)} → ${formatDate(checkOut)}</div>
        </div>
      </div>
      <div class="rooms-grid">
        ${rooms.map(r => `
          <div class="room-card" id="room-card-${r.room_id}" data-room-id="${r.room_id}" data-prop-id="${propId}" onclick="selectRoom(${r.room_id},'${checkIn}','${checkOut}',${guests})" style="cursor:pointer;">
            <div class="room-card-header"><div class="room-number">Room ${escHtml(r.room_number)}</div><div class="room-type-badge">${escHtml(r.type_name)}</div></div>
            <div class="room-card-name">${escHtml(r.type_name)} Suite</div>
            <div class="room-card-meta">
              <div class="room-meta-item"><span class="room-meta-icon">👥</span> Up to ${r.max_occupancy} guests</div>
              <div class="room-meta-item"><span class="room-meta-icon">🌙</span> ${nights} nights</div>
            </div>
            <div class="room-card-pricing">
              <div><div class="room-nightly-rate">${formatCurrency(r.nightly_rate)} / night</div><div class="room-total-label">Total</div></div>
              <div class="room-total-rate">${formatCurrency(r.total_rate)}</div>
            </div>
          </div>`).join('')}
      </div>
    </div>`;
  wrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function selectRoom(roomId, checkIn, checkOut, guests, roomData) {
  document.querySelectorAll('.room-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`room-card-${roomId}`)?.classList.add('selected');
  // Capture room data from cache or DOM if not provided
  if (!roomData) {
    roomData = roomsCache[roomId];
  }
  if (!roomData) {
    const card = document.getElementById(`room-card-${roomId}`) || document.querySelector(`[data-room-id="${roomId}"]`);
    if (card) {
      roomData = {
        room_id: roomId,
        room_number: card.querySelector('.room-number')?.textContent.replace('Room ', '').trim() || String(roomId),
        type_name: card.querySelector('.room-card-name')?.textContent.replace(' Suite', '').trim() || 'Deluxe',
        total_rate: parseFloat(card.querySelector('.room-total-rate')?.textContent.replace(/[^0-9.]/g, '') || 0),
        nightly_rate: parseFloat(card.querySelector('.room-nightly-rate')?.textContent.split('/')[0].replace(/[^0-9.]/g, '') || 0),
        max_occupancy: parseInt(card.querySelector('.room-meta-item')?.textContent.replace(/\D/g, '') || 4),
        property_name: propertiesCache?.find(p => p.property_id == parseInt(card.closest('[data-prop-id]')?.dataset?.propId || 0))?.name || null,
      };
      roomsCache[roomId] = roomData;
    }
  }
  if (!Auth.isLoggedIn()) {
    showToast('Please log in', 'Create an account or log in to book.', 'info');
    sessionStorage.setItem('pending_booking', JSON.stringify({ roomId, checkIn, checkOut, guests, roomData }));
    openAuthModal('login'); return;
  }
  openBookingModal(roomId, checkIn, checkOut, guests, roomData);
}

/* ─────────────────────────────────────────────────────────────────────────
   PAGE: REVIEWS (Resort reviews & guest experiences)
   ───────────────────────────────────────────────────────────────────────── */
registerPage('reviews', async (container, params = {}) => {
  const initialPropId = params.property_id || null;
  let selectedPropId = initialPropId ? parseInt(initialPropId) : null;
  let selectedRating = null;

  container.innerHTML = `
    <div class="page">
      <div class="container">
        <div style="margin-bottom:var(--space-6);padding-top:var(--space-4);">
          <div class="section-eyebrow">✦ Verified Stays & Experiences</div>
          <h1 class="heading-display" style="font-size:2.4rem;color:var(--cream-50)">Guest Reviews & Ratings</h1>
          <p class="text-muted" style="margin-top:var(--space-2)">Authentic stories and ratings from guests who experienced the luxury of Kaveri Stays.</p>
        </div>

        <!-- Resort Selector Pills -->
        <div class="resort-selector-pills" id="review-resort-pills">
          <button class="resort-pill-btn ${!selectedPropId ? 'active' : ''}" data-prop="all">✦ All Resorts</button>
          <button class="resort-pill-btn ${selectedPropId === 1 ? 'active' : ''}" data-prop="1">🌲 Kaveri Riverside · Coorg</button>
          <button class="resort-pill-btn ${selectedPropId === 2 ? 'active' : ''}" data-prop="2">🍃 Kaveri Hilltop · Ooty</button>
          <button class="resort-pill-btn ${selectedPropId === 3 ? 'active' : ''}" data-prop="3">🌊 Kaveri Backwater · Alleppey</button>
        </div>

        <!-- Rating Summary Box (Glassmorphic) -->
        <div id="reviews-summary-container">
          <div class="review-summary-card skeleton" style="height: 180px;"></div>
        </div>

        <!-- Reviews Grid -->
        <div id="reviews-feed-container">
          <div class="flex justify-center" style="padding:var(--space-12)"><div class="spinner spinner-lg"></div></div>
        </div>

        <!-- Call to Action Banner -->
        <div class="glass-card" style="margin-top:var(--space-10);text-align:center;padding:var(--space-8);background:linear-gradient(135deg,rgba(15,23,42,0.8),rgba(26,54,93,0.4));border:1px solid rgba(212,137,31,0.25);">
          <h2 class="heading-serif" style="font-size:1.6rem;color:var(--cream-50);margin-bottom:var(--space-2);">Have You Stayed with Us?</h2>
          <p class="text-muted text-sm" style="max-width:550px;margin:0 auto var(--space-4);">We value your feedback! Guests who have completed a stay can leave a verified review from their booking dashboard.</p>
          <div style="display:flex;justify-content:center;gap:var(--space-3);flex-wrap:wrap;">
            <button class="btn btn-primary" onclick="navigateTo('dashboard')">Go to My Bookings 📋</button>
            <button class="btn btn-secondary" onclick="navigateTo('vacancies')">Book Next Stay ✦</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // Attach tab events
  const pills = container.querySelectorAll('.resort-pill-btn');
  pills.forEach(btn => {
    btn.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const propVal = btn.dataset.prop;
      selectedPropId = propVal === 'all' ? null : parseInt(propVal);
      selectedRating = null;
      loadReviewsData(selectedPropId, selectedRating);
    });
  });

  async function loadReviewsData(propId, ratingFilter) {
    const summaryBox = document.getElementById('reviews-summary-container');
    const feedBox = document.getElementById('reviews-feed-container');
    if (!summaryBox || !feedBox) return;

    let url = propId ? `/properties/${propId}/reviews` : `/reviews`;
    if (ratingFilter) {
      url += `?rating=${ratingFilter}`;
    }

    const { ok, data, error } = await apiJSON(url);
    if (!ok || !data) {
      feedBox.innerHTML = `<div class="empty-state"><div class="empty-state-icon">❌</div><div class="empty-state-title">Failed to load reviews</div><div class="empty-state-desc">${escHtml(error || 'Please try again later.')}</div></div>`;
      return;
    }

    const total = data.total_reviews || 0;
    const avg = data.average_rating || 5.0;
    const dist = data.rating_distribution || { 5: 0, 4: 0, 3: 0, 2: 0, 1: 0 };
    const revs = data.reviews || [];

    // Render Summary Card
    summaryBox.innerHTML = `
      <div class="review-summary-card fade-in">
        <div class="review-big-score-box">
          <div class="review-big-score">${avg.toFixed(1)}</div>
          <div style="color:var(--gold-200);font-size:1.2rem;margin-bottom:4px;">${starsHTML(Math.round(avg))}</div>
          <div class="text-xs text-muted" style="margin-bottom:6px;">Based on <strong>${total}</strong> verified review${total !== 1 ? 's' : ''}</div>
          <div class="review-verified-tag">✦ 100% Verified Stays</div>
        </div>

        <div class="review-bars-container">
          ${[5, 4, 3, 2, 1].map(stars => {
            const count = dist[stars] || 0;
            const pct = total > 0 ? Math.round((count / total) * 100) : 0;
            return `
              <div class="review-bar-row">
                <div class="review-bar-label">${stars} ★</div>
                <div class="review-bar-track">
                  <div class="review-bar-fill" style="width:${pct}%;"></div>
                </div>
                <div class="review-bar-count">${count}</div>
              </div>
            `;
          }).join('')}
        </div>

        <div class="review-filter-pills">
          <div class="text-xs text-muted" style="font-weight:600;margin-bottom:2px;">Filter by Rating</div>
          <button class="review-filter-btn ${ratingFilter === null ? 'active' : ''}" onclick="window._setReviewRatingFilter(null)">
            <span>All Reviews</span>
            <span>${total}</span>
          </button>
          ${[5, 4, 3, 2, 1].map(s => `
            <button class="review-filter-btn ${ratingFilter === s ? 'active' : ''}" onclick="window._setReviewRatingFilter(${s})">
              <span>${s} Stars ★</span>
              <span>${dist[s] || 0}</span>
            </button>
          `).join('')}
        </div>
      </div>
    `;

    // Global helper for filter click
    window._setReviewRatingFilter = (r) => {
      selectedRating = r;
      loadReviewsData(selectedPropId, selectedRating);
    };

    // Render Reviews Grid
    if (revs.length === 0) {
      feedBox.innerHTML = `
        <div class="empty-state fade-in" style="padding:var(--space-12);">
          <div class="empty-state-icon">⭐</div>
          <div class="empty-state-title">No reviews found for this selection</div>
          <div class="empty-state-desc">${ratingFilter ? `No ${ratingFilter}-star reviews yet for this resort.` : 'Be the first guest to leave a review after your stay!'}</div>
        </div>
      `;
      return;
    }

    const emojis = { 1: '🌲', 2: '🍃', 3: '🌊' };
    feedBox.innerHTML = `
      <div class="reviews-grid fade-in">
        ${revs.map(r => {
          const initials = r.guest_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || 'G';
          const propEmoji = emojis[r.property_id] || '🏨';
          return `
            <div class="review-card">
              <div>
                <div class="review-card-header">
                  <div class="review-guest-avatar">${initials}</div>
                  <div style="flex-grow:1;">
                    <div style="display:flex;align-items:center;justify-content:space-between;">
                      <strong style="color:var(--cream-50);font-size:0.95rem;">${escHtml(r.guest_name)}</strong>
                      <span class="review-verified-tag">✦ Verified</span>
                    </div>
                    <div class="text-xs text-muted" style="margin-top:2px;">
                      ${r.guest_city ? `${escHtml(r.guest_city)} · ` : ''}${formatDate(r.review_date)}
                    </div>
                    <div class="review-resort-tag">
                      ${propEmoji} ${escHtml(r.property_name)} ${r.room_type_name ? `· <span style="opacity:0.8">${escHtml(r.room_type_name)}</span>` : ''}
                    </div>
                  </div>
                </div>

                <div style="color:var(--gold-200);font-size:1.1rem;margin-bottom:var(--space-3);letter-spacing:2px;">
                  ${starsHTML(r.rating)}
                </div>

                <div class="review-comment-body">
                  "${escHtml(r.comment || 'An exceptional luxury experience amidst tranquil nature.')}"
                </div>
              </div>

              <div class="review-card-footer">
                <span>Stay at ${escHtml(r.city)}</span>
                <span style="color:var(--gold-300);font-weight:600;">${r.rating}.0 / 5.0 ★</span>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  await loadReviewsData(selectedPropId, selectedRating);
});

/* ─────────────────────────────────────────────────────────────────────────
   PAGE: KAVERI AI CONCIERGE (Intelligent Hotel Booking Agent)
   ───────────────────────────────────────────────────────────────────────── */
registerPage('ai-agent', async (container) => {
  container.innerHTML = `
    <div class="page">
      <div class="container" style="max-width:900px;">
        <div style="margin-bottom:var(--space-8);padding-top:var(--space-4);text-align:center;">
          <div class="section-eyebrow">✦ Intelligent Concierge & Booking Agent</div>
          <h1 class="heading-display" style="font-size:2.6rem;color:var(--cream-50)">Kaveri AI Assistant</h1>
          <p class="text-muted" style="margin-top:var(--space-2);max-width:600px;margin-left:auto;margin-right:auto;">
            Ask questions in plain English, query real-time bookings, check your total spend, and search available sanctuary suites.
          </p>
        </div>

        <div class="glass-card" style="padding:var(--space-6);margin-bottom:var(--space-6);background:linear-gradient(135deg,rgba(15,23,42,0.85),rgba(26,54,93,0.5));border:1px solid rgba(212,137,31,0.3);">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:var(--space-4);margin-bottom:var(--space-4);">
            <div style="display:flex;align-items:center;gap:var(--space-3);">
              <div class="ai-avatar-badge" style="width:44px;height:44px;font-size:1.3rem;">✨</div>
              <div>
                <h2 style="font-family:var(--font-display);font-size:1.3rem;color:var(--cream-50);margin:0;">Kaveri AI Concierge</h2>
                <div class="ai-status-indicator">
                  <span class="ai-status-dot"></span> Online · Connected to Live PostgreSQL Database
                </div>
              </div>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="resetAiSession()">🔄 Reset Session</button>
          </div>

          <div style="font-size:0.85rem;color:var(--charcoal-300);margin-bottom:var(--space-4);">
            Try asking one of these quick prompts:
          </div>
          <div class="ai-suggestions-container" id="page-ai-suggestions" style="background:transparent;border:none;padding:0 0 var(--space-4) 0;">
            <!-- Rendered by initAiConcierge -->
          </div>

          <!-- Full Page Chat Area -->
          <div class="ai-messages-container" id="page-ai-messages" style="height:420px;background:rgba(15,23,42,0.6);border:1px solid rgba(255,255,255,0.08);border-radius:var(--radius-xl);padding:var(--space-5);">
          </div>

          <!-- Input Field -->
          <div style="margin-top:var(--space-4);">
            <form id="page-ai-form" onsubmit="return false;" style="display:flex;gap:var(--space-2);">
              <input
                type="text"
                id="page-ai-input"
                class="ai-input-field"
                placeholder="Type your question (e.g., 'Show my pending bookings', 'Find rooms in Coorg')..."
                autocomplete="off"
              />
              <button type="submit" id="page-ai-send-btn" class="ai-send-btn">
                <span>Send</span> ✦
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  `;

  // Attach page-specific AI chat events
  const pageForm = document.getElementById('page-ai-form');
  const pageInput = document.getElementById('page-ai-input');
  if (pageForm && pageInput) {
    pageForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = pageInput.value.trim();
      if (!text) return;
      pageInput.value = '';
      sendAiChatMessage(text, 'page');
    });
  }

  // Populate prompt pills on page
  renderPageSuggestions();
  renderAiHistory('page');
});

/* ─────────────────────────────────────────────────────────────────────────
   PAGE: VACANCIES (Room availability across all properties)
   ───────────────────────────────────────────────────────────────────────── */
registerPage('vacancies', async (container) => {
  container.innerHTML = `
    <div class="page">
      <div class="container">
        <div style="margin-bottom:var(--space-8);padding-top:var(--space-4);">
          <div class="section-eyebrow">Live Availability</div>
          <h1 class="heading-display" style="font-size:2.4rem;color:var(--cream-50)">Room Vacancies</h1>
          <p class="text-muted" style="margin-top:var(--space-2)">Check real-time availability across all Kaveri Stays properties.</p>
        </div>

        <!-- Filters -->
        <div class="glass-card" style="margin-bottom:var(--space-6)">
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:var(--space-4);align-items:end;">
            <div class="search-field">
              <label class="search-label" for="vac-property">Property</label>
              <select class="search-input" id="vac-property" aria-label="Select Property"><option value="">All Properties</option></select>
            </div>
            <div class="search-field">
              <label class="search-label" for="vac-checkin">Check-in</label>
              <input type="date" class="search-input" id="vac-checkin" aria-label="Check-in Date" />
            </div>
            <div class="search-field">
              <label class="search-label" for="vac-checkout">Check-out</label>
              <input type="date" class="search-input" id="vac-checkout" aria-label="Check-out Date" />
            </div>
            <div class="search-field">
              <label class="search-label" for="vac-type">Room Type</label>
              <select class="search-input" id="vac-type" aria-label="Select Room Type">
                <option value="">Any Type</option>
                <option value="1">Standard</option>
                <option value="2">Deluxe</option>
                <option value="3">Suite</option>
              </select>
            </div>
            <button class="btn btn-primary btn-lg" id="vac-search-btn" aria-label="Search Room Vacancies">Search</button>
          </div>
        </div>

        <!-- Results area -->
        <div id="vac-results">
          <div class="empty-state">
            <div class="empty-state-icon">🔍</div>
            <div class="empty-state-title">Search to see vacancies</div>
            <div class="empty-state-desc">Select dates and click Search to check real-time room availability.</div>
          </div>
        </div>
      </div>
    </div>`;

  // Populate property select
  if (!propertiesCache) await loadPropertiesCache();
  const ps = document.getElementById('vac-property');
  if (ps && propertiesCache) propertiesCache.forEach(p => ps.innerHTML += `<option value="${p.property_id}">${escHtml(p.name)} — ${escHtml(p.city)}</option>`);

  const d1 = daysFromNow(1), d3 = daysFromNow(3);
  document.getElementById('vac-checkin').value = d1;
  document.getElementById('vac-checkin').min = todayStr();
  document.getElementById('vac-checkout').value = d3;
  document.getElementById('vac-checkout').min = d1;

  document.getElementById('vac-search-btn').addEventListener('click', searchVacancies);
  document.getElementById('vac-checkin').addEventListener('change', e => {
    const d = new Date(e.target.value); d.setDate(d.getDate() + 1);
    document.getElementById('vac-checkout').min = d.toISOString().split('T')[0];
  });

  // Auto-search on load
  await searchVacancies();
});

async function loadPropertiesCache() {
  const { ok, data } = await apiJSON('/properties');
  if (ok && data) propertiesCache = data;
}

async function searchVacancies() {
  const propId = document.getElementById('vac-property')?.value;
  const checkIn = document.getElementById('vac-checkin')?.value;
  const checkOut = document.getElementById('vac-checkout')?.value;
  const roomType = document.getElementById('vac-type')?.value;
  if (!checkIn || !checkOut) { showToast('Select dates', '', 'warning'); return; }
  if (new Date(checkOut) <= new Date(checkIn)) { showToast('Invalid dates', 'Check-out must be after check-in.', 'error'); return; }
  const btn = document.getElementById('vac-search-btn');
  setLoading(btn, true, 'Searching…');
  const results = document.getElementById('vac-results');
  results.innerHTML = `<div class="flex justify-center" style="padding:var(--space-12)"><div class="spinner spinner-lg"></div></div>`;
  const nights = nightsBetween(checkIn, checkOut);

  let allRooms = [];
  if (propId) {
    const params = new URLSearchParams({ property_id: propId, check_in: checkIn, check_out: checkOut });
    if (roomType) params.set('room_type_id', roomType);
    const { ok, data } = await apiJSON(`/rooms/availability?${params}`);
    if (ok && data) allRooms = data;
  } else {
    const params = new URLSearchParams({ check_in: checkIn, check_out: checkOut });
    if (roomType) params.set('room_type_id', roomType);
    const { ok, data } = await apiJSON(`/rooms/availability?${params}`);
    if (ok && data) {
      allRooms = data;
    } else {
      const propsToQuery = propertiesCache || [];
      const results = await Promise.all(propsToQuery.map(prop => {
        const pParams = new URLSearchParams({ property_id: prop.property_id, check_in: checkIn, check_out: checkOut });
        if (roomType) pParams.set('room_type_id', roomType);
        return apiJSON(`/rooms/availability?${pParams}`).then(r => r.ok && r.data ? r.data.map(room => ({ ...room, property_name: prop.name, property_city: prop.city })) : []);
      }));
      allRooms = results.flat();
    }
  }
  setLoading(btn, false);

  if (allRooms.length === 0) {
    results.innerHTML = `<div class="empty-state"><div class="empty-state-icon">😔</div><div class="empty-state-title">No rooms available</div><div class="empty-state-desc">No rooms match your criteria for ${formatDate(checkIn)} → ${formatDate(checkOut)}. Try adjusting dates or room type.</div></div>`;
    return;
  }

  // Group by property
  const grouped = {};
  allRooms.forEach(r => {
    roomsCache[r.room_id] = r;
    const key = r.property_id;
    if (!grouped[key]) grouped[key] = { name: r.property_name, city: r.property_city, rooms: [] };
    grouped[key].rooms.push(r);
  });

  results.innerHTML = `
    <div style="margin-bottom:var(--space-4);display:flex;align-items:center;justify-content:space-between;">
      <div>
        <div class="text-muted text-sm">${formatDate(checkIn)} → ${formatDate(checkOut)} · ${nights} night${nights !== 1 ? 's' : ''}</div>
        <div style="font-weight:600;color:var(--cream-50)">${allRooms.length} room${allRooms.length !== 1 ? 's' : ''} available across ${Object.keys(grouped).length} propert${Object.keys(grouped).length === 1 ? 'y' : 'ies'}</div>
      </div>
      ${Auth.isLoggedIn() ? '' : '<button class="btn btn-primary btn-sm" onclick="openAuthModal(\'login\')">Login to Book</button>'}
    </div>
    ${Object.values(grouped).map(g => `
      <div style="margin-bottom:var(--space-8)">
        <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4);">
          <div style="width:40px;height:40px;border-radius:var(--radius-lg);background:rgba(212,137,31,0.15);border:1px solid rgba(212,137,31,0.3);display:flex;align-items:center;justify-content:center;font-size:1.2rem;">🏨</div>
          <div>
            <div style="font-family:var(--font-display);font-size:1.2rem;color:var(--cream-50)">${escHtml(g.name)}</div>
            <div class="text-xs text-muted">${escHtml(g.city)} · ${g.rooms.length} room${g.rooms.length !== 1 ? 's' : ''} available</div>
          </div>
        </div>
        <div class="rooms-grid">
          ${g.rooms.map(r => `
            <div class="room-card" id="room-card-${r.room_id}" data-room-id="${r.room_id}" data-prop-id="${r.property_id}" onclick="selectRoom(${r.room_id},'${checkIn}','${checkOut}',1)" style="cursor:pointer;">
              <div class="room-card-header"><div class="room-number">Room ${escHtml(r.room_number)}</div><div class="room-type-badge">${escHtml(r.type_name)}</div></div>
              <div class="room-card-name">${escHtml(r.type_name)} Suite</div>
              <div class="room-card-meta">
                <div class="room-meta-item"><span class="room-meta-icon">👥</span> Max ${r.max_occupancy}</div>
                <div class="room-meta-item"><span class="room-meta-icon">🌙</span> ${nights}n</div>
              </div>
              <div class="room-card-pricing">
                <div><div class="room-nightly-rate">${formatCurrency(r.nightly_rate)}/night</div><div class="room-total-label">Total</div></div>
                <div class="room-total-rate">${formatCurrency(r.total_rate)}</div>
              </div>
            </div>`).join('')}
        </div>
      </div>`).join('')}`;
}

/* ─────────────────────────────────────────────────────────────────────────
   PAGE: DASHBOARD (My Bookings)
   ───────────────────────────────────────────────────────────────────────── */
registerPage('dashboard', async (container) => {
  if (!Auth.isLoggedIn()) { openAuthModal('login'); navigateTo('home'); showToast('Login required', '', 'info'); return; }
  const user = Auth.user;
  container.innerHTML = `
    <div class="page">
      <div class="container">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:var(--space-8);padding-top:var(--space-4);flex-wrap:wrap;gap:var(--space-4)">
          <div>
            <div class="section-eyebrow">Welcome back</div>
            <h1 class="heading-display" style="font-size:2.2rem;color:var(--cream-50)">${escHtml(user?.name || 'Guest')}</h1>
            <div class="text-sm text-muted" style="margin-top:var(--space-1)">${escHtml(user?.email || '')} · <span class="room-type-badge" style="font-size:0.7rem">${escHtml(user?.role || 'guest')}</span></div>
          </div>
          <div style="display:flex;gap:var(--space-3);flex-wrap:wrap">
            <button class="btn btn-primary" onclick="navigateTo('home')">+ New Booking</button>
            <button class="btn btn-outline" onclick="navigateTo('vacancies')">Check Vacancies</button>
            ${Auth.isStaff() ? `<button class="btn btn-secondary" onclick="navigateTo('admin')">Admin Panel →</button>` : ''}
          </div>
        </div>
        <div class="stat-cards-grid" id="dash-stats"></div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-5);flex-wrap:wrap;gap:var(--space-3)">
          <div>
            <div class="section-eyebrow">Reservations</div>
            <h2 class="heading-serif" style="font-size:1.4rem;color:var(--cream-50)">Booking History</h2>
          </div>
          <div id="dash-filter-container"></div>
        </div>
        <div id="bookings-area"><div class="flex justify-center" style="padding:var(--space-12)"><div class="spinner spinner-lg"></div></div></div>
      </div>
    </div>`;
  await loadDashboard();
});

let allBookings = [];
let currentStatusFilter = '';

function renderDashboardFilters() {
  const confirmed = allBookings.filter(b => b.status === 'confirmed').length;
  const completed = allBookings.filter(b => b.status === 'checked_out').length;
  const cancelled = allBookings.filter(b => b.status === 'cancelled').length;
  const filterContainer = document.getElementById('dash-filter-container');
  if (filterContainer) {
    filterContainer.innerHTML = `
      <div class="filter-pills-bar">
        <button class="filter-pill ${currentStatusFilter === '' ? 'active' : ''}" onclick="setDashboardFilter('')">All Stays <span class="filter-pill-count">${allBookings.length}</span></button>
        <button class="filter-pill ${currentStatusFilter === 'confirmed' ? 'active' : ''}" onclick="setDashboardFilter('confirmed')">Confirmed <span class="filter-pill-count">${confirmed}</span></button>
        <button class="filter-pill ${currentStatusFilter === 'checked_out' ? 'active' : ''}" onclick="setDashboardFilter('checked_out')">Completed <span class="filter-pill-count">${completed}</span></button>
        <button class="filter-pill ${currentStatusFilter === 'cancelled' ? 'active' : ''}" onclick="setDashboardFilter('cancelled')">Cancelled <span class="filter-pill-count">${cancelled}</span></button>
      </div>`;
  }
}

async function loadDashboard() {
  const { ok, data } = await apiJSON('/bookings?limit=100');
  if (!ok || !data) { document.getElementById('bookings-area').innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-title">Could not load bookings</div></div>`; return; }
  allBookings = data.items || [];
  const confirmed = allBookings.filter(b => b.status === 'confirmed').length;
  const checkedIn = allBookings.filter(b => b.status === 'checked_in').length;
  const totalSpent = allBookings.reduce((s, b) => s + (b.amount_paid || 0), 0);

  const statsEl = document.getElementById('dash-stats');
  if (statsEl) statsEl.innerHTML = `
    <div class="stat-card stat-card-gold"><div class="stat-card-label">Total Bookings</div><div class="stat-card-value">${data.total}</div><div class="stat-card-icon">📋</div></div>
    <div class="stat-card stat-card-blue"><div class="stat-card-label">Upcoming</div><div class="stat-card-value">${confirmed}</div><div class="stat-card-icon">📅</div></div>
    <div class="stat-card stat-card-green"><div class="stat-card-label">Active Stays</div><div class="stat-card-value">${checkedIn}</div><div class="stat-card-icon">🏨</div></div>
    <div class="stat-card stat-card-purple"><div class="stat-card-label">Amount Paid</div><div class="stat-card-value" style="font-size:1.3rem">${formatCurrency(totalSpent)}</div><div class="stat-card-icon">💰</div></div>`;

  renderDashboardFilters();
  loadBookingsTable(currentStatusFilter);
}

function setDashboardFilter(status) {
  currentStatusFilter = status;
  renderDashboardFilters();
  loadBookingsTable(currentStatusFilter);
}

function loadBookingsTable(statusFilter) {
  const filtered = statusFilter ? allBookings.filter(b => b.status === statusFilter) : allBookings;
  const area = document.getElementById('bookings-area'); if (!area) return;
  if (filtered.length === 0) {
    area.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🌴</div><div class="empty-state-title">No bookings found</div><div class="empty-state-desc">Ready to plan your next escape?</div><button class="btn btn-primary" onclick="navigateTo('home')">Explore Properties</button></div>`;
    return;
  }
  area.innerHTML = `
    <div class="stay-cards-list">
      ${filtered.map(b => {
    const nights = Math.max(1, nightsBetween(b.check_in, b.check_out));
    const due = Math.max(0, (b.total_amount || 0) - (b.amount_paid || 0));
    const method = (b.payment_method || 'card').toUpperCase();
    return `
          <div class="stay-card" id="stay-card-${b.booking_id}">
            <div class="stay-card-header">
              <div>
                <span class="stay-card-title">BOOKING #${b.booking_id}</span>
                <span class="stay-card-badge">ROOM ID ${b.room_id || b.room_number || '—'}</span>
              </div>
              <div>${statusBadge(b.status)}</div>
            </div>
            
            <div class="stay-card-body">
              <div class="stay-dates-group">
                <div class="stay-date-box">
                  <div class="stay-date-label">Check-In</div>
                  <div class="stay-date-value">${formatDate(b.check_in)}</div>
                </div>
                <div class="stay-date-box">
                  <div class="stay-date-label">Check-Out</div>
                  <div class="stay-date-value">${formatDate(b.check_out)}</div>
                </div>
              </div>

              <div>
                <div class="stay-meta">${nights} Night${nights > 1 ? 's' : ''} · ${b.guest_count} Guest${b.guest_count > 1 ? 's' : ''}</div>
                <div class="stay-submeta">Paid via ${method} · ${escHtml(b.property_name || 'Kaveri Stays')}</div>
              </div>

              <div class="stay-financials">
                <div class="stay-total">Total: <strong>${formatCurrency(b.total_amount)}</strong></div>
                <div class="stay-paid">Paid: ${formatCurrency(b.amount_paid)}</div>
                ${due > 0 && b.status !== 'cancelled'
        ? `<div class="stay-due-red">Due Balance: ${formatCurrency(due)}</div>`
        : `<div class="stay-settled-green">Fully Settled ✓</div>`}
              </div>
            </div>

            <div class="stay-actions">
              ${b.status === 'checked_in' ? `<button class="btn btn-secondary btn-sm" onclick="adminCheckOut(${b.booking_id})">Complete Checkout</button>` : `<button class="btn btn-secondary btn-sm" onclick="openBookingDetail(${b.booking_id})">View Details</button>`}
              ${b.status === 'confirmed' ? `<button class="btn btn-danger-outline btn-sm" onclick="cancelBooking(${b.booking_id})">Cancel Stay</button>` : ''}
              ${b.status === 'checked_out'
                ? (b.review
                    ? `<div class="stay-review-badge">✦ You rated this stay: <strong style="color:var(--gold-200);">${'★'.repeat(b.review.rating)}${'☆'.repeat(5 - b.review.rating)}</strong> ${b.review.comment ? `<span style="font-style:italic;color:var(--cream-100);display:block;margin-top:2px;">"${escHtml(b.review.comment)}"</span>` : ''}</div>`
                    : `<button class="btn btn-primary btn-sm" onclick="openReviewModal(${b.booking_id})">Leave Review ⭐</button>`)
                : ''}
              ${due > 0 && b.status !== 'cancelled'
        ? `<button class="btn btn-forest btn-sm" onclick="settleBalance(${b.booking_id}, ${due})">Settle Balance (${formatCurrency(due)}) →</button>`
        : ''}
            </div>
          </div>
        `;
  }).join('')}
    </div>`;
}

async function settleBalance(bookingId, dueAmount) {
  const { ok, error } = await apiJSON(`/bookings/${bookingId}/payments`, {
    method: 'POST',
    body: JSON.stringify({ amount: dueAmount, method: 'card' })
  });
  if (!ok) {
    showToast('Payment failed', error, 'error');
    return;
  }
  showToast('Balance Settled! ✓', `Payment of ${formatCurrency(dueAmount)} recorded.`, 'success');

  // Fetch updated booking details to show the secured stay confirmation display
  const { ok: bok, data: updatedBooking } = await apiJSON(`/bookings/${bookingId}`);
  if (bok && updatedBooking) {
    showBookingSuccess(updatedBooking, null, 'Remaining Balance Paid');
  }

  await loadDashboard();
}

function cancelBooking(id) {
  const b = allBookings.find(x => x.booking_id == id);
  const paid = b ? (b.amount_paid || 0) : 0;
  const prop = b ? (b.property_name || 'Kaveri Stays') : 'Kaveri Stays';

  document.getElementById('cancel-modal-title').textContent = 'Cancel Reservation';
  document.getElementById('cancel-modal-body').innerHTML = `
    <div style="text-align:center;padding:var(--space-2) 0 var(--space-4);">
      <div style="width:52px;height:52px;border-radius:50%;background:rgba(229,62,62,0.12);border:1.5px solid #e53e3e;color:#fc8181;display:flex;align-items:center;justify-content:center;font-size:1.6rem;margin:0 auto var(--space-3);">⚠️</div>
      <div style="display:inline-block;padding:4px 12px;background:rgba(229,62,62,0.12);border:1px solid rgba(229,62,62,0.3);border-radius:var(--radius-full);color:#feb2b2;font-size:0.75rem;font-weight:700;letter-spacing:0.05em;margin-bottom:var(--space-2);">CANCELLATION REQUEST</div>
      <h3 class="heading-serif" style="font-size:1.5rem;color:var(--cream-50);margin-bottom:6px;">Cancel Booking #${id}?</h3>
      <p class="text-xs text-muted" style="margin-bottom:var(--space-4);">Under our flexible cancellation policy, your full deposit will be initiated for refund.</p>

      <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:var(--radius-lg);padding:var(--space-4);text-align:left;margin-bottom:var(--space-5);">
        <div class="booking-summary-row"><span class="booking-summary-label">Property</span><span class="booking-summary-value">${escHtml(prop)}</span></div>
        <div class="booking-summary-row" style="margin-top:var(--space-2);"><span class="booking-summary-label">Deposit Paid</span><span class="booking-summary-value" style="color:var(--cream-50);">${formatCurrency(paid)}</span></div>
        <div class="booking-summary-row" style="margin-top:var(--space-2);padding-top:var(--space-2);border-top:1px dashed rgba(255,255,255,0.1);"><span style="color:#68d391;font-weight:700;">Refund Eligible</span><span style="color:#68d391;font-weight:800;font-size:1.05rem;">${formatCurrency(paid)} (100%)</span></div>
      </div>

      <div style="display:flex;flex-direction:column;gap:var(--space-3);">
        <button class="btn btn-danger w-full" id="confirm-cancel-action-btn" style="padding:14px;border-radius:var(--radius-full);font-size:0.95rem;font-weight:700;" onclick="executeCancellation(${id})">Confirm Cancellation</button>
        <button class="btn btn-outline w-full" style="padding:12px;border-radius:var(--radius-full);font-size:0.9rem;" onclick="closeCancelModal()">Keep My Reservation</button>
      </div>
    </div>
  `;
  document.getElementById('cancel-modal-overlay')?.classList.add('active');
}

function closeCancelModal() {
  document.getElementById('cancel-modal-overlay')?.classList.remove('active');
}

async function executeCancellation(id) {
  const btn = document.getElementById('confirm-cancel-action-btn');
  if (btn) setLoading(btn, true, 'Processing Cancellation…');
  const { ok, error } = await apiJSON(`/bookings/${id}/cancel`, { method: 'POST' });
  if (btn) setLoading(btn, false);
  if (!ok) {
    showToast('Failed to cancel', error, 'error');
    return;
  }

  const b = allBookings.find(x => x.booking_id == id);
  const paid = b ? (b.amount_paid || 0) : 0;

  // Show the confirmation display
  document.getElementById('cancel-modal-title').textContent = 'Cancellation Confirmed';
  document.getElementById('cancel-modal-body').innerHTML = `
    <div style="text-align:center;padding:var(--space-2) 0 var(--space-4);">
      <div style="width:52px;height:52px;border-radius:50%;background:rgba(229,62,62,0.15);border:1.5px solid #e53e3e;color:#fc8181;display:flex;align-items:center;justify-content:center;font-size:1.8rem;margin:0 auto var(--space-3);">✕</div>
      <div style="display:inline-block;padding:4px 12px;background:rgba(229,62,62,0.12);border:1px solid rgba(229,62,62,0.3);border-radius:var(--radius-full);color:#feb2b2;font-size:0.75rem;font-weight:700;letter-spacing:0.05em;margin-bottom:var(--space-2);">RESERVATION CANCELLED</div>
      <h3 class="heading-serif" style="font-size:1.7rem;color:var(--cream-50);margin-bottom:4px">Booking #${id} Cancelled</h3>
      <p class="text-xs text-muted" style="margin-bottom:var(--space-5)">Status updated to: <strong style="color:#fc8181">cancelled</strong></p>

      <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:var(--radius-lg);padding:var(--space-4);text-align:left;margin-bottom:var(--space-6);">
        <div class="booking-summary-row"><span class="booking-summary-label">Booking ID</span><span class="booking-summary-value">#${id}</span></div>
        <div class="booking-summary-row" style="margin-top:var(--space-2);"><span class="booking-summary-label">Refund Amount</span><span class="booking-summary-value" style="color:#68d391;font-weight:700;">${formatCurrency(paid)}</span></div>
        <div class="booking-summary-row" style="margin-top:var(--space-2);"><span class="booking-summary-label">Refund Timeline</span><span class="booking-summary-value">3–5 Business Days</span></div>
        <div class="booking-summary-row" style="margin-top:var(--space-2);padding-top:var(--space-2);border-top:1px dashed rgba(255,255,255,0.1);"><span class="booking-summary-label">Cancellation Fee</span><span class="booking-summary-value" style="color:var(--cream-100);">₹0 (Free Cancellation)</span></div>
      </div>

      <div style="display:flex;flex-direction:column;gap:var(--space-3);">
        <button class="btn btn-forest w-full" style="padding:14px;border-radius:var(--radius-full);font-size:0.95rem;" onclick="closeCancelModal();loadDashboard();">View My Reservations</button>
        <button class="btn btn-outline w-full" style="padding:12px;border-radius:var(--radius-full);font-size:0.9rem;" onclick="closeCancelModal();navigateTo('vacancies')">Book Another Stay ✦</button>
      </div>
    </div>
  `;

  showToast('Booking Cancelled', `Booking #${id} has been cancelled.`, 'info');
  await loadDashboard();
}

/* ─────────────────────────────────────────────────────────────────────────
   PAGE: ADMIN PANEL
   ───────────────────────────────────────────────────────────────────────── */
registerPage('admin', async (container) => {
  if (!Auth.isLoggedIn() || !Auth.isStaff()) { showToast('Access denied', 'Staff or above required.', 'error'); navigateTo('home'); return; }
  const user = Auth.user;
  const isManager = Auth.isManager();
  container.innerHTML = `
    <div class="page">
      <div class="container">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-6);padding-top:var(--space-4);flex-wrap:wrap;gap:var(--space-4)">
          <div>
            <div class="section-eyebrow">🛡️ Admin Panel</div>
            <h1 class="heading-display" style="font-size:2rem;color:var(--cream-50)">Hotel Operations</h1>
            <div class="text-sm text-muted">${escHtml(user?.name)} · <span class="room-type-badge">${escHtml(user?.role)}</span> ${user?.property_id ? `· Property #${user.property_id}` : ''}</div>
          </div>
          <button class="btn btn-secondary" onclick="navigateTo('dashboard')">← My Dashboard</button>
        </div>

        <!-- Admin stat cards -->
        <div class="stat-cards-grid" id="admin-stats">
          <div class="stat-card stat-card-gold skeleton" style="height:110px"></div>
          <div class="stat-card stat-card-blue skeleton" style="height:110px"></div>
          <div class="stat-card stat-card-green skeleton" style="height:110px"></div>
          <div class="stat-card stat-card-purple skeleton" style="height:110px"></div>
        </div>

        <!-- Pill tabs -->
        <div class="pill-tabs" id="admin-tabs" style="margin-bottom:var(--space-6)">
          <div class="pill-tab active" data-admin-tab="bookings">All Bookings</div>
          <div class="pill-tab" data-admin-tab="checkin">Check-in / Out</div>
          <div class="pill-tab" data-admin-tab="reviews">Guest Reviews ⭐</div>
          ${isManager ? `<div class="pill-tab" data-admin-tab="reports">Reports</div>` : ''}
        </div>

        <!-- Tab content -->
        <div id="admin-content">
          <div class="flex justify-center" style="padding:var(--space-12)"><div class="spinner spinner-lg"></div></div>
        </div>
      </div>
    </div>`;

  // Tab switching
  document.querySelectorAll('[data-admin-tab]').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('[data-admin-tab]').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      loadAdminTab(t.dataset.adminTab);
    });
  });

  await loadAdminStats();
  await loadAdminTab('bookings');
});

async function loadAdminStats() {
  const { ok, data } = await apiJSON('/bookings?limit=100');
  if (!ok || !data) return;
  const items = data.items || [];
  const checkedIn = items.filter(b => b.status === 'checked_in');
  const confirmed = items.filter(b => b.status === 'confirmed');
  const revenue = items.reduce((s, b) => s + (b.amount_paid || 0), 0);
  const el = document.getElementById('admin-stats');
  if (el) el.innerHTML = `
    <div class="stat-card stat-card-gold"><div class="stat-card-label">Total Bookings</div><div class="stat-card-value">${data.total}</div><div class="stat-card-icon">📋</div></div>
    <div class="stat-card stat-card-green"><div class="stat-card-label">Currently Checked In</div><div class="stat-card-value">${checkedIn.length}</div><div class="stat-card-icon">🏨</div></div>
    <div class="stat-card stat-card-blue"><div class="stat-card-label">Upcoming Arrivals</div><div class="stat-card-value">${confirmed.length}</div><div class="stat-card-icon">📅</div></div>
    <div class="stat-card stat-card-purple"><div class="stat-card-label">Revenue Collected</div><div class="stat-card-value" style="font-size:1.3rem">${formatCurrency(revenue)}</div><div class="stat-card-icon">💰</div></div>`;
}

async function loadAdminTab(tab) {
  const content = document.getElementById('admin-content'); if (!content) return;
  content.innerHTML = `<div class="flex justify-center" style="padding:var(--space-12)"><div class="spinner spinner-lg"></div></div>`;

  if (tab === 'bookings') {
    const { ok, data } = await apiJSON('/bookings?limit=100&sort=check_in&sort_order=desc');
    if (!ok || !data) { content.innerHTML = `<div class="empty-state"><div class="empty-state-title">Failed to load</div></div>`; return; }
    const items = data.items || [];
    content.innerHTML = `
      <div style="display:flex;gap:var(--space-3);margin-bottom:var(--space-4);flex-wrap:wrap">
        <label class="sr-only" for="admin-status-filter">Filter bookings by status</label>
        <select class="search-input" style="width:auto" id="admin-status-filter" aria-label="Filter bookings by status">
          <option value="">All Statuses</option>
          <option value="confirmed">Confirmed</option>
          <option value="checked_in">Checked In</option>
          <option value="checked_out">Checked Out</option>
          <option value="cancelled">Cancelled</option>
          <option value="no_show">No-Show</option>
        </select>
      </div>
      <div class="bookings-table-wrapper" id="admin-table-wrap">
        ${renderAdminTable(items)}
      </div>`;
    document.getElementById('admin-status-filter')?.addEventListener('change', e => {
      const f = e.target.value;
      document.getElementById('admin-table-wrap').innerHTML = renderAdminTable(f ? items.filter(b => b.status === f) : items);
    });
  }

  if (tab === 'checkin') {
    const { ok, data } = await apiJSON('/bookings?limit=100');
    if (!ok || !data) { content.innerHTML = `<div class="empty-state"><div class="empty-state-title">Failed to load</div></div>`; return; }
    const items = data.items || [];
    const arrivals = items.filter(b => b.status === 'confirmed');
    const inHouse = items.filter(b => b.status === 'checked_in');
    content.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-6);">
        <div>
          <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4)">
            <div style="width:10px;height:10px;border-radius:50%;background:#63b3ed"></div>
            <div class="heading-serif" style="font-size:1.1rem;color:var(--cream-50)">Upcoming Arrivals (${arrivals.length})</div>
          </div>
          ${arrivals.length === 0 ? `<div class="empty-state" style="padding:var(--space-8)"><div class="empty-state-icon">✅</div><div class="empty-state-title">No pending arrivals</div></div>` :
        arrivals.map(b => `
            <div class="glass-card" style="margin-bottom:var(--space-3);padding:var(--space-4)">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--space-2)">
                <div>
                  <div style="font-weight:600;color:var(--cream-50)">${escHtml(b.guest_name || 'Guest')}</div>
                  <div class="text-xs text-muted">Room ${escHtml(b.room_number)} · ${escHtml(b.property_name)}</div>
                  <div class="text-xs text-muted">Check-in: <strong style="color:var(--gold-300)">${formatDate(b.check_in)}</strong></div>
                </div>
                <button class="btn btn-success btn-sm" onclick="adminCheckIn(${b.booking_id})">✓ Check In</button>
              </div>
            </div>`).join('')}
        </div>
        <div>
          <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4)">
            <div style="width:10px;height:10px;border-radius:50%;background:#68d391"></div>
            <div class="heading-serif" style="font-size:1.1rem;color:var(--cream-50)">Currently In-House (${inHouse.length})</div>
          </div>
          ${inHouse.length === 0 ? `<div class="empty-state" style="padding:var(--space-8)"><div class="empty-state-icon">🏨</div><div class="empty-state-title">No active guests</div></div>` :
        inHouse.map(b => `
            <div class="glass-card" style="margin-bottom:var(--space-3);padding:var(--space-4)">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--space-2)">
                <div>
                  <div style="font-weight:600;color:var(--cream-50)">${escHtml(b.guest_name || 'Guest')}</div>
                  <div class="text-xs text-muted">Room ${escHtml(b.room_number)} · ${escHtml(b.property_name)}</div>
                  <div class="text-xs text-muted">Check-out: <strong style="color:var(--gold-300)">${formatDate(b.check_out)}</strong></div>
                </div>
                <button class="btn btn-outline btn-sm" onclick="adminCheckOut(${b.booking_id})">↩ Check Out</button>
              </div>
            </div>`).join('')}
        </div>
      </div>`;
  }

  if (tab === 'reports' && Auth.isManager()) {
    const today = todayStr();
    const monthStart = today.slice(0, 8) + '01';
    content.innerHTML = `
      <div class="glass-card" style="margin-bottom:var(--space-6)">
        <div class="heading-serif" style="font-size:1.1rem;color:var(--cream-50);margin-bottom:var(--space-4)">Report Date Range</div>
        <div style="display:flex;gap:var(--space-4);align-items:flex-end;flex-wrap:wrap">
          <div class="search-field">
            <label class="search-label" for="report-start">From</label>
            <input type="date" class="search-input" id="report-start" aria-label="Report Start Date" value="${monthStart}" />
          </div>
          <div class="search-field">
            <label class="search-label" for="report-end">To</label>
            <input type="date" class="search-input" id="report-end" aria-label="Report End Date" value="${today}" />
          </div>
          <button class="btn btn-primary" id="run-report-btn" onclick="runReports()">Run Reports</button>
        </div>
      </div>
      <div id="report-results"><div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-title">Click Run Reports</div></div></div>`;
    await runReports();
  }

  if (tab === 'reviews') {
    const { ok, data } = await apiJSON('/reviews/stats');
    if (!ok || !data) { content.innerHTML = `<div class="empty-state"><div class="empty-state-title">Failed to load reviews</div></div>`; return; }
    
    const { ok: rOk, data: revData } = await apiJSON('/reviews?limit=100');
    const allRevs = rOk && revData ? revData.reviews : [];

    content.innerHTML = `
      <div style="margin-bottom:var(--space-6);">
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:var(--space-4);margin-bottom:var(--space-6);">
          ${data.resorts.map(r => `
            <div class="stat-card stat-card-gold" style="padding:var(--space-4);">
              <div class="stat-card-label">${escHtml(r.property_name)} (${escHtml(r.city)})</div>
              <div class="stat-card-value" style="font-size:1.8rem;color:var(--gold-200);">${r.average_rating.toFixed(1)} ★</div>
              <div class="text-xs text-muted" style="margin-top:4px;">${r.total_reviews} verified reviews</div>
            </div>
          `).join('')}
        </div>

        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--space-4);flex-wrap:wrap;gap:var(--space-3);">
          <h2 class="heading-serif" style="font-size:1.3rem;color:var(--cream-50);">All Guest Feedback (${allRevs.length})</h2>
        </div>

        <div class="reviews-grid" style="margin-top:0;">
          ${allRevs.map(r => {
            const initials = r.guest_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || 'G';
            return `
              <div class="review-card">
                <div>
                  <div class="review-card-header">
                    <div class="review-guest-avatar">${initials}</div>
                    <div style="flex-grow:1;">
                      <div style="display:flex;align-items:center;justify-content:space-between;">
                        <strong style="color:var(--cream-50);">${escHtml(r.guest_name)}</strong>
                        <span class="review-verified-tag">✦ Verified</span>
                      </div>
                      <div class="text-xs text-muted">${formatDate(r.review_date)} · Booking #${r.booking_id}</div>
                      <div class="review-resort-tag">${escHtml(r.property_name)}</div>
                    </div>
                  </div>
                  <div style="color:var(--gold-200);margin-bottom:var(--space-2);">${starsHTML(r.rating)} (${r.rating}/5)</div>
                  <div class="review-comment-body">"${escHtml(r.comment || 'No comment provided.')}"</div>
                </div>
                <div class="review-card-footer">
                  <span>Guest location: ${escHtml(r.guest_city || 'India')}</span>
                  <span style="color:var(--gold-300);">${r.rating}★</span>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;
    return;
  }
}

function renderAdminTable(items) {
  if (!items || items.length === 0) return `<div class="empty-state" style="padding:var(--space-8)"><div class="empty-state-icon">📋</div><div class="empty-state-title">No bookings found</div></div>`;
  return `
    <table class="bookings-table">
      <thead><tr><th>#</th><th>Guest</th><th>Property</th><th>Room</th><th>Check-in</th><th>Check-out</th><th>Status</th><th>Total</th><th>Paid</th><th>Actions</th></tr></thead>
      <tbody>${items.map(b => `
        <tr>
          <td><span style="color:var(--gold-300);font-weight:600">#${b.booking_id}</span></td>
          <td>${escHtml(b.guest_name || '—')}</td>
          <td>${escHtml(b.property_name || '—')}</td>
          <td>${escHtml(b.room_number || '—')}</td>
          <td>${formatDate(b.check_in)}</td>
          <td>${formatDate(b.check_out)}</td>
          <td>${statusBadge(b.status)}</td>
          <td>${formatCurrency(b.total_amount)}</td>
          <td>${formatCurrency(b.amount_paid)}</td>
          <td><div style="display:flex;gap:6px">
            <button class="btn btn-ghost btn-sm" onclick="openBookingDetail(${b.booking_id})" title="View">👁</button>
            ${b.status === 'confirmed' ? `<button class="btn btn-success btn-sm" onclick="adminCheckIn(${b.booking_id})" title="Check In">✓</button>` : ''}
            ${b.status === 'checked_in' ? `<button class="btn btn-outline btn-sm" onclick="adminCheckOut(${b.booking_id})" title="Check Out">↩</button>` : ''}
          </div></td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

async function adminCheckIn(id) {
  const { ok, error } = await apiJSON(`/bookings/${id}/check-in`, { method: 'POST' });
  if (!ok) { showToast('Check-in failed', error, 'error'); return; }
  showToast('Checked in! ✓', `Booking #${id} — guest is now checked in.`, 'success');
  await Promise.all([loadAdminTab('checkin'), loadAdminStats()]);
}
async function adminCheckOut(id) {
  const { ok, error } = await apiJSON(`/bookings/${id}/check-out`, { method: 'POST' });
  if (!ok) { showToast('Check-out failed', error, 'error'); return; }
  showToast('Checked out ✓', `Booking #${id} — guest has checked out.`, 'success');
  await Promise.all([loadAdminTab('checkin'), loadAdminStats()]);
}

async function runReports() {
  const start = document.getElementById('report-start')?.value;
  const end = document.getElementById('report-end')?.value;
  if (!start || !end) { showToast('Select date range', '', 'warning'); return; }
  const btn = document.getElementById('run-report-btn');
  if (btn) setLoading(btn, true, 'Running…');
  const [occ, rev] = await Promise.all([
    apiJSON(`/reports/occupancy?start_date=${start}&end_date=${end}`),
    apiJSON(`/reports/revenue?start_date=${start}&end_date=${end}`)
  ]);
  if (btn) setLoading(btn, false);
  const area = document.getElementById('report-results'); if (!area) return;
  area.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-6)">
      <div>
        <div class="section-eyebrow" style="margin-bottom:var(--space-4)">Occupancy Report</div>
        ${occ.ok && occ.data?.length > 0 ? occ.data.map(r => `
          <div class="glass-card" style="margin-bottom:var(--space-3)">
            <div style="font-family:var(--font-display);font-size:1rem;color:var(--cream-50);margin-bottom:var(--space-3)">${escHtml(r.property_name)}</div>
            <div style="background:rgba(255,255,255,0.06);border-radius:var(--radius-md);overflow:hidden;margin-bottom:var(--space-3)">
              <div style="height:8px;background:linear-gradient(90deg,var(--gold-300),var(--gold-500));width:${Math.min(100, r.occupancy_percentage)}%;transition:width 1s ease"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.85rem">
              <div><div class="text-muted" style="font-size:0.72rem">OCCUPANCY</div><div style="color:var(--gold-300);font-weight:700;font-size:1.3rem">${r.occupancy_percentage.toFixed(1)}%</div></div>
              <div><div class="text-muted" style="font-size:0.72rem">OCCUPIED NIGHTS</div><div style="color:var(--cream-50);font-weight:600">${r.occupied_room_nights} / ${r.available_room_nights}</div></div>
              <div><div class="text-muted" style="font-size:0.72rem">TOTAL ROOMS</div><div style="color:var(--cream-50);font-weight:600">${r.total_rooms}</div></div>
            </div>
          </div>`).join('') : `<div class="empty-state" style="padding:var(--space-6)"><div class="empty-state-icon">📊</div><div class="empty-state-title">${occ.error || 'No data'}</div></div>`}
      </div>
      <div>
        <div class="section-eyebrow" style="margin-bottom:var(--space-4)">Revenue Report</div>
        ${rev.ok && rev.data?.length > 0 ? rev.data.map(r => `
          <div class="glass-card" style="margin-bottom:var(--space-3)">
            <div style="font-family:var(--font-display);font-size:1rem;color:var(--cream-50);margin-bottom:var(--space-4)">${escHtml(r.property_name)}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:var(--space-3)">
              <div style="text-align:center">
                <div class="text-muted text-xs" style="margin-bottom:var(--space-1)">REVENUE</div>
                <div style="color:var(--gold-300);font-family:var(--font-display);font-weight:700;font-size:1.1rem">${formatCurrency(r.total_revenue)}</div>
              </div>
              <div style="text-align:center">
                <div class="text-muted text-xs" style="margin-bottom:var(--space-1)">ADR</div>
                <div style="color:#68d391;font-family:var(--font-display);font-weight:700;font-size:1.1rem">${formatCurrency(r.adr)}</div>
              </div>
              <div style="text-align:center">
                <div class="text-muted text-xs" style="margin-bottom:var(--space-1)">RevPAR</div>
                <div style="color:#63b3ed;font-family:var(--font-display);font-weight:700;font-size:1.1rem">${formatCurrency(r.revpar)}</div>
              </div>
            </div>
          </div>`).join('') : `<div class="empty-state" style="padding:var(--space-6)"><div class="empty-state-icon">💰</div><div class="empty-state-title">${rev.error || 'No data'}</div></div>`}
      </div>
    </div>`;
}

/* ─────────────────────────────────────────────────────────────────────────
   PAGE: PROFILE
   ───────────────────────────────────────────────────────────────────────── */
registerPage('profile', async (container) => {
  if (!Auth.isLoggedIn()) { navigateTo('home'); return; }
  let user = Auth.user;
  if (!user || !user.name) {
    const { ok, data } = await apiJSON('/auth/me');
    if (ok && data) {
      Auth.save({ access_token: Auth.token, refresh_token: Auth.refresh }, data);
      user = data;
    }
  }
  container.innerHTML = `
    <div class="page"><div class="container" style="max-width:680px">
      <div style="margin-bottom:var(--space-8);padding-top:var(--space-4)">
        <div class="section-eyebrow">Account</div>
        <h1 class="heading-display" style="font-size:2rem;color:var(--cream-50)">My Profile</h1>
      </div>
      <div class="glass-card">
        <div style="display:flex;align-items:center;gap:var(--space-5);margin-bottom:var(--space-6);padding-bottom:var(--space-6);border-bottom:1px solid rgba(255,255,255,0.07)">
          <div style="width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,var(--gold-300),var(--gold-500));display:flex;align-items:center;justify-content:center;font-size:1.8rem;font-weight:800;color:var(--charcoal-800)">${(user?.name || 'G').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}</div>
          <div>
            <div class="heading-serif" style="font-size:1.4rem;color:var(--cream-50)">${escHtml(user?.name || '')}</div>
            <div class="text-sm text-muted">${escHtml(user?.email || '')}</div>
            <div style="margin-top:var(--space-2)"><span class="room-type-badge">${escHtml(user?.role || 'guest')}</span></div>
          </div>
        </div>
        <div class="booking-summary">
          <div class="booking-summary-row"><span class="booking-summary-label">Account ID</span><span class="booking-summary-value">#${user?.account_id}</span></div>
          <div class="booking-summary-row"><span class="booking-summary-label">Name</span><span class="booking-summary-value">${escHtml(user?.name)}</span></div>
          <div class="booking-summary-row"><span class="booking-summary-label">Email</span><span class="booking-summary-value">${escHtml(user?.email)}</span></div>
          <div class="booking-summary-row"><span class="booking-summary-label">Role</span><span class="booking-summary-value">${escHtml(user?.role)}</span></div>
          ${user?.property_id ? `<div class="booking-summary-row"><span class="booking-summary-label">Property</span><span class="booking-summary-value">#${user.property_id}</span></div>` : ''}
        </div>
        <div style="margin-top:var(--space-6);display:flex;gap:var(--space-3);flex-wrap:wrap">
          <button class="btn btn-outline" onclick="navigateTo('dashboard')">My Bookings</button>
          ${Auth.isStaff() ? `<button class="btn btn-secondary" onclick="navigateTo('admin')">Admin Panel</button>` : ''}
          <button class="btn btn-danger" onclick="logoutUser()">Sign Out</button>
        </div>
      </div>
    </div></div>`;
});

/* ─────────────────────────────────────────────────────────────────────────
   AUTH MODAL  (with Demo Quick-Fill)
   ───────────────────────────────────────────────────────────────────────── */
function openAuthModal(tab = 'login') {
  const overlay = document.getElementById('auth-modal-overlay');
  overlay.classList.add('active');
  switchAuthTab(tab);
  injectDemoCredentials();
}
function closeAuthModal() { document.getElementById('auth-modal-overlay').classList.remove('active'); }
function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
}

function injectDemoCredentials() {
  const existing = document.getElementById('demo-credentials-panel');
  if (existing) return; // already injected

  const panel = document.createElement('div');
  panel.id = 'demo-credentials-panel';
  panel.innerHTML = `
    <div style="background:rgba(212,137,31,0.08);border:1px solid rgba(212,137,31,0.2);border-radius:var(--radius-lg);padding:var(--space-4);margin-bottom:var(--space-5)">
      <div style="font-size:0.75rem;font-weight:700;letter-spacing:0.08em;color:var(--gold-400);margin-bottom:var(--space-3);text-transform:uppercase">⚡ Demo Accounts — Click to Autofill</div>
      <div style="display:flex;flex-wrap:wrap;gap:var(--space-2)" id="demo-btns">
        ${DEMO_ACCOUNTS.map((a, i) => `
          <button class="demo-cred-btn" data-idx="${i}" style="
            display:inline-flex;align-items:center;gap:6px;
            padding:4px 10px;border-radius:var(--radius-full);
            background:rgba(255,255,255,0.05);
            border:1px solid rgba(255,255,255,0.1);
            font-size:0.75rem;font-weight:500;color:${a.color};
            cursor:pointer;transition:all 0.15s;font-family:var(--font-body)
          ">
            ${a.icon} ${a.label}
          </button>`).join('')}
      </div>
    </div>`;
  const loginForm = document.getElementById('login-form');
  if (loginForm) loginForm.insertBefore(panel, loginForm.firstChild);

  document.querySelectorAll('.demo-cred-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const acc = DEMO_ACCOUNTS[parseInt(btn.dataset.idx)];
      document.getElementById('login-email').value = acc.email;
      document.getElementById('login-password').value = acc.password;
      switchAuthTab('login');
      // Flash effect
      btn.style.background = 'rgba(212,137,31,0.25)';
      btn.style.borderColor = 'var(--gold-400)';
      setTimeout(() => { btn.style.background = 'rgba(255,255,255,0.05)'; btn.style.borderColor = 'rgba(255,255,255,0.1)'; }, 600);
      showToast('Credentials filled', `${acc.label} — click Sign In to continue.`, 'info', 2500);
    });
    btn.addEventListener('mouseenter', () => btn.style.background = 'rgba(255,255,255,0.1)');
    btn.addEventListener('mouseleave', () => btn.style.background = 'rgba(255,255,255,0.05)');
  });
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  if (!email || !password) { showToast('Fill all fields', '', 'warning'); return; }
  setLoading(btn, true, 'Signing in…');
  const { ok, data, error } = await apiJSON('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  setLoading(btn, false);
  if (!ok) { showToast('Login failed', error, 'error'); return; }
  Auth.save(data, null);
  closeAuthModal();
  updateNavForAuthState();
  const role = Auth.user?.role;
  showToast(`Welcome back, ${Auth.user?.name?.split(' ')[0] || 'Guest'}!`, `Logged in as ${role}.`, 'success');
  const pending = sessionStorage.getItem('pending_booking');
  if (pending) {
    sessionStorage.removeItem('pending_booking');
    const b = JSON.parse(pending);
    // Use stored roomData directly — no DOM scraping needed
    openBookingModal(b.roomId, b.checkIn, b.checkOut, b.guests, b.roomData || null);
    return;
  }
  // Role-based redirect
  if (Auth.isStaff()) navigateTo('admin');
  else navigateTo('dashboard');
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('register-btn');
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const phone = document.getElementById('reg-phone').value.trim();
  const city = document.getElementById('reg-city').value.trim();
  if (!name || !email || !password) { showToast('Fill required fields', '', 'warning'); return; }
  if (password.length < 8) { showToast('Weak password', 'Min 8 characters.', 'warning'); return; }
  setLoading(btn, true, 'Creating…');
  const { ok, error } = await apiJSON('/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password, phone: phone || null, city: city || null }) });
  setLoading(btn, false);
  if (!ok) { showToast('Registration failed', error, 'error'); return; }
  showToast('Account created!', 'Log in with your credentials.', 'success');
  switchAuthTab('login');
  document.getElementById('login-email').value = email;
}

/* ─────────────────────────────────────────────────────────────────────────
   BOOKING MODAL
   ───────────────────────────────────────────────────────────────────────── */
let activeBookingData = null;
function openBookingModal(roomId, checkIn, checkOut, guests, roomData) {
  const nights = Math.max(1, nightsBetween(checkIn, checkOut));
  roomData = roomData || roomsCache[roomId];
  // If roomData not provided, try to scrape from DOM
  if (!roomData) {
    const card = document.getElementById(`room-card-${roomId}`) ||
      document.querySelector(`[data-room-id="${roomId}"]`);
    if (card) {
      roomData = {
        room_id: roomId,
        room_number: card.querySelector('.room-number')?.textContent.replace('Room ', '').trim() || String(roomId),
        type_name: card.querySelector('.room-card-name')?.textContent.replace(' Suite', '').trim() || 'Deluxe',
        total_rate: parseFloat(card.querySelector('.room-total-rate')?.textContent.replace(/[^0-9.]/g, '') || 0),
        nightly_rate: parseFloat(card.querySelector('.room-nightly-rate')?.textContent.split('/')[0].replace(/[^0-9.]/g, '') || 0),
        max_occupancy: parseInt(card.querySelector('.room-meta-item')?.textContent.replace(/\D/g, '') || 4),
      };
      roomsCache[roomId] = roomData;
    }
  }
  if (!roomData) {
    roomData = {
      room_id: roomId,
      room_number: String(roomId),
      type_name: 'Deluxe',
      nightly_rate: 4000,
      total_rate: 4000 * nights,
      max_occupancy: 4,
      property_name: 'Kaveri Stays'
    };
    roomsCache[roomId] = roomData;
  }

  const totalAmount = (roomData.nightly_rate || 4000) * nights;
  const depositAmount = Math.round(totalAmount * 0.20);
  const remainingBalance = totalAmount - depositAmount;

  activeBookingData = { roomId, checkIn, checkOut, guests, roomData, nights, totalAmount, depositAmount, remainingBalance };

  let propName = roomData.property_name || 'Kaveri Stays';
  const searchSel = document.getElementById('search-property') || document.getElementById('vac-property');
  if (searchSel && searchSel.value && searchSel.value !== "") {
    propName = propertiesCache?.find(p => p.property_id == parseInt(searchSel.value))?.name || propName;
  }
  const maxOcc = roomData.max_occupancy || 6;

  document.getElementById('booking-modal-body').innerHTML = `
    <div style="margin-bottom:var(--space-4)">
      <div class="text-xs text-muted" style="letter-spacing:0.05em">ROOM SELECTION</div>
      <div class="heading-serif" style="font-size:1.2rem;color:var(--cream-50)">${escHtml(roomData.type_name)} Suite · Room ${escHtml(roomData.room_number)}</div>
      <div class="text-sm text-muted">${escHtml(propName)} · ${formatDate(checkIn)} → ${formatDate(checkOut)} (${nights} night${nights > 1 ? 's' : ''})</div>
    </div>

    <!-- 20% Deposit Breakdown Card (Screenshot 2 Match) -->
    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:var(--radius-lg);padding:var(--space-4);margin-bottom:var(--space-4);">
      <div class="booking-summary-row" style="margin-bottom:var(--space-2);">
        <span style="color:var(--cream-100);font-size:0.95rem;">${formatCurrency(roomData.nightly_rate)} × ${nights} night${nights > 1 ? 's' : ''}</span>
        <span style="color:var(--cream-50);font-weight:600;font-size:0.95rem;">${formatCurrency(totalAmount)}</span>
      </div>
      <div class="booking-summary-row" style="margin-bottom:var(--space-2);padding-top:var(--space-2);border-top:1px dashed rgba(255,255,255,0.1);">
        <span style="color:var(--gold-200);font-weight:700;font-size:1.05rem;">20% Deposit (Due Now)</span>
        <span style="color:var(--gold-200);font-weight:800;font-size:1.15rem;">${formatCurrency(depositAmount)}</span>
      </div>
      <div class="booking-summary-row">
        <span style="color:var(--charcoal-300);font-size:0.85rem;">Remaining Balance Due at Checkout</span>
        <span style="color:var(--charcoal-300);font-size:0.85rem;">${formatCurrency(remainingBalance)}</span>
      </div>
    </div>

    <div class="form-group" style="margin-bottom:var(--space-3);">
      <label class="form-label" for="booking-guest-count">Guests <span class="required">*</span></label>
      <select class="form-input" id="booking-guest-count" aria-label="Number of Guests">${Array.from({ length: maxOcc }, (_, i) => i + 1).map(n => `<option value="${n}" ${n == Math.min(guests, maxOcc) ? 'selected' : ''}>${n} Guest${n > 1 ? 's' : ''}</option>`).join('')}</select>
    </div>

    <div class="form-group" style="margin-bottom:var(--space-4);">
      <label class="form-label">Payment Method <span class="required">*</span></label>
      <div class="payment-methods">
        ${[{ value: 'card', icon: '💳', label: 'Card' }, { value: 'upi', icon: '📱', label: 'UPI' }, { value: 'cash', icon: '💵', label: 'Cash' }, { value: 'bank_transfer', icon: '🏦', label: 'Bank' }].map(m => `
          <div class="payment-method-option"><input type="radio" name="payment-method" id="pm-${m.value}" value="${m.value}" ${m.value === 'card' ? 'checked' : ''}>
          <label class="payment-method-label" for="pm-${m.value}"><span class="payment-method-icon">${m.icon}</span>${m.label}</label></div>`).join('')}
      </div>
    </div>

    <div style="margin-bottom:var(--space-2);">
      <button class="btn btn-forest w-full" id="confirm-booking-modal-btn" style="padding:14px;border-radius:var(--radius-full);font-size:1rem;" onclick="confirmBooking()">
        Hold Room with ${formatCurrency(depositAmount)} Deposit
      </button>
    </div>
    <div style="text-align:center;font-size:0.78rem;color:var(--charcoal-300);margin-top:var(--space-2);">
      Free cancellation available up to 48 hours prior to check-in.
    </div>`;

  // Hide the default modal footer button since we have the full-width CTA inside the body
  const modalFooter = document.querySelector('#booking-modal-overlay .modal-footer');
  if (modalFooter) modalFooter.style.display = 'none';

  document.getElementById('booking-modal-overlay').classList.add('active');
}
function closeBookingModal() { document.getElementById('booking-modal-overlay').classList.remove('active'); activeBookingData = null; }

async function confirmBooking() {
  if (!activeBookingData) return;
  const snapshot = activeBookingData; // Keep reference before closing modal
  const btn = document.getElementById('confirm-booking-modal-btn') || document.getElementById('confirm-booking-btn');
  const { roomId, checkIn, checkOut, roomData, nights } = snapshot;
  const guestCount = parseInt(document.getElementById('booking-guest-count')?.value || '1');
  const method = document.querySelector('input[name="payment-method"]:checked')?.value || 'card';

  if (!Auth.isLoggedIn()) {
    sessionStorage.setItem('pending_booking', JSON.stringify({
      roomId, checkIn, checkOut, guests: guestCount, roomData, nights
    }));
    closeBookingModal();
    openAuthModal('login');
    showToast('Sign in required', 'Please sign in or select a demo guest account to complete your booking.', 'info');
    return;
  }

  // Validate guest count against room capacity
  const maxOcc = roomData?.max_occupancy || 99;
  if (guestCount > maxOcc) {
    showToast('Too many guests', `This room type allows a maximum of ${maxOcc} guest${maxOcc > 1 ? 's' : ''}.`, 'error');
    return;
  }

  if (btn) setLoading(btn, true, 'Securing Stay…');
  const { ok, data, error } = await apiJSON('/bookings', {
    method: 'POST',
    body: JSON.stringify({
      room_id: roomId,
      check_in: checkIn,
      check_out: checkOut,
      guest_count: guestCount,
      payment_method: method
    })
  });
  if (btn) setLoading(btn, false);

  if (!ok) {
    if (error === 'Session expired' || error?.includes('401') || error?.includes('credentials') || error?.includes('Unauthorized')) {
      sessionStorage.setItem('pending_booking', JSON.stringify({
        roomId, checkIn, checkOut, guests: guestCount, roomData, nights
      }));
      closeBookingModal();
      openAuthModal('login');
      showToast('Session expired', 'Please log in to finalize your booking.', 'warning');
      return;
    }
    showToast('Booking failed', error, 'error');
    return;
  }

  closeBookingModal();
  showBookingSuccess(data, nights, '20% Deposit Paid');
  showToast('Booking confirmed! 🎉', `Booking #${data.booking_id} created.`, 'success');
}

function showBookingSuccess(booking, nights = null, paymentLabel = null) {
  if (!booking) return;
  const n = nights || (booking.check_in && booking.check_out ? Math.max(1, nightsBetween(booking.check_in, booking.check_out)) : 1);
  const paid = booking.amount_paid || Math.round((booking.total_amount || 0) * 0.20);
  const label = paymentLabel || '20% Deposit Paid';

  const successModal = document.getElementById('success-modal-overlay');
  const successBody = document.getElementById('success-modal-body');
  if (!successModal || !successBody) return;

  successBody.innerHTML = `
    <div style="text-align:center;padding:var(--space-2) 0 var(--space-4);">
      <div style="width:56px;height:56px;border-radius:50%;background:rgba(72,187,120,0.15);border:2px solid #48bb78;color:#48bb78;display:flex;align-items:center;justify-content:center;font-size:1.8rem;margin:0 auto var(--space-3);">✓</div>
      <div style="display:inline-block;padding:4px 14px;background:rgba(72,187,120,0.12);border:1px solid rgba(72,187,120,0.3);border-radius:var(--radius-full);color:#68d391;font-size:0.75rem;font-weight:700;letter-spacing:0.05em;margin-bottom:var(--space-2);">RESERVATION CONFIRMED</div>
      <h3 class="heading-serif" style="font-size:1.8rem;color:var(--cream-50);margin-bottom:4px">Your Stay is Secured</h3>
      <p class="text-xs text-muted" style="margin-bottom:var(--space-5)">Booking reference: #${booking.booking_id} · Status: <strong style="color:var(--forest-300)">${booking.status || 'confirmed'}</strong></p>
      
      <!-- Summary Box (Exact Screenshot Match) -->
      <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:var(--radius-lg);padding:var(--space-4);text-align:left;margin-bottom:var(--space-6);">
        <div class="booking-summary-row"><span class="booking-summary-label">Duration</span><span class="booking-summary-value">${n} Night${n > 1 ? 's' : ''}</span></div>
        <div class="booking-summary-row" style="margin-top:var(--space-2);"><span class="booking-summary-label">Total Stay Cost</span><span class="booking-summary-value" style="color:var(--cream-50);font-weight:700;">${formatCurrency(booking.total_amount)}</span></div>
        <div class="booking-summary-row" style="margin-top:var(--space-2);padding-top:var(--space-2);border-top:1px dashed rgba(255,255,255,0.1);"><span style="color:#68d391;font-weight:700;">${label}</span><span style="color:#68d391;font-weight:800;font-size:1.15rem;">${formatCurrency(paid)}</span></div>
      </div>

      <div style="display:flex;flex-direction:column;gap:var(--space-3);">
        <button class="btn btn-forest w-full" style="padding:14px;border-radius:var(--radius-full);font-size:0.95rem;" onclick="closeSuccessModal();navigateTo('dashboard')">View All My Reservations</button>
        <button class="btn btn-outline w-full" style="padding:12px;border-radius:var(--radius-full);font-size:0.9rem;" onclick="closeSuccessModal();navigateTo('home')">Return to Homepage</button>
      </div>
    </div>`;

  successModal.classList.add('active');
}
function closeSuccessModal() { document.getElementById('success-modal-overlay')?.classList.remove('active'); }

/* ─── Booking Detail Modal ─────────────────────────────────────────────── */
async function openBookingDetail(id) {
  document.getElementById('detail-modal-body').innerHTML = `<div class="flex justify-center" style="padding:var(--space-8)"><div class="spinner spinner-lg"></div></div>`;
  document.getElementById('detail-modal-overlay').classList.add('active');
  const { ok, data, error } = await apiJSON(`/bookings/${id}`);
  if (!ok) { document.getElementById('detail-modal-body').innerHTML = `<div class="empty-state"><div class="empty-state-title">${escHtml(error)}</div></div>`; return; }
  const { ok: ok2, data: payments } = await apiJSON(`/bookings/${id}/payments`);
  const plist = ok2 && payments ? payments : [];
  document.getElementById('detail-modal-body').innerHTML = `
    <div class="booking-summary">
      <div class="booking-summary-row"><span class="booking-summary-label">Booking ID</span><span class="booking-summary-value">#${data.booking_id}</span></div>
      <div class="booking-summary-row"><span class="booking-summary-label">Property</span><span class="booking-summary-value">${escHtml(data.property_name)}</span></div>
      <div class="booking-summary-row"><span class="booking-summary-label">Room</span><span class="booking-summary-value">${escHtml(data.room_number)}</span></div>
      <div class="booking-summary-row"><span class="booking-summary-label">Guest</span><span class="booking-summary-value">${escHtml(data.guest_name)}</span></div>
      <div class="booking-summary-row"><span class="booking-summary-label">Check-in</span><span class="booking-summary-value">${formatDate(data.check_in)}</span></div>
      <div class="booking-summary-row"><span class="booking-summary-label">Check-out</span><span class="booking-summary-value">${formatDate(data.check_out)}</span></div>
      <div class="booking-summary-row"><span class="booking-summary-label">Guests</span><span class="booking-summary-value">${data.guest_count}</span></div>
      <div class="booking-summary-row"><span class="booking-summary-label">Status</span><span class="booking-summary-value">${statusBadge(data.status)}</span></div>
      <div class="booking-summary-total"><div class="booking-summary-total-label">Total</div><div class="booking-summary-total-amount">${formatCurrency(data.total_amount)}</div></div>
    </div>
    ${plist.length > 0 ? `
    <div style="margin-top:var(--space-5)">
      <div class="section-eyebrow" style="margin-bottom:var(--space-3)">Payment History</div>
      ${plist.map(p => `<div class="booking-summary-row" style="border:1px solid rgba(255,255,255,0.05);border-radius:var(--radius-md);padding:var(--space-3) var(--space-4);margin-bottom:var(--space-2)"><span class="booking-summary-label">${formatDate(p.payment_date)} · ${escHtml(p.method)}</span><span class="booking-summary-value" style="color:var(--gold-300)">${formatCurrency(p.amount)}</span></div>`).join('')}
      <div style="text-align:right;margin-top:var(--space-3);font-size:0.875rem;color:var(--charcoal-300)">Paid: <strong style="color:var(--cream-50)">${formatCurrency(data.amount_paid)}</strong> of ${formatCurrency(data.total_amount)}</div>
    </div>`: ''}
    ${(data.status === 'confirmed' || data.status === 'checked_in') ? `
    <div style="margin-top:var(--space-5)">
      <div class="section-eyebrow" style="margin-bottom:var(--space-3)">Add Payment</div>
      <div style="display:flex;gap:var(--space-3);align-items:flex-end;flex-wrap:wrap">
        <div class="form-group" style="flex:1;min-width:120px;margin-bottom:0"><label class="form-label" for="payment-amount-input">Amount (₹)</label><input type="number" class="form-input" id="payment-amount-input" placeholder="e.g. 5000" min="1" aria-label="Payment Amount in Rupees"></div>
        <div class="form-group" style="flex:1;min-width:120px;margin-bottom:0"><label class="form-label" for="payment-method-input">Method</label><select class="form-input" id="payment-method-input" aria-label="Payment Method"><option value="card">Card</option><option value="upi">UPI</option><option value="cash">Cash</option><option value="bank_transfer">Bank Transfer</option></select></div>
        <button class="btn btn-primary" onclick="addPayment(${data.booking_id})">Pay Now</button>
      </div>
    </div>`: ''}`;
}

async function addPayment(id) {
  const amount = parseFloat(document.getElementById('payment-amount-input').value);
  const method = document.getElementById('payment-method-input').value;
  if (!amount || amount <= 0) { showToast('Invalid amount', '', 'warning'); return; }
  const { ok, error } = await apiJSON(`/bookings/${id}/payments`, { method: 'POST', body: JSON.stringify({ amount, method }) });
  if (!ok) { showToast('Payment failed', error, 'error'); return; }
  showToast('Payment recorded! ✓', `${formatCurrency(amount)} recorded.`, 'success');
  closeDetailModal();

  // Open the secured stay confirmation display
  const { ok: bok, data: updatedBooking } = await apiJSON(`/bookings/${id}`);
  if (bok && updatedBooking) {
    showBookingSuccess(updatedBooking, null, 'Payment Received');
  }

  if (currentPage === 'dashboard') await loadDashboard();
  if (currentPage === 'admin') await loadAdminStats();
}
function closeDetailModal() { document.getElementById('detail-modal-overlay').classList.remove('active'); }

/* ─── Review Modal ─────────────────────────────────────────────────────── */
let reviewBookingId = null, reviewRating = 0;
function openReviewModal(id) {
  reviewBookingId = id; reviewRating = 0;
  const stars = document.querySelectorAll('.star-btn');
  stars.forEach(b => { b.textContent = '☆'; b.classList.remove('filled', 'hovered'); });
  // Add hover cascade to stars
  stars.forEach((b, i) => {
    b.addEventListener('mouseenter', () => stars.forEach((s, j) => s.classList.toggle('hovered', j <= i)));
    b.addEventListener('mouseleave', () => stars.forEach(s => s.classList.remove('hovered')));
  });
  document.getElementById('review-comment').value = '';
  document.getElementById('review-modal-overlay').classList.add('active');
}
function setRating(n) { reviewRating = n; document.querySelectorAll('.star-btn').forEach((b, i) => { b.textContent = i < n ? '★' : '☆'; b.classList.toggle('filled', i < n); }); }
function closeReviewModal() { document.getElementById('review-modal-overlay').classList.remove('active'); reviewBookingId = null; reviewRating = 0; }
async function submitReview() {
  if (!reviewBookingId) return;
  if (!reviewRating) { showToast('Select a rating', '', 'warning'); return; }
  const btn = document.getElementById('submit-review-btn');
  const comment = document.getElementById('review-comment').value.trim();
  setLoading(btn, true, 'Submitting…');
  const { ok, error } = await apiJSON(`/bookings/${reviewBookingId}/review`, { method: 'POST', body: JSON.stringify({ rating: reviewRating, comment: comment || null }) });
  setLoading(btn, false);
  if (!ok) { showToast('Review failed', error, 'error'); return; }
  showToast('Review submitted! ⭐', 'Thank you for your feedback.', 'success');
  closeReviewModal();
  if (currentPage === 'dashboard') await loadDashboard();
  if (currentPage === 'reviews') {
    const curP = document.querySelector('.resort-pill-btn.active')?.dataset?.prop;
    navigateTo('reviews', { property_id: curP && curP !== 'all' ? curP : null });
  }
  await loadProperties();
}

/* ─────────────────────────────────────────────────────────────────────────
   LOGOUT
   ───────────────────────────────────────────────────────────────────────── */
async function logoutUser() {
  const refresh = Auth.refresh;
  if (refresh) await apiJSON('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: refresh }) });
  Auth.clear(); updateNavForAuthState(); navigateTo('home');
  showToast('Signed out', 'You have been signed out.', 'info');
}

/* ─── Info & Experience Modals ─────────────────────────────────────────── */
const INFO_DATA = {
  safaris: {
    title: '🌿 Wildlife & Wilderness Safaris',
    body: `
      <div style="text-align:center;margin-bottom:var(--space-4);font-size:3rem;">🐅</div>
      <p style="margin-bottom:var(--space-3);color:var(--cream-100);">Embark on dawn and dusk jeep safaris through the protected reserves surrounding Kaveri Riverside in Coorg and Kaveri Hilltop in Ooty.</p>
      <div class="booking-summary" style="margin-bottom:var(--space-4);">
        <div class="booking-summary-row"><span class="booking-summary-label">Available At</span><span class="booking-summary-value">Coorg & Ooty</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Schedule</span><span class="booking-summary-value">6:00 AM & 4:30 PM Daily</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Guided By</span><span class="booking-summary-value">Certified Naturalists</span></div>
      </div>
      <p class="text-xs text-muted">Complimentary for guests booked in Suite rooms; add-on available for all bookings at concierge desk.</p>
    `
  },
  spa: {
    title: '🧖 Ayurvedic Signature Spa',
    body: `
      <div style="text-align:center;margin-bottom:var(--space-4);font-size:3rem;">🌸</div>
      <p style="margin-bottom:var(--space-3);color:var(--cream-100);">Immerse in ancient Vedic wellness therapies using hand-pressed herbal oils, steam sanctuaries, and meditation sessions overlooking the mist-clad hills.</p>
      <div class="booking-summary" style="margin-bottom:var(--space-4);">
        <div class="booking-summary-row"><span class="booking-summary-label">Available At</span><span class="booking-summary-value">All 3 Properties</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Signature Ritual</span><span class="booking-summary-value">Abhyanga & Shirodhara</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Operating Hours</span><span class="booking-summary-value">7:00 AM – 8:00 PM</span></div>
      </div>
    `
  },
  tea: {
    title: '🍃 Estate Tea & Coffee Tours',
    body: `
      <div style="text-align:center;margin-bottom:var(--space-4);font-size:3rem;">☕</div>
      <p style="margin-bottom:var(--space-3);color:var(--cream-100);">Walk amidst 100-year-old organic Arabica coffee and Nilgiri tea plantations with our master estate curator. Includes artisan cupping and tasting masterclass.</p>
      <div class="booking-summary" style="margin-bottom:var(--space-4);">
        <div class="booking-summary-row"><span class="booking-summary-label">Available At</span><span class="booking-summary-value">Coorg & Ooty</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Includes</span><span class="booking-summary-value">Private Tasting Session</span></div>
      </div>
    `
  },
  cruise: {
    title: '🌊 Sunset Backwater Cruises',
    body: `
      <div style="text-align:center;margin-bottom:var(--space-4);font-size:3rem;">⛵</div>
      <p style="margin-bottom:var(--space-3);color:var(--cream-100);">Glide across the tranquil emerald lagoons of Alleppey on our handcrafted luxury cedar houseboats. Enjoy live classical music and authentic Kerala coastal delicacies.</p>
      <div class="booking-summary" style="margin-bottom:var(--space-4);">
        <div class="booking-summary-row"><span class="booking-summary-label">Available At</span><span class="booking-summary-value">Alleppey Backwaters</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Duration</span><span class="booking-summary-value">3 Hours Sunset Voyage</span></div>
      </div>
    `
  },
  cancellation: {
    title: '🛡️ Flexible Cancellation Policy',
    body: `
      <div style="text-align:center;margin-bottom:var(--space-4);font-size:3rem;">📜</div>
      <div class="booking-summary" style="margin-bottom:var(--space-4);">
        <div class="booking-summary-row"><span class="booking-summary-label">Full Refund</span><span class="booking-summary-value" style="color:var(--forest-300)">Up to 48 hours before check-in</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Late Cancellation</span><span class="booking-summary-value">30% deposit retained</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Modification</span><span class="booking-summary-value">Free date changes subject to availability</span></div>
      </div>
      <p class="text-xs text-muted">You can cancel any confirmed booking with 1-click directly from the My Bookings dashboard.</p>
    `
  },
  contact: {
    title: '📞 Concierge & Support',
    body: `
      <div style="text-align:center;margin-bottom:var(--space-4);font-size:3rem;">🛎️</div>
      <p style="margin-bottom:var(--space-3);color:var(--cream-100);">Our 24/7 dedicated guest concierge is always at your service to craft personalized itineraries, private transfers, and special celebration requests.</p>
      <div class="booking-summary" style="margin-bottom:var(--space-4);">
        <div class="booking-summary-row"><span class="booking-summary-label">Email Concierge</span><span class="booking-summary-value" style="color:var(--gold-300)">api@kaveristays.in</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Toll Free</span><span class="booking-summary-value">+91 1800 200 5283</span></div>
        <div class="booking-summary-row"><span class="booking-summary-label">Support Hours</span><span class="booking-summary-value">24 Hours / 7 Days</span></div>
      </div>
    `
  }
};

function openInfoModal(type) {
  const data = INFO_DATA[type] || { title: 'Kaveri Stays', body: '<p>Luxury hospitality across Coorg, Ooty, and Alleppey.</p>' };
  document.getElementById('info-modal-title').textContent = data.title;
  document.getElementById('info-modal-body').innerHTML = data.body;
  document.getElementById('info-modal-overlay').classList.add('active');
}
function closeInfoModal() {
  document.getElementById('info-modal-overlay')?.classList.remove('active');
}

/* ─── User Dropdown ──────────────────────────────────────────────────────── */
function toggleUserDropdown() {
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) dropdown.classList.toggle('hidden');
}
function closeUserDropdown() {
  document.getElementById('user-dropdown-menu')?.classList.add('hidden');
}

/* ─────────────────────────────────────────────────────────────────────────
   KAVERI AI CONCIERGE AGENT CLIENT LOGIC
   ───────────────────────────────────────────────────────────────────────── */
let aiSessionId = localStorage.getItem('kaveri_ai_session_id') || ('ks_sess_' + Math.random().toString(36).substring(2, 12));
localStorage.setItem('kaveri_ai_session_id', aiSessionId);
let aiChatHistory = [];
let aiSuggestionsCache = [];

function initAiConcierge() {
  // Floating FAB & Navbar button
  document.getElementById('ai-fab-btn')?.addEventListener('click', () => toggleAiDrawer(true));
  document.getElementById('nav-ai-agent-btn')?.addEventListener('click', (e) => {
    // If on mobile or clicking nav, also open drawer
    toggleAiDrawer(true);
  });

  // Drawer Controls
  document.getElementById('ai-close-btn')?.addEventListener('click', () => toggleAiDrawer(false));
  document.getElementById('ai-drawer-overlay')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) toggleAiDrawer(false);
  });
  document.getElementById('ai-reset-btn')?.addEventListener('click', resetAiSession);

  // Form submit
  const drawerForm = document.getElementById('ai-chat-form');
  const drawerInput = document.getElementById('ai-user-input');
  if (drawerForm && drawerInput) {
    drawerForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = drawerInput.value.trim();
      if (!text) return;
      drawerInput.value = '';
      sendAiChatMessage(text, 'drawer');
    });
  }

  // Load suggestions
  loadAiSuggestions();

  // Initial welcome message if empty
  if (aiChatHistory.length === 0) {
    const user = Auth.user;
    const name = user ? user.name : 'Valued Guest';
    aiChatHistory.push({
      role: 'assistant',
      content: `Namaste ${name}! ✦\n\nI am your **Kaveri AI Concierge**. How may I assist your stay today? You can ask me to check your bookings, view pending balances, calculate spending, search available rooms, or look up resort amenities.`,
      toolTraces: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    });
    renderAiHistory();
  }
}

async function loadAiSuggestions() {
  try {
    const { ok, data } = await apiJSON('/agent/suggestions');
    if (ok && Array.isArray(data)) {
      aiSuggestionsCache = data;
      renderDrawerSuggestions();
      renderPageSuggestions();
    }
  } catch {
    // Fallback default suggestions
    aiSuggestionsCache = [
      { icon: '📋', label: 'Show my bookings', prompt: 'Show my bookings and itinerary.' },
      { icon: '⏳', label: 'Pending bookings', prompt: 'What bookings are still pending or unpaid?' },
      { icon: '💳', label: 'Total spending', prompt: 'How much have I spent on hotel bookings?' },
      { icon: '🌲', label: 'Coorg availability', prompt: 'Find me a Deluxe room in Coorg for next weekend.' }
    ];
    renderDrawerSuggestions();
    renderPageSuggestions();
  }
}

function renderDrawerSuggestions() {
  const container = document.getElementById('ai-suggestions-container');
  if (!container || !aiSuggestionsCache.length) return;
  container.innerHTML = aiSuggestionsCache.map(s => `
    <button class="ai-suggestion-chip" onclick="sendAiChatMessage('${escHtml(s.prompt)}', 'drawer')">
      <span>${s.icon}</span> ${escHtml(s.label)}
    </button>
  `).join('');
}

function renderPageSuggestions() {
  const container = document.getElementById('page-ai-suggestions');
  if (!container || !aiSuggestionsCache.length) return;
  container.innerHTML = aiSuggestionsCache.map(s => `
    <button class="ai-suggestion-chip" onclick="sendAiChatMessage('${escHtml(s.prompt)}', 'page')">
      <span>${s.icon}</span> ${escHtml(s.label)}
    </button>
  `).join('');
}

function toggleAiDrawer(open) {
  const overlay = document.getElementById('ai-drawer-overlay');
  if (!overlay) return;
  if (open) {
    overlay.classList.remove('hidden');
    renderAiHistory('drawer');
    setTimeout(() => document.getElementById('ai-user-input')?.focus(), 150);
  } else {
    overlay.classList.add('hidden');
  }
}

async function resetAiSession() {
  try {
    await apiJSON(`/agent/reset?session_id=${aiSessionId}`, { method: 'POST' });
  } catch {}
  aiSessionId = 'ks_sess_' + Math.random().toString(36).substring(2, 12);
  localStorage.setItem('kaveri_ai_session_id', aiSessionId);
  aiChatHistory = [];
  const user = Auth.user;
  const name = user ? user.name : 'Valued Guest';
  aiChatHistory.push({
    role: 'assistant',
    content: `Session memory reset. Namaste ${name}! ✦ How can I help you today?`,
    toolTraces: [],
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  });
  renderAiHistory();
  showToast('Session Reset', 'Kaveri AI conversation memory has been cleared.', 'info');
}

function formatAiMarkdown(text) {
  if (!text) return '';
  let html = escHtml(text);

  // Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic *text*
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Code `code`
  html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;color:#fef08a;">$1</code>');
  // Bullet points
  html = html.replace(/^[•\-\*]\s+(.*)$/gm, '<div style="display:flex;gap:6px;margin:3px 0;"><span style="color:var(--gold-300);">✦</span><div>$1</div></div>');
  // Newlines
  html = html.replace(/\n\n/g, '</p><p style="margin-top:8px;">');
  html = html.replace(/\n/g, '<br/>');

  return `<p>${html}</p>`;
}

function renderAiHistory(target = 'both') {
  const targets = [];
  if (target === 'drawer' || target === 'both') {
    const el = document.getElementById('ai-messages-container');
    if (el) targets.push(el);
  }
  if (target === 'page' || target === 'both') {
    const el = document.getElementById('page-ai-messages');
    if (el) targets.push(el);
  }

  targets.forEach(container => {
    container.innerHTML = aiChatHistory.map(msg => {
      const isUser = msg.role === 'user';
      const tracesHTML = (msg.toolTraces && msg.toolTraces.length > 0)
        ? `<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px;">` +
            msg.toolTraces.map(t => `<span class="ai-tool-pill">⚡ Database Tool: <code>${escHtml(t.tool_name)}</code></span>`).join('') +
          `</div>`
        : '';

      const actionHTML = msg.pendingAction
        ? `
          <div class="ai-action-card">
            <div class="ai-action-card-prompt">${escHtml(msg.pendingAction.prompt_message || 'Human confirmation required for this action:')}</div>
            <div class="ai-action-btn-group">
              <button class="ai-action-btn-yes" onclick="confirmAiAction('${msg.pendingAction.action_type}', ${msg.pendingAction.booking_id || 0}, true)">
                ✓ Yes, Cancel Booking #${msg.pendingAction.booking_id || ''}
              </button>
              <button class="ai-action-btn-no" onclick="confirmAiAction('${msg.pendingAction.action_type}', ${msg.pendingAction.booking_id || 0}, false)">
                ✕ No, Keep Booking
              </button>
            </div>
          </div>
        `
        : '';

      return `
        <div class="ai-msg ${isUser ? 'ai-msg-user' : 'ai-msg-assistant'}">
          <div class="ai-msg-bubble">
            ${tracesHTML}
            ${isUser ? escHtml(msg.content) : formatAiMarkdown(msg.content)}
            ${actionHTML}
          </div>
          <div class="ai-msg-time">${msg.timestamp || ''}</div>
        </div>
      `;
    }).join('');

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
  });
}

async function sendAiChatMessage(text, source = 'drawer') {
  if (!text) return;

  const userTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  aiChatHistory.push({
    role: 'user',
    content: text,
    timestamp: userTime
  });

  // Add temporary typing indicator
  aiChatHistory.push({
    role: 'assistant',
    content: '✦ Kaveri AI is thinking & querying database tools...',
    isTyping: true,
    timestamp: userTime
  });
  renderAiHistory(source === 'page' ? 'both' : 'drawer');

  // Disable send buttons while thinking
  const dSend = document.getElementById('ai-send-btn');
  const pSend = document.getElementById('page-ai-send-btn');
  if (dSend) dSend.disabled = true;
  if (pSend) pSend.disabled = true;

  try {
    const token = Auth.token;
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/agent/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: text,
        session_id: aiSessionId
      })
    });

    // Remove typing bubble
    aiChatHistory = aiChatHistory.filter(m => !m.isTyping);

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      aiChatHistory.push({
        role: 'assistant',
        content: `Sorry, I encountered an issue: ${errJson.error?.message || res.statusText || 'Unable to connect to AI engine.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
    } else {
      const data = await res.json();
      if (data.session_id) {
        aiSessionId = data.session_id;
        localStorage.setItem('kaveri_ai_session_id', aiSessionId);
      }
      aiChatHistory.push({
        role: 'assistant',
        content: data.reply,
        toolTraces: data.tool_traces || [],
        pendingAction: data.pending_action || null,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
    }
  } catch (err) {
    aiChatHistory = aiChatHistory.filter(m => !m.isTyping);
    aiChatHistory.push({
      role: 'assistant',
      content: `Network connection error: ${err.message}. Please ensure the Kaveri Stays backend is running.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    });
  } finally {
    if (dSend) dSend.disabled = false;
    if (pSend) pSend.disabled = false;
    renderAiHistory(source === 'page' ? 'both' : 'drawer');
  }
}

function confirmAiAction(actionType, bookingId, affirmative, source = 'drawer') {
  const replyText = affirmative ? `Yes, please confirm cancellation for Booking #${bookingId}` : `No, keep Booking #${bookingId} active`;
  sendAiChatMessage(replyText, source);
}

Object.assign(window, {
  Auth,
  DEMO_ACCOUNTS,
  apiFetch,
  apiJSON,
  showToast,
  navigateTo,
  openAuthModal,
  closeAuthModal,
  switchAuthTab,
  selectRoom,
  viewProperty,
  openBookingModal,
  closeBookingModal,
  confirmBooking,
  showBookingSuccess,
  closeSuccessModal,
  openBookingDetail,
  closeDetailModal,
  openReviewModal,
  closeReviewModal,
  setRating,
  submitReview,
  cancelBooking,
  adminCheckIn,
  adminCheckOut,
  runReports,
  logoutUser,
  searchAvailability,
  searchVacancies,
  loadDashboard,
  loadAdminStats,
  loadAdminTab,
  openInfoModal,
  closeInfoModal,
  openPropertyModal,
  closePropertyModal,
  toggleUserDropdown,
  closeUserDropdown,
  settleBalance,
  setDashboardFilter,
  renderDashboardFilters,
  executeCancellation,
  closeCancelModal,
  toggleAiDrawer,
  sendAiChatMessage,
  resetAiSession,
  confirmAiAction,
  renderPageSuggestions
});

/* ─────────────────────────────────────────────────────────────────────────
   INIT
   ───────────────────────────────────────────────────────────────────────── */
function initApp() {
  // Initialize Kaveri AI Concierge
  initAiConcierge();

  // Logo & navigation links
  document.getElementById('logo-link')?.addEventListener('click', () => navigateTo('home'));
  document.getElementById('nav-properties-link')?.addEventListener('click', () => {
    navigateTo('home');
    setTimeout(() => document.getElementById('properties-section')?.scrollIntoView({ behavior: 'smooth' }), 300);
  });

  // Navbar scroll
  const navbar = document.getElementById('main-navbar');
  window.addEventListener('scroll', () => navbar?.classList.toggle('scrolled', window.scrollY > 60), { passive: true });

  // Nav routing
  document.querySelectorAll('[data-nav]').forEach(el => el.addEventListener('click', () => {
    navigateTo(el.dataset.nav);
    closeMobileNav();
  }));

  // Auth modal
  document.getElementById('open-login-btn')?.addEventListener('click', () => openAuthModal('login'));
  document.getElementById('open-register-btn')?.addEventListener('click', () => openAuthModal('register'));
  document.getElementById('auth-modal-close')?.addEventListener('click', closeAuthModal);
  document.getElementById('auth-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeAuthModal(); });
  document.querySelectorAll('.auth-tab').forEach(t => t.addEventListener('click', () => switchAuthTab(t.dataset.tab)));
  document.getElementById('login-form')?.addEventListener('submit', handleLogin);
  document.getElementById('register-form')?.addEventListener('submit', handleRegister);

  // Booking modals
  document.getElementById('booking-modal-close')?.addEventListener('click', closeBookingModal);
  document.getElementById('booking-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeBookingModal(); });
  document.getElementById('confirm-booking-btn')?.addEventListener('click', confirmBooking);
  document.getElementById('cancel-booking-modal-btn')?.addEventListener('click', closeBookingModal);
  document.getElementById('success-modal-close')?.addEventListener('click', closeSuccessModal);
  document.getElementById('success-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeSuccessModal(); });
  document.getElementById('detail-modal-close')?.addEventListener('click', closeDetailModal);
  document.getElementById('detail-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeDetailModal(); });

  // Property modal overlay click
  document.getElementById('property-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closePropertyModal(); });

  // Info modal overlay click
  document.getElementById('info-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeInfoModal(); });

  // Cancel modal overlay click
  document.getElementById('cancel-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeCancelModal(); });

  // Review modal
  document.getElementById('review-modal-close')?.addEventListener('click', closeReviewModal);
  document.getElementById('review-modal-overlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeReviewModal(); });
  document.getElementById('submit-review-btn')?.addEventListener('click', submitReview);
  document.getElementById('cancel-review-btn')?.addEventListener('click', closeReviewModal);

  // User menu & Dropdown
  document.getElementById('nav-user-btn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleUserDropdown();
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#nav-user')) closeUserDropdown();
  });
  document.getElementById('nav-logout-btn')?.addEventListener('click', logoutUser);

  // Focus-based autofill hint on login fields
  ['login-email', 'login-password'].forEach(id => {
    document.getElementById(id)?.addEventListener('focus', () => {
      const overlay = document.getElementById('auth-modal-overlay');
      if (overlay?.classList.contains('active')) injectDemoCredentials();
    });
  });

  // Mobile hamburger
  const hamburger = document.getElementById('hamburger-btn');
  const navLinks = document.getElementById('main-nav-links');
  function openMobileNav() { navLinks?.classList.add('mobile-open'); hamburger?.classList.add('open'); hamburger?.setAttribute('aria-expanded', 'true'); document.body.style.overflow = 'hidden'; }
  function closeMobileNav() { navLinks?.classList.remove('mobile-open'); hamburger?.classList.remove('open'); hamburger?.setAttribute('aria-expanded', 'false'); document.body.style.overflow = ''; }
  hamburger?.addEventListener('click', () => navLinks?.classList.contains('mobile-open') ? closeMobileNav() : openMobileNav());
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMobileNav(); });

  initRocketCursor();
  updateNavForAuthState();
  navigateTo('home', {}, false);
}

/* ─── Orange Rocket Cursor & Thruster Star Trail ─────────────────────────── */
function initRocketCursor() {
  const rocket = document.getElementById('rocket-cursor');
  const canvas = document.getElementById('rocket-trail-canvas');
  if (!rocket || !canvas) return;

  const ctx = canvas.getContext('2d');
  let width = 0, height = 0;
  let canvasSized = false;

  function ensureCanvasSize() {
    if (!canvasSized || width !== window.innerWidth || height !== window.innerHeight) {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      canvasSized = true;
    }
  }

  window.addEventListener('resize', () => { canvasSized = false; }, { passive: true });

  const particles = [];
  const colors = ['#ff9a3c', '#ff5500', '#ff2200', '#ffc233', '#ffffff'];

  function spawnParticle(x, y, isBurst = false) {
    ensureCanvasSize();
    const count = isBurst ? 12 : 2;
    for (let i = 0; i < count; i++) {
      const angle = isBurst ? Math.random() * Math.PI * 2 : (Math.PI / 4) + (Math.random() * 0.8 - 0.4);
      const speed = isBurst ? Math.random() * 3.5 + 1.2 : Math.random() * 1.6 + 0.6;
      particles.push({
        x: x + (Math.random() * 4 - 2),
        y: y + (Math.random() * 4 - 2),
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: isBurst ? Math.random() * 4 + 2 : Math.random() * 3 + 1.5,
        alpha: 1,
        decay: isBurst ? 0.03 : 0.045 + Math.random() * 0.02,
        color: colors[Math.floor(Math.random() * colors.length)],
        isStar: Math.random() > 0.45
      });
    }
  }

  function drawStar(cx, cy, spikes, outerRadius, innerRadius, color, alpha) {
    let rot = (Math.PI / 2) * 3;
    let x = cx;
    let y = cy;
    const step = Math.PI / spikes;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(cx, cy - outerRadius);
    for (let i = 0; i < spikes; i++) {
      x = cx + Math.cos(rot) * outerRadius;
      y = cy + Math.sin(rot) * outerRadius;
      ctx.lineTo(x, y);
      rot += step;

      x = cx + Math.cos(rot) * innerRadius;
      y = cy + Math.sin(rot) * innerRadius;
      ctx.lineTo(x, y);
      rot += step;
    }
    ctx.lineTo(cx, cy - outerRadius);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.globalAlpha = alpha;
    ctx.shadowColor = color;
    ctx.shadowBlur = 6;
    ctx.fill();
    ctx.restore();
  }

  let mouseX = -100, mouseY = -100;
  let prevX = -100, prevY = -100;
  let isAnimating = false;

  function renderParticles() {
    ctx.clearRect(0, 0, width, height);

    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.alpha -= p.decay;
      p.size = Math.max(0, p.size - 0.04);

      if (p.alpha <= 0 || p.size <= 0) {
        particles.splice(i, 1);
        continue;
      }

      if (p.isStar) {
        drawStar(p.x, p.y, 4, p.size * 1.5, p.size * 0.6, p.color, p.alpha);
      } else {
        ctx.save();
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.alpha;
        ctx.shadowColor = p.color;
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.restore();
      }
    }

    if (particles.length > 0) {
      requestAnimationFrame(renderParticles);
    } else {
      isAnimating = false;
    }
  }

  window.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    rocket.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
    rocket.classList.remove('hidden');

    const dist = Math.hypot(mouseX - prevX, mouseY - prevY);
    if (dist > 4) {
      spawnParticle(mouseX + 10, mouseY + 10);
      prevX = mouseX;
      prevY = mouseY;
    }

    if (!isAnimating && particles.length > 0) {
      isAnimating = true;
      requestAnimationFrame(renderParticles);
    }
  }, { passive: true });

  const interactiveSelectors = 'a, button, [role="button"], [onclick], .property-card, .room-card, .feature-card, .nav-link, .star-btn, .room-type-chip, .footer-link, .modal-close, .logo, .demo-cred-btn, .payment-method-label, .filter-pill, .stay-card';
  const inputSelectors = 'input, textarea, select';

  document.addEventListener('mouseover', (e) => {
    if (e.target.closest(interactiveSelectors)) {
      document.body.classList.add('cursor-hover');
    }
    if (e.target.closest(inputSelectors)) {
      document.body.classList.add('cursor-typing');
    }
  });

  document.addEventListener('mouseout', (e) => {
    if (e.target.closest(interactiveSelectors)) {
      document.body.classList.remove('cursor-hover');
    }
    if (e.target.closest(inputSelectors)) {
      document.body.classList.remove('cursor-typing');
    }
  });

  document.addEventListener('mousedown', (e) => {
    document.body.classList.add('cursor-active');
    spawnParticle(e.clientX, e.clientY, true);
    if (!isAnimating) {
      isAnimating = true;
      requestAnimationFrame(renderParticles);
    }
  });
  document.addEventListener('mouseup', () => document.body.classList.remove('cursor-active'));

  document.addEventListener('mouseleave', () => rocket.classList.add('hidden'));
  document.addEventListener('mouseenter', () => rocket.classList.remove('hidden'));
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}




