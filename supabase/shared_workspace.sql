-- Login-free shared workspace. No direct anon table access.
create role posiful_shared_executor nologin inherit;
grant authenticated to posiful_shared_executor;
grant posiful_shared_executor to postgres;
grant usage on schema public, extensions, posiful_private to posiful_shared_executor;
create table posiful_private.shared_workspace (
 singleton boolean primary key default true check(singleton),
 owner_id uuid not null references auth.users(id)
);
revoke all on posiful_private.shared_workspace from public, anon, authenticated;
do $$ declare owners integer; begin
 select count(distinct user_id) into owners from public.menus;
 if owners <> 1 then raise exception 'Expected exactly one existing workspace; select it explicitly'; end if;
 insert into posiful_private.shared_workspace(owner_id) select distinct user_id from public.menus;
end $$;
grant select on posiful_private.shared_workspace to posiful_shared_executor;
create function posiful_private.shared_dispatch(operation text, payload jsonb default '{}') returns jsonb
language plpgsql security definer set search_path=''
as $$
declare shared_owner uuid; prior_claims text; prior_sub text; result jsonb;
begin
 select owner_id into strict shared_owner from posiful_private.shared_workspace where singleton;
 prior_claims := current_setting('request.jwt.claims',true);
 prior_sub := current_setting('request.jwt.claim.sub',true);
 perform set_config('request.jwt.claim.sub', shared_owner::text, true);
 perform set_config('request.jwt.claims',jsonb_build_object('sub',shared_owner,'role','authenticated')::text,true);
 case operation
 when 'load' then result := public.posiful_load();
 when 'save' then
   if payload->'recipe' is null then raise exception 'Recipe required'; end if;
   result := to_jsonb(public.posiful_save_recipe(payload->'recipe'));
 when 'replace' then
   if payload->>'target_date' is null or payload->>'new_menu_id' is null or payload->>'expected_revision' is null
      or (payload->>'expected_revision')::integer < 0 then raise exception 'Date, menu and revision required'; end if;
   result := public.posiful_replace_menu(
   (payload->>'target_date')::date,(payload->>'new_menu_id')::bigint,(payload->>'expected_revision')::integer);
 else raise exception 'Unsupported shared operation';
 end case;
 perform set_config('request.jwt.claim.sub',coalesce(prior_sub,''),true);
 perform set_config('request.jwt.claims',coalesce(prior_claims,'{}'),true);
 return result;
end $$;
revoke all on function posiful_private.shared_dispatch(text,jsonb) from public;
grant create on schema posiful_private to posiful_shared_executor;
alter function posiful_private.shared_dispatch(text,jsonb) owner to posiful_shared_executor;
revoke create on schema posiful_private from posiful_shared_executor;
grant usage on schema posiful_private to anon;
grant execute on function posiful_private.shared_dispatch(text,jsonb) to anon,authenticated,postgres;
create function public.posiful_shared_load() returns jsonb language sql security invoker set search_path=''
as $$ select posiful_private.shared_dispatch('load','{}'); $$;
create function public.posiful_shared_save_recipe(recipe jsonb) returns jsonb language sql security invoker set search_path=''
as $$ select posiful_private.shared_dispatch('save',jsonb_build_object('recipe',recipe)); $$;
create function public.posiful_shared_replace_menu(target_date date,new_menu_id bigint,expected_revision integer)
returns jsonb language sql security invoker set search_path=''
as $$ select posiful_private.shared_dispatch('replace',jsonb_build_object('target_date',target_date,'new_menu_id',new_menu_id,'expected_revision',expected_revision)); $$;
revoke all on function public.posiful_shared_load(),public.posiful_shared_save_recipe(jsonb),public.posiful_shared_replace_menu(date,bigint,integer) from public;
grant execute on function public.posiful_shared_load(),public.posiful_shared_save_recipe(jsonb),public.posiful_shared_replace_menu(date,bigint,integer) to anon,authenticated;
revoke posiful_shared_executor from postgres;
