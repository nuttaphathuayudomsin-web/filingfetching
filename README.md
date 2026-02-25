# SEC DR Filing Monitor — Streamlit App

Monitor DR (ตราสารแสดงสิทธิในหลักทรัพย์ต่างประเทศ) filings from SEC Thailand.

## Features
- Fetch filing data directly from SEC website
- Auto-scrapes underlying stock name from each detail page
- Filter by Stage / Issuer / Offer Type / Search
- Download filtered or full results as Excel

## Deploy to Streamlit Cloud

1. Push this folder to a **GitHub repository**
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app**
4. Select your repo → branch → set **Main file path** to `app.py`
5. Click **Deploy** — done!

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- Fetching ALL 336 filings (34 pages) takes ~10-15 minutes due to detail page requests
- Start with 2-3 pages to test
- Data is held in session — refresh page to clear
