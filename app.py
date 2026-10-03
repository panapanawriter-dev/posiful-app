import json
import os
import time
from datetime import date
from pathlib import Path

import streamlit as st
from posiful.core import demo_data, rank, consumption, UNITS, convert
from posiful.ui import setup, description, candidate_text, amount, evaluation
from posiful.history import load_sample, surrounding_plans
from posiful.history import load_menu_plan as load_base_plan
from posiful.plan_store import load_menu_plan, replace_menu
from posiful.demo_plan import replace_in_plan
from posiful.forecast import predict_sales
from posiful.search import rank_targets
from posiful.api import Database, sign_in, sign_up, refresh_session, ai_recipe, embed
from posiful.cloud import sample_payload

# .env はローカル設定のみ。シェル式として実行しない。
if Path('.env').exists():
    for line in Path('.env').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

st.set_page_config(page_title='Posiful | 日替わり提案', page_icon='🍱', layout='wide')
# Community CloudのSecretsを読み、公開デモの変更をセッションに限定する。
try:
    demo_session_only = bool(st.secrets.get('POSIFUL_DEMO_SESSION_ONLY',False))
except st.errors.StreamlitSecretNotFoundError:
    demo_session_only = os.getenv('POSIFUL_DEMO_SESSION_ONLY','').lower() in ['true','1']
setup()
st.sidebar.caption('メニュー管理')
page = st.sidebar.radio('画面', ['日替わりを探す', 'レシピを登録', 'レシピ一覧', '日替わり予定', '提供履歴'], label_visibility='collapsed', key='navigation')
st.sidebar.caption('余った食材を活かして、\n毎日の献立に変化を。')
with st.sidebar.expander('接続設定'):
    mode = st.radio('データ接続', ['デモ', 'Supabase'])
    if mode == 'デモ':
        st.caption('サンプルデータと仮ベクトル。保存はセッション内のみ。')
db = None
if mode == 'デモ':
    if 'demo' not in st.session_state:
        st.session_state.demo = demo_data()
    data = st.session_state.demo
    if data.get('stock_revision') != 3:
        refreshed = demo_data()
        data['inventory'] = refreshed['inventory']
        data.pop('stock_plan',None)
        data['stock_revision'] = 3
        data['history'],data['companies'] = refreshed['history'],refreshed['companies']
    # 既存セッションの登録レシピを残し、追加サンプルも利用できるようにする。
    if data.get('sample_menu_revision',0) < 11:
        refreshed = demo_data()
        known_names = {m['menu_name'] for m in data['menus']}
        for sample_menu in refreshed['menus']:
            existing_sample = next((m for m in data['menus'] if m['menu_name']==sample_menu['menu_name'] and m.get('embedding_model')=='demo-manual-v1'),None)
            if existing_sample:
                existing_sample['ingredients'] = sample_menu['ingredients']
                existing_sample['recipe_text'] = sample_menu['recipe_text']
            if sample_menu['menu_name'] not in known_names:
                sample_menu = dict(sample_menu)
                if any(m['menu_id']==sample_menu['menu_id'] for m in data['menus']):
                    sample_menu['menu_id'] = max(m['menu_id'] for m in data['menus'])+1
                data['menus'].append(sample_menu)
        data['sample_menu_revision'] = 11
    if 'history' not in data or (data['history'] and 'weather' not in data['history'][0]):
        refreshed = demo_data()
        data['history'],data['companies'] = refreshed['history'],refreshed['companies']
        known = {m['menu_id'] for m in data['menus']}
        data['menus'].extend(m for m in refreshed['menus'] if m['menu_id'] not in known)
