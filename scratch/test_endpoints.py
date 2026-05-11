import requests

rxcui = "1549155"
url1 = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/status.json"
res1 = requests.get(url1)
print("1.", res1.status_code, res1.text[:100])
