"""CSV 컬럼별 최대 길이 확인."""
import csv
from pathlib import Path

csv_path = Path(__file__).parent / "output" / "components.csv"
max_comp = 0
max_note = 0
max_comp_chunk = ""
max_note_chunk = ""

with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cl = len(row["components"])
        nl = len(row.get("note", "") or "")
        if cl > max_comp:
            max_comp = cl
            max_comp_chunk = row["chunk_id"]
        if nl > max_note:
            max_note = nl
            max_note_chunk = row["chunk_id"]

out = Path(__file__).parent / "output" / "max_len_result.txt"
out.write_text(
    f"components 최대 길이: {max_comp}자 (chunk_id: {max_comp_chunk})\n"
    f"note 최대 길이: {max_note}자 (chunk_id: {max_note_chunk})\n",
    encoding="utf-8",
)
print(f"saved to {out}")
