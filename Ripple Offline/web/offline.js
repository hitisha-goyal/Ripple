/* Ripple Offline — the screens that only exist here.

   Appended to the shared front end when the offline build is made. Everything
   else on screen is the shared file, unchanged, so the two editions cannot
   drift apart. What is here is what genuinely differs: online, the folder to
   scan and the SQL dialect are environment variables set by whoever deploys
   the thing. Offline there is nobody to set them, so they are asked for on
   screen and remembered in a file beside the program.

   These three functions replace ones of the same name in the shared file.
   JavaScript hoists every function declaration in a file before running any of
   it, so the later ones — these — are the ones that run. */

// ── the first run ─────────────────────────────────────────────────────────
/* Nothing has been chosen yet, so the first thing on screen is the question,
   rather than a wizard that would scan nothing and say nothing was found. */
function afterBoot() {
  if (S.health && !S.health.configured) S.view = 'settings';
  keepAlive();
}

// ── telling the program somebody is still here ────────────────────────────
/* The built program has no console window and nothing to close. Closing this
   tab used to leave it running where nobody could see it, holding its own
   folder open — so the folder could not be deleted, the port stayed taken, and
   the only way out was Task Manager.

   So this page says it is here, every few seconds, and says goodbye on the way
   out. The goodbye is the reliable half: sendBeacon is delivered even as the
   tab is closing, which fetch is not. The repeating beat is the backstop for a
   browser that was killed outright and never got to say anything.

   BEAT is deliberately shorter than the program's quiet limit by a long way —
   a hidden tab is throttled to about one timer a minute, and being throttled
   must never look like being gone. */
const BEAT = 10000;

function keepAlive() {
  if (S.beatTimer) return;
  const beat = () => { fetch('/api/alive', { method: 'POST' }).catch(() => {}); };
  beat();
  S.beatTimer = setInterval(beat, BEAT);
  // pagehide covers closing the tab, closing the window and navigating away,
  // in every browser that matters. It also fires on a refresh, which is why
  // the program treats this as "start a short clock", not "stop now".
  addEventListener('pagehide', () => {
    try { navigator.sendBeacon('/api/leaving'); } catch (e) { /* going anyway */ }
  });
}

/* Stop the program, and say so, rather than leaving a dead tab that looks
   exactly like a working one. */
function closeRipple() {
  if (S.beatTimer) { clearInterval(S.beatTimer); S.beatTimer = null; }
  fetch('/api/quit', { method: 'POST' }).catch(() => {});
  // The reply may never arrive — the server is shutting down as it answers —
  // so the screen changes on the way out rather than waiting for it.
  setTimeout(() => {
    document.body.innerHTML = '';
    document.body.append(el('div', { className: 'empty', style: 'padding-top:120px' },
      el('b', { textContent: 'Ripple has stopped.' }),
      el('div', { className: 'small muted', style: 'margin-top:10px;line-height:1.6',
        textContent: 'You can close this tab. The program is no longer running, so its folder '
          + 'can be moved or deleted now.' }),
      el('div', { className: 'small faint', style: 'margin-top:10px',
        textContent: 'To use Ripple again, double-click Ripple Offline.exe.' })));
  }, 250);
}

// ── what step 3 says when the folder is not there ─────────────────────────
/* Online this reports a connection that failed. Offline there is no connection
   to fail — but a folder chosen last week can be moved, renamed or deleted, and
   that is an ordinary Tuesday on a locked-down machine, not an exception. */
function repoAlert(h) {
  const f = h.folder;
  if (!f || f.ok) return null;
  const box = el('div', { className: 'note bad', style: 'margin-bottom:18px' },
    el('b', { textContent: f.state === 'unset' ? 'No repository folder chosen yet. ' : 'Nothing can be scanned. ' }),
    f.message);
  const go = el('button', { className: 'ghost sm', textContent: 'Choose the folder', style: 'margin-top:12px' });
  go.onclick = () => { S.view = 'settings'; render(); };
  box.append(el('div', {}, go));
  return box;
}

