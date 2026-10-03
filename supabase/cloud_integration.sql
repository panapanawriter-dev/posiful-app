-- initial schema.sql の後に適用する販売実績・予定の連携。
create table public.visit_companies (
 user_id uuid not null default auth.uid() references auth.users(id),
 company_code text not null, company_name text not null,
 work_type text not null check(work_type in ('現場職','内勤中心')),
 details jsonb not null default '{}', primary key(user_id,company_code)
);
create table public.sales_history (
 history_id bigint generated always as identity primary key,
 user_id uuid not null default auth.uid() references auth.users(id),
 company_code text not null, menu_id bigint not null, served_date date not null,
 sales_quantity integer not null check(sales_quantity >= 0),
 weather text not null check(weather in ('晴れ','曇り','雨')),
 details jsonb not null default '{}', unique(user_id,company_code,served_date),
 foreign key(user_id,company_code) references public.visit_companies(user_id,company_code),
 foreign key(menu_id,user_id) references public.menus(menu_id,user_id)
);
create table public.menu_plans (
 user_id uuid not null default auth.uid() references auth.users(id),
 planned_date date not null, menu_id bigint not null,
 status text not null default '暫定', revision integer not null default 0,
 primary key(user_id,planned_date),
 foreign key(menu_id,user_id) references public.menus(menu_id,user_id)
);
create table public.menu_plan_changes (
 change_id bigint generated always as identity primary key,
 user_id uuid not null default auth.uid() references auth.users(id),
 planned_date date not null, previous_menu_id bigint not null, menu_id bigint not null,
 changed_at timestamptz not null default now(),
 foreign key(user_id,planned_date) references public.menu_plans(user_id,planned_date),
 foreign key(previous_menu_id,user_id) references public.menus(menu_id,user_id),
 foreign key(menu_id,user_id) references public.menus(menu_id,user_id)
);
create index sales_menu_owner_idx on public.sales_history(menu_id,user_id);
create index plans_menu_owner_idx on public.menu_plans(menu_id,user_id);
create index changes_previous_owner_idx on public.menu_plan_changes(previous_menu_id,user_id);
create index changes_menu_owner_idx on public.menu_plan_changes(menu_id,user_id);
create index changes_plan_owner_idx on public.menu_plan_changes(user_id,planned_date);
do $$ declare tbl text; begin
 foreach tbl in array array['visit_companies','sales_history','menu_plans','menu_plan_changes'] loop
  execute format('alter table public.%I enable row level security',tbl);
  execute format('revoke all on public.%I from anon, authenticated',tbl);
  execute format('grant select, insert, update on public.%I to authenticated',tbl);
  execute format('create policy own_rows on public.%I for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id)',tbl);
 end loop;
end $$;
grant usage,select on sequence public.sales_history_history_id_seq,public.menu_plan_changes_change_id_seq to authenticated;

alter function public.posiful_load() rename to posiful_load_recipes;
create function public.posiful_load() returns jsonb
language sql stable security invoker set search_path=public,extensions
as $$ select public.posiful_load_recipes() || jsonb_build_object(
 'companies',coalesce((select jsonb_agg(c.details || jsonb_build_object('company_id',company_code,'company_name',company_name,'work_type',work_type) order by company_code) from public.visit_companies c),'[]'::jsonb),
 'history',coalesce((select jsonb_agg(h.details || jsonb_build_object('served_date',served_date,'company_id',h.company_code,'company_name',c.company_name,'work_type',c.work_type,'menu_id',h.menu_id,'menu_name',m.menu_name,'menu_type',m.menu_type,'sales_quantity',sales_quantity,'weather',weather) order by served_date,h.company_code)
  from public.sales_history h join public.visit_companies c using(user_id,company_code) join public.menus m on m.menu_id=h.menu_id and m.user_id=h.user_id),'[]'::jsonb),
 'plans',coalesce((select jsonb_agg(jsonb_build_object('planned_date',planned_date,'weekday',(array['月','火','水','木','金','土','日'])[extract(isodow from planned_date)::integer],'menu_id',p.menu_id,'menu_name',m.menu_name,'status',status,'revision',revision) order by planned_date)
  from public.menu_plans p join public.menus m on m.menu_id=p.menu_id and m.user_id=p.user_id),'[]'::jsonb)
 ); $$;

create function public.posiful_replace_menu(target_date date,new_menu_id bigint,expected_revision integer)
returns jsonb language plpgsql security invoker set search_path=public,extensions
as $$ declare current_plan public.menu_plans; old_name text; new_name text;
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 select * into current_plan from public.menu_plans where user_id=auth.uid() and planned_date=target_date for update;
 if not found then raise exception 'Planned date not found'; end if;
 if current_plan.revision <> expected_revision then raise exception 'Plan changed; reload'; end if;
 if current_plan.menu_id=new_menu_id then raise exception 'Same menu'; end if;
 select menu_name into new_name from public.menus where user_id=auth.uid() and menu_id=new_menu_id and menu_type='日替わり';
 if not found then raise exception 'Daily menu not found'; end if;
 select menu_name into old_name from public.menus where user_id=auth.uid() and menu_id=current_plan.menu_id;
 insert into public.menu_plan_changes(planned_date,previous_menu_id,menu_id) values(target_date,current_plan.menu_id,new_menu_id);
 update public.menu_plans set menu_id=new_menu_id,status='差し替え済み',revision=revision+1 where user_id=auth.uid() and planned_date=target_date;
 return jsonb_build_object('previous_menu_name',old_name,'menu_name',new_name);
