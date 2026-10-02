-- Restore the signup path, matching what production actually has.
--
-- Production carries TWO functions: handle_user_create (insert on signup) and
-- handle_user_update_phone_avatar (sync phone/avatar afterwards). The export in
-- functions.sql gave BOTH the name handle_user_create, so the second overwrote the
-- first and signup silently stopped inserting. Splitting them back apart is what
-- makes this migration match production rather than a merged invention.
--
-- The trigger was also missing: it lived in the Supabase dashboard, so a project
-- built purely from migrations had none. A user could sign in with no
-- public.users row, and /users/info/me would 404 for them forever.
--
-- Metadata keys are the ones the app really sends — see authSignup() in
-- frontend/src/apis/auth/apiAuth.js: { fullname, is_seller }.

create or replace function public.handle_user_create()
returns trigger as
$$
begin
    if not exists (select 1 from public.users where id = new.id) then
        insert into public.users (
          id, email, name, is_seller, created_at, updated_at
        ) values (
            new.id,
            new.email,
            new.raw_user_meta_data->>'fullname',
            coalesce((new.raw_user_meta_data->>'is_seller')::boolean, false),
            new.created_at,
            new.updated_at
        );
    end if;
    return new;
end;
$$
language plpgsql security definer;

-- security definer runs as the owner, so pin the search_path: without it
-- "public.users" would resolve against whatever the caller has set.
alter function public.handle_user_create() set search_path = public;

-- The second body from functions.sql, under the name production gives it.
create or replace function public.handle_user_update_phone_avatar()
returns trigger as
$$
begin
    update public.users
    set
        avatar_url = new.raw_user_meta_data->>'avatar_url',
        phone = new.phone,
        updated_at = new.updated_at
    where id = new.id;
    return new;
end;
$$
language plpgsql security definer;

alter function public.handle_user_update_phone_avatar() set search_path = public;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_user_create();

-- NOT created here: a trigger for handle_user_update_phone_avatar. Production
-- lists only on_auth_user_created on auth.users, so either that function is
-- unbound there too, or the binding is elsewhere. Guessing would put dev out of
-- step with prod in a different way — confirm on the dashboard first.