// ── settings ──────────────────────────────────────────────────────────────
function offState() {
  const h = S.health;
  if (!S.off) {
    S.off = {
      path: (h && h.repo.path) || '',
      dialect: (h && h.sqlDialectId) || '',
      hops: (h && h.maxHops) || 0,
      check: null,        // the answer to "check this folder", before saving
      msg: null,          // the answer to the last save
      working: '',        // which button is busy: 'check', 'browse' or 'save'
    };
  }
  // The published-table list lives in the shared control's own state, so that
  // one box and one reading of it are used by both editions.
  productionState();
  return S.off;
}

/* Slow work here has to be visible on the button that started it. The header
   spinner is across the screen from whatever was pressed, and a folder being
   read is the one moment on this screen where nothing happens for a while and
   then several numbers change at once. */
function offRun(which, fn) {
  const o = offState();
  o.working = which;
  run(async () => {
    try { await fn(); } finally { o.working = ''; }
  }, which === 'save' ? 'Reading every file in the folder…'
    : which === 'check' ? 'Counting what is in the folder…'
    : 'Waiting for the folder picker…');
}

function settingsView(root) {
  const h = S.health;
  const o = offState();
  // The shared header says "Connections and health", and offline there are no
  // connections to have.
  setHeader('Settings & checks', h.configured
    ? 'What Ripple reads, and where it keeps things'
    : 'Choose the folder to scan');
  root.append(el('div', { className: 'head' }, el('div', {},
    el('h2', { textContent: 'Settings & checks' }),
    el('p', { textContent: h.configured
      ? 'What Ripple is reading, and where it keeps what it saves.'
      : 'Two things to choose before the first scan.' }))));

  if (!h.configured) {
    root.append(el('div', { className: 'note info', style: 'margin-bottom:18px' },
      why(el('b', { textContent: 'Choose the repository folder to get started.' }),
        'what choosing a folder does',
        'Ripple reads a copy of your code that is already on this machine. It downloads '
        + 'nothing and it never writes to your code. Point it at the folder, check the SQL '
        + 'type underneath, and save.')));
  }

  const grid = el('div', { className: 'grid2 even' });
  const prod = el('div', { style: 'margin-top:18px' },
    productionCard({ persistNote: '' }),
    el('div', { className: 'note warn', style: 'margin-top:14px' },
      why(el('b', { textContent: 'Get this wrong and a real impact reads as a clean result.' }),
        'what the published-table list decides',
        'A finding only counts as production impact when the table it ends at is on this list. '
        + 'Nothing is hidden either way — every table the change reaches is still listed — but '
        + 'the headline, the risk level and the drafted reply all follow this list.')));
  grid.append(el('div', {}, folderCard(h, o), dialectCard(h, o), prod, saveRow(h, o)),
              el('div', { className: 'rail' }, whereCard(h), guardCard(), factsCard(h),
                 buildCard(h), closeCard()));
  root.append(grid);
}

/* The way out. There is no console window and no application window, so
   without this the only way to stop Ripple is Task Manager — and until it is
   stopped, its own folder cannot be deleted or moved. */
function closeCard() {
  const card = el('div', { className: 'card pad lg', style: 'margin-top:18px' });
  card.append(why(
    el('span', { className: 'lbl', textContent: 'Finished with Ripple' }),
    'closing the tab is not closing Ripple',
    'Ripple is a small program running on this machine, not a website. Closing this tab leaves '
    + 'it running, and while it runs its own folder cannot be moved or deleted.'));
  const stop = el('button', { className: 'ghost', style: 'margin-top:12px',
    textContent: 'Close Ripple' });
  stop.onclick = () => closeRipple();
  card.append(stop);
  card.append(el('div', { className: 'small faint', style: 'margin-top:10px' },
    why(el('span', { textContent: 'It also closes itself.' }),
      'when Ripple closes itself',
      'A few minutes after the last tab is closed, so a forgotten one is not left holding the '
      + 'folder open.')));
  return card;
}

/* The folder to scan. Typing a path always works; the picker is only offered
   when this machine actually has one to open. */
