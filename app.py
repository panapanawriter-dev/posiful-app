import json
import os
from datetime import date
from pathlib import Path

import streamlit as st
from posiful.core import demo_data, rank, consumption, UNITS, convert
from posiful.ui import setup, description, candidate_text, amount, evaluation, grade_guide, status_label
from posiful.history import load_sample, surrounding_plans
from posiful.history import load_menu_plan as load_base_plan
from posiful.plan_store import load_menu_plan, replace_menu
from posiful.demo_plan import replace_in_plan
from posiful.forecast import predict_sales
from posiful.search import rank_targets, evaluate_current
from posiful.api import Database, ai_recipe, embed
from posiful.cloud import sample_payload
from posiful.recipe import validate_ingredients, comparison_text, COMPARISON_FIELDS
from posiful.demo_embeddings import apply_demo_embeddings
from posiful.ingredient_names import normalize_rows
from posiful.weather import fetch_fukuoka, forecast_for
from posiful.settings import configure


@st.cache_data(ttl=1800, show_spinner=False)
def cached_fukuoka_weather():
    return fetch_fukuoka()


def weather_input(target, label, key, container=st, fallback='晴れ'):
    # 表示は入力欄が先。予報反映はウィジェット生成前に処理する。
    weather_slot = container.empty()
    if container.button('福岡市の天気を調べる', key=key+'_fetch'):
        try:
            payload = cached_fukuoka_weather()
            st.session_state[key+'_forecast'] = payload
            forecast = forecast_for(payload, target)
            if forecast and forecast['weather'] and not forecast['reference_only']:
                st.session_state[key+'_'+target] = forecast['weather']
        except RuntimeError as exc:
            container.warning(str(exc))
    container.caption('天気予報：[Open-Meteo](https://open-meteo.com/)')
    payload = st.session_state.get(key+'_forecast')
    forecast = forecast_for(payload, target) if payload else None
    if forecast:
        widget_key = key+'_'+target
        if widget_key not in st.session_state and forecast['weather'] and not forecast['reference_only']:
            st.session_state[widget_key] = forecast['weather']
        if forecast['reference_only']:
            container.caption('8日以上先の参考予報です。販売予測の天気はご自身で選んでください。')
    elif payload:
        container.caption('指定日は予報の取得範囲外です。過去の天気ではなく、ご自身で選んだ天気の想定を使います。')
    selected = weather_slot.selectbox(label, ['晴れ','曇り','雨'], index=['晴れ','曇り','雨'].index(fallback), key=key+'_'+target,
                                   format_func=lambda value: {'晴れ':'☀️ 晴れ', '曇り':'☁️ 曇り', '雨':'🌧️ 雨'}[value],
                                   help='販売予測に使う天気です。取得した予報から変更できます。')
    if forecast and forecast['weather'] and selected != forecast['weather']:
        container.caption('取得した予報とは異なる天気の想定で予測しています。')
    return selected

# .env はローカル設定のみ。シェル式として実行しない。
if Path('.env').exists():
    for line in Path('.env').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

st.set_page_config(page_title='Posiful | 日替わり提案', page_icon='🍱', layout='wide')
# Cloud SecretsをAPI層へ渡す。設定なしの場合は通常の共有版を使用する。
try:
    demo_session_only = configure(st.secrets)
except st.errors.StreamlitSecretNotFoundError:
    demo_session_only = configure({})
setup()
main_pages = ['日替わりを探す', 'レシピを登録']
admin_pages = ['レシピ一覧', '日替わり予定', '提供履歴']
if 'pending_navigation' in st.session_state:
    st.session_state['navigation'] = st.session_state.pop('pending_navigation')
if st.session_state.get('navigation') not in main_pages + admin_pages:
    st.session_state['navigation'] = main_pages[0]
st.session_state['main_navigation'] = st.session_state['navigation'] if st.session_state['navigation'] in main_pages else None

def select_main_page():
    st.session_state['navigation'] = st.session_state['main_navigation']

def select_admin_page(value):
    st.session_state['navigation'] = value

st.sidebar.radio('画面', main_pages, index=None, label_visibility='collapsed',
                 key='main_navigation', on_change=select_main_page)
