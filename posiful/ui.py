"""Figma C案の色・カード・画面共通レイアウト。"""
from html import escape
import streamlit as st


def setup():
    st.markdown('''<style>
    :root {--bento-bg:#f6f7f2;--bento-green:#237355;--bento-ink:#203a32;--bento-muted:#697b73;--bento-soft:#eaf3ed;}
    .stApp {background:var(--bento-bg);color:var(--bento-ink);font-family:'Noto Sans JP','Yu Gothic',sans-serif;}
    [data-testid="stHeader"] {background:transparent;height:0;}
    [data-testid="stMainBlockContainer"] {max-width:1128px;padding:113px 32px 40px;}
    .bento-header {position:fixed;top:0;left:0;right:0;height:81px;z-index:999;background:white;display:flex;align-items:center;justify-content:space-between;padding:24px;box-sizing:border-box;}
    .bento-brand {font-size:22px;font-weight:700;color:var(--bento-green);}
    .bento-status {font-size:13px;color:var(--bento-muted);}
    [data-testid="stSidebar"] {background:white;min-width:216px!important;max-width:216px!important;top:81px;}
    [data-testid="stSidebarUserContent"] {padding:24px 0;}
    [data-testid="stToolbar"] {display:none;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label p {white-space:nowrap;font-size:16px;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {color:var(--bento-green);font-weight:700;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label>div:first-child {display:none;}
    [data-testid="stSidebar"] [data-testid="stSidebarHeader"] {display:none;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {padding:8px 0;}
    h1 {font-size:28px!important;font-weight:700!important;color:var(--bento-ink)!important;padding:0!important;margin:0 0 16px!important;}
    h3 {font-size:18px!important;font-weight:700!important;color:var(--bento-ink)!important;padding:0!important;}
    .stCaption p {color:var(--bento-muted);font-size:13px;}
    [data-testid="stVerticalBlock"] {gap:20px;}
    [data-testid="stVerticalBlockBorderWrapper"]>div {border-color:transparent!important;border-radius:16px!important;}
    [data-testid="stForm"],.st-key-search_conditions,.st-key-detail_recipe,.st-key-materials,.st-key-confirm_panel {background:white;border:0!important;border-radius:16px;padding:24px;}
    .st-key-recent_panel,.st-key-difference {background:var(--bento-soft);padding:24px;border-radius:16px;}
    div[class*="st-key-candidate_"] {background:white;border-radius:14px;padding:20px 20px 22px;}
    div[class*="st-key-candidate_"] [data-testid="stVerticalBlock"] {gap:14px;}
    div[class*="st-key-candidate_"] h3 {line-height:1.5!important;margin-bottom:8px!important;}
    .stButton button,.stFormSubmitButton button {border-radius:7px;min-height:40px;}
    button[kind="primary"],button[kind="primaryFormSubmit"] {background:var(--bento-green);border-color:var(--bento-green);color:white;}
    [data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="textarea"] {background:var(--bento-bg);border-color:transparent;border-radius:8px;}
    [data-baseweb="tag"] {background:var(--bento-green)!important;}
    [data-testid="stMetric"] {padding:24px;background:white;border-radius:16px;}
    [data-testid="stMetricValue"] {color:var(--bento-green);font-size:36px;}
    .candidate-number {color:var(--bento-green);font-size:20px;font-weight:700;white-space:nowrap;}
    .evaluation-row {display:flex;align-items:center;gap:14px;margin:12px 0 2px;min-height:56px;}
    .evaluation-label {font-size:15px;font-weight:600;color:var(--bento-ink);white-space:nowrap;}
    .evaluation-badge {display:inline-flex;align-items:center;gap:14px;padding:6px 14px;border-radius:12px;border:2px solid;}
    .evaluation-grade {font-size:36px;font-weight:800;line-height:1.1;white-space:nowrap;}
    .evaluation-score {font-size:16px;font-weight:600;white-space:nowrap;}
    .evaluation-a {color:#145b38;background:#e5f5e9;border-color:#83bc94;}
    .evaluation-b {color:#174d80;background:#e8f2fc;border-color:#85b5df;}
    .evaluation-c {color:#82400c;background:#fff1de;border-color:#e4ad65;}
    .candidate-tags {color:var(--bento-green);font-size:12px;}
    .candidate-description {color:var(--bento-muted);font-size:13px;line-height:1.6;}
    .bento-soft {background:var(--bento-soft);padding:24px;border-radius:16px;}
    @media(max-width:768px) {.bento-brand{font-size:18px}.bento-status{font-size:11px}[data-testid="stMainBlockContainer"]{padding:105px 20px 32px;}.bento-header{padding:20px;}}
    </style><div class="bento-header"><span class="bento-brand">BENTO / 献立サポート</span></div>''', unsafe_allow_html=True)