function folderCard(h, o) {
  const card = el('div', { className: 'card pad lg' });
  card.append(why(
    el('span', { className: 'lbl', textContent: 'Repository folder' }),
    'what Ripple does with this folder',
    'The folder holding the code you want searched. Ripple reads every file in it and never '
    + 'writes to any of them.'));

  const inp = el('input', { type: 'text', className: 'mono', value: o.path,
    placeholder: 'D:\\code\\our-pipelines', style: 'margin-top:12px;padding:12px 14px' });
  inp.oninput = () => { o.path = inp.value; o.check = null; };
  inp.onkeydown = (e) => { if (e.key === 'Enter') checkFolder(); };
  card.append(inp);

  const row = el('div', { className: 'foot', style: 'margin-top:14px' });
  if (h.canBrowse) {
    const browse = el('button', { className: 'ghost',
      textContent: o.working === 'browse' ? 'Waiting for the picker…' : 'Browse…' });
    browse.disabled = !!o.working;
    browse.onclick = () => browseForFolder();
    row.append(browse);
  }
  const check = el('button', { className: 'ghost',
    textContent: o.working === 'check' ? 'Counting the files…' : 'Check this folder' });
  check.disabled = !!o.working;
  check.onclick = () => checkFolder();
  row.append(check);
  if (o.working === 'check') {
    row.append(el('span', { className: 'spin' }),
      el('span', { className: 'small muted', textContent: 'Walking the folder. A large one takes a moment.' }));
  }
  card.append(row);

  // A note with nothing in it is an empty coloured box, which reads as
  // something that failed to load rather than as an answer.
  if (o.check && o.check.message) {
    card.append(el('div', { className: 'note ' + (o.check.ok ? 'good' : 'bad'), style: 'margin-top:14px' },
      o.check.message));
  }
  return card;
}

/* The dialect. This is the setting that looks cosmetic and is not. */
function dialectCard(h, o) {
  const card = el('div', { className: 'card pad lg', style: 'margin-top:18px' });
  card.append(el('span', { className: 'lbl', textContent: 'How the SQL is read' }));
  const sel = el('select', { className: 'statussel', style: 'width:100%;padding:11px 12px;margin-top:12px' });
  (h.dialects || []).forEach(d => sel.append(el('option', {
    value: d.id, textContent: d.label, selected: d.id === o.dialect })));
  // NOT called `why`. That is the name of the shared information-button helper,
  // and a local const of the same name shadows it for the whole function -- so
  // calling it here would throw instead of drawing a button.
  const note = el('div', { className: 'small faint', style: 'margin-top:6px;line-height:1.55' });
  const showNote = () => {
    const d = (h.dialects || []).find(x => x.id === sel.value);
    note.textContent = d ? d.note : '';
  };
  sel.onchange = () => { o.dialect = sel.value; showNote(); };
  showNote();
  card.append(sel, note);
  card.append(el('div', { className: 'note warn', style: 'margin-top:14px' },
    why(el('b', { textContent: 'This matters more than it looks.' }),
      'why the dialect changes the answer',
      'Every warehouse writes SQL a little differently. Choose the wrong one and Ripple cannot '
      + 'read some of your files — and a file it cannot read is a file it cannot warn you '
      + 'about. That does not give you a vaguer answer. It gives you the wrong one. If you are '
      + 'not sure which to pick, ask whoever runs the pipeline.')));
  return card;
}

function saveRow(h, o) {
  const row = el('div', { className: 'card pad lg foot', style: 'margin-top:18px' });
  const busy = o.working === 'save';
  const save = el('button', { className: 'pri',
    textContent: busy ? 'Reading the folder…'
      : h.configured ? 'Save and read the repository again' : 'Save and read the repository' });
  save.disabled = !!o.working;
  save.onclick = () => saveOfflineSettings();
  row.append(save);
  if (busy) {
    // Reading a real repository is thousands of files. Without this the screen
    // sits still and then several numbers change on their own, which reads as
    // the page having done something by itself.
    row.append(el('span', { className: 'spin' }),
      el('span', { className: 'small muted',
        textContent: 'Reading every file and parsing the SQL — the counts on the right '
          + 'update when it finishes.' }));
  } else {
    row.append(el('span', { className: 'small faint',
      textContent: 'Saved to the settings file beside Ripple, so it is remembered next time.' }));
  }
  const box = el('div', {}, row);
  if (o.msg) {
    box.append(el('div', { className: 'note ' + (o.msg.ok ? 'good' : 'bad'), style: 'margin-top:14px' },
      o.msg.text));
  }
  return box;
}

