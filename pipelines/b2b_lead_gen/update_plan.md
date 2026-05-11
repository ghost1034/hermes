# B2B Lead Gen Pipeline Update Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Update the B2B lead generation pipeline to broaden the target audience, extract more leads per run, refine the pitch around available and relevant products (including digital workers), and run daily.

**Architecture:** We will modify the text files driving the pipeline (`target_queries.txt` and `pipeline_instructions.md`) to reflect the new goals. Finally, we will use the `cronjob` tool to update the schedule and resume the background orchestration.

**Tech Stack:** python (`execute_code`), text files, Hermes cronjob tool, git

---

### Task 1: Expand Target Queries List

**Objective:** Overwrite the target queries list with an extensive set of queries covering all potential customer segments.

**Files:**
- Modify: `/home/ianstewart/pipelines/b2b_lead_gen/target_queries.txt`

**Step 1: Write minimal implementation**
Use the `write_file` tool to replace the content of `/home/ianstewart/pipelines/b2b_lead_gen/target_queries.txt` with an extensive list covering accounting, bookkeeping, finance, and legal services across various major cities:

```text
"Accounting firm" in San Francisco CA
"CPA firm" in San Jose CA
"Bookkeeping services" in Oakland CA
"Accounting firm" in New York NY
"CPA firm" in New York NY
"Bookkeeping services" in Brooklyn NY
"Accounting firm" in Chicago IL
"CPA firm" in Chicago IL
"Bookkeeping services" in Chicago IL
"Legal practice" in Los Angeles CA
"Law firm" in Los Angeles CA
"Corporate finance consulting" in Austin TX
"Fractional CFO services" in Dallas TX
"Tax preparation services" in Miami FL
"Estate planning attorneys" in Boston MA
"Audit firm" in Seattle WA
"Family law attorneys" in Denver CO
"Financial advisory firm" in Atlanta GA
```

**Step 2: Verify**
Run: `cat /home/ianstewart/pipelines/b2b_lead_gen/target_queries.txt | wc -l`
Expected: Number of lines is > 10.

**Step 3: Commit**
```bash
cd /home/ianstewart/pipelines/
git add b2b_lead_gen/target_queries.txt
git commit -m "feat(b2b): expand target queries for broader reach"
```

### Task 2: Update Lead Count in Pipeline Instructions

**Objective:** Increase the number of leads generated per run from 2 to 5.

**Files:**
- Modify: `/home/ianstewart/pipelines/b2b_lead_gen/pipeline_instructions.md`

**Step 1: Write minimal implementation**
Use `execute_code` with Python to replace the text "Find 2 unique accounting/CPA firm websites" with "Find 5 unique professional firm websites" in `/home/ianstewart/pipelines/b2b_lead_gen/pipeline_instructions.md`.

```python
import pathlib
path = pathlib.Path("/home/ianstewart/pipelines/b2b_lead_gen/pipeline_instructions.md")
content = path.read_text()
content = content.replace("Find 2 unique accounting/CPA firm websites", "Find 5 unique professional firm websites")
path.write_text(content)
print("Updated lead count")
```

**Step 2: Verify**
Run: `grep "Find 5 unique professional firm websites" /home/ianstewart/pipelines/b2b_lead_gen/pipeline_instructions.md`
Expected: Returns the matching line.

**Step 3: No commit yet** (We will commit in Task 3)


### Task 3: Refine Pitch Guidelines in Pipeline Instructions

**Objective:** Update the drafting prompt to pitch specific, relevant CPAAutomation products and accurate capabilities while excluding unreleased products.

**Files:**
- Modify: `/home/ianstewart/pipelines/b2b_lead_gen/pipeline_instructions.md`

**Step 1: Write minimal implementation**
Use `execute_code` with Python to rewrite the pitching instructions in Step 2.

```python
import pathlib
path = pathlib.Path("/home/ianstewart/pipelines/b2b_lead_gen/pipeline_instructions.md")
content = path.read_text()

old_text = "Sentence 3 offers CPAAutomation.ai's document parsing."
new_text = """Sentence 3 offers the specific CPAAutomation product most relevant to their pain point:
  - Universal Document Analysis (Capabilities: Data Extraction, Table Extraction, Custom Extraction) for heavy document processing.
  - Form Fill for auto-filling PDFs/Word docs.
  - Inkwise for AI-powered writing with citations.
  - Digital Workers (AccountingClaw / FinanceClaw / LegalClaw) with our personalized setup service for private agentic infrastructure.
  DO NOT pitch Chrona or Analysis & Productivity suites."""

content = content.replace(old_text, new_text)
path.write_text(content)
print("Updated pitch instructions")
```

**Step 2: Verify**
Run: `grep "Universal Document Analysis" /home/ianstewart/pipelines/b2b_lead_gen/pipeline_instructions.md`
Expected: Returns the matching lines.

**Step 3: Commit**
```bash
cd /home/ianstewart/pipelines/
git add b2b_lead_gen/pipeline_instructions.md
git commit -m "docs(b2b): update pipeline instructions for lead count and pitch rules"
```

### Task 4: Update and Resume Cronjob

**Objective:** Update the existing B2B lead gen cronjob to run daily and resume it.

**Files:**
- None (Hermes API call via `execute_code`)

**Step 1: Write minimal implementation**
Use `execute_code` with Python to update the schedule of cronjob `4d7fd0ef9513` to daily (`0 14 * * *`) and resume it. Provide the full prompt so we don't accidentally wipe it out due to preview truncation.

```python
from hermes_tools import cronjob

full_prompt = "Read the orchestration instructions located at ~/pipelines/b2b_lead_gen/pipeline_instructions.md and execute the workflow."

# Update the job to run every day
cronjob(
    action="update",
    job_id="4d7fd0ef9513",
    schedule="0 14 * * *",
    prompt=full_prompt
)

# Resume the job
cronjob(
    action="resume",
    job_id="4d7fd0ef9513"
)
print("Cronjob updated and resumed")
```

**Step 2: Verify**
Use the `execute_code` block below to verify the cronjob state.
```python
from hermes_tools import cronjob
jobs = cronjob(action="list")
job = next((j for j in jobs["jobs"] if j["job_id"] == "4d7fd0ef9513"), None)
print(f"State: {job['state']}, Schedule: {job['schedule']}")
```
Expected: `State: scheduled, Schedule: 0 14 * * *`

**Step 3: Commit**
Not applicable.
