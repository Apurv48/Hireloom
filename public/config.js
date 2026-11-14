// Supabase settings. Leave both values empty to run Hireloom in local demo mode.
// Find them in Supabase -> Project Settings -> API. The anon key is meant to be public;
// the Row Level Security rules in supabase/schema.sql are what protect each user's data.
window.HIRELOOM_SUPABASE = {
  url: '',      // e.g. 'https://abcdefghijkl.supabase.co'
  anonKey: ''   // the "anon public" key
};
