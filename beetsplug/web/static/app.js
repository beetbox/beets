// beets web — redesigned frontend (buildless ES module, talks to the Flask API)
import * as api from './api.js';

// ---- Cover helpers (real art layered over a per-album gradient) -------
const covers = [
  ['#3a2e4d','#e64980'], ['#2d1f2b','#f08c00'], ['#12303a','#22b8cf'], ['#3a1f24','#ff8787'],
  ['#2a2140','#845ef7'], ['#1f2e2a','#51cf66'], ['#33261a','#ffd43b'], ['#1a2433','#4dabf7'],
  ['#241a33','#5c7cfa'], ['#331a2b','#f06595'], ['#1a3330','#20c997'], ['#33301a','#fab005'],
];
function hashIdx(str) { let h = 0; str = '' + (str || ''); for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0; return Math.abs(h) % covers.length; }
const coverStyle = (seed) => `background:linear-gradient(140deg, ${covers[hashIdx(seed)][0]}, ${covers[hashIdx(seed)][1]})`;
const artImg = (albumId) => (albumId != null && albumId !== '') ? `<img class="art" src="album/${albumId}/art" alt="" loading="lazy" onerror="this.remove()">` : '';

// ---- Formatting ------------------------------------------------------
const esc = (s) => ('' + (s ?? '')).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtTime = (s) => { if (s == null || isNaN(s)) return '0:00'; s = Math.round(s); const m = Math.floor(s/60), sec = String(s%60).padStart(2,'0'); return m >= 60 ? `${Math.floor(m/60)}:${String(m%60).padStart(2,'0')}:${sec}` : `${m}:${sec}`; };
const fmtSize = (b) => !b ? '—' : b >= 1073741824 ? (b/1073741824).toFixed(2)+' GB' : (b/1048576).toFixed(1)+' MB';
const yearOf = (o) => o && o.year ? o.year : '';
// Sort by disc, then track, so multi-disc albums keep their disc order.
const byDiscTrack = (x, y) => (x.disc || 0) - (y.disc || 0) || (x.track || 0) - (y.track || 0);

// ---- State -----------------------------------------------------------
let mode = 'songs';
let openAlbum = null, openArtist = null, openTrack = null;
let searchMode = 'simple', searchText = '', albumQ = '', artistQ = '';
let results = [];             // current song search results
let selected = null;         // selected item id in songs mode
let artistsAll = null;       // cached [name]
let artistArt = {};          // name -> a cover album id (random one of the artist's albums)
const itemCache = {};        // id -> item
let renderGen = 0;           // bumped on every render(); async detail callbacks check it before writing

// playback
const audio = document.getElementById('audio');
let queue = [], qIndex = -1;

const contentEl = document.getElementById('content');
const PLACEHOLDER = { simple: 'Search artists, albums, tracks…', query: 'artist:radiohead year:2007..2009 format:FLAC' };
const SEARCH_CAP = 300;   // rows shown; we ask the server for one more to detect "there are more"

