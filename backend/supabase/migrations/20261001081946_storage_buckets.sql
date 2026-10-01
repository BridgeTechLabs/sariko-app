-- Buckets lived only in the production dashboard, so a project built from
-- migrations had none and every upload via utils/storage.py failed on dev.
-- Settings match production: public, no size or mime limits. Uploads go through
-- the backend's service role, so no storage.objects policies are needed.
--
-- on conflict: production already has both, this is a no-op there.

insert into storage.buckets (id, name, public) values
  ('sariko-public', 'sariko-public', true),
  ('blog-images',   'blog-images',   true)
on conflict (id) do nothing;
