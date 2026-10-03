"""MCPで適用する追加スキーマを構成する。SQLをDBへ送る処理は含まない。"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cloud = (root/'supabase/cloud_data.sql').read_text(encoding='utf-8')
team = (root/'supabase/team_access.sql').read_text(encoding='utf-8')
initial = (root/'supabase/schema.sql').read_text(encoding='utf-8')
recipe = initial[initial.index('create function public.posiful_save_recipe'):initial.index('create function public.posiful_load')]
functions = cloud[cloud.index('create function public.posiful_replace_menu'):cloud.index('revoke all on function public.posiful_load')]
functions = functions.replace("if exists(select 1 from public.menus", "insert into public.app_members(user_id,workspace_owner_id) values(auth.uid(),auth.uid()) on conflict(user_id) do nothing;\n if public.posiful_owner() <> auth.uid() then raise exception 'Workspace owner required'; end if;\n if exists(select 1 from public.menus")
replacements = (recipe+functions).replace('create function','create or replace function').replace('user_id=auth.uid()','user_id=public.posiful_owner()')
sql = cloud+'\n'+team+'\n'+replacements
(root/'supabase/cloud_integration.sql').write_text(sql,encoding='utf-8')