// ---- Routing ---------------------------------------------------------
function go(hash) { if (location.hash === hash) applyRoute(); else location.hash = hash; }
function applyRoute() {
  const h = decodeURIComponent(location.hash.replace(/^#/, ''));
  const slash = h.indexOf('/');
  const a = slash < 0 ? h : h.slice(0, slash);
  const b = slash < 0 ? '' : h.slice(slash + 1);
  openAlbum = openArtist = openTrack = null;
  if (a === 'album')        { mode = 'albums';  openAlbum = b; }
  else if (a === 'artist')  { mode = 'artists'; openArtist = b; }
  else if (a === 'track')   { openTrack = b; }
  else if (a === 'albums')  { mode = 'albums'; }
  else if (a === 'artists') { mode = 'artists'; }
  else                      { mode = 'songs'; }
  render();
}

const metaCell = (k, v) => `<div class="meta-cell"><div class="k">${k}</div><div class="v">${v}</div></div>`;

// ---- Dispatch --------------------------------------------------------
function render() {
  renderGen++;                 // any in-flight detail fetch from a prior view is now stale
  if (albumPager) { albumPager.stop(); albumPager = null; }
  clearTimeout(albumFilterTimer);
  contentEl.className = 'content' + (mode === 'songs' && openTrack === null ? ' mode-songs' : '');
  document.querySelectorAll('.seg').forEach(s => s.classList.toggle('active', s.dataset.mode === mode));
  if (openTrack !== null)  return renderTrackDetail(openTrack);
  if (mode === 'songs')    return renderSongs();
  if (openArtist !== null) return renderArtistPage(openArtist);
  if (openAlbum !== null)  return renderAlbumDetail(openAlbum);
  if (mode === 'albums')   return renderAlbums();
  if (mode === 'artists')  return renderArtists();
}

// ---- Songs -----------------------------------------------------------
const rowHTML = (t) => `
  <li class="result ${t.id===selected?'selected':''} ${t.id===currentId()&&!audio.paused?'playing':''}" data-id="${t.id}">
    <div class="cover-sm" style="${coverStyle(t.album||t.album_id)}">${artImg(t.album_id)}</div>
    <div class="meta"><div class="r-title">${esc(t.title)}</div><div class="r-sub">${esc(t.artist)} — ${esc(t.album)}</div></div>
    <div class="eq"><span></span><span></span><span></span></div>
  </li>`;

function renderSongs() {
  const sel = selected != null ? itemCache[selected] : null;
  contentEl.innerHTML = `
    <nav class="rail">
      <div class="search">
        <div class="search-modes">
          <button class="smode ${searchMode==='simple'?'active':''}" data-smode="simple">Simple</button>
          <button class="smode ${searchMode==='query'?'active':''}" data-smode="query">beets query</button>
        </div>
        <div class="search-field">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
          <input type="search" id="query" placeholder="${PLACEHOLDER[searchMode]}">
        </div>
        <div class="search-hint" id="searchHint"></div>
      </div>
      <ul class="results" id="results"></ul>
    </nav>
    <main class="detail"><div class="detail-inner" id="songDetail">${sel ? trackDetailHTML(sel) : emptyDetail()}</div></main>`;
  const q = document.getElementById('query'); if (q) q.value = searchText;
  paintResults();
}
function emptyDetail() {
  return `<div class="empty-note" style="margin-top:40px">Search your library, then pick a track to see its full metadata.</div>`;
}
function paintResults() {
  const ul = document.getElementById('results');
  const hint = document.getElementById('searchHint');
  if (!ul) return;
  if (searchText.trim().length < 2) {
    ul.innerHTML = `<li class="empty-note">Type at least 2 characters to search.</li>`;
    if (hint) hint.innerHTML = 'beets query syntax supported';
    return;
  }
  const capped = results.length > SEARCH_CAP;
  const shown = results.slice(0, SEARCH_CAP);
  ul.innerHTML = shown.length ? shown.map(rowHTML).join('') : `<li class="empty-note">No matching tracks.</li>`;
  if (hint) hint.innerHTML = capped
    ? `showing first <b>${SEARCH_CAP}</b> — refine to narrow`
    : `<b>${results.length}</b> result${results.length===1?'':'s'}`;
}
let searchTimer = null;
function runSearch() {
  const q = searchText.trim();
  if (q.length < 2) { results = []; paintResults(); return; }
  const hint = document.getElementById('searchHint');
  if (hint) hint.textContent = 'Searching…';
  const mine = q;
  api.itemQuery(q, SEARCH_CAP + 1).then(data => {
    if (mine !== searchText.trim()) return; // stale
    results = data.results || [];
    results.forEach(it => itemCache[it.id] = it);
    paintResults();
  }).catch(() => { if (hint) hint.textContent = 'Search failed.'; });
}

// ---- Track detail ----------------------------------------------------
function trackDetailHTML(t, crumbs) {
  return `
    ${crumbs || ''}
    <div class="now-head">
      <div class="cover-lg" style="${coverStyle(t.album||t.album_id)}"><div class="grain"></div>${artImg(t.album_id)}</div>
      <div class="head-text">
        <div class="eyebrow">Track metadata</div>
        <h1 class="song-title">${esc(t.title)}</h1>
        <div class="by"><b>${esc(t.artist)}</b></div>
        <div class="album-line">${esc(t.album)}${yearOf(t)?' · '+t.year:''}${t.genre?' · '+esc(t.genre):''}</div>
        <button class="play-cta" data-play="${t.id}"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>Play track</button>
      </div>
    </div>
    <div class="meta-grid">
      ${metaCell('Track', `${t.track||'—'}${t.tracktotal?' / '+t.tracktotal:''}`)}
      ${metaCell('Disc', `${t.disc||1}${t.disctotal?' / '+t.disctotal:''}`)}
      ${metaCell('Length', fmtTime(t.length))}
      ${metaCell('Format', esc(t.format||'—'))}
      ${metaCell('Bitrate', t.bitrate?`${Math.round(t.bitrate/1000)} <span style="color:var(--text-3);font-size:12px">kbps</span>`:'—')}
      ${metaCell('Sample rate', t.samplerate?`${(t.samplerate/1000).toFixed(1)} <span style="color:var(--text-3);font-size:12px">kHz</span>`:'—')}
      ${metaCell('Channels', `${t.channels||'—'}${t.bitdepth?' · '+t.bitdepth+'-bit':''}`)}
      ${metaCell('Size', fmtSize(t.size))}
    </div>
    <div class="links">
      ${t.mb_trackid ? `<a class="chip" target="_blank" href="https://musicbrainz.org/recording/${encodeURIComponent(t.mb_trackid)}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 000 18M3 12h18" stroke-linecap="round"/></svg>MusicBrainz</a>` : ''}
      <a class="chip" target="_blank" href="item/${t.id}/file"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>Download</a>
      ${t.genre?`<span class="chip" style="cursor:default">${esc(t.genre)}</span>`:''}
    </div>
    ${t.lyrics ? `<div class="lyrics-block"><h3>Lyrics</h3><div class="lyrics">${esc(t.lyrics)}</div></div>`
               : `<div class="lyrics-block"><h3>Lyrics</h3><div class="lyrics" style="color:var(--text-3)">No lyrics stored for this track.</div></div>`}
    ${t.comments ? `<div class="lyrics-block"><h3>Comments</h3><div class="lyrics">${esc(t.comments)}</div></div>` : ''}`;
}
function renderTrackDetail(id) {
  const gen = renderGen;
  contentEl.innerHTML = `<div class="browse"><div class="detail-page"><div class="loading-note">Loading track…</div></div></div>`;
  const done = (t) => {
    itemCache[id] = t;
    if (gen !== renderGen) return;   // navigated away while loading
    const crumbs = `<div class="crumbs">
      ${t.album_id!=null?`<button class="crumb" data-nav="album/${t.album_id}">${esc(t.album)}</button><span class="sep">/</span>`:''}
      <span class="crumb-cur">${esc(t.title)}</span></div>`;
    contentEl.innerHTML = `<div class="browse"><div class="detail-page">${trackDetailHTML(t, crumbs)}</div></div>`;
  };
  if (itemCache[id]) return done(itemCache[id]);
  api.item(id).then(done).catch(() => { if (gen === renderGen) contentEl.innerHTML = `<div class="browse"><div class="empty-note">Track not found.</div></div>`; });
}

// ---- Albums grid -----------------------------------------------------
const albumCardHTML = (a) => `
  <div class="album-card" data-album="${a.id}">
    <div class="cover" style="${coverStyle(a.album||a.id)}"><div class="grain"></div>${artImg(a.id)}
      <div class="play-badge" data-playalbum="${a.id}"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></div>
    </div>
    <div class="a-title">${esc(a.album)}</div>
    <div class="a-sub">${esc(a.albumartist)}</div>
    <div class="a-year">${yearOf(a)||'—'}</div>
  </div>`;

const PAGE = 120;
function makePager(fetchPage, renderCard, gridId, countId) {
  let offset = 0, total = Infinity, loading = false, io = null, dead = false;
  async function loadMore() {
    if (dead || loading || offset >= total) return;
    loading = true;
    let page;
    try { page = await fetchPage(offset, PAGE); }
    catch (e) { loading = false; return; }
    if (dead) { loading = false; return; }   // a re-render superseded this pager mid-fetch
    const grid = document.getElementById(gridId);
    if (!grid) { dead = true; return; }            // view changed while awaiting
    total = page.total;
    offset += page.items.length;
    grid.insertAdjacentHTML('beforeend', page.items.map(renderCard).join(''));
    const c = document.getElementById(countId); if (c) c.textContent = total;
    loading = false;
    if (page.items.length === 0 && io) io.disconnect();
  }
  function attachSentinel() {
    const grid = document.getElementById(gridId); if (!grid) return;
    const sentinel = document.createElement('div');
    sentinel.style.cssText = 'grid-column:1/-1;height:1px';
    grid.after(sentinel);
    io = new IntersectionObserver(
      (es) => { if (es.some((e) => e.isIntersecting)) loadMore(); },
      { rootMargin: '600px' },
    );
    io.observe(sentinel);
  }
  function stop() { dead = true; if (io) io.disconnect(); }
  return { loadMore, attachSentinel, stop };
}
let albumPager = null;
let albumFilterTimer = null;

function renderAlbums() {
  if (albumPager) { albumPager.stop(); albumPager = null; }
  // browseShell(title, count, filterId, placeholder, filterValue, gridId, gridInner)
  contentEl.innerHTML = browseShell('Albums', '…', 'albumFilter', 'Filter albums…', albumQ, 'albumGrid', '');
  loadAlbumGrid();
}
function loadAlbumGrid() {
  if (albumPager) { albumPager.stop(); albumPager = null; }
  const grid = document.getElementById('albumGrid'); if (grid) grid.innerHTML = '';
  if (albumQ.trim()) {
    // filtered: server-side beets query, no infinite scroll
    const mine = albumQ.trim();
    api.albumQuery(mine, SEARCH_CAP + 1).then((d) => {
      if (mine !== albumQ.trim()) return;   // a newer filter superseded this one
      const all = d.results || [];
      const capped = all.length > SEARCH_CAP;
      const list = all.slice(0, SEARCH_CAP);
      const g = document.getElementById('albumGrid'); if (!g) return;
      g.innerHTML = list.length
        ? list.map(albumCardHTML).join('')
        : '<div class="empty-note">No matching albums.</div>';
      const c = document.getElementById('albumCount'); if (c) c.textContent = capped ? SEARCH_CAP + '+' : list.length;
    }).catch(() => {});
  } else {
    albumPager = makePager(
      (o, l) => api.albumsPage(o, l).then((r) => ({ items: r.albums, total: r.total })),
      albumCardHTML, 'albumGrid', 'albumCount',
    );
    albumPager.loadMore().then(() => { if (albumPager) albumPager.attachSentinel(); });
  }
}

// ---- Artists grid ----------------------------------------------------
const CAP = 180;
const artistCardHTML = (name) => `
  <div class="artist-card" data-artist="${esc(name)}">
    <div class="avatar" style="${coverStyle(name)}"><span class="initial">${esc((name||'?').trim()[0]||'?')}</span>${artImg(artistArt[name])}</div>
    <div class="ar-name">${esc(name)}</div>
  </div>`;
function artistMatches() {
  const q = artistQ.trim().toLowerCase(); const list = artistsAll || [];
  return q ? list.filter(n => (n||'').toLowerCase().includes(q)) : list;
}
function renderArtists() {
  contentEl.innerHTML = browseShell('Artists', artistsAll ? artistsAll.length : '…', 'artistFilter', 'Filter artists…', artistQ, 'artistGrid',
    artistsAll ? '' : '<div class="loading-note">Loading artists…</div>');
  if (!artistsAll) {
    api.artists().then(d => { artistsAll = (d.artist_names || []).filter(Boolean); artistArt = d.artist_art || {}; if (mode==='artists' && openArtist===null) paintArtistGrid(); })
      .catch(() => { const g = document.getElementById('artistGrid'); if (g) g.innerHTML = '<div class="empty-note">Could not load artists.</div>'; });
  } else paintArtistGrid();
}
function paintArtistGrid() {
  const g = document.getElementById('artistGrid'); const c = document.getElementById('artistCount'); if (!g) return;
  const list = artistMatches();
  g.innerHTML = list.length ? list.slice(0, CAP).map(artistCardHTML).join('') : '<div class="empty-note">No matching artists.</div>';
  if (c) c.textContent = list.length;
  const note = document.getElementById('capNote');
  if (note) note.textContent = list.length > CAP ? `showing first ${CAP} — refine with the filter` : '';
}

function browseShell(title, count, filterId, ph, val, gridId, gridInner) {
  const gridClass = gridId === 'albumGrid' ? 'album-grid' : 'artist-grid';
  return `
    <div class="browse">
      <div class="browse-head">
        <div class="mini-search"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg><input id="${filterId}" placeholder="${ph}" value="${esc(val)}"></div>
        <h2>${title}</h2><span class="count" id="${gridId==='albumGrid'?'albumCount':'artistCount'}">${count}</span>
        <span class="a-year" id="capNote" style="margin-left:10px"></span>
        <div class="grow"></div>
      </div>
      <div class="${gridClass}" id="${gridId}">${gridInner}</div>
    </div>`;
}

// ---- Album detail ----------------------------------------------------
const ICON_PLAY_SM = '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
function renderAlbumDetail(id) {
  const gen = renderGen;
  contentEl.innerHTML = `<div class="browse"><div class="loading-note">Loading album…</div></div>`;
  api.album(id).then(a => {
    const items = (a.items || []).slice().sort(byDiscTrack);
    items.forEach(it => itemCache[it.id] = it);
    if (gen !== renderGen) return;   // navigated away while loading
    const total = items.reduce((s,t)=>s+(t.length||0),0);
    const totalSize = items.reduce((s,t)=>s+(t.size||0),0);
    const rows = items.map(t => `
      <div class="trow ${t.id===currentId()&&!audio.paused?'playing':''}" data-track="${t.id}">
        <div class="num">${t.track||''}</div>
        <div class="tt"><div class="tt-name">${esc(t.title)}</div></div>
        <button class="rowplay" data-play="${t.id}" title="Play">${ICON_PLAY_SM}</button>
        <div class="len">${fmtTime(t.length)}</div>
      </div>`).join('');
    contentEl.innerHTML = `
      <div class="browse">
        <div class="crumbs">
          <button class="crumb" data-nav="albums"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 18l-6-6 6-6"/></svg>Albums</button>
          <span class="sep">/</span><span class="crumb-cur">${esc(a.album)}</span>
        </div>
        <div class="album-hero">
          <div class="cover" style="${coverStyle(a.album||a.id)}"><div class="grain"></div>${artImg(a.id)}</div>
          <div>
            <div class="eyebrow">Album</div>
            <h1 class="ah-title">${esc(a.album)}</h1>
            <div class="ah-artist link" data-nav="artist/${encodeURIComponent(a.albumartist||'')}">${esc(a.albumartist)}</div>
            <button class="play-cta" data-play="${items[0]?items[0].id:''}"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>Play album</button>
          </div>
        </div>
        <div class="meta-grid">
          ${metaCell('Album artist', esc(a.albumartist||'—'))}
          ${metaCell('Year', yearOf(a)||'—')}
          ${metaCell('Genre', esc(a.genre||'—'))}
          ${metaCell('Label', esc(a.label||'—'))}
          ${metaCell('Tracks', items.length)}
          ${metaCell('Total time', fmtTime(total))}
          ${metaCell('Format', esc((items[0]&&items[0].format)||'—'))}
          ${metaCell('Total size', fmtSize(totalSize))}
        </div>
        ${a.mb_albumid?`<div class="links"><a class="chip" target="_blank" href="https://musicbrainz.org/release/${encodeURIComponent(a.mb_albumid)}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 000 18M3 12h18" stroke-linecap="round"/></svg>MusicBrainz release</a></div>`:''}
        <div class="tracklist">${rows}</div>
        <div class="tl-hint">Click a track for its full metadata · hover to play</div>
      </div>`;
  }).catch(() => { if (gen === renderGen) contentEl.innerHTML = `<div class="browse"><div class="empty-note">Album not found.</div></div>`; });
}

// ---- Artist page -----------------------------------------------------
function renderArtistPage(name) {
  const gen = renderGen;
  contentEl.innerHTML = `<div class="browse"><div class="loading-note">Loading artist…</div></div>`;
  api.albumsByArtist(name).then(d => {
    if (gen !== renderGen) return;   // navigated away while loading
    const albums = (d.results || []).slice().sort((x,y)=>(y.year||0)-(x.year||0));
    const years = albums.map(a=>a.year).filter(Boolean);
    contentEl.innerHTML = `
      <div class="browse">
        <div class="crumbs">
          <button class="crumb" data-nav="artists"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 18l-6-6 6-6"/></svg>Artists</button>
          <span class="sep">/</span><span class="crumb-cur">${esc(name)}</span>
        </div>
        <div class="album-hero">
          <div class="cover" style="border-radius:999px;${coverStyle(name)};display:grid;place-items:center"><div class="grain"></div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;font-size:64px;color:rgba(255,255,255,.92)">${esc((name||'?').trim()[0]||'?')}</span></div>
          <div>
            <div class="eyebrow">Artist</div>
            <h1 class="ah-title">${esc(name)}</h1>
            <div class="ah-facts"><span class="badge">${albums.length} album${albums.length===1?'':'s'}</span>${years.length?`<span class="badge">${Math.min(...years)}–${Math.max(...years)}</span>`:''}</div>
          </div>
        </div>
        <div class="album-grid">${albums.length?albums.map(albumCardHTML).join(''):'<div class="empty-note">No albums found for this artist.</div>'}</div>
      </div>`;
  }).catch(() => { if (gen === renderGen) contentEl.innerHTML = `<div class="browse"><div class="empty-note">Could not load artist.</div></div>`; });
}

// ---- Player ----------------------------------------------------------
const playIcon = document.getElementById('playIcon');
const PLAY = '<path d="M8 5v14l11-7z"/>', PAUSE = '<path d="M6 5h4v14H6zM14 5h4v14h-4z"/>';
const currentId = () => (qIndex >= 0 && queue[qIndex]) ? queue[qIndex].id : null;

function playFrom(list, idx) {
  queue = list; qIndex = idx;
  const t = queue[qIndex]; if (!t) return;
  audio.src = 'item/' + t.id + '/file';
  audio.play().catch(()=>{});
  updatePlayerBar();
  if ('mediaSession' in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: t.title||'', artist: t.artist||'', album: t.album||'',
      artwork: t.album_id!=null ? [96,128,192,256,384,512].map(s=>({src:'album/'+t.album_id+'/art', sizes:s+'x'+s})) : [],
    });
  }
}
function playOne(id) {
  // Play a single track (the track-detail "Play track" button).
  const t = itemCache[id];
  if (t) { playFrom([t], 0); return; }
  api.item(id).then(x => { itemCache[x.id] = x; playFrom([x], 0); }).catch(() => {});
}
function playFromTracklist(id) {
  // Play from the album tracklist currently on screen, in its displayed order,
  // so Play-album and the per-row play buttons queue the album's own tracks.
  const ids = [...document.querySelectorAll('.tracklist .trow[data-track]')].map(el => +el.dataset.track);
  const list = ids.map(i => itemCache[i]).filter(Boolean);
  const idx = list.findIndex(x => x.id == id);
  if (idx >= 0) playFrom(list, idx); else playOne(id);
}
function playFromResults(id) {
  // Play from the current Songs search results.
  const idx = results.findIndex(x => x.id == id);
  if (idx >= 0) playFrom(results, idx); else playOne(id);
}
function togglePlay() {
  if (!audio.src) { if (results[0]) playFrom(results, 0); return; }
  if (audio.paused) audio.play(); else audio.pause();
}
function updatePlayerBar() {
  const t = queue[qIndex] || null;
  const cover = document.getElementById('pl-cover');
  cover.style.cssText = t ? coverStyle(t.album||t.album_id) : 'background:var(--surface-2)';
  cover.innerHTML = t ? artImg(t.album_id) : '';
  document.getElementById('pl-title').textContent = t ? t.title : '—';
  document.getElementById('pl-sub').textContent = t ? `${t.artist} — ${t.album}` : 'Nothing playing';
  document.getElementById('totTime').textContent = t ? fmtTime(t.length) : '0:00';
  playIcon.innerHTML = (t && !audio.paused) ? PAUSE : PLAY;
}
audio.addEventListener('timeupdate', () => {
  const d = audio.duration || (queue[qIndex] && queue[qIndex].length) || 0;
  const p = d ? audio.currentTime / d : 0;
  document.getElementById('seekFill').style.width = (p*100)+'%';
  document.getElementById('seekKnob').style.left = (p*100)+'%';
  document.getElementById('curTime').textContent = fmtTime(audio.currentTime);
});
audio.addEventListener('play', () => { playIcon.innerHTML = PAUSE; markPlaying(); });
audio.addEventListener('pause', () => { playIcon.innerHTML = PLAY; markPlaying(); });
audio.addEventListener('ended', () => { if (qIndex < queue.length-1) playFrom(queue, qIndex+1); });
function markPlaying() { document.querySelectorAll('.result,.trow').forEach(el => {
  const id = +(el.dataset.id ?? el.dataset.track); el.classList.toggle('playing', id===currentId() && !audio.paused); }); }

