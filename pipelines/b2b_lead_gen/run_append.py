import csv
import urllib.parse

new_rows = [
    [
        "Bridgepoint Consulting",
        "https://bridgepointconsulting.com",
        "MediaRelations@addisongroup.com",
        "Manual extraction of data from complex financial documents slowing down advisory processes and increasing overhead.",
        "I noticed that Bridgepoint Consulting offers top-tier Finance & Accounting Advisory services, helping clients optimize their financial operations and mitigate risks. I imagine that manually extracting data from complex client financial documents can slow down your advisory processes and create unnecessary overhead for your team. CPAAutomation's Universal Document Analysis can automatically process these documents with high accuracy, saving your consultants hours of manual work so they can focus on high-value client advisory."
    ],
    [
        "Maxwell Locke & Ritter",
        "https://www.mlrpc.com",
        "info@mlrpc.com",
        "Highly-trained CPAs spending too much time on repetitive document analysis and manual data entry rather than high-value advisory services.",
        "I was impressed by Maxwell Locke & Ritter's dedication to providing top-tier CPA and advisory services that truly help clients navigate complex challenges. When delivering such comprehensive financial strategies, experienced professionals often find their time consumed by repetitive data extraction and manual form filling instead of high-value client advising. CPAAutomation's Universal Document Analysis can eliminate this bottleneck by automatically processing routine documents, freeing your team to focus entirely on the advisory work that drives your clients' success."
    ],
    [
        "Holtzman Partners",
        "https://www.holtzmanpartners.com",
        "info@holtzmanpartners.com",
        "As your advisory practice scales—especially following your integration with Armanino—managing and processing the massive influx of unstructured client documents likely creates significant workflow bottlenecks.",
        "I noticed that Holtzman Partners has built a premier reputation in Austin for delivering top-tier accounting services, particularly your expertise in SOC Compliance and SOX Readiness. As your advisory practice scales—especially following your integration with Armanino—managing and processing the massive influx of unstructured client documents likely creates significant workflow bottlenecks. Our Universal Document Analysis platform automatically extracts and categorizes critical data from these complex files, saving your team hours of manual review each week and accelerating your compliance engagements."
    ],
    [
        "vcfo",
        "https://www.vcfo.com",
        "info@vcfo.com",
        "Manual extraction and organization of financial data from disparate client systems and documents during new engagements.",
        "I noticed vcfo has successfully completed over 6,000 client engagements by providing highly experienced fractional CFOs and controllers to growing businesses. Given the diverse financial environments your team has to jump into, I imagine manual data extraction from varied client documents can significantly slow down your strategic analysis, which is where CPAAutomation's Universal Document Analysis can help. Our platform automatically parses and structures data from any financial document so your experts can focus on driving value rather than data entry—would you be open to a quick chat?"
    ],
    [
        "Embark",
        "https://embarkwithus.com",
        "paul@embarkwithus.com",
        "Manual extraction of data from complex financial and M&A documents diverts time from high-level advisory work.",
        "Hi Paul,\n\nAs Embark continues to turn complex financial problems into clear solutions for clients from blue chips to boutiques, your advisors likely spend countless hours manually extracting data from dense deal and compliance documents. Our Universal Document Analysis platform eliminates this tedious manual data entry, empowering your teams to extract accurate insights instantly and focus entirely on strategic advisory. I would love to connect and show how CPAAutomation can streamline your firm's document workflows and enhance your Data Analytics & Automation offerings."
    ]
]

with open("/home/ianstewart/pipelines/b2b_lead_gen/leads.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(new_rows)
    
with open("/home/ianstewart/pipelines/b2b_lead_gen/processed_domains.txt", "a", encoding="utf-8") as f:
    for row in new_rows:
        domain = urllib.parse.urlparse(row[1]).netloc
        domain = domain.replace("www.", "")
        f.write(f"{domain}\n")
print("Success")