end $$;

-- ログイン後に任意で実行。既存データがある場合は上書きせず、全体を1トランザクションで移行。
create function public.posiful_import_sample(sample jsonb) returns jsonb
language plpgsql security invoker set search_path=public,extensions
as $$ declare item jsonb; mid bigint; iid bigint; menu_map jsonb:='{}';
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text,0));
 if exists(select 1 from public.menus where user_id=auth.uid())
 or exists(select 1 from public.visit_companies where user_id=auth.uid()) then
  raise exception 'Existing data; sample import rejected';
 end if;
 for item in select value from jsonb_array_elements(sample->'menus') loop
  mid:=public.posiful_save_recipe(item);
  menu_map:=menu_map || jsonb_build_object(item->>'menu_name',mid);
 end loop;
 for item in select value from jsonb_array_elements(sample->'inventory') loop
  select ingredient_id into strict iid from public.ingredients where user_id=auth.uid() and ingredient_name=item->>'name';
  insert into public.inventory(ingredient_id,current_quantity,unit,expiration_date)
   values(iid,(item->>'current_quantity')::numeric,item->>'unit',(item->>'expiration_date')::date);
 end loop;
 for item in select value from jsonb_array_elements(sample->'companies') loop
  insert into public.visit_companies(company_code,company_name,work_type,details)
   values(item->>'company_id',item->>'company_name',item->>'work_type',item);
 end loop;
 for item in select value from jsonb_array_elements(sample->'history') loop
  mid:=(menu_map->>(item->>'menu_name'))::bigint;
  insert into public.sales_history(company_code,menu_id,served_date,sales_quantity,weather,details)
   values(item->>'company_id',mid,(item->>'served_date')::date,(item->>'sales_quantity')::integer,item->>'weather',item);
 end loop;
 for item in select value from jsonb_array_elements(sample->'plans') loop
  mid:=(menu_map->>(item->>'menu_name'))::bigint;
  insert into public.menu_plans(planned_date,menu_id,status)
   values((item->>'planned_date')::date,mid,item->>'status');
 end loop;
 return jsonb_build_object('menus',jsonb_array_length(sample->'menus'),'history',jsonb_array_length(sample->'history'),'plans',jsonb_array_length(sample->'plans'));
end $$;
revoke all on function public.posiful_load(),public.posiful_replace_menu(date,bigint,integer),public.posiful_import_sample(jsonb) from public,anon;
grant execute on function public.posiful_load(),public.posiful_replace_menu(date,bigint,integer),public.posiful_import_sample(jsonb) to authenticated;

-- 共同編集。user_idは作成者ではなくワークスペース所有者として扱う。
create table public.app_members (
 user_id uuid primary key references auth.users(id),
 workspace_owner_id uuid not null references auth.users(id)
);
create index app_members_owner_idx on public.app_members(workspace_owner_id);
alter table public.app_members enable row level security;
revoke all on public.app_members from anon,authenticated;
grant select,insert on public.app_members to authenticated;
create policy own_membership on public.app_members for select to authenticated using(user_id=(select auth.uid()));
create policy start_workspace on public.app_members for insert to authenticated with check(user_id=(select auth.uid()) and workspace_owner_id=(select auth.uid()));
create function public.posiful_owner() returns uuid language sql stable security invoker set search_path=public
as $$ select coalesce((select workspace_owner_id from public.app_members where user_id=auth.uid()),auth.uid()); $$;
revoke all on function public.posiful_owner() from public,anon;
grant execute on function public.posiful_owner() to authenticated;
do $$ declare tbl text; begin
 foreach tbl in array array['menus','ingredients','recipe_ingredients','menu_features','menu_embeddings','inventory','menu_sales_estimates','visit_companies','sales_history','menu_plans','menu_plan_changes'] loop
  execute format('drop policy own_rows on public.%I',tbl);
  execute format('alter table public.%I alter column user_id set default public.posiful_owner()',tbl);
  execute format('create policy own_rows on public.%I for all to authenticated using ((select public.posiful_owner())=user_id) with check ((select public.posiful_owner())=user_id)',tbl);
 end loop;
end $$;

