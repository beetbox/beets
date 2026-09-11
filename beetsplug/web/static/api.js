// api.js — thin wrappers over the beets web Flask endpoints. All relative URLs
// so a reverse-proxy prefix keeps working.

const jget = (u) => fetch(u).then((r) => {
  if (!r.ok) throw new Error(r.status + ' ' + u);
  return r.json();
});
const qpath = (q) => q.trim().split(/\s+/).filter(Boolean).map(encodeURIComponent).join('/');

export const stats = () => jget('stats');
export const itemQuery = (q, limit) => jget('item/query/' + qpath(q) + (limit ? '?limit=' + limit : ''));
export const item = (id) => jget('item/' + id);
export const album = (id) => jget('album/' + id + '?expand');
export const albumQuery = (q, limit) => jget('album/query/' + qpath(q) + (limit ? '?limit=' + limit : ''));
export const albumsByArtist = (n) => jget('album/query/' + encodeURIComponent('albumartist:' + n));
export const artists = () => jget('artist/');

// Paged albums for the infinite-scroll grid; reads the X-Total-Count header.
export async function albumsPage(offset, limit) {
  const r = await fetch(`album/?offset=${offset}&limit=${limit}`);
  if (!r.ok) throw new Error(r.status + ' album/ page');
  const total = parseInt(r.headers.get('X-Total-Count') || '0', 10);
  const data = await r.json();
  return { albums: data.albums || [], total };
}
