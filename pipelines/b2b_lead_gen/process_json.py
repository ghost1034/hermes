import json
import csv
import os

new_rows = []
domains = []

for i in range(1, 6):
    file_path = f"/home/ianstewart/pipelines/b2b_lead_gen/firm{i}.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            firm_name = data.get("firm_name", "")
            website = data.get("website", "")
            email = data.get("email", "")
            pain_point = data.get("pain_point", "")
            draft_email = data.get("draft_email", "")
            new_rows.append([firm_name, website, email, pain_point, draft_email])
            
            # Extract domain
            domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            if domain:
                domains.append(domain)

if new_rows:
    with open("/home/ianstewart/pipelines/b2b_lead_gen/leads.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)
        
    with open("/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt", "a", encoding="utf-8") as f:
        for domain in domains:
            f.write(f"{domain}\n")
            
    print(f"Successfully processed {len(new_rows)} leads.")
else:
    print("No leads processed.")