// ---- Events ----------------------------------------------------------
document.getElementById('nav').addEventListener('click', e => { const b = e.target.closest('.seg'); if (b) go('#' + b.dataset.mode); });
let inputTimer = null;
contentEl.addEventListener('input', e => {
  if (e.target.id === 'query') { searchText = e.target.value; clearTimeout(inputTimer); inputTimer = setTimeout(runSearch, 280); }
  else if (e.target.id === 'albumFilter') {
    albumQ = e.target.value;
    clearTimeout(albumFilterTimer);
    albumFilterTimer = setTimeout(loadAlbumGrid, 280);
  }
  else if (e.target.id === 'artistFilter') { artistQ = e.target.value; paintArtistGrid(); }
});
contentEl.addEventListener('click', e => {
  const smode = e.target.closest('.smode');
  if (smode) { searchMode = smode.dataset.smode; document.querySelectorAll('.smode').forEach(s=>s.classList.toggle('active', s===smode));
    const inp = document.getElementById('query'); if (inp) inp.placeholder = PLACEHOLDER[searchMode]; if (searchText.trim()) runSearch(); return; }
  const navEl = e.target.closest('[data-nav]'); if (navEl) { go('#' + navEl.dataset.nav); return; }
  const pb = e.target.closest('[data-playalbum]');
  if (pb) { e.stopPropagation(); api.album(pb.dataset.playalbum).then(a=>{ const its=(a.items||[]).slice().sort(byDiscTrack); its.forEach(it=>itemCache[it.id]=it); if (its[0]) playFrom(its,0); }); return; }
  const pe = e.target.closest('[data-play]');
  if (pe && pe.dataset.play) {
    e.stopPropagation();
    // An album tracklist on screen means album context (Play-album and the row
    // play buttons); otherwise it's the track-detail "Play track" button.
    if (document.querySelector('.tracklist')) playFromTracklist(pe.dataset.play);
    else playOne(pe.dataset.play);
    return;
  }
  const tr = e.target.closest('[data-track]'); if (tr) { go('#track/' + tr.dataset.track); return; }
  const card = e.target.closest('[data-album]'); if (card) { go('#album/' + card.dataset.album); return; }
  const ar = e.target.closest('[data-artist]'); if (ar) { go('#artist/' + encodeURIComponent(ar.dataset.artist)); return; }
  const row = e.target.closest('.result');
  if (row) {
    // Update selection and the detail panel in place, without rebuilding the
    // results list, so the clicked row survives for a following double-click.
    selected = +row.dataset.id;
    document.querySelectorAll('.result.selected').forEach(el => el.classList.remove('selected'));
    row.classList.add('selected');
    const sel = itemCache[selected], detail = document.getElementById('songDetail');
    if (detail && sel) detail.innerHTML = trackDetailHTML(sel);
  }
});
contentEl.addEventListener('dblclick', e => { const row = e.target.closest('.result'); if (row) playFromResults(row.dataset.id); });
document.getElementById('playBtn').addEventListener('click', togglePlay);
document.getElementById('nextBtn').addEventListener('click', () => { if (qIndex < queue.length-1) playFrom(queue, qIndex+1); });
document.getElementById('prevBtn').addEventListener('click', () => { if (qIndex > 0) playFrom(queue, qIndex-1); });
document.getElementById('seek').addEventListener('click', e => {
  const r = e.currentTarget.getBoundingClientRect();
  const d = audio.duration || 0; if (d) audio.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left)/r.width)) * d;
});
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === ' ') { togglePlay(); e.preventDefault(); }
});

