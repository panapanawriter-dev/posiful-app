-- C案。新規専用プロジェクトで実行する初期スキーマ。
create schema if not exists extensions;
create extension if not exists vector with schema extensions;

create table public.menus (
  menu_id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id),
  menu_name text not null check (length(trim(menu_name)) > 0),
  menu_type text not null check (menu_type in ('日替わり', 'レギュラー')),
  recipe_text text not null,
  unique(menu_id, user_id)
);
create table public.ingredients (
  ingredient_id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id),
  ingredient_name text not null check (length(trim(ingredient_name)) > 0),
  base_unit text not null check (base_unit in ('g','kg','ml','L','個')),
  unique(user_id, ingredient_name), unique(ingredient_id, user_id)
);
create table public.recipe_ingredients (
  recipe_ingredient_id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id),
  menu_id bigint not null, ingredient_id bigint not null,
  quantity_per_serving numeric not null check (quantity_per_serving > 0),
  unit text not null check (unit in ('g','kg','ml','L','個')),
  foreign key(menu_id,user_id) references public.menus(menu_id,user_id) on delete cascade,
  foreign key(ingredient_id,user_id) references public.ingredients(ingredient_id,user_id),
  unique(menu_id, ingredient_id)
);
create table public.menu_features (
  menu_feature_id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id),
  menu_id bigint not null unique,
  genre text not null, seasoning text not null, cooking_method text not null,
  richness text not null, feature_text text not null,
  foreign key(menu_id,user_id) references public.menus(menu_id,user_id) on delete cascade,
  unique(menu_feature_id, user_id)
);
create table public.menu_embeddings (
  menu_embedding_id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id),
  menu_feature_id bigint not null unique,
  embedding extensions.vector(1536) not null,
  embedding_model text not null,
  embedded_at timestamptz not null default now(),
  foreign key(menu_feature_id,user_id) references public.menu_features(menu_feature_id,user_id) on delete cascade
);
create table public.inventory (
  inventory_id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id),
  ingredient_id bigint not null,
  current_quantity numeric not null check(current_quantity >= 0),
  unit text not null check (unit in ('g','kg','ml','L','個')),
  expiration_date date not null,
  foreign key(ingredient_id,user_id) references public.ingredients(ingredient_id,user_id)
);
create table public.menu_sales_estimates (
  estimate_id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id),
  menu_id bigint not null, target_date date not null,
  estimated_quantity integer not null check(estimated_quantity >= 0),
  foreign key(menu_id,user_id) references public.menus(menu_id,user_id) on delete cascade,
  unique(menu_id, target_date)
);

do $$
declare tbl text;
begin
  foreach tbl in array array['menus','ingredients','recipe_ingredients','menu_features','menu_embeddings','inventory','menu_sales_estimates'] loop
    execute format('alter table public.%I enable row level security', tbl);
    execute format('create policy own_rows on public.%I for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)', tbl);
    execute format('create index on public.%I(user_id)', tbl);
    execute format('grant select, insert, update, delete on public.%I to authenticated', tbl);
  end loop;
end $$;
grant usage, select on all sequences in schema public to authenticated;
create index on public.recipe_ingredients(ingredient_id,user_id);
create index on public.inventory(ingredient_id,user_id);
create index menu_embeddings_feature_owner_idx on public.menu_embeddings(menu_feature_id,user_id);
create index menu_features_menu_owner_idx on public.menu_features(menu_id,user_id);
create index estimates_menu_owner_idx on public.menu_sales_estimates(menu_id,user_id);
create index recipe_menu_owner_idx on public.recipe_ingredients(menu_id,user_id);

-- 1回のRPCで登録。途中で失敗するとすべてロールバックする。
create function public.posiful_save_recipe(recipe jsonb) returns bigint
language plpgsql security invoker set search_path = public, extensions
as $$
declare mid bigint; fid bigint; iid bigint; item jsonb; existing_unit text;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if jsonb_array_length(recipe->'ingredients') = 0 then raise exception 'Ingredients required'; end if;
  insert into public.menus(menu_name,menu_type,recipe_text)
  values (recipe->>'menu_name',recipe->>'menu_type',recipe->>'recipe_text') returning menu_id into mid;
  for item in select value from jsonb_array_elements(recipe->'ingredients') loop
    insert into public.ingredients(ingredient_name,base_unit)
      values(trim(item->>'name'),item->>'unit')
      on conflict(user_id,ingredient_name) do nothing;
    select ingredient_id,base_unit into iid,existing_unit from public.ingredients
      where user_id=auth.uid() and ingredient_name=trim(item->>'name');
    if not (existing_unit = item->>'unit' or
      (existing_unit in ('g','kg') and item->>'unit' in ('g','kg')) or
      (existing_unit in ('ml','L') and item->>'unit' in ('ml','L'))) then
      raise exception 'Incompatible ingredient unit';
    end if;
    insert into public.recipe_ingredients(menu_id,ingredient_id,quantity_per_serving,unit)
      values(mid,iid,(item->>'quantity')::numeric,item->>'unit');
  end loop;
  insert into public.menu_features(menu_id,genre,seasoning,cooking_method,richness,feature_text)
    values(mid,recipe->>'genre',recipe->>'seasoning',recipe->>'cooking_method',recipe->>'richness',recipe->>'feature_text')
    returning menu_feature_id into fid;
  insert into public.menu_embeddings(menu_feature_id,embedding,embedding_model)
    values(fid,(recipe->>'embedding')::extensions.vector,recipe->>'embedding_model');
  return mid;
end $$;

create function public.posiful_load() returns jsonb
language sql stable security invoker set search_path = public, extensions
as $$
  select jsonb_build_object(
    'menus', coalesce((select jsonb_agg(to_jsonb(result) order by menu_id) from (
      select m.*,f.genre,f.seasoning,f.cooking_method,f.richness,f.feature_text,
        e.embedding::text::jsonb as embedding,e.embedding_model,
        coalesce((select jsonb_agg(jsonb_build_object('name',i.ingredient_name,'quantity',r.quantity_per_serving,'unit',r.unit))
          from public.recipe_ingredients r join public.ingredients i using(ingredient_id) where r.menu_id=m.menu_id),'[]'::jsonb) as ingredients
      from public.menus m join public.menu_features f using(menu_id)
        join public.menu_embeddings e using(menu_feature_id)
    ) result),'[]'::jsonb),
    'inventory',coalesce((select jsonb_agg(jsonb_build_object('name',i.ingredient_name,'current_quantity',s.current_quantity,'unit',s.unit,'expiration_date',s.expiration_date))
      from public.inventory s join public.ingredients i using(ingredient_id)),'[]'::jsonb),
    'estimates',coalesce((select jsonb_agg(jsonb_build_object('menu_id',menu_id,'target_date',target_date,'estimated_quantity',estimated_quantity))
      from public.menu_sales_estimates),'[]'::jsonb)
  );
$$;
revoke all on function public.posiful_save_recipe(jsonb) from public, anon;
revoke all on function public.posiful_load() from public, anon;
grant execute on function public.posiful_save_recipe(jsonb), public.posiful_load() to authenticated;
