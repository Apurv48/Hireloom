-- Hireloom Supabase setup. Paste this whole file into Supabase -> SQL Editor -> Run.
-- It is safe to run more than once.

-- 1) One row per user holding their workspace (profile, chats, tracker, settings).
create table if not exists public.user_data (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  state      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint user_data_state_size check (octet_length(state::text) < 2000000)
);

alter table public.user_data enable row level security;

drop policy if exists "user_data select own" on public.user_data;
drop policy if exists "user_data insert own" on public.user_data;
drop policy if exists "user_data update own" on public.user_data;
drop policy if exists "user_data delete own" on public.user_data;

create policy "user_data select own" on public.user_data
  for select to authenticated using (auth.uid() = user_id);
create policy "user_data insert own" on public.user_data
  for insert to authenticated with check (auth.uid() = user_id);
create policy "user_data update own" on public.user_data
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "user_data delete own" on public.user_data
  for delete to authenticated using (auth.uid() = user_id);

-- 2) Private bucket for CVs: max 1 MB per file, PDF only, one folder per user.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'cvs', 'cvs', false, 1048576,
  array['application/pdf']
)
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "cvs select own" on storage.objects;
drop policy if exists "cvs insert own" on storage.objects;
drop policy if exists "cvs update own" on storage.objects;
drop policy if exists "cvs delete own" on storage.objects;

create policy "cvs select own" on storage.objects
  for select to authenticated
  using (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "cvs insert own" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "cvs update own" on storage.objects
  for update to authenticated
  using (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "cvs delete own" on storage.objects
  for delete to authenticated
  using (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);

-- 3) Lets a signed-in user delete their own account (their data row is removed by the cascade above).
--    The app deletes the user's stored CV files through the Storage API first.
create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'Not signed in';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