// ---- Volume ----------------------------------------------------------
const volTrack = document.getElementById('volTrack');
function setVolume(frac) {
  frac = Math.min(1, Math.max(0, frac));
  audio.volume = frac;
  const fill = document.getElementById('volFill');
  if (fill) fill.style.width = (frac * 100) + '%';
  if (volTrack) volTrack.setAttribute('aria-valuenow', Math.round(frac * 100));
}
if (volTrack) {
  volTrack.addEventListener('click', e => {
    const r = volTrack.getBoundingClientRect();
    setVolume((e.clientX - r.left) / r.width);
  });
  volTrack.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { setVolume(audio.volume + 0.05); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { setVolume(audio.volume - 0.05); e.preventDefault(); }
    else if (e.key === 'Home') { setVolume(0); e.preventDefault(); }
    else if (e.key === 'End') { setVolume(1); e.preventDefault(); }
  });
}
setVolume(audio.volume);   // reflect the audio element's actual volume in the bar

// ---- Media Session (OS / hardware transport controls) ----------------
if ('mediaSession' in navigator) {
  try {
    const ms = navigator.mediaSession;
    ms.setActionHandler('play', () => { audio.play().catch(() => {}); });
    ms.setActionHandler('pause', () => audio.pause());
    ms.setActionHandler('previoustrack', () => { if (qIndex > 0) playFrom(queue, qIndex - 1); });
    ms.setActionHandler('nexttrack', () => { if (qIndex < queue.length - 1) playFrom(queue, qIndex + 1); });
  } catch (e) { /* not all actions are supported everywhere */ }
}

// ---- Theme -----------------------------------------------------------
const root = document.documentElement, themeIcon = document.getElementById('themeIcon');
const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON = '<path d="M21 12.8A9 9 0 1111.2 3 7 7 0 0021 12.8z"/>';
const curTheme = () => root.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
const syncIcon = () => themeIcon.innerHTML = curTheme()==='dark' ? SUN : MOON;
document.getElementById('themeToggle').addEventListener('click', () => { root.setAttribute('data-theme', curTheme()==='dark'?'light':'dark'); syncIcon(); });

// ---- Boot ------------------------------------------------------------
api.stats().then(s => {
  document.getElementById('stat-songs').textContent = (s.items||0).toLocaleString();
  document.getElementById('stat-albums').textContent = (s.albums||0).toLocaleString();
}).catch(()=>{});
window.addEventListener('hashchange', applyRoute);
applyRoute(); updatePlayerBar(); syncIcon();
