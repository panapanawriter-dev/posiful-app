"""クラウド連携のトランザクション内検証SQLを作成。実ユーザー・データは残さない。"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from posiful.cloud import sample_payload

root = Path(__file__).resolve().parents[1]
sample = sample_payload()
for menu in sample['menus']:
    menu['embedding'] = menu['embedding'][:3]
payload = json.dumps(sample,ensure_ascii=False,separators=(',',':'))
sql = '''begin;
select set_config('posiful.test_owner',gen_random_uuid()::text,true),
       set_config('posiful.test_member',gen_random_uuid()::text,true),
       set_config('posiful.test_other',gen_random_uuid()::text,true);
insert into auth.users(id,email) values
 (current_setting('posiful.test_owner')::uuid,'owner-rollback@posiful.invalid'),
 (current_setting('posiful.test_member')::uuid,'member-rollback@posiful.invalid'),
 (current_setting('posiful.test_other')::uuid,'other-rollback@posiful.invalid');
select set_config('request.jwt.claim.sub',current_setting('posiful.test_owner'),true);
set local role authenticated;
'''+'''select set_config('posiful.test_sample',($seed$'''+payload+'''$seed$::jsonb || jsonb_build_object('menus',
 (select jsonb_agg(m || jsonb_build_object('embedding',(m->'embedding') || (select jsonb_agg(0) from generate_series(1,1533)))) from jsonb_array_elements($seed$'''+json.dumps(sample['menus'],ensure_ascii=False,separators=(',',':'))+'''$seed$::jsonb) m)))::text,true);
select public.posiful_import_sample(current_setting('posiful.test_sample')::jsonb);
do $$ declare d jsonb; begin
 d:=public.posiful_load();
 if jsonb_array_length(d->'menus')<>10 or jsonb_array_length(d->'history')<>220 or jsonb_array_length(d->'companies')<>10 or jsonb_array_length(d->'inventory')<>7 then raise exception 'Import count mismatch'; end if;
 begin perform public.posiful_import_sample(current_setting('posiful.test_sample')::jsonb); raise exception 'Duplicate import unexpectedly succeeded';
 exception when raise_exception then if sqlerrm='Duplicate import unexpectedly succeeded' then raise; end if; end;
end $$;
select public.posiful_invite_member('member-rollback@posiful.invalid');
select set_config('request.jwt.claim.sub',current_setting('posiful.test_member'),true);
do $$ declare d jsonb; p jsonb; mid bigint; begin
 d:=public.posiful_load();
 if jsonb_array_length(d->'menus')<>10 then raise exception 'Member cannot read shared menus'; end if;
 select value into p from jsonb_array_elements(d->'plans') where value->>'planned_date'='2026-10-08';
 select (value->>'menu_id')::bigint into mid from jsonb_array_elements(d->'menus') where value->>'menu_name'<>p->>'menu_name' limit 1;
 perform public.posiful_replace_menu('2026-10-08',mid,(p->>'revision')::integer);
 begin perform public.posiful_replace_menu('2026-10-08',mid,(p->>'revision')::integer); raise exception 'Stale revision unexpectedly succeeded';
 exception when raise_exception then if sqlerrm='Stale revision unexpectedly succeeded' then raise; end if; end;
 mid:=public.posiful_save_recipe((current_setting('posiful.test_sample')::jsonb->'menus'->0)||jsonb_build_object('menu_name','共同編集検証レシピ'));
 if not exists(select 1 from public.menus where menu_id=mid and user_id=current_setting('posiful.test_owner')::uuid) then raise exception 'Shared recipe owner mismatch'; end if;
 begin perform public.posiful_invite_member('other-rollback@posiful.invalid'); raise exception 'Member invite unexpectedly succeeded';
 exception when raise_exception then if sqlerrm='Member invite unexpectedly succeeded' then raise; end if; end;
end $$;
select set_config('request.jwt.claim.sub',current_setting('posiful.test_other'),true);
do $$ begin
 if (select count(*) from public.menus)<>0 or (select count(*) from public.sales_history)<>0 then raise exception 'Unrelated user saw shared data'; end if;
 begin insert into public.menu_plans(user_id,planned_date,menu_id) values(current_setting('posiful.test_owner')::uuid,'2026-11-01',1); raise exception 'Cross-workspace write succeeded';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
select jsonb_build_object('verified',true,'sample_menus',10,'history_rows',220,'shared_read_write',true,'unrelated_user_blocked',true,'stale_revision_blocked',true,'anon_rpc_blocked',not has_function_privilege('anon','public.posiful_load()','execute')) as verification;
rollback;
'''
(root/'supabase/test_cloud_transaction.sql').write_text(sql,encoding='utf-8')