with st.sidebar.expander('管理メニュー', expanded=False):
    for admin_page in admin_pages:
        st.button(admin_page, key='admin_'+admin_page, width='stretch',
                  on_click=select_admin_page, args=(admin_page,))
page = st.session_state['navigation']
# 通常起動はSupabase。公開サンプル専用の明示設定だけは維持する。
mode = 'デモ' if demo_session_only else 'Supabase'
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
    apply_demo_embeddings(data['menus'])
else:
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_PUBLISHABLE_KEY'):
        st.warning('SupabaseのURLと公開キーを設定してください。CloudではSettings → Secrets、ローカルでは.envに設定します。')
        st.stop()
    db = Database(None)
    try:
        data = db.load()
    except RuntimeError as exc:
        st.error(str(exc))
        st.info('共有データを取得できません。Supabaseの接続設定・共有用RPCを確認してください。')
        st.stop()
    if not data['menus']:
        st.info('レシピがまだ登録されていません。「レシピを登録」から追加してください。')


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
        try:
            rows = consumption(menu, data['inventory'], predicted_estimates, target)
            if rows is None:
                st.warning('予測に使える販売実績が未登録のため、在庫消費量は計算できません。')
            else:
                estimate = forecast['quantity']
                evaluated = None
                if selected.get('targets'):
                    evaluated = next(m for m in rank_targets(menus, selected['targets'], selected['recent_ids'], estimate)
                                     if m['menu_id']==menu['menu_id'])
                a,b,c = st.columns(3)
                a.metric('予想販売数（目安）', f'{estimate} 食')
                comparisons = evaluated['target_comparisons'] if evaluated else []
                if comparisons:
                    for index, item in enumerate(comparisons):
                        if index:
                            _,b,c = st.columns(3)
                        b.metric(item['材料']+'の消費量', amount(item['予測消費量'],item['単位']))
                        difference = item['差分']
                        c.metric('希望との差', ('+' if difference>0 else '')+amount(difference,item['単位']))
                        b.caption('希望消費量：'+amount(item['希望消費量'],item['単位']))
                    st.caption('希望との差：＋は希望より多く消費、−は希望より少なく消費します。')
                else:
                    chosen = next(r for r in rows if r['材料'] == selected['ingredient'])
                    b.metric(chosen['材料']+'の消費量', amount(chosen['想定使用量'], chosen['単位']))
                    c.metric('希望との差', '希望量未設定')
                if evaluated:
                    evaluation(evaluated, show_targets=False)
                if any(r['不足量'] > 0 for r in rows):
                    with st.expander('仕込み前の在庫確認'):
                        st.warning('不足する材料があります。仕入れや数量を確認してください。')
        except ValueError as exc:
            st.error(str(exc))
        with st.container(border=True):
            st.markdown('**前後1営業日のメニュー**')
            nearby_plans = surrounding_plans(current_plan()['plans'], target)
            if nearby_plans:
                for planned in nearby_plans:
                    st.write(f"{planned['planned_date']}　{planned['menu_name']}")
            else:
                st.caption('前後1営業日に提供予定がありません。')
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
        ingredients = sorted({i['name'] for m in menus for i in m['ingredients']})
        if not ingredients:
            st.info('レシピを登録すると材料から検索できます。')
        else:
            with st.container(key='search_conditions'):
                st.subheader('1  検索条件')
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
                a,b = st.columns(2)
                target = a.date_input('対象日', date.today()).isoformat()
                weather = weather_input(target, '対象日の天気', 'search_weather', b)
                ingredient = selected_ingredients[0] if selected_ingredients else None
                stocks = [s for s in data['inventory'] if s['name']==ingredient and s['expiration_date'] >= target]
                if stocks:
                    unit = stocks[0]['unit']
                    try:
                        total = sum(convert(s['current_quantity'],s['unit'],unit) for s in stocks)
                        st.caption(f"現在庫 {amount(total,unit)} ｜ 最も近い消費期限 {min(s['expiration_date'] for s in stocks)}")
                    except ValueError as exc:
                        st.error(str(exc))
                else:
                    st.caption('対象日に使用できる在庫データがありません。')
                st.button('候補を検索', type='primary')
            names = {m['menu_id']:m['menu_name'] for m in menus}
            with st.container(key='recent_panel'):
                st.subheader('2  前後1営業日の日替わり予定')
                plan = current_plan()
                nearby = surrounding_plans(plan['plans'],target)
                # サンプルのローカルIDをSupabaseのIDへ流用しない。名前で対応付ける。
                ids_by_name = {m['menu_name']:m['menu_id'] for m in menus}
                recent_ids = sorted({ids_by_name[r['menu_name']] for r in nearby if r['menu_name'] in ids_by_name})
                if nearby:
                    st.dataframe([{'日付':r['planned_date'],'曜日':r['weekday'],'日替わり':r['menu_name'],'メニューの扱い':status_label(r['status'])} for r in nearby],hide_index=True,width='stretch')
                    missing = [r['menu_name'] for r in nearby if r['menu_name'] not in ids_by_name]
                    if missing:
                        st.warning('比較用のレシピ・ベクトルが未登録: '+'、'.join(dict.fromkeys(missing)))
                else:
                    st.info('前後1営業日に提供予定がありません。現在の予定表は2026年10月の平日分のみです。')
                recent = [m for m in menus if m['menu_id'] in recent_ids]
            st.subheader('3  候補メニュー')
            try:
                forecast = predict_sales(data.get('history',[]),data.get('companies',[]),target,weather)
                candidates = rank_targets(menus, targets, recent_ids, None if forecast is None else forecast['quantity'])
                st.caption(f'{"・".join(selected_ingredients)}を使う{len(candidates)}件')
                if forecast is None:
                    st.warning('販売実績が未登録のため、希望消費量への近さは未評価です。')
                    grade_guide()
                else:
                    metric_column, guide_column = st.columns([1,2], vertical_alignment='center')
                    metric_column.metric(f'{target} の予測販売個数', f"{forecast['quantity']} 食")
                    with guide_column:
                        grade_guide()
                current_plan_row = next((r for r in plan['plans'] if r['planned_date']==target), None)
                current_menu = next((m for m in menus if current_plan_row and m['menu_name']==current_plan_row['menu_name']), None)
                if current_menu:
                    baseline = evaluate_current(current_menu, targets, recent, None if forecast is None else forecast['quantity'])
                    with st.container(key='candidate_current'):
                        st.subheader('現在の予定メニュー')
                        _, body, _ = st.columns([1,6,1.5])
                        with body:
                            candidate_text(baseline)
                            evaluation(baseline)
                    candidates = [m for m in candidates if m['menu_id'] != current_menu['menu_id']]
                    if baseline['priority_score'] is not None and baseline['novelty'] is not None and baseline['quantity_fit'] is not None:
                        comparable = [m for m in candidates if m['priority_score'] is not None and m['novelty'] is not None and m['quantity_fit'] is not None]
                        if comparable and all(m['priority_score'] <= baseline['priority_score'] for m in comparable):
                            st.info('評価できる差し替え候補は、現在の予定を上回っていません。現在の予定のままにする選択もできます。')
                elif current_plan_row:
                    st.info('現在の予定メニューはレシピ未登録のため評価できません。')
                else:
                    st.info('対象日に現在の提供予定がありません。')
                candidates.sort(key=lambda m:(m['priority_score'] is None,-(m['priority_score'] or 0),m['menu_name']))
                if not candidates:
                    st.info('条件に一致する候補がありません。')
                for index,menu in enumerate(candidates, 1):
                    with st.container(key=f"candidate_{menu['menu_id']}"):
                        number, body, action = st.columns([1,6,1.5])
                        number.markdown(f'<div class="candidate-number">候補{index:02}</div>', unsafe_allow_html=True)
                        with body:
                            candidate_text(menu)
                            evaluation(menu)
                            if menu['novelty'] is None:
                                st.caption('前後の予定と比べられないため、おススメ度は参考です。')
                        with action:
                            if st.button('消化量を確認', key=f"detail_{menu['menu_id']}", width='stretch'):
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
    st.caption('レシピ全体の量から、1食分の材料量を計算します。')
    with input_panel:
        with st.form('recipe'):
            st.subheader('1  登録するレシピ')
            name = st.text_input('メニュー名')
            menu_type = st.selectbox('メニュー区分', ['日替わり', 'レギュラー'])
            servings = st.number_input('何食分のレシピですか？', min_value=1, value=10, step=1)
            recipe = st.text_area('レシピ（材料と量を書いてください）', height=150)
            analyze = st.form_submit_button('材料を読み取る', type='primary')
    if analyze:
        st.session_state.pop('draft', None)
        if not name.strip() or not recipe.strip():
            st.error('メニュー名とレシピを入力してください。')
        else:
            try:
                with st.spinner('材料を読み取っています…'):
                    draft = ai_recipe(name, recipe, servings=servings)
                    known_names = [i['name'] for m in menus for i in m['ingredients']] + [i['name'] for i in data['inventory']]
                    draft['ingredients'], name_notes = normalize_rows(draft['ingredients'], known_names, merge=True)
                    draft['review_notes'] = draft.get('review_notes', []) + name_notes
                    draft.update(menu_name=name.strip(), menu_type=menu_type, recipe_text=recipe.strip())
                    st.session_state.draft = draft
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
    if 'draft' in st.session_state:
        draft = st.session_state.draft
        with confirm_panel:
            for note in draft.get('review_notes', []):
                st.warning(note)
            with st.expander('レシピ全体の材料量'):
                st.caption(f"{draft.get('servings', 1)}食分の合計")
                st.dataframe(draft.get('batch_ingredients', draft['ingredients']), hide_index=True)
            with st.form('confirm'):
                st.subheader(draft['menu_name'])
                st.caption('以下は1食あたりの材料量です。内容を確認・修正してください。')
                edited = st.data_editor(draft['ingredients'], num_rows='dynamic', hide_index=True,
                    column_config={'name': st.column_config.TextColumn('材料名', required=True),
                                   'quantity': st.column_config.NumberColumn('1食あたりの数量', min_value=0.0, format='%.3f', required=True),
                                   'unit': st.column_config.SelectboxColumn('単位', options=['g','kg','ml','L','個'], required=True)})
                features = {k:st.text_input(label, draft[k]) for k,label in [('genre','ジャンル'),('seasoning','味付け'),('cooking_method','調理法'),('richness','こってり／さっぱり')]}
                for key, label in COMPARISON_FIELDS:
                    if key not in features:
                        features[key] = st.text_input(label, draft.get(key, ''))
                save = st.form_submit_button('レシピを保存', type='primary')
        if save:
            try:
                known_names = [i['name'] for m in menus for i in m['ingredients']] + [i['name'] for i in data['inventory']]
                edited, name_notes = normalize_rows(edited, known_names)
                edited = validate_ingredients(edited)
                for note in name_notes:
                    st.info(note)
                draft.update(features, ingredients=edited)
                draft['comparison_updated'] = True
                draft['feature_text'] = comparison_text(features)
                with st.spinner('保存しています…'):
                    draft['embedding'], draft['embedding_model'] = embed(draft['feature_text'])
                    if db:
                        db.save(draft)
                    else:
                        existing_recipe = next((m for m in menus if m['menu_id']==draft.get('menu_id')), None)
                        if existing_recipe:
                            existing_recipe.update(dict(draft))
                        else:
                            draft['menu_id'] = max([m['menu_id'] for m in menus], default=0)+1
                            menus.append(dict(draft))
                del st.session_state.draft
                st.success('レシピを保存しました。')
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))

    else:
        with confirm_panel:
            with st.container(key='confirm_panel'):
                st.subheader('2  登録内容の確認')
                st.caption('材料を読み取ると、ここで1食あたりの材料量を確認・修正できます。')