else:
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_PUBLISHABLE_KEY'):
        st.warning('.env にSupabaseのURLと公開キーを設定してください。')
        st.stop()
    if 'token' not in st.session_state:
        with st.form('login'):
            st.subheader('Supabaseに接続')
            auth_action = st.selectbox('操作',['ログイン','アカウント登録'])
            email = st.text_input('メールアドレス')
            password = st.text_input('パスワード', type='password')
            login = st.form_submit_button('続ける')
        st.caption('初回はアカウント登録を選び、確認メールのリンクを開いてからログインしてください。協力者は登録・メール確認後、所有者から招待を受けてログインします。')
        if login:
            try:
                if not email.strip() or len(password)<8:
                    raise ValueError('メールアドレスと8文字以上のパスワードを入力してください。')
                result = sign_up(email.strip(), password) if auth_action=='アカウント登録' else sign_in(email.strip(), password)
                if result.get('access_token'):
                    st.session_state.token = result['access_token']
                    st.session_state.refresh_token = result['refresh_token']
                    st.session_state.token_expires = time.time()+result.get('expires_in',3600)
                    st.session_state.auth_user_id = result['user']['id']
                    st.rerun()
                else:
                    st.success('確認メールを送信しました。メールのリンクを開いてからログインしてください。')
            except (RuntimeError, KeyError, ValueError) as exc:
                st.error(str(exc))
        st.stop()
    if st.sidebar.button('ログアウト'):
        for key in ['token','refresh_token','token_expires','auth_user_id','selected_menu']:
            st.session_state.pop(key,None)
        st.session_state.pop('draft', None)
        st.rerun()
    db = Database(st.session_state.token)
    try:
        if time.time() >= st.session_state.get('token_expires',float('inf'))-60:
            result = refresh_session(st.session_state.refresh_token)
            st.session_state.token = result['access_token']
            st.session_state.refresh_token = result['refresh_token']
            st.session_state.token_expires = time.time()+result.get('expires_in',3600)
            db = Database(st.session_state.token)
        data = db.load()
    except RuntimeError as exc:
        st.error(str(exc))
        st.info('セッション期限切れの場合は、ログアウトして再度ログインしてください。')
        st.stop()
    if not data['menus']:
        st.title('共有データの初期設定')
        st.info('このワークスペースにはレシピがありません。所有者はサンプルを移行してください。招待待ちの協力者は移行せず、所有者の招待後に再読み込みしてください。')
        if st.button('サンプルをSupabaseへ移行',type='primary'):
            try:
                db.import_sample(sample_payload())
                st.session_state.plan_notice = 'レシピ10種類・在庫・10社の販売履歴・予定をSupabaseへ移行しました。'
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))
        st.stop()
    with st.sidebar.expander('共同編集メンバー'):
        st.caption('所有者のみ招待できます。協力者は先にアカウント登録とメール確認を行ってください。')
        invite_email = st.text_input('協力者のメールアドレス')
        if st.button('共同編集に招待'):
            try:
                db.invite(invite_email)
                st.success('同じデータを共同編集できるようにしました。協力者はアプリを再読み込みしてください。')
            except RuntimeError:
                st.error('招待できません。所有者であること、協力者の登録が済んでいること、他のワークスペースに所属していないことを確認してください。')


def current_plan():
    if not db and demo_session_only:
        if 'demo_plan' not in st.session_state:
            st.session_state.demo_plan = load_base_plan()
        return st.session_state.demo_plan
    return {'plans':data.get('plans',[]),'metadata':{'source':'Supabase'}} if db else load_menu_plan()

menus = data['menus']
if st.session_state.get('plan_notice'):
    st.success(st.session_state.pop('plan_notice'))