/* Where the two files Ripple writes actually are. Nobody should have to guess,
   and "somewhere in your user profile" is not an answer. */
function whereCard(h) {
  const card = el('div', { className: 'card pad' });
  card.append(el('span', { className: 'lbl', textContent: 'What Ripple writes' }));
  [['Settings', h.settingsFile], ['Saved analyses', h.historyFile]].forEach(([k, v]) =>
    card.append(el('div', { style: 'padding:9px 0;border-top:1px solid var(--hair);margin-top:8px' },
      el('div', { className: 'small muted', textContent: k }),
      el('div', { className: 'small mono', textContent: v,
        style: 'margin-top:3px;font-weight:600;word-break:break-all' }))));
  card.append(el('div', { className: 'small faint', style: 'margin-top:12px' },
    why(el('span', { textContent: 'Both sit in the folder you copied across.' }),
      'what moving the folder takes with it',
      'Move that folder to another machine and your settings and saved analyses go with it. '
      + 'Delete it and Ripple is gone.')));
  const sync = h.syncedFolder;
  if (sync && sync.synced) {
    // Keeping everything beside the executable is what makes this copy portable.
    // In an office where sync is on for everybody it also means the folder is
    // being uploaded, and that is worth one plain paragraph rather than a
    // surprise. Neither point is a reason to stop; both are a reason to say so.
    card.append(el('div', { className: 'note warn', style: 'margin-top:14px' },
      el('b', { style: 'display:block', textContent: `${sync.client} is syncing this folder` }),
      why(el('div', { style: 'margin-top:6px;line-height:1.55', textContent:
          'Everything in this folder is being uploaded to your company\u2019s cloud — including '
          + 'the Ripple program itself, about 44 MB across roughly 1,770 files, and not '
          + 'signed by a known publisher.' }),
        'what a synced folder means for Ripple',
        'Your saved analyses live in a file inside this folder, and a sync tool copies files '
        + 'whenever it likes. If Ripple ever says it could not save an analysis, that is the '
        + 'usual reason, and trying again normally works.'),
      el('div', { className: 'small', style: 'margin-top:8px;line-height:1.55', textContent:
        'If you would rather neither happened, close Ripple and move this folder somewhere '
        + 'that is not synced — C:\\Ripple, for example — then start it again from there. '
        + 'Your settings and saved analyses move with it.' })));
  }
  return card;
}

/* Whether this copy really is sealed off, asked of the running program rather
   than asserted on a screen. */
function guardCard() {
  const card = el('div', { className: 'card pad' });
  card.append(el('span', { className: 'lbl', textContent: 'Nothing leaves this machine' }));
  const state = el('div', { style: 'margin-top:12px' },
    el('span', { className: 'small muted', textContent: 'Checking…' }));
  card.append(state);
  card.append(el('div', { className: 'small faint', style: 'margin-top:12px' },
    why(el('span', { textContent: 'No connection to anywhere, and no AI.' }),
      'what this copy can and cannot do',
      'There is nowhere here to type a key or an address. Ripple reads the folder above and '
      + 'writes the two files listed.')));
  api('/api/offline-check').then(g => {
    state.innerHTML = '';
    if (g.guardInstalled) {
      state.append(el('div', { className: 'note good' },
        why(el('b', { textContent: 'Outbound connections are blocked.' }),
          'how the block behaves',
          'If anything in this program tried to reach the internet it would fail immediately. '
          + 'It would not quietly succeed just because this machine happens to be online.')));
    } else {
      state.append(el('div', { className: 'note warn' },
        why(el('b', { textContent: 'The block is not switched on in this copy.' }),
          'what an unenforced block means',
          'Ripple still has nothing in it that reaches out, but that is not being enforced in '
          + 'this copy. Start Ripple the normal way to switch it back on.')));
    }
    if (g.attempts && g.attempts.length) {
      state.append(el('div', { className: 'note bad', style: 'margin-top:10px' },
        el('b', { textContent: `${g.attempts.length} attempt${g.attempts.length === 1 ? '' : 's'} to reach the network were refused: ` }),
        g.attempts.slice(0, 5).join(', ')));
    }
  }).catch(() => {
    state.innerHTML = '';
    state.append(el('div', { className: 'note warn', textContent: 'Could not ask this copy whether the block is on.' }));
  });
  return card;
}