def description(menu, recent):
    if not recent:
        return '前後1営業日に比較可能な予定がありません。'
    differences = []
    for key,label in [('genre','ジャンル'),('seasoning','味付け'),('cooking_method','調理法')]:
        previous = list(dict.fromkeys(m[key] for m in recent))
        if menu[key] not in previous:
            differences.append(f"{label}: {'・'.join(previous)} → {menu[key]}")
    return ' ／ '.join(differences) if differences else '前後1営業日の予定に似た特徴の献立があります。'


def candidate_text(menu, explanation=None):
    st.subheader(menu['menu_name'])
    html = '<div class="candidate-tags">'+escape(' / '.join(menu[k] for k in ['genre','seasoning','cooking_method']))+'</div>'
    if explanation:
        html += '<div class="candidate-description">'+escape(explanation)+'</div>'
    st.markdown(html, unsafe_allow_html=True)


STATUS_LABELS = {'暫定': '暫定メニュー'}


def status_label(status):
    """保存された値は変えず、表示のときだけ分かりやすい言葉にする。"""
    return STATUS_LABELS.get(status, status)


def grade_guide():
    with st.expander('おススメ度の見方'):
        st.caption('A+: 90以上 ／ A: 80以上 ／ A-: 70以上 ／ B+: 60以上 ／ B: 50以上 ／ B-: 40以上 ／ C+: 30以上 ／ C: 20以上 ／ C-: 20未満')


def amount(value, unit):
    if unit == 'g' and abs(value) >= 1000:
        return f'{value/1000:,.1f} kg'
    if unit == 'ml' and abs(value) >= 1000:
        return f'{value/1000:,.1f} L'
    return f'{value:,.1f}'.rstrip('0').rstrip('.')+' '+unit


def _score_badge(menu):
    fit = menu['quantity_fit']
    difference = None if menu['novelty'] is None else menu['novelty']/2
    total = menu['priority_score']
    label = 'おススメ度' if fit is not None and difference is not None else 'おススメ度（参考）'
    if total is None:
        st.markdown(f'<div class="evaluation-row"><span class="evaluation-label">{label}</span><span>未評価</span></div>', unsafe_allow_html=True)
        return
    score = round(total*100, 1)
    grade = next((label for threshold,label in [(90,'A+'),(80,'A'),(70,'A-'),
                 (60,'B+'),(50,'B'),(40,'B-'),(30,'C+'),(20,'C')] if score >= threshold), 'C-')
    st.markdown(f'<div class="evaluation-row"><span class="evaluation-label">{label}</span>'
                f'<div class="evaluation-badge evaluation-{grade[0].lower()}">'
                f'<span class="evaluation-grade">{grade}</span>'
                f'<span class="evaluation-score">{score:.1f}<br>/ 100</span></div></div>', unsafe_allow_html=True)


def evaluation(menu, show_targets=True):
    """おススメ度のバッジを表示する。材料の表はバッジの右に並べる。"""
    if not show_targets:
        _score_badge(menu)
        return
    badge, table = st.columns([2, 5], vertical_alignment='center')
    with badge:
        _score_badge(menu)
    with table:
        st.dataframe([{'材料':r['材料'],
                       '希望消費量':amount(r['希望消費量'],r['単位']),
                       '予測消費量':'未評価' if r['予測消費量'] is None else amount(r['予測消費量'],r['単位']),
                       '希望との差':'未評価' if r['差分'] is None else ('+' if r['差分']>0 else '')+amount(r['差分'],r['単位'])}
                      for r in menu['target_comparisons']], hide_index=True, width='stretch')