if page == 'レシピ一覧':
    st.title('レシピ一覧')
    if menus and mode == 'デモ':
        recipe_id = st.selectbox('特徴を更新するレシピ', [m['menu_id'] for m in menus],
                                format_func=lambda value: next(m['menu_name'] for m in menus if m['menu_id']==value))
        if st.button('このレシピの特徴を読み取り直す'):
            original = next(m for m in menus if m['menu_id']==recipe_id)
            try:
                with st.spinner('特徴を読み取っています…'):
                    source = f"登録済みジャンル：{original['genre']}。\n{original['recipe_text']}"
                    extracted = ai_recipe(original['menu_name'], source, servings=original.get('servings',1))
                    extracted.update(menu_id=original['menu_id'], menu_name=original['menu_name'],
                                     menu_type=original['menu_type'], recipe_text=original['recipe_text'],
                                     ingredients=[dict(i) for i in original['ingredients']])
                    extracted['review_notes'] = ['材料と1食分の量はそのままです。特徴を確認してください。']
                    st.session_state.draft = extracted
                    st.session_state['pending_navigation'] = 'レシピを登録'
                    st.rerun()
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
    st.subheader('登録メニュー')
    st.dataframe([{'メニュー名':m['menu_name'],'区分':m['menu_type'],'ジャンル':m['genre'],'味付け':m['seasoning'],'調理法':m['cooking_method'],
                   '1食あたりの材料量':'、'.join(f"{i['name']} {amount(i['quantity'],i['unit'])}" for i in m['ingredients'])} for m in menus], hide_index=True)
    with st.expander('管理データ：在庫・販売予測', expanded=False):
        st.subheader('在庫')
        st.dataframe([{'材料名':i.get('name'),'在庫量':i.get('current_quantity'),'単位':i.get('unit'),'消費期限':i.get('expiration_date')} for i in data['inventory']], hide_index=True)
        st.subheader('指定日の販売予測')
        a,b = st.columns(2)
        forecast_date = a.date_input('販売予測を確認する日付',date.today(),key='forecast_date').isoformat()
        forecast_weather = weather_input(forecast_date, '予測日の天気', 'forecast_weather', b)
        forecast = predict_sales(data.get('history',[]),data.get('companies',[]),forecast_date,forecast_weather)
        if forecast:
            st.columns([1,2])[0].metric(f'{forecast_date} の予測販売個数',f"{forecast['quantity']} 食")
        else:
            st.info('予測に使える販売実績が未登録です。')