function factsCard(h) {
  const card = el('div', { className: 'card pad' });
  card.append(el('span', { className: 'lbl', textContent: 'What was read' }));
  // "Files indexed 3, files unreadable 0" is the line somebody reads to decide
  // whether the whole folder was covered, and on its own it answers yes. The
  // row below it only appears when the answer is no, and then it has to appear,
  // because this is the panel that gets believed.
  const neverOpened = (h.repo.heldOnline || 0) + (h.repo.pathTooLong || 0);
  [['Files indexed', String(h.repo.files)],
   ['Statements understood', String(h.repo.statements)],
   ['Files unreadable', String(h.repo.unreadable)],
   ...(neverOpened ? [['Files never opened', String(neverOpened)]] : []),
   ['Tables found', String(h.catalog.tables)],
   ['SQL read as', h.sqlDialect],
   ['Renames followed', `${h.maxHops} hops`],
   ['Tables you publish', h.production || 'not set']].forEach(([k, v]) =>
    card.append(el('div', { className: 'factrow' },
      el('span', { className: 'small muted', textContent: k }),
      el('span', { className: 'small', textContent: v }))));
  return card;
}

// ── the three things those buttons do ─────────────────────────────────────
function checkFolder() {
  const o = offState();
  offRun('check', async () => {
    o.check = await api('/api/settings/check', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: o.path.trim() }),
    });
  });
}

function browseForFolder() {
  const o = offState();
  offRun('browse', async () => {
    const out = await api('/api/settings/browse', { method: 'POST' });
    if (out.path) { o.path = out.path; o.check = null; o.msg = null; }
  });
}

function saveOfflineSettings() {
  const o = offState();
  const p = productionState();
  offRun('save', async () => {
    try {
      S.health = await api('/api/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repoPath: o.path.trim(), sqlDialect: o.dialect,
                               maxHops: o.hops, prodTables: p.text }),
      });
      // The box keeps whatever was pasted, so it can be edited rather than
      // handed back a tidied version of somebody's list. An empty box is the
      // exception: the server falls back to the default rather than treating
      // no table as published, and the box has to show what is really in force.
      p.text = S.health.productionRule?.text ?? p.text;
      p.report = null; p.loaded = false;
      // The saved message below says what happened. Leaving the "check this
      // folder" answer up as well puts an empty green box on screen, because
      // once it has been saved there is nothing left for it to report.
      o.check = null;
      o.msg = { ok: true, text: `Saved. ${S.health.repo.files} file`
        + `${S.health.repo.files === 1 ? '' : 's'} indexed from ${S.health.repo.label}, `
        + `read as ${S.health.sqlDialect}. ${S.health.repo.statements} statement`
        + `${S.health.repo.statements === 1 ? '' : 's'} understood, ${S.health.repo.unreadable} file`
        + `${S.health.repo.unreadable === 1 ? '' : 's'} could not be read. `
        + `Published tables: ${S.health.production}.` };
      // Whatever was scanned before came from a different folder or a different
      // dialect, so it is dropped rather than left on screen looking current.
      S.scan = null; S.summary = null; S.reply = null;
    } catch (e) {
      o.msg = { ok: false, text: e.message };
    }
  });
}
