# Pipelines Production Readiness Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Solidify the four agentic pipelines in `~/pipelines/` (B2B Lead Gen, Bounty Sniper, DaaS Newsletter, Scholarship Data) to production-grade by fixing state tracking, fixing permission constraints on subagents, and utilizing robust file IO for data persistence.

**Architecture:** We are updating the Markdown playbook files (`pipeline_instructions.md`) for each pipeline. The orchestrator prompts will be enhanced to use `execute_code` for robust file appends (CSV and text) instead of unsafe heredocs, fix state-tracking loops, and move privileged API calls (like `send_message`) back to the orchestrator layer since leaf agents are restricted from them.

**Tech Stack:** Markdown (Prompt Engineering), Python (`execute_code` inside Orchestrators for file IO), Hermes Tools (`delegate_task`, `send_message`).

---

### Task 1: Solidify B2B Lead Gen Pipeline (CSV & Exclusions)

**Objective:** Ensure the B2B Lead Gen pipeline safely appends data to the CSV and handles internal quotes, rather than relying on the LLM to format CSV strings manually.

**Files:**
- Modify: `~/pipelines/b2b_lead_gen/pipeline_instructions.md`

**Step 1: Write minimal implementation**

Update `Step 3: Save & Track` in the playbook to use `execute_code` to reliably append the CSV rows using Python's built-in `csv` module.

```markdown
**Step 3: Save & Track**
- For each successful result, use the `execute_code` tool with a Python script to safely append the data to the CSV. Use the `csv` module to handle internal quotes and escaping properly.
  Example Python code to execute:
  ```python
  import csv
  
  new_rows = [
      ["Firm A", "https://...", "Pain Point...", "Email..."],
      # ...
  ]
  with open("/home/ianstewart/pipelines/b2b_lead_gen/leads.csv", "a", newline="", encoding="utf-8") as f:
      writer = csv.writer(f)
      writer.writerows(new_rows)
      
  with open("/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt", "a", encoding="utf-8") as f:
      f.write("example.com\n")
  print("Success")
  ```
- Extract the root domain (e.g., `example.com`) and ensure it gets appended to `~/pipelines/b2b_lead_gen/processed_domains.txt` within the same script.
```

**Step 2: Run verification**

Run: `cat ~/pipelines/b2b_lead_gen/pipeline_instructions.md | grep execute_code`
Expected: Output showing the new `execute_code` instructions.

---

### Task 2: Solidify Bounty Sniper Pipeline (State Tracking)

**Objective:** Add state tracking to the Bounty Sniper pipeline so it remembers which jobs it has processed and avoids duplicate alerts.

**Files:**
- Modify: `~/pipelines/bounty_sniper/pipeline_instructions.md`

**Step 1: Write minimal implementation**

Add a final step to the workflow to append the processed job URL/ID to the tracking file.

```markdown
**Step 3: Update State Tracker**
- After successfully sending the Telegram message, use the `execute_code` tool to append the `[Job URL]` or unique job ID to `/home/ianstewart/pipelines/bounty_sniper/seen_jobs.txt`.
- This ensures the pipeline does not re-process the same bounty in future runs.
```

**Step 2: Run verification**

Run: `cat ~/pipelines/bounty_sniper/pipeline_instructions.md | grep "Step 3: Update State Tracker"`
Expected: Output showing the new state tracking step.

---

### Task 3: Solidify DaaS Newsletter Pipeline (File Overwrite Bug & State Tracking)

**Objective:** Prevent the Editor subagent from overwriting past drafts (as `write_file` replaces file contents) and add missing state tracking for seen AI papers.

**Files:**
- Modify: `~/pipelines/daas_newsletter/pipeline_instructions.md`

**Step 1: Write minimal implementation**

Update `Step 2` to have the Editor *return* the text, and instruct the Orchestrator to append it. Update `Step 3` to include tracking.

