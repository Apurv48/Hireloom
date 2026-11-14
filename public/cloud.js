/* Hireloom cloud layer: Supabase Auth, per-user workspace sync and private CV storage.
   Stays disabled (the app runs in local demo mode) until public/config.js has a project URL and anon key. */
(function () {
  const cfg = window.HIRELOOM_SUPABASE || {};
  const lib = window.supabase;
  if (!(cfg.url && cfg.anonKey && lib && typeof lib.createClient === 'function')) {
    window.HireloomCloud = { enabled: false };
    return;
  }

  const sb = lib.createClient(cfg.url, cfg.anonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });
  const TABLE = 'user_data';
  const BUCKET = 'cvs';
  const MAX_CV_BYTES = 1024 * 1024; // keep in sync with server.py and supabase/schema.sql
  const MIME = {
    pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  };
  const cloud = { enabled: true, MAX_CV_BYTES, onSyncError: null };
  let timer = null;
  let builder = null;
  let lastErrorAt = 0;

  function friendly(error, fallback) {
    const text = String((error && error.message) || '');
    if (/invalid login credentials/i.test(text)) return 'That email and password do not match.';
    if (/email not confirmed/i.test(text)) return 'Confirm your email address first: check your inbox for the link.';
    if (/already registered|already been registered/i.test(text)) return 'An account for this email already exists. Log in instead.';
    if (/rate limit|too many/i.test(text)) return 'Too many attempts. Wait a few minutes and try again.';
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

  // Local scope only, so signing out here does not sign the user out of their other devices.
  cloud.signOut = async () => { try { await sb.auth.signOut({ scope: 'local' }); } catch (error) { /* already signed out */ } };

  cloud.pull = async () => {
    const user = await cloud.getUser();
    if (!user) throw new Error('Not signed in');
    const { data, error } = await sb.from(TABLE).select('state').eq('user_id', user.id).maybeSingle();
    if (error) throw error;
    return data ? data.state : null;
  };

  cloud.flush = async () => {
    if (timer) clearTimeout(timer);
    timer = null;
    const build = builder;
    builder = null;
    if (!build) return;
    try {
      const user = await cloud.getUser();
      if (!user) return;
      const { error } = await sb.from(TABLE).upsert({ user_id: user.id, state: build(), updated_at: new Date().toISOString() });
      if (error) throw error;
    } catch (error) {
      console.warn('Hireloom sync failed:', error && error.message);
      if (cloud.onSyncError && Date.now() - lastErrorAt > 60000) { lastErrorAt = Date.now(); cloud.onSyncError(error); }
    }
  };

  // Saves are debounced: many quick edits become one write.
  cloud.queuePush = (build) => {
    builder = build;
    if (timer) clearTimeout(timer);
    timer = setTimeout(cloud.flush, 2000);
  };
  window.addEventListener('pagehide', () => { cloud.flush(); });
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') cloud.flush(); });

  // One CV per user: a new upload replaces the previous file.
  cloud.uploadCv = async (file) => {
    const user = await cloud.getUser();
    if (!user) throw new Error('Not signed in');
    const ext = extensionOf(file.name);
    if (!MIME[ext]) throw new Error('Choose a PDF or DOCX CV.');
    if (file.size > MAX_CV_BYTES) throw new Error('The CV must be 1 MB or smaller.');
    const path = `${user.id}/cv.${ext}`;
    const { error } = await sb.storage.from(BUCKET).upload(path, file, { upsert: true, contentType: MIME[ext] });
    if (error) throw error;
    const other = ext === 'pdf' ? 'docx' : 'pdf';
    await sb.storage.from(BUCKET).remove([`${user.id}/cv.${other}`]).catch(() => {});
    return path;
  };

  cloud.signedCvUrl = async (path, downloadName) => {
    const { data, error } = await sb.storage.from(BUCKET).createSignedUrl(path, 60, { download: downloadName || true });
    if (error) throw error;
    return data.signedUrl;
  };

  cloud.deleteAccount = async () => {
    if (timer) clearTimeout(timer);
    timer = null;
    builder = null;
    const user = await cloud.getUser();
    if (!user) throw new Error('Not signed in');
    const { data: files } = await sb.storage.from(BUCKET).list(user.id);
    if (files && files.length) {
      const { error } = await sb.storage.from(BUCKET).remove(files.map((file) => `${user.id}/${file.name}`));
      if (error) throw error;
    }
    const { error } = await sb.rpc('delete_my_account');
    if (error) throw error;
    await cloud.signOut();
  };

  window.HireloomCloud = cloud;
})();
