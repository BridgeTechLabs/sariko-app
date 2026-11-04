-- ============================================================
-- Admin users get push notifications (docs/dev/admin-push/, Q1).
-- push_subscriptions.app tells which web app subscribed: the marketplace (buyers / sellers)
-- or the admin panel. Marketplace pushes read app = 'marketplace' only, admin pushes
-- (new complaint, order about to auto-cancel, delivery failed) read app = 'admin' only, so a
-- person with both an admin login and a marketplace account never gets the other app's push.
-- Expand-only: existing rows become 'marketplace'; the running backend ignores the column, and
-- no 'admin' row exists until the admin panel ships its subscribe button.
-- ============================================================
alter table public.push_subscriptions
  add column if not exists app text not null default 'marketplace';

alter table public.push_subscriptions drop constraint if exists push_subscriptions_app_check;
alter table public.push_subscriptions add constraint push_subscriptions_app_check
  check (app in ('marketplace', 'admin'));

comment on column public.push_subscriptions.app is
  'Web app that subscribed: marketplace (buyer / seller app) or admin (admin panel).';
