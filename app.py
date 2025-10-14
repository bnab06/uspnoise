import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
import json, os, csv, re

# Optional PDF lib
try:
    import pdfplumber
except:
    pdfplumber = None

st.set_page_config(page_title="Chromatogram Analyzer – USP S/N Method B",
                   page_icon="📈", layout="wide")

# --- Users ---
USERS_FILE = "users.json"
DEFAULT_USERS = {
    "admin": {"pwd": "admin123", "role": "admin"},
    "bb": {"pwd": "pass", "role": "user"},
    "user": {"pwd": "user123", "role": "user"}
}

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return DEFAULT_USERS.copy()
    else:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_USERS, f, indent=2)
        return DEFAULT_USERS.copy()

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)
        return True
    except:
        return False

users = load_users()

# --- Session defaults ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# --- Utility helpers ---
def safe_rerun_on_logout():
    st.experimental_rerun()

def read_csv_smart(uploaded_file):
    uploaded_file.seek(0)
    sample = uploaded_file.read(2048).decode("utf-8", errors="ignore")
    uploaded_file.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample)
        sep = dialect.delimiter
    except:
        sep = ','
    df = pd.read_csv(uploaded_file, sep=sep)
    if len(df.columns) >= 2:
        df.columns = ["Time","Signal"] + [f"Extra_{i}" for i in range(len(df.columns)-2)]
    else:
        st.error("CSV must contain at least two columns: Time and Signal.")
        st.stop()
    df["Time"] = pd.to_numeric(df["Time"].astype(str).str.replace(',','.'), errors="coerce")
    df["Signal"] = pd.to_numeric(df["Signal"].astype(str).str.replace(',','.'), errors="coerce")
    df = df.dropna(subset=["Time","Signal"]).sort_values("Time").reset_index(drop=True)
    return df

def extract_pdf_data(uploaded_pdf):
    if pdfplumber is None:
        st.warning("pdfplumber not installed — cannot extract numeric data from PDF.")
        return None
    rows = []
    uploaded_pdf.seek(0)
    try:
        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for r in table[1:]:
                        try:
                            t = float(str(r[0]).replace(',', '.'))
                            s = float(str(r[1]).replace(',', '.'))
                            rows.append([t,s])
                        except:
                            pass
                text = page.extract_text() or ""
                for line in text.splitlines():
                    nums = re.findall(r"[-+]?[0-9]*\\.?[0-9]+(?:[eE][-+]?[0-9]+)?", line.replace(',', '.'))
                    if len(nums) >= 2:
                        try:
                            rows.append([float(nums[0]), float(nums[1])])
                        except:
                            pass
    except Exception as e:
        st.warning(f"Error opening PDF: {e}")
        return None
    if rows:
        df = pd.DataFrame(rows, columns=["Time","Signal"])
        df = df.dropna(subset=["Time","Signal"]).sort_values("Time").reset_index(drop=True)
        return df
    return None

# --- Sidebar / Login ---
st.sidebar.title("Account")

if not st.session_state.logged_in:
    selected_user = st.sidebar.selectbox("User", list(users.keys()))
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if selected_user in users and password == users[selected_user]['pwd']:
            st.session_state.logged_in = True
            st.session_state.user = selected_user
            st.sidebar.success(f"Welcome, {selected_user}!")
        else:
            st.sidebar.error("Incorrect credentials")
    # Homepage for not-logged-in
    st.title("Chromatogram Analyzer – USP S/N Method B")
    st.markdown("""**What this app does**

- Calculate USP-style Signal-to-Noise (Method B) on chromatograms.
- Supported uploads: **CSV** (recommended) and **PDF** (table/text extraction).
- Select a time window and compute **USP S/N**, **S/N**, **LOD = 3*σ_noise**, **LOQ = 10*σ_noise**.
- Exports: CSV / Excel / PNG / PDF.

**Quick start**
1. Log in from the sidebar (accounts: admin, bb, user).
2. Upload a CSV or PDF.
3. Select start/end time and inspect results.

*Note: image OCR disabled for Cloud-ready build.*""")
    st.markdown("---")
    st.info("Need help? See README or contact the app administrator.")
    st.stop()

# --- Main UI (logged in) ---
role = users.get(st.session_state.user, {}).get('role', 'user')

if role == 'admin':
    st.title("Chromatogram Analyzer — Admin Dashboard")
    st.markdown("You are logged in as **admin**. Use the sidebar to manage users and the app.")
elif role == 'user':
    st.title(f"Chromatogram Analyzer — Welcome {st.session_state.user}")
    st.markdown("Upload chromatograms and compute S/N, LOD, LOQ.")
else:
    st.title("Chromatogram Analyzer")
    st.markdown("Upload chromatograms and compute S/N, LOD, LOQ.")

