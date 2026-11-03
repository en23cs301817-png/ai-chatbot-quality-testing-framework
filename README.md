# AI Chatbot Quality Testing Framework

A Streamlit portfolio project for evaluating chatbot conversation quality.

## Run locally

1. Install Python 3.10 or 3.11.
2. Open a terminal in this project folder.
3. Install dependencies: `pip install -r requirements.txt`
4. Start: `streamlit run app.py`
5. Open `http://localhost:8501`.

## Deploy free with Streamlit Community Cloud

1. Create a GitHub repository and upload the contents of this folder.
2. Sign in at https://share.streamlit.io/ using GitHub.
3. Select **Create app**, choose your repository and branch.
4. Set main file path to `app.py`, then click **Deploy**.
5. Streamlit generates your public application URL.

## CSV input format

Required: `user_message`, `actual_response`. Recommended: `expected_answer`. Optional: `tags`.
A sample file is included at `data/sample_conversations.csv`.

## Evaluation methodology

- **Conformity:** response exists, has a minimum length, and does not contain common technical error text.
- **Correctness proxy:** at least 25% of meaningful reference-answer keywords appear in the generated answer.
- **Custom check:** all comma-separated required terms configured for the run appear in the response.

These are starter heuristics, not a guarantee of factual correctness. For production use, add human-reviewed gold labels, semantic evaluation, a calibrated LLM judge, prompt-injection tests, privacy checks, and audit logs.

## Portfolio description

Built an interactive chatbot QA dashboard using Python, Streamlit, Pandas, Plotly, and SQLite. Implemented dataset ingestion, configurable response checks, conversation-level pass/fail reporting, searchable evaluation results, historical run tracking, and CSV exports.
