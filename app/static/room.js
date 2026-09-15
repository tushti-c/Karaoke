const code = location.pathname.split('/').pop();
const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---------- identity ----------
const store = {
  get: (k) => localStorage.getItem('kb:' + k),
  set: (k, v) => localStorage.setItem('kb:' + k, v),
};
let userId = store.get('uid');
if (!userId) { userId = crypto.randomUUID(); store.set('uid', userId); }
let userName = store.get('name') || '';
const tasteKey = 'taste:' + code;
let taste = store.get(tasteKey);

let GENRES = {}, QUIZ = [], songs = [], listed = new Set();

const toast = (msg) => { const t = $('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('show'), 1800); };
const show = (...ids) => ['quiz', 'pick', 'main'].forEach((id) => $(id).classList.toggle('hidden', !ids.includes(id)));

// ---------- name / share ----------
const renderName = () => { $('nameLabel').textContent = userName || 'Set your name'; };
$('nameBtn').onclick = () => {
  const n = prompt('What should we call you? (shown next to songs you add)', userName);
  if (n !== null) { userName = n.trim().slice(0, 40); store.set('name', userName); renderName(); }
};
$('share').onclick = async () => {
  const url = location.origin + '/r/' + code;
  if (navigator.share) { try { await navigator.share({ title: 'Karaoke Board', url }); return; } catch {} }
  await navigator.clipboard.writeText(url).catch(() => {});
  toast('Link copied — send it to everyone!');
};

// ---------- quiz ----------
let qi = 0, answers = [];
function renderQuiz() {
  const q = QUIZ[qi];
  $('qbar').style.width = (qi / QUIZ.length) * 100 + '%';
  $('qcount').textContent = `Question ${qi + 1} of ${QUIZ.length}`;
  $('qtext').textContent = q.q;
  $('qopts').innerHTML = q.options.map((o, i) => `<button class="option" data-i="${i}">${esc(o.text)}</button>`).join('');
  $('qopts').querySelectorAll('.option').forEach((b) => (b.onclick = async () => {
    answers.push(+b.dataset.i);
    qi++;
    if (qi < QUIZ.length) return renderQuiz();
    const res = await api('/api/quiz', { method: 'POST', body: JSON.stringify({ answers }) });
    setTaste(res.primary, true);
  }));
}
const startQuiz = () => { qi = 0; answers = []; renderQuiz(); show('quiz'); };
$('qskip').onclick = () => showPick();
$('retake').onclick = startQuiz;
$('pickCancel').onclick = () => (taste ? show('main') : startQuiz());
$('changeTaste').onclick = showPick;

function showPick() {
  $('genreGrid').innerHTML = Object.entries(GENRES).map(([k, g]) =>
    `<button class="genre-chip ${k === taste ? 'active' : ''}" data-g="${k}"><span>${g.emoji}</span>${esc(g.label)}</button>`).join('');
  $('genreGrid').querySelectorAll('.genre-chip').forEach((b) => (b.onclick = () => setTaste(b.dataset.g, false)));
  $('pickCancel').classList.toggle('hidden', !taste);
  show('pick');
}

function setTaste(g, fromQuiz) {
  taste = g; store.set(tasteKey, g);
  const info = GENRES[g];
  $('tEmoji').textContent = info.emoji; $('tLabel').textContent = info.label; $('tBlurb').textContent = info.blurb;
  $('sugIntro').textContent = `Top ${info.label} tracks right now. Tap + to add one to the board.`;
  show('main');
  loadSuggestions();
  if (fromQuiz) { toast(`You're a ${info.label} person ${info.emoji}`); switchTab('suggested'); }
}

// ---------- tabs ----------
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  ['board', 'suggested', 'playlists', 'search'].forEach((t) => $('tab-' + t).classList.toggle('hidden', t !== name));
  if (name === 'playlists' && !$('pls').children.length) loadPlaylists();
  if (name === 'search') $('q').focus();
}
document.querySelectorAll('.tab').forEach((t) => (t.onclick = () => switchTab(t.dataset.tab)));

// ---------- audio preview ----------
const audio = $('audio');
let playing = null;
audio.onended = () => { document.querySelectorAll('.play.on').forEach((b) => b.classList.remove('on')); playing = null; };
function bindPlay(container) {
  container.querySelectorAll('.play').forEach((b) => (b.onclick = () => {
    const src = b.dataset.src;
    if (playing === src) { audio.pause(); playing = null; b.classList.remove('on'); return; }
    document.querySelectorAll('.play.on').forEach((x) => x.classList.remove('on'));
    audio.src = src; audio.play(); playing = src; b.classList.add('on');
  }));
}

// ---------- track rendering ----------
const art = (t) => (t.cover ? `<img src="${esc(t.cover)}" alt="" loading="lazy">` : '<div class="noart"></div>');
const playBtn = (t) => (t.preview ? `<button class="play" data-src="${esc(t.preview)}" title="Preview">▶</button>` : '');

function renderTracks(el, tracks) {
  if (!tracks.length) { el.innerHTML = '<div class="empty">Nothing here.</div>'; return; }
  el.innerHTML = tracks.map((t, i) => {
    const on = listed.has(t.deezer_id);
    return `<div class="track">
      ${art(t)}
      <div class="meta"><div class="t">${esc(t.title)}</div><div class="a">${esc(t.artist)}</div></div>
      <div class="actions">${playBtn(t)}
        <button class="btn sm ${on ? 'secondary' : ''}" data-i="${i}">${on ? 'On board ✓' : '+ Add'}</button></div>
    </div>`;
  }).join('');
  bindPlay(el);
  el.querySelectorAll('.btn[data-i]').forEach((b) => (b.onclick = () => addSong(tracks[+b.dataset.i], b)));
}

async function addSong(t, btn) {
  if (btn) btn.disabled = true;
  try {
    const res = await api(`/api/rooms/${code}/songs`, {
      method: 'POST',
      body: JSON.stringify({ ...t, genre: taste, user_id: userId, user_name: userName }),
    });
    applySongs(res.songs);
    toast(res.already_listed ? 'Already on the board — your vote was added' : `Added “${t.title}”`);
    if (btn) { btn.textContent = 'On board ✓'; btn.classList.add('secondary'); }
  } catch (e) { toast(e.message); }
  finally { if (btn) btn.disabled = false; }
}

// ---------- leaderboard ----------
function applySongs(list) {
  songs = list;
  listed = new Set(songs.filter((s) => s.deezer_id).map((s) => s.deezer_id));
  const lb = $('lb');
  $('lbEmpty').classList.toggle('hidden', songs.length > 0);
  $('lbCount').classList.toggle('hidden', !songs.length);
  $('lbCount').textContent = songs.length;
  lb.innerHTML = songs.map((s, i) => `<div class="track">
      <div class="rank r${i + 1}">${i + 1}</div>
      ${art(s)}
      <div class="meta"><div class="t">${esc(s.title)}</div><div class="a">${esc(s.artist)}</div>
        ${s.added_by_name ? `<div class="by">added by ${esc(s.added_by_name)}</div>` : ''}</div>
      <div class="actions">${playBtn(s)}
        <button class="vote ${s.mine ? 'on' : ''}" data-id="${s.id}" title="${s.mine ? 'Remove your vote' : 'Second this'}">👍 ${s.votes}</button></div>
    </div>`).join('');
  bindPlay(lb);
  lb.querySelectorAll('.vote').forEach((b) => (b.onclick = async () => {
    b.disabled = true;
    try { applySongs((await api(`/api/rooms/${code}/songs/${b.dataset.id}/vote`, { method: 'POST', body: JSON.stringify({ user_id: userId }) })).songs); }
    catch (e) { toast(e.message); }
  }));
}
async function refreshBoard() {
  try { applySongs((await api(`/api/rooms/${code}/songs?user_id=${userId}`)).songs); } catch {}
}

// ---------- suggestions / playlists / search ----------
async function loadSuggestions() {
  $('sug').innerHTML = '<div class="empty">Loading…</div>';
  try { renderTracks($('sug'), (await api(`/api/suggest?genre=${taste}`)).tracks); }
  catch (e) { $('sug').innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function loadPlaylists() {
  $('pls').innerHTML = '<div class="empty">Loading…</div>';
  try {
    const { playlists } = await api('/api/playlists');
    $('pls').innerHTML = playlists.map((p) => `<button class="pl" data-id="${p.id}" data-title="${esc(p.title)}">
        <img src="${esc(p.cover)}" alt="" loading="lazy"><div>${esc(p.title)}<small>${p.tracks} tracks</small></div></button>`).join('');
    $('pls').querySelectorAll('.pl').forEach((b) => (b.onclick = () => openPlaylist(b.dataset.id, b.dataset.title)));
  } catch (e) { $('pls').innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
async function openPlaylist(id, title) {
  $('plList').classList.add('hidden'); $('plDetail').classList.remove('hidden');
  $('plTitle').textContent = title;
  $('plTracks').innerHTML = '<div class="empty">Loading…</div>';
  try { renderTracks($('plTracks'), (await api(`/api/playlists/${id}`)).tracks); }
  catch (e) { $('plTracks').innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
$('plBack').onclick = () => { $('plDetail').classList.add('hidden'); $('plList').classList.remove('hidden'); };

let searchT;
$('q').addEventListener('input', () => {
  clearTimeout(searchT);
  const q = $('q').value.trim();
  if (q.length < 2) { $('results').innerHTML = ''; return; }
  searchT = setTimeout(async () => {
    try { renderTracks($('results'), (await api(`/api/search?q=${encodeURIComponent(q)}`)).tracks); } catch {}
  }, 300);
});
$('mAdd').onclick = () => {
  const title = $('mTitle').value.trim(), artist = $('mArtist').value.trim();
  if (!title || !artist) return toast('Need both a title and an artist');
  addSong({ title, artist }, $('mAdd')).then(() => { $('mTitle').value = ''; $('mArtist').value = ''; switchTab('board'); });
};

// ---------- boot ----------
(async () => {
  renderName();
  const [room, quiz] = await Promise.all([api(`/api/rooms/${code}`), api('/api/quiz')]);
  $('roomName').textContent = room.name; $('roomCode').textContent = '#' + code; document.title = room.name + ' · Karaoke Board';
  GENRES = quiz.genres; QUIZ = quiz.questions;
  refreshBoard();
  setInterval(refreshBoard, 8000);
  if (taste && GENRES[taste]) setTaste(taste, false); else startQuiz();
})();