if page == '日替わりを探す':
    selected = st.session_state.get('selected_menu')
    if selected and selected['mode'] != mode:
        st.session_state.pop('selected_menu', None)
        selected = None
    if selected:
        menu = next((m for m in menus if m['menu_id'] == selected['menu_id']), None)
        if menu is None:
            st.session_state.pop('selected_menu', None)
            st.rerun()
        target = selected['target']
        weather = st.selectbox('対象日の天気', ['晴れ','曇り','雨'], index=['晴れ','曇り','雨'].index(selected.get('weather','晴れ')))
        forecast = predict_sales(data.get('history',[]),data.get('companies',[]),target,weather)
        predicted_estimates = [] if forecast is None else [{'menu_id':menu['menu_id'],'target_date':target,'estimated_quantity':forecast['quantity']}]
        recent = [m for m in menus if m['menu_id'] in selected['recent_ids']]
        st.title(menu['menu_name'])
        st.caption(f'{target} · 日替わり候補の在庫消化効果')
        with st.container(key='difference'):
            st.subheader('前後2日の予定と、ここが違います')
            st.write(description(menu, recent))
            st.caption('同じ材料でも、味付けや調理法の違いを確認できます。')
        try:
            rows = consumption(menu, data['inventory'], predicted_estimates, target)
            if rows is None:
                st.warning('予測に使える販売実績が未登録のため、在庫消費量は計算できません。')
            else:
                estimate = forecast['quantity']
                chosen = next(r for r in rows if r['材料'] == selected['ingredient'])
                a,b,c = st.columns(3)
                a.metric('想定販売個数', f'{estimate} 食')
                b.metric(chosen['材料']+'の消費量', amount(chosen['想定使用量'], chosen['単位']))
                c.metric('使用後の想定残量', amount(chosen['想定残量'], chosen['単位']))
                if selected.get('targets'):
                    evaluated = rank_targets(menus, selected['targets'], selected['recent_ids'], estimate)
                    evaluated = next(m for m in evaluated if m['menu_id']==menu['menu_id'])
                    st.subheader('希望消費量との比較')
                    evaluation(evaluated)
                with st.expander('販売実績からの予測根拠'):
                    st.caption(f"対象日より前の販売実績 {forecast['training_count']}件を使用。最終実績日: {forecast['training_end']}。天気: {weather}")
                    st.write(forecast['reason'])
                    st.dataframe(forecast['companies'],hide_index=True,width='stretch')
                    st.caption('サンプル実績からの試作予測です。数量は目安で、売り切れによる潜在需要は補正していません。')
                with st.container(key='materials'):
                    st.subheader('材料ごとの使用量')
                    st.dataframe(rows, hide_index=True, width='stretch')
                    st.caption('販売実績から予測した個数をもとにした試算です。期限切れ在庫は除外しています。')
                    if any(r['不足量'] > 0 for r in rows):
                        st.warning('不足する材料があります。仕入れや数量を確認してください。')
        except ValueError as exc:
            st.error(str(exc))
        with st.container(key='detail_recipe'):
            st.subheader('レシピ')
            st.write(menu['recipe_text'])
        existing = next((r for r in current_plan()['plans'] if r['planned_date']==target),None)
        if existing:
            st.caption(f"{target} の現在の予定: {existing['menu_name']} → {menu['menu_name']}")
        else:
            st.info('この日には提供予定がありません。対象日を平日の提供予定日に変更してください。')
        if st.button('このメニューに差し替える',type='primary',disabled=not existing or existing['menu_name']==menu['menu_name'] or menu['menu_type']!='日替わり'):
            try:
                if db:
                    change = db.replace_menu(target,menu['menu_id'],selected.get('original_revision',existing['revision']))
                elif demo_session_only:
                    change = replace_in_plan(current_plan(),target,menu,selected.get('original_menu_name',existing['menu_name']))
                else:
                    change = replace_menu(target,menu,selected.get('original_menu_name',existing['menu_name']))
                st.session_state.plan_notice = f"{target} の予定を「{change['previous_menu_name']}」から「{change['menu_name']}」に差し替えました。"
                del st.session_state.selected_menu
                st.rerun()
            except (ValueError,OSError,RuntimeError) as exc:
                st.error('差し替えできませんでした。予定が別の操作で変更された可能性があります。候補一覧に戻って再検索してください。')
        st.caption('差し替えはSupabaseの共有予定に保存されます。在庫の実数量は変更しません。' if db else ('公開デモの差し替えはこのセッション内だけに保存されます。' if demo_session_only else '差し替えはローカルの日替わり予定に保存されます。在庫の実数量は変更しません。'))
        if st.button('候補一覧に戻る'):
            del st.session_state.selected_menu
            st.rerun()
    else:
        st.title('在庫を活かして、日替わりに変化を。')
        st.caption('消費したい食材から、前後2日の予定とは違う候補を見つけます。')
        ingredients = sorted({i['name'] for m in menus for i in m['ingredients']})
        if not ingredients:
            st.info('レシピを登録すると材料から検索できます。')
        else:
            with st.container(key='search_conditions'):
                st.subheader('1  検索条件')
                a,b = st.columns(2)
                target = a.date_input('対象日', date.today()).isoformat()
                weather = b.selectbox('対象日の天気', ['晴れ','曇り','雨'])
                selected_ingredients = st.multiselect('消費したい材料（複数選択可）', ingredients,
                    default=['鶏もも肉'] if '鶏もも肉' in ingredients else ingredients[:1])
                targets = []
                for name in selected_ingredients:
                    a,b,c = st.columns([2,2,1])
                    a.write(name)
                    default_unit = next(i['unit'] for m in menus for i in m['ingredients'] if i['name']==name)
                    unit_options = [u for u in UNITS if UNITS[u][0]==UNITS[default_unit][0]]
                    unit = c.selectbox('単位',unit_options,index=unit_options.index(default_unit),key=f'target_unit_{name}')
                    quantity = b.number_input('希望消費量',min_value=0.01,value=20000.0 if unit=='g' else 20.0, key=f'target_quantity_v3_{name}')
                    targets.append({'name':name,'quantity':quantity,'unit':unit})
                ingredient = selected_ingredients[0] if selected_ingredients else None
                st.caption('選択した材料をすべて使う候補を表示。メニューの違いと希望消費量への近さを同じ重みで評価します。希望量を超える場合も差として評価します。')
                st.caption('比較範囲: 対象日の前後2日（暦日）。対象日自身は比較から除外します。')
                stocks = [s for s in data['inventory'] if s['name']==ingredient and s['expiration_date'] >= target]
                if stocks:
                    unit = stocks[0]['unit']
                    try:
                        total = sum(convert(s['current_quantity'],s['unit'],unit) for s in stocks)
                        st.caption(f"現在庫 {amount(total,unit)} ｜ 最も近い消費期限 {min(s['expiration_date'] for s in stocks)} （既存データ）")
                    except ValueError as exc:
                        st.error(str(exc))
                else:
                    st.caption('対象日に使用できる在庫データがありません。')
                st.button('候補を検索', type='primary')
            names = {m['menu_id']:m['menu_name'] for m in menus}
            with st.container(key='recent_panel'):
                st.subheader('2  前後2日の日替わり予定')
                plan = current_plan()
                nearby = surrounding_plans(plan['plans'],target)
                # サンプルのローカルIDをSupabaseのIDへ流用しない。名前で対応付ける。
                ids_by_name = {m['menu_name']:m['menu_id'] for m in menus}
                recent_ids = sorted({ids_by_name[r['menu_name']] for r in nearby if r['menu_name'] in ids_by_name})
                if nearby:
                    st.dataframe([{'日付':r['planned_date'],'曜日':r['weekday'],'日替わり':r['menu_name'],'状態':r['status']} for r in nearby],hide_index=True,width='stretch')
                    missing = [r['menu_name'] for r in nearby if r['menu_name'] not in ids_by_name]
                    if missing:
                        st.warning('比較用のレシピ・ベクトルが未登録: '+'、'.join(dict.fromkeys(missing)))
                else:
                    st.info('前後2日に提供予定がありません。暫定サンプルは2026年10月の平日です。')
                st.caption('全企業共通の暫定予定を参照します。土日は提供予定なし。')
                recent = [m for m in menus if m['menu_id'] in recent_ids]
                st.caption(' ／ '.join(m['menu_name'] for m in recent) if recent else '比較可能な予定がないため、材料条件だけで表示します。')
            st.subheader('3  候補メニュー')
            try:
                forecast = predict_sales(data.get('history',[]),data.get('companies',[]),target,weather)
                candidates = rank_targets(menus, targets, recent_ids, None if forecast is None else forecast['quantity'])
                st.caption(f'{"・".join(selected_ingredients)}を使う{len(candidates)}件 · メニューの違い＋希望消費量への近さで優先表示')
                if forecast is None:
                    st.warning('販売実績が未登録のため、希望消費量への近さは未評価です。')
                else:
                    st.metric(f'{target} の予測販売個数（{weather}）', f"{forecast['quantity']} 食")
                    with st.expander('指定日の販売予測の内訳・根拠'):
                        st.caption(f"対象日より前の実績 {forecast['training_count']}件を使用。最終実績日: {forecast['training_end']}")
                        st.write(forecast['reason'])
                        st.dataframe(forecast['companies'],hide_index=True,width='stretch')
                st.caption('各指標は高いほど優先。相違度は前後2日のうち最も似たメニューとの距離です。総合評価は消費量への近さと相違度の平均です。差分は＋が希望量超過、−が不足。評価を比較し、詳細画面で人が差し替えを決定します。')
                ordering = st.selectbox('表示順', ['総合評価が高い順','相違度が高い順','希望消費量に近い順'])
                score_key = {'総合評価が高い順':'priority_score','相違度が高い順':'novelty','希望消費量に近い順':'quantity_fit'}[ordering]
                candidates.sort(key=lambda m:(m[score_key] is None,-(m[score_key] or 0),m['menu_name']))
                if not candidates:
                    st.info('条件に一致する候補がありません。')
                for index,menu in enumerate(candidates, 1):
                    with st.container(key=f"candidate_{menu['menu_id']}"):
                        number, body, action = st.columns([0.5,6,1.5])
                        number.markdown(f'<div class="candidate-number">{index:02}</div>', unsafe_allow_html=True)
                        with body:
                            candidate_text(menu, description(menu,recent))
                            evaluation(menu)
                            if menu['novelty'] is None:
                                st.caption('比較可能な予定がない、またはEmbeddingモデルが異なるため順位は未計算')
                        with action:
                            if st.button('消化量を確認', key=f"detail_{menu['menu_id']}"):
                                st.session_state.selected_menu = {'menu_id':menu['menu_id'],'mode':mode,
                                    'ingredient':ingredient,'target':target,'recent_ids':recent_ids,
                                    'targets':targets,
                                    'weather':weather,
                                    'original_menu_name':next((r['menu_name'] for r in current_plan()['plans'] if r['planned_date']==target),None),
                                    'original_revision':next((r.get('revision',0) for r in current_plan()['plans'] if r['planned_date']==target),0)}
                                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

