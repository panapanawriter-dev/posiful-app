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