if page == '日替わり予定':
    st.title('1か月の日替わり予定')
    plan = current_plan()
    st.caption('2026年10月 · 全企業共通の暫定メニュー')
    st.dataframe([{'提供日':r['planned_date'],'曜日':r['weekday'],'日替わり':r['menu_name'],'メニューの扱い':status_label(r['status'])} for r in plan['plans']],hide_index=True,width='stretch')
    st.download_button('予定表をダウンロード',json.dumps(plan,ensure_ascii=False,indent=2),file_name='sample_menu_plan_2026_10.json',mime='application/json')

if page == '提供履歴':
    import pandas as pd
    st.title('提供履歴')
    st.caption('2026年9月 · 訪問販売の実績(10社合計)')
    st.info('実際の販売ではない、サンプルのデータです。')
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
        weekdays = frame.groupby(['company_name','weekday'])['sales_quantity'].mean().unstack().reindex(columns=['月','火','水','木','金']).round(1).rename_axis(index='企業名')
        st.dataframe(weekdays, width='stretch')
        st.subheader('企業別・天気別の平均販売食数')
        weather_means = frame.groupby(['company_name','weather'])['sales_quantity'].mean().unstack().reindex(columns=['晴れ','曇り','雨']).round(1).rename_axis(index='企業名')
        st.dataframe(weather_means,width='stretch')
        st.subheader('提供履歴の明細')
        st.dataframe(frame[['served_date','weekday','weather','company_name','work_type','menu_name','normal_quantity','sales_quantity','reason']].rename(columns={
            'served_date':'提供日','weekday':'曜日','company_name':'企業名','menu_name':'日替わり',
            'weather':'天気','work_type':'職種',
            'normal_quantity':'通常時の食数','sales_quantity':'販売食数','reason':'理由'}),hide_index=True,width='stretch')
    st.download_button('履歴をダウンロード',json.dumps(sample,ensure_ascii=False,indent=2),file_name='sample_history_2026_09.json',mime='application/json')
