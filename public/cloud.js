/* Hireloom cloud layer: Supabase Auth, per-user workspace sync and private CV storage.
   Stays disabled (the app runs in local demo mode) until public/config.js has a project URL and anon key. */
(function () {
  const cfg = window.HIRELOOM_SUPABASE || {};
  const lib = window.supabase;
  if (!(cfg.url && cfg.anonKey && lib && typeof lib.createClient === 'function')) {
    window.HireloomCloud = { enabled: false, unavailable: Boolean(cfg.url || cfg.anonKey) };
    return;
  }

  let lifecycleKeepalive = false;
  const nativeFetch = typeof window.fetch === 'function' ? window.fetch.bind(window) : null;
  const resilientFetch = nativeFetch ? (input, init = {}) => {
    const bodyBytes = typeof init.body === 'string' ? new TextEncoder().encode(init.body).length : 0;
    return nativeFetch(input, { ...init, keepalive: lifecycleKeepalive && bodyBytes <= 60000 });
  } : undefined;
  const options = { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false } };
  if (resilientFetch) options.global = { fetch: resilientFetch };
  const sb = lib.createClient(cfg.url, cfg.anonKey, options);
  const TABLE = 'user_data';
  const BUCKET = 'cvs';
  const MAX_CV_BYTES = 1024 * 1024; // keep in sync with server.py and supabase/schema.sql
  const PENDING_PREFIX = 'hireloom-cloud-pending:';
  const MIME = { pdf: 'application/pdf' }; // CV uploads are PDF only
  const cloud = { enabled: true, MAX_CV_BYTES, onSyncError: null };
  let timer = null;
  let pending = null;
  let writing = null;
  let revision = null;
  let closing = false;
  let lastErrorAt = 0;
  function pendingKey(owner) { return `${PENDING_PREFIX}${owner}`; }
  function savePending(entry) {
    try {
      localStorage.setItem(pendingKey(entry.owner), JSON.stringify(entry));
    } catch {
      if (cloud.onSyncError) cloud.onSyncError(new Error('Browser storage is unavailable. Keep this tab open until your account save finishes.'));
    }
  }
  function loadPending(owner) {
    try {
      const entry = JSON.parse(localStorage.getItem(pendingKey(owner)) || 'null');
      return entry && entry.owner === owner && entry.state ? entry : null;
    } catch (error) { return null; }
  }
  function clearPending(entry) {
    try {
      const saved = loadPending(entry.owner);
      if (!saved || saved.savedAt === entry.savedAt) localStorage.removeItem(pendingKey(entry.owner));
    } catch (error) { /* storage unavailable */ }
  }
  sb.auth.onAuthStateChange((_event, session) => {
    const owner = session?.user?.id || null;
    if (pending && pending.owner !== owner) pending = null;
    if (cloud.onUserChange) cloud.onUserChange(owner);
  });

  function friendly(error, fallback) {
    const text = String((error && error.message) || '');
    if (/invalid login credentials/i.test(text)) return 'That email and password do not match.';
    if (/email not confirmed/i.test(text)) return 'Confirm your email address first: check your inbox for the link.';
    if (/already registered|already been registered/i.test(text)) return 'An account for this email already exists. Log in instead.';
    if (/same as the old|different from the old/i.test(text)) return 'Choose a new password that is different from your current one.';
    if (/session missing/i.test(text)) return 'Your reset session has expired. Request a new code.';
    if (/password.*(weak|at least|characters)|weak password/i.test(text)) return 'Choose a stronger password of at least 8 characters.';
    if (/rate limit|too many|security purposes/i.test(text)) return 'Too many attempts. Wait a few minutes and try again.';
    if (/failed to fetch|network/i.test(text)) return 'Could not reach Hireloom. Check your connection and try again.';
    return text || fallback;
  }
  const toUser = (user) => user ? { id: user.id, email: user.email || '', name: (user.user_metadata && user.user_metadata.name) || '' } : null;
  const extensionOf = (name) => String(name || '').split('.').pop().toLowerCase();

  cloud.getUser = async () => {
    const { data } = await sb.auth.getSession();
    return toUser(data && data.session && data.session.user);
  };

  cloud.signIn = async (email, password) => {
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    return error ? { error: friendly(error, 'Could not log in.') } : { user: toUser(data.user) };
  };

  cloud.signUp = async (email, password, name) => {
    const { data, error } = await sb.auth.signUp({ email, password, options: { data: { name } } });
    if (error) return { error: friendly(error, 'Could not create the account.') };
    // Supabase returns an obfuscated user with no identities when the email is already registered.
    if (data.user && Array.isArray(data.user.identities) && data.user.identities.length === 0) {
      return { error: 'An account for this email already exists. Log in instead.' };
    }
    return { user: toUser(data.user), signedIn: !!data.session };
  };

  // Password reset by one-time code. Supabase emails a numeric code (the "Reset Password" email template must
  // contain {{ .Token }}, see README); the user types it here, and a correct code opens a short session
  // that is used only to save the new password.
  const RESET_FLAG = 'hireloom-reset-pending';
  const setFlag = (on) => { try { if (on) localStorage.setItem(RESET_FLAG, '1'); else localStorage.removeItem(RESET_FLAG); } catch (error) { /* storage unavailable */ } };
  const hasFlag = () => { try { return localStorage.getItem(RESET_FLAG) === '1'; } catch (error) { return false; } };

  cloud.requestResetCode = async (email) => {
    const { error } = await sb.auth.resetPasswordForEmail(email);
    return error ? { error: friendly(error, 'Could not send the code. Try again in a few minutes.') } : { ok: true };
  };

  cloud.verifyResetCode = async (email, code) => {
    const { error } = await sb.auth.verifyOtp({ email, token: code, type: 'recovery' });
    if (error) return { error: /rate limit|too many/i.test(error.message || '') ? friendly(error) : 'That code is incorrect or has expired. Check it, or request a new code.' };
    setFlag(true);
    return { ok: true };
  };

  // True when a correct code was entered but the new password was never saved (for example the tab was closed),
  // so the app asks for the new password instead of silently signing the user in.
  cloud.resetPending = async () => {
    if (!hasFlag()) return false;
    const user = await cloud.getUser();
    if (!user) setFlag(false);
    return !!user;
  };

  cloud.updatePassword = async (password) => {
    const { data, error } = await sb.auth.updateUser({ password });
    if (error) return { error: friendly(error, 'Could not update the password.') };
    setFlag(false);
    return { user: toUser(data && data.user) };
  };

  // Local scope only, so signing out here does not sign the user out of their other devices.
  cloud.signOut = async () => {
    closing = true;
    try {
      await cloud.flush().catch(error => {
        if (pending && loadPending(pending.owner)?.savedAt !== pending.savedAt) throw error;
      });
    } finally { closing = false; }
    const { error } = await sb.auth.signOut({ scope: 'local' });
    if (error) throw error;
    setFlag(false);
  };

  cloud.pull = async (owner) => {
    const user = await cloud.getUser();
    if (!user || user.id !== owner) throw new Error('Account changed. Please sign in again.');
    const { data, error } = await sb.from(TABLE).select('state,updated_at').eq('user_id', user.id).maybeSingle();
    if (error) throw error;
    revision = data?.updated_at || null;
    const local = loadPending(owner);
    if (local) {
      // Device clocks can differ. Only the revision identifies the row these edits started from.
      if (data?.state && local.base !== revision) {
        if (pending?.owner === owner) pending = null;
        localStorage.setItem(pendingKey(owner)+':conflict', JSON.stringify(local.state));
        clearPending(local);
        return data.state;
      }
      pending = local;
      setTimeout(backgroundSave, 0);
      return local.state;
    }
    return data ? data.state : null;
  };

  cloud.flush = async () => {
    clearTimeout(timer);
    timer = null;
    while (writing || pending) {
      if (writing) { await writing; continue; }
      const operation = (async () => {
        while (pending) {
          const entry = pending;
          const user = await cloud.getUser();
          if (!user || user.id !== entry.owner) throw new Error('Workspace owner changed');
          const stamp = new Date(Math.max(entry.savedAt, (Date.parse(revision)||0)+1)).toISOString();
          const row = {user_id:entry.owner, state:entry.state, updated_at:stamp};
          const table = sb.from(TABLE);
          const result = revision
            ? await table.update(row).eq('user_id',entry.owner).eq('updated_at',revision).select('updated_at').maybeSingle()
            : await table.insert(row).select('updated_at').maybeSingle();
          if (result.error && result.error.code !== '23505') throw result.error;
          if (!result.data) throw Error('Another session saved changes. Export your edits, then reload the workspace.');
          revision = result.data.updated_at;
          if (pending && pending !== entry) { pending.base=revision; savePending(pending); }
          if (pending === entry) { pending = null; clearPending(entry); }
        }
      })();
      writing = operation;
      try { await operation; }
      finally { if (writing === operation) writing = null; }
    }
  };

  function backgroundSave() {
    cloud.flush().catch(error => {
      if (cloud.onSyncError && Date.now() - lastErrorAt > 60000) {
        lastErrorAt = Date.now();
        cloud.onSyncError(error);
      }
    });
  }
  cloud.queuePush = (build, owner) => {
    if (closing) return;
    pending = { owner, state: structuredClone(build()), base: revision, savedAt: Date.now() };
    savePending(pending);
    if (timer) clearTimeout(timer);
    timer = setTimeout(backgroundSave, 300);
  };
  window.addEventListener('online', backgroundSave);
  window.addEventListener('pagehide', () => { lifecycleKeepalive = true; backgroundSave(); });
  document.addEventListener('visibilitychange', () => {
    lifecycleKeepalive = document.visibilityState === 'hidden';
    if (lifecycleKeepalive) backgroundSave();
  });

  // One CV per user: a new upload replaces the previous file.
  cloud.uploadCv = async (file, owner) => {
    const ext = extensionOf(file.name);
    if (!MIME[ext]) throw new Error('Only PDF CVs are accepted. Save your CV as a PDF and upload that file.');
    if (file.size > MAX_CV_BYTES) throw new Error('The CV must be 1 MB or smaller.');
    const signature = new Uint8Array(await file.slice(0, 5).arrayBuffer());
    if (String.fromCharCode(...signature) !== '%PDF-') throw new Error('This file is not a real PDF. Save it as a PDF and try again.');
    const {data} = await sb.auth.getSession();
    const session = data?.session;
    if (!session?.access_token || session.user?.id !== owner) throw new Error('Account changed. Please sign in again.');
    const path = `${owner}/cv.${ext}`;
    const response = await window.fetch('/api/store-cv',{method:'POST',headers:{Authorization:'Bearer '+session.access_token,'Content-Type':'application/pdf'},body:file});
    if (!response.ok) throw Error((await response.json()).error || 'CV storage failed.');
    // Remove a CV stored earlier in the old DOCX format so only one file is kept.
    await sb.storage.from(BUCKET).remove([`${owner}/cv.docx`]).catch(() => {});
    return path;
  };

  cloud.signedCvUrl = async (path, downloadName) => {
    const { data, error } = await sb.storage.from(BUCKET).createSignedUrl(path, 60, { download: downloadName || true });
    if (error) throw error;
    return data.signedUrl;
  };

  async function removeAccount(owner, email) {
    if (timer) clearTimeout(timer);
    timer = null;
    if (writing) await writing.catch(()=>{});
    const user = await cloud.getUser();
    if (!user || user.id !== owner) throw new Error('Account changed. Please sign in again.');
    if (!email || user.email.trim().toLowerCase() !== email) throw new Error('Enter the email address you use to sign in.');
    const { data: files, error: listError } = await sb.storage.from(BUCKET).list(user.id);
    if (listError) throw listError;
    const currentUser = await cloud.getUser();
    if (currentUser?.id !== owner) throw new Error('Account changed. Please sign in again.');
    const { error } = await sb.rpc('delete_my_account');
    if (error) throw error;
    // The signed access token still authorizes this account's private folder
    // until it expires. Clean up after Auth deletion succeeds.
    let cleanupPending = false;
    if (files?.length) {
      const paths = files.map(file => `${owner}/${file.name}`);
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          const result = await sb.storage.from(BUCKET).remove(paths);
          cleanupPending = !!result.error;
        } catch { cleanupPending = true; }
        if (!cleanupPending) break;
      }
    }
    pending = null;
    try {
      localStorage.removeItem(pendingKey(user.id));
      localStorage.removeItem(pendingKey(user.id)+':conflict');
    } catch { /* storage unavailable */ }
    await cloud.signOut().catch(() => {});
    return {cleanupPending};
  }
  cloud.deleteAccount = async (owner, email) => {
    closing=true;
    try { return await removeAccount(owner, email); } finally { closing=false; }
  };
  cloud.conflictCopy = owner => localStorage.getItem(pendingKey(owner)+':conflict');

  window.HireloomCloud = cloud;
})();
