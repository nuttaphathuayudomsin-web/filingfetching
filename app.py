import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import time
import re
from datetime import datetime

# ── Page config ─────────────────────────────────────────────
st.set_page_config(
    page_title="SEC DR Filing Monitor",
    page_icon="📋",
    layout="wide"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans Thai', sans-serif;
}
.block-container { padding-top: 2rem; padding-bottom: 2rem; }

/* Header */
.app-header {
    background: linear-gradient(135deg, #1a3a5c 0%, #0d2137 100%);
    border-radius: 12px;
    padding: 28px 36px;
    margin-bottom: 24px;
    border-left: 5px solid #3498db;
}
.app-header h1 { color: white; margin: 0; font-size: 1.8rem; font-weight: 600; }
.app-header p  { color: #a8c4de; margin: 6px 0 0; font-size: 0.95rem; }

/* Metric cards */
.metric-row { display: flex; gap: 14px; margin-bottom: 20px; flex-wrap: wrap; }
.metric-card {
    flex: 1; min-width: 140px;
    background: white;
    border-radius: 10px;
    padding: 18px 20px;
    border-top: 4px solid;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.metric-card .num  { font-size: 2.2rem; font-weight: 700; line-height: 1; font-family: 'IBM Plex Mono', monospace; }
.metric-card .lbl  { font-size: 0.78rem; color: #666; margin-top: 4px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
.card-total   { border-color: #1a3a5c; } .card-total .num   { color: #1a3a5c; }
.card-stage1  { border-color: #95a5a6; } .card-stage1 .num  { color: #7f8c8d; }
.card-stage2  { border-color: #3498db; } .card-stage2 .num  { color: #2980b9; }
.card-stage3  { border-color: #27ae60; } .card-stage3 .num  { color: #27ae60; }

/* Stage badges */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    white-space: nowrap;
}
.badge-1 { background: #95a5a6; }
.badge-2 { background: #2980b9; }
.badge-3 { background: #27ae60; }

/* Filter bar */
.filter-bar {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 16px;
    border: 1px solid #e9ecef;
}

/* Fetch button */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #1a3a5c, #2980b9);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 1rem;
    font-weight: 600;
    width: 100%;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #0d2137, #1a3a5c);
}

/* Download button */
div[data-testid="stDownloadButton"] > button {
    background: #27ae60;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)


# ── Constants ────────────────────────────────────────────────
ISSUER_CODES = {
    "บัวหลวง": "01", "bualuang": "01", "bls": "01",
    "พาย": "03", "pi": "03", "pai": "03",
    "เกียรตินาคิน": "06", "ภัทร": "06", "kiatnakin": "06", "phatra": "06", "kkp": "06",
    "เคเจไอ": "13", "kgi": "13",
    "หยวนต้า": "19", "yuanta": "19",
    "อินโนเวสท์": "23", "innovest": "23", "scbx": "23",
    "กรุงไทย": "80", "ktb": "80", "ktbst": "80", "ธนาคารกรุงไทย": "80"
}

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
}


# ── Helper functions ─────────────────────────────────────────
def get_issuer_code(name):
    if not name:
        return ""
    lower = name.lower()
    for key, code in ISSUER_CODES.items():
        if key.lower() in lower:
            return code
    return ""

def generate_set_symbol(underlying, issuer):
    if not underlying or underlying == "—":
        return ""
    code = get_issuer_code(issuer)
    if not code:
        return ""
    ticker = re.sub(r'\d+$', '', underlying.strip().split()[0].upper())
    return f"{ticker}{code}"

def parse_date_th(date_str):
    if not date_str or str(date_str).strip() in ("", "—"):
        return None
    try:
        parts = str(date_str).strip().split("/")
        if len(parts) == 3:
            year = int(parts[2])
            if year > 2400:
                year -= 543
            return f"{parts[0]}/{parts[1]}/{year}"
    except:
        pass
    return str(date_str)

def detect_stage(first, amend, effective, trade_start):
    if trade_start and trade_start.strip():
        return "3. Trading Started"
    if effective and effective.strip():
        return "2. Filing Effective"
    if first and first.strip():
        return "1. Initial Filing"
    return "—"

def scrape_underlying(detail_url):
    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=10)
        resp.encoding = "TIS-620"
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ")
        # Find ผู้เสนอขายหลักทรัพย์ section
        idx = text.find("ผู้เสนอขายหลักทรัพย์")
        if idx == -1:
            return ""
        segment = text[idx:idx+400]
        # Find all parenthesised values, return last one with Latin chars
        parens = re.findall(r'\(([^)]{3,})\)', segment)
        for p in reversed(parens):
            if re.search(r'[A-Za-z]{3,}', p):
                return p.strip()
    except Exception as e:
        pass
    return ""

def fetch_page(page_num):
    url = f"https://market.sec.or.th/public/idisc/th/ViewMore/filing-equity?SecuTypeCode=DS&FilingData={page_num}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.encoding = "UTF-8"
    return resp.text

def parse_filings(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    filings = []
    for row in rows:
        if row.find("th"):
            continue
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        # Get detail URL from last link in row
        links = row.find_all("a", href=True)
        detail_url = links[-1]["href"] if links else ""

        issuer_raw    = cells[0].get_text(" ", strip=True)
        issuer        = issuer_raw.split("/")[0].strip()
        first_date    = cells[3].get_text(strip=True)
        amend_date    = cells[4].get_text(strip=True)
        effective     = cells[5].get_text(strip=True)
        trade_start   = cells[6].get_text(strip=True) if len(cells) > 6 else ""
        offer_end     = cells[7].get_text(strip=True) if len(cells) > 7 else ""
        remark        = cells[8].get_text(strip=True) if len(cells) > 8 else ""

        filings.append({
            "issuer":         issuer,
            "sec_type":       cells[1].get_text(strip=True),
            "offer_type":     cells[2].get_text(strip=True),
            "first_date":     first_date,
            "amend_date":     amend_date,
            "effective":      effective,
            "trade_start":    trade_start,
            "offer_end":      offer_end,
            "remark":         remark,
            "detail_url":     detail_url,
        })
    return filings


def fetch_all_filings(max_pages, progress_bar, status_text):
    all_filings = []
    for page in range(max_pages):
        status_text.text(f"📄 Fetching list page {page + 1}/{max_pages}...")
        try:
            html = fetch_page(page)
            page_filings = parse_filings(html)
            if not page_filings:
                status_text.text(f"✅ No more data at page {page + 1}, stopping.")
                break
            all_filings.extend(page_filings)
            progress_bar.progress((page + 1) / (max_pages * 2))  # first half = list pages
            time.sleep(0.8)
        except Exception as e:
            status_text.text(f"⚠️ Error on page {page + 1}: {e}")
            break

    # Enrich with underlying from detail pages
    total = len(all_filings)
    for i, f in enumerate(all_filings):
        status_text.text(f"🔍 Fetching underlying {i + 1}/{total}: {f['issuer'][:30]}...")
        progress_bar.progress(0.5 + (i + 1) / (total * 2))

        if f["detail_url"]:
            underlying = scrape_underlying(f["detail_url"])
            f["underlying"] = underlying or "—"
        else:
            f["underlying"] = "—"

        set_symbol = generate_set_symbol(f["underlying"], f["issuer"])
        f["set_symbol"] = set_symbol
        f["set_link"]   = f"https://www.set.or.th/en/market/product/dr/quote/{set_symbol}/price" if set_symbol else ""
        f["stage"]      = detect_stage(f["first_date"], f["amend_date"], f["effective"], f["trade_start"])

        if i < total - 1:
            time.sleep(0.5)

    progress_bar.progress(1.0)
    status_text.text(f"✅ Done! Fetched {total} filings.")
    return all_filings


def to_dataframe(filings):
    rows = []
    for f in filings:
        rows.append({
            "Underlying Stock":           f.get("underlying", "—"),
            "SET Symbol":                 f.get("set_symbol", "—") or "—",
            "Stage":                      f.get("stage", "—"),
            "Issuer":                     f.get("issuer", ""),
            "Security Type":              f.get("sec_type", ""),
            "Offer Type":                 f.get("offer_type", ""),
            "วันที่ยื่น Filing แรก":       f.get("first_date", ""),
            "วันที่แก้ไขล่าสุด":           f.get("amend_date", ""),
            "วันที่ Filing มีผลบังคับ":    f.get("effective", ""),
            "วันที่เริ่มเทรด":             f.get("trade_start", ""),
            "วันที่สิ้นสุดการขาย":         f.get("offer_end", ""),
            "หมายเหตุ":                   f.get("remark", ""),
            "SEC Filing URL":             f.get("detail_url", ""),
            "SET Link":                   f.get("set_link", ""),
        })
    return pd.DataFrame(rows)


def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DR Filings")
        ws = writer.sheets["DR Filings"]
        # Column widths
        widths = [30, 12, 20, 30, 25, 15, 18, 18, 22, 18, 20, 15, 50, 40]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = w
        # Header style
        from openpyxl.styles import PatternFill, Font, Alignment
        header_fill = PatternFill("solid", fgColor="1a3a5c")
        for cell in ws[1]:
            cell.fill   = header_fill
            cell.font   = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 36
        ws.freeze_panes = "A2"
        # Stage color rows
        stage_colors = {
            "3. Trading Started": "C8E6C9",
            "2. Filing Effective": "BBDEFB",
            "1. Initial Filing":  "FFF9C4",
        }
        stage_col = [c.column for c in ws[1] if c.value == "Stage"]
        if stage_col:
            sc = stage_col[0]
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                stage_val = str(row[sc - 1].value or "")
                color = stage_colors.get(stage_val)
                if color:
                    fill = PatternFill("solid", fgColor=color)
                    for cell in row:
                        cell.fill = fill
    output.seek(0)
    return output


# ── UI ───────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <h1>📋 SEC DR Filing Monitor</h1>
  <p>ตราสารแสดงสิทธิในหลักทรัพย์ต่างประเทศ (DR) · Real-time data from SEC Thailand</p>
</div>
""", unsafe_allow_html=True)

# ── Fetch Controls ───────────────────────────────────────────
with st.container():
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        max_pages = st.slider(
            "Number of pages to fetch (10 filings per page)",
            min_value=1, max_value=34, value=2,
            help="336 total filings ÷ 10 per page = 34 pages max"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔄 Fetch Filings", type="primary", use_container_width=True)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_all_btn = st.button("📥 Fetch ALL (34 pages)", use_container_width=True)

# ── Fetch Logic ──────────────────────────────────────────────
if fetch_btn or fetch_all_btn:
    pages = 34 if fetch_all_btn else max_pages
    with st.spinner(""):
        progress_bar = st.progress(0)
        status_text  = st.empty()
        filings = fetch_all_filings(pages, progress_bar, status_text)
        st.session_state["filings"] = filings
        st.session_state["fetched_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        st.session_state["df"] = to_dataframe(filings)
        time.sleep(0.5)
        st.rerun()

# ── Show Data ────────────────────────────────────────────────
if "df" in st.session_state and not st.session_state["df"].empty:
    df = st.session_state["df"]
    fetched_at = st.session_state.get("fetched_at", "")

    # ── Metrics ─────────────────────────────────────────────
    total   = len(df)
    stage1  = len(df[df["Stage"] == "1. Initial Filing"])
    stage2  = len(df[df["Stage"] == "2. Filing Effective"])
    stage3  = len(df[df["Stage"] == "3. Trading Started"])

    st.markdown(f"""
    <div class="metric-row">
      <div class="metric-card card-total">
        <div class="num">{total}</div>
        <div class="lbl">Total Filings</div>
      </div>
      <div class="metric-card card-stage1">
        <div class="num">{stage1}</div>
        <div class="lbl">1. Initial Filing</div>
      </div>
      <div class="metric-card card-stage2">
        <div class="num">{stage2}</div>
        <div class="lbl">2. Filing Effective</div>
      </div>
      <div class="metric-card card-stage3">
        <div class="num">{stage3}</div>
        <div class="lbl">3. Trading Started</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Filters ──────────────────────────────────────────────
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])
    with fc1:
        stage_filter = st.multiselect(
            "Stage",
            options=["1. Initial Filing", "2. Filing Effective", "3. Trading Started"],
            default=[]
        )
    with fc2:
        issuer_opts = sorted(df["Issuer"].dropna().unique().tolist())
        issuer_filter = st.multiselect("Issuer", options=issuer_opts, default=[])
    with fc3:
        search = st.text_input("🔍 Search Underlying / Symbol", placeholder="e.g. NVIDIA, TSLA...")
    with fc4:
        offer_filter = st.multiselect(
            "Offer Type",
            options=sorted(df["Offer Type"].dropna().unique().tolist()),
            default=[]
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Apply Filters ────────────────────────────────────────
    filtered = df.copy()
    if stage_filter:
        filtered = filtered[filtered["Stage"].isin(stage_filter)]
    if issuer_filter:
        filtered = filtered[filtered["Issuer"].isin(issuer_filter)]
    if offer_filter:
        filtered = filtered[filtered["Offer Type"].isin(offer_filter)]
    if search:
        mask = (
            filtered["Underlying Stock"].str.contains(search, case=False, na=False) |
            filtered["SET Symbol"].str.contains(search, case=False, na=False) |
            filtered["Issuer"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    # ── Table ────────────────────────────────────────────────
    st.markdown(f"**{len(filtered)} filings** shown · Last fetched: {fetched_at}")

    # Display columns (hide raw URLs from table)
    display_cols = [
        "Underlying Stock", "SET Symbol", "Stage", "Issuer",
        "Offer Type", "วันที่ยื่น Filing แรก", "วันที่แก้ไขล่าสุด",
        "วันที่ Filing มีผลบังคับ", "วันที่เริ่มเทรด"
    ]

    # Stage color map for display
    def color_stage(val):
        colors = {
            "3. Trading Started":  "background-color: #C8E6C9",
            "2. Filing Effective": "background-color: #BBDEFB",
            "1. Initial Filing":   "background-color: #FFF9C4",
        }
        return colors.get(val, "")

    styled = filtered[display_cols].style.applymap(color_stage, subset=["Stage"])
    st.dataframe(styled, use_container_width=True, height=520, hide_index=True)

    # ── Download ─────────────────────────────────────────────
    st.markdown("---")
    dl1, dl2, _ = st.columns([2, 2, 4])
    with dl1:
        excel_data = to_excel(filtered)
        fname = f"DR_Filings_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        st.download_button(
            label="📥 Download Filtered Excel",
            data=excel_data,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with dl2:
        excel_all = to_excel(df)
        fname_all = f"DR_Filings_ALL_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        st.download_button(
            label="📥 Download ALL Excel",
            data=excel_all,
            file_name=fname_all,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

else:
    st.info("👆 Press **Fetch Filings** to load data from SEC Thailand.")
    st.markdown("""
    **What this app does:**
    - Scrapes DR filing data from [SEC Thailand](https://market.sec.or.th)
    - Fetches underlying stock name from each detail page
    - Shows stage: Initial Filing → Filing Effective → Trading Started
    - Filter by stage, issuer, offer type, or search by name
    - Download as Excel with color-coded rows
    """)
