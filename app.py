import streamlit as st
import pandas as pd
from datetime import date, timedelta
from login import login
import os

# ----------------------------------
# PAGE CONFIG
# ----------------------------------
st.set_page_config(
    page_title="ETA - Event participant attendance tracker",
    layout="wide"
)

# ----------------------------------
# LOGIN CHECK
# ----------------------------------
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align:center'>🔐 Login</h2>", unsafe_allow_html=True)
        login()
    st.stop()

# ----------------------------------
# USER INFO
# ----------------------------------
current_user = st.session_state["user"]
current_role = st.session_state["role"]

st.sidebar.success(f"Logged in as: {current_user} ({current_role})")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ----------------------------------
# UPLOAD (PERSISTENT)
# ----------------------------------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
DATA_PATH = os.path.join(UPLOAD_DIR, "latest_uploaded.xlsx")

if current_role == "admin":
    uploaded = st.sidebar.file_uploader(
        "📁 Upload Excel file",
        type=["xlsx", "xls"],
        key="uploader"
    )

    if uploaded:
        with open(DATA_PATH, "wb") as f:
            f.write(uploaded.getbuffer())

        # 🔥 HARD RESET
        st.cache_data.clear()

        # Preserve login but reset everything else
        logged_in = st.session_state.get("logged_in")
        user = st.session_state.get("user")
        role = st.session_state.get("role")

        st.session_state.clear()

        st.session_state["logged_in"] = logged_in
        st.session_state["user"] = user
        st.session_state["role"] = role

        st.success("✅ New file uploaded and dashboard refreshed")
        st.rerun()


# ----------------------------------
# LOAD DATA
# ----------------------------------
@st.cache_data
def load_data(path):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

df = load_data(DATA_PATH)

# ----------------------------------
# DATE HANDLING (SEPARATE df_time)
# ----------------------------------
df_time = df.copy()

df_time["received_on"] = pd.to_datetime(
    df_time["received_on"], errors="coerce"
)

df_time = df_time.dropna(subset=["received_on"])

df_time["date"] = df_time["received_on"].dt.date
df_time["month"] = df_time["received_on"].dt.to_period("M").astype(str)

# ----------------------------------
# USER ACCESS CONTROL
# ----------------------------------
if current_role != "admin":
    df = df[df["username"] == current_user]
    df_time = df_time[df_time["username"] == current_user]
    st.info(f"🔒 You are viewing only your own records ({current_user})")

# ----------------------------------
# SIDEBAR FILTERS
# ----------------------------------
st.sidebar.header("🔎 Filters")

region_filter = st.sidebar.multiselect(
    "Region", sorted(df["region_name"].dropna().unique())
)
woreda_filter = st.sidebar.multiselect(
    "Woreda", sorted(df["woreda_name"].dropna().unique())
)
organizer_filter = st.sidebar.multiselect(
    "Event organizer", sorted(df["event_organizer_name"].dropna().unique())
)
event_filter = st.sidebar.multiselect(
    "Event ID", sorted(df["event_id"].dropna().unique())
)

if current_role == "admin":
    username_filter = st.sidebar.multiselect(
        "User", sorted(df["username"].dropna().unique())
    )
else:
    username_filter = [current_user]

# ---- Apply filters to BOTH df & df_time
def apply_filters(data):
    if region_filter:
        data = data[data["region_name"].isin(region_filter)]
    if woreda_filter:
        data = data[data["woreda_name"].isin(woreda_filter)]
    if organizer_filter:
        data = data[data["event_organizer_name"].isin(organizer_filter)]
    if event_filter:
        data = data[data["event_id"].isin(event_filter)]
    if username_filter:
        data = data[data["username"].isin(username_filter)]
    return data

df = apply_filters(df)
df_time = apply_filters(df_time)

# ----------------------------------
# DATE FILTER (APPLIES TO df_time ONLY)
# ----------------------------------
#st.sidebar.subheader("📅 Date filter")

min_date = df_time["date"].min()
max_date = df_time["date"].max()

date_range = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Apply date range to df_time only
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    df_time = df_time[
        (df_time["date"] >= start_date) &
        (df_time["date"] <= end_date)
    ]


# ----------------------------------
# KPI CARDS (USE df)
# ----------------------------------
today = date.today()

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)

k1.metric("📄 Total records", len(df))
k2.metric("👤 Users", df["username"].nunique())
k3.metric("🌍 Regions", df["region_name"].nunique())
k4.metric("🗺️ Woredas", df["woreda_name"].nunique())
k5.metric("🎪 Organizers", df["event_organizer_name"].nunique())
k6.metric("📅 Today", df_time[df_time["date"] == today].shape[0])
k7.metric("📆 This month", df_time[df_time["month"] == today.strftime("%Y-%m")].shape[0])

st.divider()

# ----------------------------------
# 📊 DATA ENTRY TRENDS (USE df_time)
# ----------------------------------
st.subheader("🕒 Data Entry Trends")

last_7_days = today - timedelta(days=6)

daily_7 = (
    df_time[df_time["date"] >= last_7_days]
    .groupby("date")
    .size()
    .reset_index(name="records")
)

daily_7["day_label"] = pd.to_datetime(
    daily_7["date"]
).dt.strftime("%b %d")

monthly_trend = (
    df_time.groupby("month")
    .size()
    .reset_index(name="records")
)

c1, c2 = st.columns(2)

with c1:
    st.markdown("**📅 Last 7 days**")
    st.line_chart(daily_7, x="day_label", y="records")

with c2:
    st.markdown("**📆 Monthly records**")
    st.bar_chart(monthly_trend, x="month", y="records")

st.divider()

# ----------------------------------
# 👤 ENUMERATOR PERFORMANCE
# ----------------------------------
st.subheader("👤 Enumerator performance")

user_summary = (
    df.groupby("username")
    .size()
    .reset_index(name="records")
    .sort_values("records", ascending=False)
)

daily_user = (
    df_time.groupby(["date", "username"])
    .size()
    .reset_index(name="records")
)

c3, c4 = st.columns(2)

with c3:
    st.markdown("**🏆 Records per user**")
    st.dataframe(user_summary, use_container_width=True)

with c4:
    st.markdown("**📅 Daily entries per user**")
    st.dataframe(daily_user, use_container_width=True)

st.divider()

# ----------------------------------
# 🌍 EVENT & GEOGRAPHIC TABLES
# ----------------------------------
st.subheader("📍 Event & Geographic Coverage")

geo_summary = (
    df.groupby(["region_name", "woreda_name"])
    .size()
    .reset_index(name="records")
)

event_summary = (
    df.groupby("event_id")
    .size()
    .reset_index(name="records")
    .sort_values("records", ascending=False)
)

c5, c6 = st.columns(2)

with c5:
    st.markdown("**🎪 Records by Event ID**")
    st.dataframe(event_summary, use_container_width=True)

with c6:
    st.markdown("**🌍 Geographic coverage**")
    st.dataframe(geo_summary, use_container_width=True)