-- auth.usersのメール検索が必要な招待処理だけ特権関数。既存メンバーは移動・上書きしない。
create schema if not exists posiful_private;
create function posiful_private.invite_member(member_email text) returns jsonb
language plpgsql security definer set search_path=public
as $$ declare invitee uuid; begin
 if auth.uid() is null or not exists(select 1 from public.app_members where user_id=auth.uid() and workspace_owner_id=auth.uid()) then
  raise exception 'Workspace owner required';
 end if;
 select id into invitee from auth.users where lower(email)=lower(trim(member_email));
 if invitee is null then raise exception 'Collaborator must register first'; end if;
 if exists(select 1 from public.app_members where user_id=invitee) then raise exception 'User already belongs to a workspace'; end if;
 if exists(select 1 from public.menus where user_id=invitee) then raise exception 'User already owns data'; end if;
 insert into public.app_members(user_id,workspace_owner_id) values(invitee,auth.uid());
 return jsonb_build_object('invited',true);
end $$;
revoke all on function posiful_private.invite_member(text) from public,anon;
grant usage on schema posiful_private to authenticated;
grant execute on function posiful_private.invite_member(text) to authenticated;
create function public.posiful_invite_member(member_email text) returns jsonb
language sql security invoker set search_path=public
as $$ select posiful_private.invite_member(member_email); $$;
revoke all on function public.posiful_invite_member(text) from public,anon;
grant execute on function public.posiful_invite_member(text) to authenticated;

create or replace function public.posiful_save_recipe(recipe jsonb) returns bigint
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
      where user_id=public.posiful_owner() and ingredient_name=trim(item->>'name');
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

create or replace function public.posiful_replace_menu(target_date date,new_menu_id bigint,expected_revision integer)
returns jsonb language plpgsql security invoker set search_path=public,extensions
as $$ declare current_plan public.menu_plans; old_name text; new_name text;
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 select * into current_plan from public.menu_plans where user_id=public.posiful_owner() and planned_date=target_date for update;
 if not found then raise exception 'Planned date not found'; end if;
 if current_plan.revision <> expected_revision then raise exception 'Plan changed; reload'; end if;
 if current_plan.menu_id=new_menu_id then raise exception 'Same menu'; end if;
 select menu_name into new_name from public.menus where user_id=public.posiful_owner() and menu_id=new_menu_id and menu_type='日替わり';
 if not found then raise exception 'Daily menu not found'; end if;
 select menu_name into old_name from public.menus where user_id=public.posiful_owner() and menu_id=current_plan.menu_id;
 insert into public.menu_plan_changes(planned_date,previous_menu_id,menu_id) values(target_date,current_plan.menu_id,new_menu_id);
 update public.menu_plans set menu_id=new_menu_id,status='差し替え済み',revision=revision+1 where user_id=public.posiful_owner() and planned_date=target_date;
 return jsonb_build_object('previous_menu_name',old_name,'menu_name',new_name);
end $$;

-- ログイン後に任意で実行。既存データがある場合は上書きせず、全体を1トランザクションで移行。
create or replace function public.posiful_import_sample(sample jsonb) returns jsonb
language plpgsql security invoker set search_path=public,extensions
as $$ declare item jsonb; mid bigint; iid bigint; menu_map jsonb:='{}';
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text,0));
 insert into public.app_members(user_id,workspace_owner_id) values(auth.uid(),auth.uid()) on conflict(user_id) do nothing;
 if public.posiful_owner() <> auth.uid() then raise exception 'Workspace owner required'; end if;
 if exists(select 1 from public.menus where user_id=public.posiful_owner())
 or exists(select 1 from public.visit_companies where user_id=public.posiful_owner()) then
  raise exception 'Existing data; sample import rejected';
 end if;
 for item in select value from jsonb_array_elements(sample->'menus') loop
  mid:=public.posiful_save_recipe(item);
  menu_map:=menu_map || jsonb_build_object(item->>'menu_name',mid);
 end loop;
 for item in select value from jsonb_array_elements(sample->'inventory') loop
  select ingredient_id into strict iid from public.ingredients where user_id=public.posiful_owner() and ingredient_name=item->>'name';
  insert into public.inventory(ingredient_id,current_quantity,unit,expiration_date)
   values(iid,(item->>'current_quantity')::numeric,item->>'unit',(item->>'expiration_date')::date);
 end loop;
 for item in select value from jsonb_array_elements(sample->'companies') loop
  insert into public.visit_companies(company_code,company_name,work_type,details)
   values(item->>'company_id',item->>'company_name',item->>'work_type',item);
 end loop;
 for item in select value from jsonb_array_elements(sample->'history') loop
  mid:=(menu_map->>(item->>'menu_name'))::bigint;
  insert into public.sales_history(company_code,menu_id,served_date,sales_quantity,weather,details)
   values(item->>'company_id',mid,(item->>'served_date')::date,(item->>'sales_quantity')::integer,item->>'weather',item);
 end loop;
 for item in select value from jsonb_array_elements(sample->'plans') loop
  mid:=(menu_map->>(item->>'menu_name'))::bigint;
  insert into public.menu_plans(planned_date,menu_id,status)
   values((item->>'planned_date')::date,mid,item->>'status');
 end loop;
 return jsonb_build_object('menus',jsonb_array_length(sample->'menus'),'history',jsonb_array_length(sample->'history'),'plans',jsonb_array_length(sample->'plans'));
end $$;
