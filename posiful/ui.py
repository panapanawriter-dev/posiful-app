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
    [data-testid="stVerticalBlock"] {gap:24px;}
    [data-testid="stVerticalBlockBorderWrapper"]>div {border-color:transparent!important;border-radius:16px!important;}
    [data-testid="stForm"],.st-key-search_conditions,.st-key-detail_recipe,.st-key-materials,.st-key-confirm_panel {background:white;border:0!important;border-radius:16px;padding:24px;}
    .st-key-recent_panel,.st-key-difference {background:var(--bento-soft);padding:24px;border-radius:16px;}
    div[class*="st-key-candidate_"] {background:white;border-radius:14px;padding:20px;}
    .stButton button,.stFormSubmitButton button {border-radius:7px;min-height:40px;}
    button[kind="primary"],button[kind="primaryFormSubmit"] {background:var(--bento-green);border-color:var(--bento-green);color:white;}
    [data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="textarea"] {background:var(--bento-bg);border-color:transparent;border-radius:8px;}
    [data-baseweb="tag"] {background:var(--bento-green)!important;}
    [data-testid="stMetric"] {padding:24px;background:white;border-radius:16px;}
    [data-testid="stMetricValue"] {color:var(--bento-green);font-size:36px;}
    .candidate-number {color:var(--bento-green);font-size:26px;font-weight:700;}
    .evaluation-badge {display:inline-flex;align-items:center;gap:16px;padding:12px 20px;border-radius:14px;border:2px solid; margin:4px 0 12px;}
    .evaluation-grade {font-size:44px;font-weight:800;line-height:1.1;white-space:nowrap;}
    .evaluation-score {font-size:16px;font-weight:600;white-space:nowrap;}
    .evaluation-a {color:#145b38;background:#e5f5e9;border-color:#83bc94;}
    .evaluation-b {color:#174d80;background:#e8f2fc;border-color:#85b5df;}
    .evaluation-c {color:#82400c;background:#fff1de;border-color:#e4ad65;}
    .candidate-tags {color:var(--bento-green);font-size:12px;}
    .candidate-description {color:var(--bento-muted);font-size:13px;line-height:1.6;}
    .bento-soft {background:var(--bento-soft);padding:24px;border-radius:16px;}
    @media(max-width:768px) {.bento-brand{font-size:18px}.bento-status{font-size:11px}[data-testid="stMainBlockContainer"]{padding:105px 20px 32px;}.bento-header{padding:20px;}}
    </style><div class="bento-header"><span class="bento-brand">BENTO / 献立サポート</span><span class="bento-status">C案 · 試作版</span></div>''', unsafe_allow_html=True)


def description(menu, recent):
    if not recent:
        return '前後2日に比較可能な予定がありません。'
    differences = []
    for key,label in [('genre','ジャンル'),('seasoning','味付け'),('cooking_method','調理法')]:
        previous = list(dict.fromkeys(m[key] for m in recent))
        if menu[key] not in previous:
            differences.append(f"{label}: {'・'.join(previous)} → {menu[key]}")
    return ' ／ '.join(differences) if differences else '前後2日の予定に似た特徴の献立があります。'


def candidate_text(menu, explanation):
    st.subheader(menu['menu_name'])
    st.markdown('<div class="candidate-tags">'+escape(' / '.join(menu[k] for k in ['genre','seasoning','cooking_method']))+'</div>'
                +'<div class="candidate-description">'+escape(explanation)+'</div>', unsafe_allow_html=True)


def amount(value, unit):
    if unit == 'g' and abs(value) >= 1000:
        return f'{value/1000:,.1f} kg'
    if unit == 'ml' and abs(value) >= 1000:
        return f'{value/1000:,.1f} L'
    return f'{value:,.1f}'.rstrip('0').rstrip('.')+' '+unit


def evaluation(menu):
    """判断材料を独立した指標として表示する。"""
    fit = menu['quantity_fit']
    difference = None if menu['novelty'] is None else menu['novelty']/2
    total = menu['priority_score']
    a,b,c = st.columns(3)
    a.write('希望消費量への近さ')
    a.write('未評価' if fit is None else f'{fit*100:.1f} / 100')
    b.write('前後2日のメニューとの相違度')
    b.write('未評価' if difference is None else f'{difference:.1f} / 100')
    c.write('総合評価' if fit is not None and difference is not None else '参考評価（片方のみ）')
    if total is None:
        c.write('未評価')
    else:
        score = round(total*100, 1)
        grade = next((label for threshold,label in [(90,'A+'),(80,'A'),(70,'A-'),
                     (60,'B+'),(50,'B'),(40,'B-'),(30,'C+'),(20,'C')] if score >= threshold), 'C-')
        c.markdown(f'<div class="evaluation-badge evaluation-{grade[0].lower()}">'
                   f'<span class="evaluation-grade">{grade}</span>'
                   f'<span class="evaluation-score">{score:.1f}<br>/ 100</span></div>', unsafe_allow_html=True)
    with st.expander('文字評価の基準'):
        st.caption('A+: 90以上 ／ A: 80以上 ／ A-: 70以上 ／ B+: 60以上 ／ B: 50以上 ／ B-: 40以上 ／ C+: 30以上 ／ C: 20以上 ／ C-: 20未満')
        st.caption('検索の評価値に基づく目安です。片方の指標のみの場合は参考評価になります。')
    st.table([{'材料':r['材料'],
               '希望消費量':amount(r['希望消費量'],r['単位']),
               '予測消費量':'未評価' if r['予測消費量'] is None else amount(r['予測消費量'],r['単位']),
               '希望との差':'未評価' if r['差分'] is None else ('+' if r['差分']>0 else '')+amount(r['差分'],r['単位'])}
              for r in menu['target_comparisons']])
