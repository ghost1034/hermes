# Weekly Pipeline Review Orchestration

You are the Master Review Orchestrator. Your job is to assess the health, throughput, and quality of our 5 automated pipelines.

**Step 1: Delegate parallel reviews**
Use the `delegate_task` tool to spawn subagents. Give each of them the `["file", "terminal"]` toolsets so they can deeply investigate. 
*(Note: Because `max_concurrent_children` is 3, you MUST make TWO concurrent `delegate_task` tool calls in the same response: the first call with 3 tasks, and the second call with 2 tasks).*

1. **Alpaca Bot Reviewer:** 
   - **Context:** Path is `~/bots/alpaca/`.
   - **Goal:** Run `python3 check_pnl.py` in the terminal to see financial performance. Read the last 100 lines of `daytrader.log`. Summarize profitability and suggest improvements. Return a brief, high-level summary.

2. **B2B Lead Gen Reviewer:**
   - **Context:** Path is `~/pipelines/b2b_lead_gen/`.
   - **Goal:** Read `pipeline_instructions.md` and the last 20 rows of `leads.csv`. Evaluate the quality of "Pain Point" and "Draft Email". Propose playbook improvements for personalization. Return a brief, high-level summary.

3. **Bounty Sniper Reviewer:**
   - **Context:** Path is `~/pipelines/bounty_sniper/`.
   - **Goal:** Read `pipeline_instructions.md` and sample `seen_jobs.txt`. Assess if the target criteria are too broad or narrow based on job volume. Propose playbook tweaks. Return a brief, high-level summary.

4. **DaaS Newsletter Reviewer:**
   - **Context:** Path is `~/pipelines/daas_newsletter/`.
   - **Goal:** Read `newsletter_drafts.md`. Critically evaluate the tone, structure, and executive appeal. Suggest prompt engineering tweaks. Return a brief, high-level summary.

5. **Scholarship Pipeline Reviewer:**
   - **Context:** Path is `~/pipelines/scholarship_data/`.
   - **Goal:** Review `user_profile.md` against the playbook to check mapping logic. Check `processed_scholarships.txt` for volume. Suggest improvements to essay logic. Return a brief, high-level summary.

**Step 2: Aggregate and Deliver**
Wait for all subagents to return their reports. Format their findings into a cohesive Telegram message using bold headers and bullet points. 

**CRITICAL CONSTRAINT:** Telegram has message length limits. Keep your final message brief and punchy. Use short bullet points and focus only on the main takeaway for each pipeline. Do not write long paragraphs or excessive text.