if page == 'レシピを登録':
    st.title('レシピを登録する')
    st.caption('いつものレシピを貼り付けて、材料や特徴を整理します。')
    input_panel, confirm_panel = st.columns(2)
    st.caption('AIの数量推定を確認・修正してから保存してください。Embeddingは保存時に生成します。')
    with input_panel:
        with st.form('recipe'):
            st.subheader('1  レシピを入力')
            name = st.text_input('メニュー名')
            menu_type = st.selectbox('メニュー区分', ['日替わり', 'レギュラー'])
            servings = st.number_input('何食分のレシピですか？', min_value=1, value=10, step=1)
            recipe = st.text_area('自然文レシピ（何食分か、数量を記載）', height=150)
            analyze = st.form_submit_button('材料・特徴を整理', type='primary')
    if analyze:
        if not name.strip() or not recipe.strip():
            st.error('メニュー名とレシピを入力してください。')
        else:
            try:
                with st.spinner('材料と特徴を抽出しています…'):
                    draft = ai_recipe(name, f'このレシピは{servings}食分です。数量を{servings}で割って1食あたりにしてください。\n'+recipe)
                    draft.update(menu_name=name.strip(), menu_type=menu_type, recipe_text=recipe.strip())
                    st.session_state.draft = draft
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
    if 'draft' in st.session_state:
        draft = st.session_state.draft
        with confirm_panel:
            with st.form('confirm'):
                st.subheader(draft['menu_name'])
                edited = st.data_editor(draft['ingredients'], num_rows='dynamic', hide_index=True)
                features = {k:st.text_input(label, draft[k]) for k,label in [('genre','ジャンル'),('seasoning','味付け'),('cooking_method','調理法'),('richness','こってり／さっぱり')]}
                save = st.form_submit_button('確認してレシピを保存', type='primary')
        if save:
            try:
                if not edited or any(not i['name'].strip() or i['quantity'] <= 0 or i['unit'] not in UNITS for i in edited):
                    raise ValueError('材料名・正の数量・対応する単位を入力してください。')
                if len({i['name'].strip() for i in edited}) != len(edited):
                    raise ValueError('同じ材料は1行にまとめてください。')
                for i in edited:
                    i['name'] = i['name'].strip()
                draft.update(features, ingredients=edited)
                draft['feature_text'] = '、'.join([features[k] for k in features] + [i['name'] for i in edited])
                with st.spinner('ベクトルを生成して保存しています…'):
                    draft['embedding'], draft['embedding_model'] = embed(draft['feature_text'])
                    if db:
                        db.save(draft)
                    else:
                        draft['menu_id'] = max([m['menu_id'] for m in menus], default=0)+1
                        menus.append(dict(draft))
                del st.session_state.draft
                st.success('レシピ・材料・特徴・Embeddingを保存しました。')
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))

    else:
        with confirm_panel:
            with st.container(key='confirm_panel'):
                st.subheader('2  内容を確認して保存')
                st.caption('材料・特徴を整理すると、ここで1食あたりの材料量を確認・修正できます。')
    st.markdown('<div class="bento-soft"><b>登録後のイメージ</b><p>✓ 材料ごとの使用量を保存　✓ 検索用の特徴を保存　✓ 日替わり候補として検索可能</p></div>', unsafe_allow_html=True)

