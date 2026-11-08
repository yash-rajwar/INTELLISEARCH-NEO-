import csv, sys

path = "eval/questions_draft.csv"
qid, span = sys.argv[1], sys.argv[2]
with open(path, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)
gold = next(k for k in fields if "gold" in k.lower())
idc = fields[0]
hit = [r for r in rows if r[idc].strip() == qid]
if len(hit) != 1:
    sys.exit(f"STOP: found {len(hit)} rows for {qid}")
print("old:", " ".join(hit[0][gold].split()))
hit[0][gold] = span
with open(path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
print("new:", span)