st.sidebar.success(f"Logged in as: {st.session_state.user}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user = None
    safe_rerun_on_logout()

# Admin panel
if role == 'admin':
    st.sidebar.markdown("### User management (admin)")
    new_user = st.sidebar.text_input("New username")
    new_pwd = st.sidebar.text_input("New password", type="password")
    new_role = st.sidebar.selectbox("Role", ["user","admin"]) 
    if st.sidebar.button("Add user"):
        if not new_user:
            st.sidebar.error("Username cannot be empty")
        elif new_user in users:
            st.sidebar.error("User already exists")
        else:
            users[new_user] = {"pwd": new_pwd, "role": new_role}
            save_users(users)
            st.sidebar.success(f"User {new_user} added")
    st.sidebar.write("---")
    del_user = st.sidebar.selectbox("Delete user", [u for u in users.keys() if u != "admin"]) 
    if st.sidebar.button("Delete selected user"):
        users.pop(del_user, None)
        save_users(users)
        st.sidebar.success(f"Deleted {del_user}")
    st.sidebar.write("---")

# Main content: upload & parameters
st.sidebar.title("Upload & Parameters")
upload_type = st.sidebar.selectbox("Upload type", ["CSV","PDF"]) 
uploaded_file = st.sidebar.file_uploader("Upload file", type=["csv","pdf"])

extraction_notes = []
df = None

if uploaded_file is not None:
    if upload_type == "CSV":
        try:
            df = read_csv_smart(uploaded_file)
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            df = None
    else:
        df = extract_pdf_data(uploaded_file)
        if df is None:
            st.warning("Unable to extract numeric data from PDF. Upload a CSV as fallback.")
            extraction_notes.append("PDF extraction failed or yielded no numeric pairs.")

if df is None:
    if uploaded_file is None:
        st.info("Upload a CSV or PDF from the sidebar to begin analysis.")
    else:
        st.warning("No numeric data available. Please upload a CSV file with Time and Signal columns.")
        fallback = st.file_uploader("Or upload CSV fallback", type=["csv"], key="fallback")
        if fallback is not None:
            try:
                df = read_csv_smart(fallback)
            except Exception as e:
                st.error(f"Error reading fallback CSV: {e}")

if df is not None:
    st.subheader("Data preview")
    st.dataframe(df.head(200))

    t_min = float(df["Time"].min())
    t_max = float(df["Time"].max())
    st.sidebar.subheader("Zone selection")
    start_time = st.sidebar.number_input("Start Time", value=t_min, format="%.6f", step=(t_max-t_min)/100 if t_max>t_min else 0.1)
    end_time = st.sidebar.number_input("End Time", value=t_max, format="%.6f", step=(t_max-t_min)/100 if t_max>t_min else 0.1)

    if end_time <= start_time:
        st.warning("End time must be greater than Start time.")
    else:
        mask = (df["Time"] >= start_time) & (df["Time"] <= end_time)
        df_zone = df.loc[mask].copy()
        if df_zone.empty:
            st.warning("No data in selected zone.")
        else:
            signal_vals = df_zone["Signal"].values
            baseline = float(np.median(signal_vals))
            peak_idx = int(np.argmax(signal_vals))
            peak_val = float(signal_vals[peak_idx])
            peak_time = float(df_zone.iloc[peak_idx]["Time"])
            peak_height = peak_val - baseline
            noise_std = float(np.std(signal_vals, ddof=0))
            noise_rms = float(np.sqrt(np.mean((signal_vals-baseline)**2)))
            usp_sn = peak_height/noise_std if noise_std != 0 else float("nan")
            simple_sn = peak_val/noise_std if noise_std != 0 else float("nan")
            LOD = 3*noise_std
            LOQ = 10*noise_std

            metrics = {
                "baseline": baseline,
                "peak_val": peak_val,
                "peak_time": peak_time,
                "peak_height": peak_height,
                "noise_std": noise_std,
                "noise_rms": noise_rms,
                "usp_sn": usp_sn,
                "simple_sn": simple_sn,
                "LOD": LOD,
                "LOQ": LOQ
            }

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["Time"], y=df["Signal"], mode="lines", name="Chromatogram"))
            fig.add_vrect(x0=start_time, x1=end_time, fillcolor="LightSalmon", opacity=0.3, line_width=0)
            fig.add_trace(go.Scatter(x=[peak_time], y=[peak_val], mode="markers", marker=dict(size=10, color="red"), name="Peak"))
            fig.update_layout(title="Chromatogram", xaxis_title="Time", yaxis_title="Signal", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Results (selected zone)")
            for k, v in metrics.items():
                st.write(f"- {k.replace('_',' ').title()}: **{v:.6g}**")

            zone_csv = df_zone.to_csv(index=False).encode("utf-8")
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_zone.to_excel(writer, index=False, sheet_name="Zone")
                pd.DataFrame([metrics]).to_excel(writer, index=False, sheet_name="Metrics")
            excel_data = excel_buffer.getvalue()

            st.download_button("Download zone CSV", data=zone_csv, file_name="zone_data.csv", mime="text/csv")
            st.download_button("Download zone Excel (with metrics)", data=excel_data, file_name="zone_with_metrics.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.download_button("Download metrics (CSV)", data=pd.DataFrame([metrics]).to_csv(index=False).encode("utf-8"), file_name="zone_metrics.csv", mime="text/csv")

            try:
                png_bytes = fig.to_image(format="png")
                pdf_bytes = fig.to_image(format="pdf")
                st.download_button("Download chromatogram (PNG)", data=png_bytes, file_name="chromatogram.png", mime="image/png")
                st.download_button("Download chromatogram (PDF)", data=pdf_bytes, file_name="chromatogram.pdf", mime="application/pdf")
            except Exception:
                st.info("PNG/PDF export unavailable in this environment (kaleido dependency).")
st.markdown("<hr><small>Powered by: BnB – 2025</small>", unsafe_allow_html=True)