if page == 'レシピ一覧':
    st.title('レシピ一覧')
    st.subheader('登録メニュー')
    st.dataframe([{**{k:m[k] for k in ['menu_name','menu_type','genre','seasoning','cooking_method','embedding_model']},
                   '1食あたりの材料量':'、'.join(f"{i['name']} {amount(i['quantity'],i['unit'])}" for i in m['ingredients'])} for m in menus], hide_index=True)
    st.subheader('既存在庫（参照のみ）')
    st.dataframe(data['inventory'], hide_index=True)
    if mode == 'デモ':
        st.caption('テスト用の固定在庫です。鶏もも肉は多め、その他は約1週間分の目安。必要量の自動計算はしていません。消費期限も架空値です。')
    st.subheader('指定日の販売予測')
    a,b = st.columns(2)
    forecast_date = a.date_input('販売予測を確認する日付',date.today(),key='forecast_date').isoformat()
    forecast_weather = b.selectbox('予測日の天気',['晴れ','曇り','雨'],key='forecast_weather')
    forecast = predict_sales(data.get('history',[]),data.get('companies',[]),forecast_date,forecast_weather)
    if forecast:
        st.metric(f'{forecast_date} の予測販売個数（{forecast_weather}）',f"{forecast['quantity']} 食")
        st.caption(forecast['reason'])
        st.dataframe(forecast['companies'],hide_index=True,width='stretch')
    else:
        st.info('予測に使える販売実績が未登録です。')

