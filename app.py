import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "evaluations.db"

st.set_page_config(page_title="Chatbot QA Studio", page_icon="🧪", layout="wide")

st.markdown("""
<style>
    .block-container {padding-top: 1.5rem; max-width: 1450px;}
    [data-testid="stMetric"] {background:#fff; border:1px solid #e8ebf0; padding:16px; border-radius:14px;}
    .hero {padding:22px 24px; border-radius:18px; background:linear-gradient(115deg,#101d36,#263d63); color:white; margin-bottom:18px;}
    .hero p {color:#d7e1f2; margin-bottom:0;}
    .small-muted {color:#788397; font-size:0.9rem;}
</style>
""", unsafe_allow_html=True)

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_name TEXT, created_at TEXT, total INTEGER, passed INTEGER,
            failed INTEGER, success_rate REAL, conformity REAL,
            correctness REAL, custom_check REAL, results_json TEXT
        )""")

def clean_text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()

def evaluate_row(row, custom_terms):
    question = clean_text(row.get("user_message", ""))
    expected = clean_text(row.get("expected_answer", ""))
    actual = clean_text(row.get("actual_response", ""))
    tags = clean_text(row.get("tags", ""))

    # Conformity: response exists, is relevant to the expected answer, and is not an error placeholder.
    expected_words = {w.lower() for w in re.findall(r"[a-zA-Z0-9]+", expected) if len(w) > 3}
    actual_words = {w.lower() for w in re.findall(r"[a-zA-Z0-9]+", actual)}
    overlap = len(expected_words & actual_words) / max(1, len(expected_words))
    conformity = bool(actual) and len(actual) >= 12 and not any(
        x in actual.lower() for x in ["internal server error", "traceback", "null pointer"]
    )

    # Correctness is a transparent baseline proxy, not an LLM/human truth judgment.
    correctness = (overlap >= 0.25) if expected else bool(actual)
    custom_hits = sum(1 for term in custom_terms if term.lower() in actual.lower())
    custom_ok = (custom_hits == len(custom_terms)) if custom_terms else bool(actual)

    reasons = []
    if not actual:
        reasons.append("Empty response")
    if expected and overlap < 0.25:
        reasons.append("Low expected-answer keyword overlap")
    if any(x in actual.lower() for x in ["internal server error", "traceback", "null pointer"]):
        reasons.append("Technical error text detected")
    if custom_terms and not custom_ok:
        missing = [t for t in custom_terms if t.lower() not in actual.lower()]
        reasons.append("Missing custom terms: " + ", ".join(missing))
    passed = conformity and correctness and custom_ok
    return {
        "question": question, "expected_answer": expected, "actual_response": actual,
        "tags": tags, "conformity": conformity, "correctness": correctness,
        "custom_check": custom_ok, "keyword_overlap": round(overlap * 100, 1),
        "status": "Passed" if passed else "Failed",
        "reason": "; ".join(reasons) if reasons else "All configured checks passed"
    }

def save_run(name, results):
    df = pd.DataFrame(results)
    total = len(df)
    passed = int((df["status"] == "Passed").sum()) if total else 0
    pct = lambda col: round(float(df[col].mean() * 100), 1) if total else 0
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""INSERT INTO runs
        (run_name, created_at, total, passed, failed, success_rate, conformity, correctness, custom_check, results_json)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (name, datetime.now().isoformat(timespec="seconds"), total, passed, total-passed,
         round(passed/total*100,1) if total else 0, pct("conformity"), pct("correctness"),
         pct("custom_check"), df.to_json(orient="records")))
    return passed, total

init_db()

with st.sidebar:
    st.title("🧪 Chatbot QA Studio")
    st.caption("AI Chatbot Quality Testing Framework")
    page = st.radio("Workspace", ["Dashboard", "Run evaluation", "Evaluation history", "About"])
    st.divider()
    st.caption("Demo project · Rule-based baseline evaluator")

if page == "Dashboard":
    st.markdown('<div class="hero"><h1>AI Chatbot Quality Testing Framework</h1><p>Evaluate chatbot conversations, inspect failures, and track quality metrics across test runs.</p></div>', unsafe_allow_html=True)
    with sqlite3.connect(DB_PATH) as con:
        history = pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", con)
    if history.empty:
        st.info("No evaluation runs yet. Open **Run evaluation** and upload the sample dataset to create your first report.")
        cols = st.columns(3)
        for c, label, value in zip(cols, ["Conformity", "Correctness", "Custom checks"], ["—","—","—"]):
            c.metric(label, value)
    else:
        latest = history.iloc[0]
        a,b,c,d = st.columns(4)
        a.metric("Success rate", f"{latest.success_rate:.1f}%", f"{int(latest.passed)} passed")
        b.metric("Conformity", f"{latest.conformity:.1f}%")
        c.metric("Correctness", f"{latest.correctness:.1f}%")
        d.metric("Custom check", f"{latest.custom_check:.1f}%")
        left,right = st.columns([1.15,1])
        with left:
            st.subheader(f"Latest run · {latest.run_name}")
            st.caption(f"Started {latest.created_at}")
            chart = pd.DataFrame({"Status":["Passed","Failed"],"Count":[int(latest.passed),int(latest.failed)]})
            fig = px.pie(chart, names="Status", values="Count", hole=.68, color="Status",
                         color_discrete_map={"Passed":"#24966b","Failed":"#df7567"})
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), legend_title="")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.subheader("Recent evaluation runs")
            st.dataframe(history[["run_name","created_at","total","success_rate"]].head(8),
                         use_container_width=True, hide_index=True)
        st.subheader("Quality trend")
        trend = history.sort_values("id")
        fig = px.line(trend, x="created_at", y=["success_rate","conformity","correctness","custom_check"],
                      markers=True, labels={"value":"Score (%)","created_at":"Run date","variable":"Metric"})
        fig.update_yaxes(range=[0,100])
        st.plotly_chart(fig, use_container_width=True)

elif page == "Run evaluation":
    st.title("Run a chatbot evaluation")
    st.write("Upload a CSV of conversations or use the included sample dataset.")
    sample_path = APP_DIR / "data" / "sample_conversations.csv"
    sample = pd.read_csv(sample_path)
    col1,col2 = st.columns([1,1])
    with col1:
        if st.button("Load sample dataset", type="secondary", use_container_width=True):
            st.session_state["dataset"] = sample
    with col2:
        uploaded = st.file_uploader("Upload conversation CSV", type=["csv"])
        if uploaded is not None:
            try:
                st.session_state["dataset"] = pd.read_csv(uploaded)
            except Exception as exc:
                st.error(f"Could not read CSV: {exc}")
    if "dataset" not in st.session_state:
        st.session_state["dataset"] = sample
    df = st.session_state["dataset"].copy()
    required = ["user_message","actual_response"]
    missing = [x for x in required if x not in df.columns]
    if missing:
        st.error("CSV is missing required columns: " + ", ".join(missing))
    else:
        if "expected_answer" not in df.columns: df["expected_answer"] = ""
        if "tags" not in df.columns: df["tags"] = ""
        st.subheader("Dataset preview")
        st.dataframe(df.head(12), use_container_width=True, hide_index=True)
        run_name = st.text_input("Evaluation run name", value="Customer Care Bot - QA Run")
        terms = st.text_input("Custom required terms (comma-separated)", placeholder="refund policy, support team")
        custom_terms = [x.strip() for x in terms.split(",") if x.strip()]
        st.caption("Baseline checks: response present/no technical error, expected-answer keyword overlap, and optional required terms.")
        if st.button("▶ Run evaluation", type="primary", disabled=bool(missing)):
            results = [evaluate_row(row, custom_terms) for _,row in df.iterrows()]
            passed,total = save_run(run_name, results)
            st.session_state["last_results"] = results
            st.success(f"Evaluation completed: {passed}/{total} passed ({passed/total*100:.1f}% success rate).")
        if "last_results" in st.session_state:
            results_df = pd.DataFrame(st.session_state["last_results"])
            total = len(results_df)
            passed = int((results_df.status == "Passed").sum())
            a,b,c,d = st.columns(4)
            a.metric("Success rate", f"{passed/max(total,1)*100:.1f}%")
            b.metric("Passed", passed)
            c.metric("Failed", total-passed)
            d.metric("Not executed", 0)
            st.subheader("Evaluation metrics")
            m1,m2,m3 = st.columns(3)
            m1.metric("Conformity", f"{results_df.conformity.mean()*100:.1f}%")
            m2.metric("Correctness", f"{results_df.correctness.mean()*100:.1f}%")
            m3.metric("Custom check", f"{results_df.custom_check.mean()*100:.1f}%")
            status_filter = st.radio("Show conversations", ["All","Passed","Failed"], horizontal=True)
            search = st.text_input("Search conversations")
            view = results_df.copy()
            if status_filter != "All": view = view[view.status == status_filter]
            if search:
                view = view[view.astype(str).apply(lambda r: r.str.contains(search,case=False,na=False)).any(axis=1)]
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.download_button("Download detailed results (CSV)", results_df.to_csv(index=False),
                               file_name="chatbot_evaluation_results.csv", mime="text/csv")

elif page == "Evaluation history":
    st.title("Evaluation history")
    with sqlite3.connect(DB_PATH) as con:
        history = pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", con)
    if history.empty:
        st.info("No saved runs. Run an evaluation first.")
    else:
        st.dataframe(history.drop(columns=["results_json"]), use_container_width=True, hide_index=True)
        run_id = st.selectbox("Inspect a run", history.id.tolist(), format_func=lambda x: f"#{x} · {history.loc[history.id==x,'run_name'].iloc[0]}")
        record = history[history.id == run_id].iloc[0]
        details = pd.DataFrame(json.loads(record.results_json))
        st.subheader(record.run_name)
        st.dataframe(details, use_container_width=True, hide_index=True)
        st.download_button("Download this run as CSV", details.to_csv(index=False),
                           file_name=f"evaluation_run_{run_id}.csv", mime="text/csv")

else:
    st.title("About this project")
    st.markdown("""
### AI Chatbot Quality Testing Framework

A portfolio-ready application that helps QA engineers evaluate chatbot responses at conversation level.

**Main features**
- Upload CSV test datasets or use the included demo data.
- Run conformity, correctness-proxy, and configurable custom checks.
- View pass/fail status, failure reasons, and keyword-overlap scores.
- Search and filter conversations.
- Save evaluation runs in a local SQLite database.
- Track historical quality metrics and download reports.

**CSV format**

| Column | Required | Purpose |
|---|---|---|
| `user_message` | Yes | User's prompt |
| `actual_response` | Yes | Chatbot's answer |
| `expected_answer` | No, recommended | Reference answer for baseline comparison |
| `tags` | No | Category or source tags |

**Important limitation:** this starter project uses transparent rule-based checks. Keyword overlap is only a rough correctness proxy; it does not prove factual accuracy. For production use, add human review and/or a properly configured LLM-as-judge with a defined rubric, plus privacy and security testing.
    """)