```markdown
**Step 2: Compile & Edit (Delegate to Editor)**
Wait for Step 1 to finish. Then, use `delegate_task` to spawn a single `Editor` subagent.
- Toolsets: `[]` (None needed)
- Role: `leaf`
- Goal: "Take these JSON insights: [INSERT OUTPUTS FROM STEP 1]. Format them into a premium, institutional-grade newsletter draft section. Adopt a sharp, VC-firm/McKinsey tone. Avoid emojis. Structure each entry with headers: 'Strategic Imperative', 'Technical TL;DR', and 'Commercial Thesis & Moat'. Return the final formatted markdown as your summary."
- *Note:* Do NOT assign the Editor the `file` toolsets, and do NOT tell it to append the file. Leaf agents cannot safely append files without overwriting them.

**Step 3: Save Draft & Update Tracker**
- Read the Editor's returned summary.
- Use the `execute_code` tool to safely append the Editor's markdown output to `/home/ianstewart/pipelines/daas_newsletter/newsletter_drafts.md`.
- In the same python script, append the unique paper IDs/Links processed in this batch to `/home/ianstewart/pipelines/daas_newsletter/seen_papers.txt`.

**Step 4: Deliver Alert to User**
Use the `send_message` tool to deliver a notification to `telegram`:
```

**Step 2: Run verification**

Run: `cat ~/pipelines/daas_newsletter/pipeline_instructions.md | grep execute_code`
Expected: Output showing the new `execute_code` instructions.

---

### Task 4: Solidify Scholarship Pipeline (Privilege Constraints & JSON Parsing)

**Objective:** Remove `send_message` tools from leaf subagents (as they lack permission) and have the Orchestrator send the messages. Improve JSON parsing reliability.

**Files:**
- Modify: `~/pipelines/scholarship_data/pipeline_instructions.md`

**Step 1: Write minimal implementation**

Update Steps 4, 6, and 8 to centralize messaging and handle markdown blocks in JSON parsing.

```markdown
4. **Parse Output & Update History:** 
   - Read the summary returned by the Researcher. If the output is wrapped in ```json ... ``` markdown blocks, strip them out to parse the raw JSON array.
   - For each scholarship found, use the `execute_code` tool to append its name to `/home/ianstewart/pipelines/scholarship_data/processed_scholarships.txt`.

... (Update Step 6)
6. **Parallel Writers Phase:** Call `delegate_task` using the `tasks` array to spawn parallel Writers (one task per scholarship).
   - **For each task:**
     - **goal:** "Write a compelling essay draft for the [Scholarship Name]. Return the draft as your summary."
     - **context:** Provide the User Profile, Scholarship Name, and Exact Prompt.
     - **toolsets:** `[]` (None needed)
   - *Note:* Once the Writers return, the **Orchestrator** must use `send_message` (target: 'slack:#scholarships') to post each draft with the prefix '✍️ **Writer Agent ([Name]):** '.

... (Update Step 8)
8. **Parallel Reviewers Phase:** Call `delegate_task` using the `tasks` array to spawn parallel Reviewers (one task per scholarship).
   - **For each task:**
     - **goal:** "Review and finalize the essay draft for the [Scholarship Name]. Return the final text as your summary."
     - **context:** Provide the Exact Prompt and the Writer's draft. 
     - **toolsets:** `[]` (None needed)
   - *Note:* Once the Reviewers return, the **Orchestrator** must use `send_message` (target: 'slack:#scholarships') to post each final draft with the prefix '🧐 **Reviewer Agent ([Name]):** '.
```

**Step 2: Run verification**

Run: `grep "Orchestrator must use send_message" ~/pipelines/scholarship_data/pipeline_instructions.md`
Expected: Output showing the Orchestrator has assumed responsibility for the Slack messages.

---

### Execution Handoff

Plan complete and saved. Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with two-stage review (spec compliance then code quality). Shall I proceed?