if page == '日替わり予定':
    st.title('1か月の日替わり予定')
    plan = current_plan()
    st.caption('2026年10月 · 全企業共通の暫定サンプル')
    st.caption('10/5〜10/16は10種類を1日1種類ずつ配置。予定の作成には関連度を使っていません。')
    st.dataframe([{'提供予定日':r['planned_date'],'曜日':r['weekday'],'メニュー':r['menu_name'],'状態':r['status']} for r in plan['plans']],hide_index=True,width='stretch')
    st.caption('差し替え候補の検索では、対象日の前後2暦日を比較します。対象日の予定は除外します。')
    st.download_button('暫定予定JSONをダウンロード',json.dumps(plan,ensure_ascii=False,indent=2),file_name='sample_menu_plan_2026_10.json',mime='application/json')

if page == '提供履歴':
    import pandas as pd
    st.title('提供履歴')
    st.caption('2026年9月 · 10社合計で1日150〜250食の訪問販売サンプル')
    st.info('架空のサンプルデータです。実績・需要予測ではありません。土日を除き、祝日は通常営業と仮定しています。')
    sample = {'records':data.get('history',[]),'companies':data.get('companies',[])} if db else load_sample()
    selected_weather = st.multiselect('天気', ['晴れ','曇り','雨'],default=['晴れ','曇り','雨'])
    records = [r for r in sample['records'] if r['weather'] in selected_weather]
    a,b,c = st.columns(3)
    a.metric('営業日',f"{len({r['served_date'] for r in records})} 日")
    b.metric('訪問先',f"{len({r['company_id'] for r in records})} 社")
    c.metric('販売食数',f"{sum(r['sales_quantity'] for r in records):,} 食")
    if records:
        frame = pd.DataFrame(records)
        st.subheader('日別・企業別の販売食数')
        st.line_chart(frame.pivot(index='served_date',columns='company_name',values='sales_quantity'))
        st.subheader('企業別・曜日別の平均販売食数')
        weekdays = frame.groupby(['company_name','weekday'])['sales_quantity'].mean().unstack().reindex(columns=['月','火','水','木','金']).round(1)
        st.dataframe(weekdays, width='stretch')
        st.subheader('企業別・天気別の平均販売食数')
        weather_means = frame.groupby(['company_name','weather'])['sales_quantity'].mean().unstack().reindex(columns=['晴れ','曇り','雨']).round(1)
        st.dataframe(weather_means,width='stretch')
        st.caption('平均には曜日・休み・第1週の影響も含まれます。雨の増加係数は明細で確認できます。')
        st.subheader('提供履歴の明細')
        st.dataframe(frame[['served_date','weekday','weather','company_name','work_type','menu_name','normal_quantity','sales_quantity','special_factor','weather_factor','reason']].rename(columns={
            'served_date':'提供日','weekday':'曜日','company_name':'訪問先企業','menu_name':'日替わり',
            'weather':'天気','work_type':'職種','weather_factor':'天気係数',
            'normal_quantity':'通常時の食数','sales_quantity':'販売食数','special_factor':'特別減少係数','reason':'理由'}),hide_index=True,width='stretch')
    st.caption('水曜減少: 青葉製作所・みなと物流は20%。第1週（9/1〜9/7）減少: ひかり商事・東都システム・さくら企画・北町サービスは40%。')
    st.caption('現場職: みなと物流・北町サービス・中央設備は雨の日に1.3倍。天気は同一エリアを想定した架空データです。')
    st.caption('テストの営業規模に合わせ、企業別の増減を残しながら日別の全体量を調整しています。')
    st.download_button('サンプルJSONをダウンロード',json.dumps(sample,ensure_ascii=False,indent=2),file_name='sample_history_2026_09.json',mime='application/json')
