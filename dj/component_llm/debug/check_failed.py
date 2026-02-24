"""실패한 청구항 정보를 확인하는 스크립트."""
import json
from pathlib import Path

fp = r"C:\00AI\project\project_final\patent-rag\dj\data\json_refine\20260129190416\(refine)1020257022508.json"
out = Path(__file__).parent / "output" / "check_failed_result.txt"
data = json.load(open(fp, encoding="utf-8"))
claims = data.get("claims", {}).get("last_version", {}).get("claims", [])
targets = [53, 78, 98, 148, 161, 164]
lines = []
for c in claims:
    n = c.get("claim_number")
    if n in targets:
        text = c.get("text", "")
        lines.append(f"claim {n}: type={c.get('claim_type')}, text_len={len(text)}, change_code={c.get('change_code', '')}")
        lines.append(f"  text_preview: {text[:300]}...")
        lines.append("")
out.write_text("\n".join(lines), encoding="utf-8")
print(f"saved to {out}")
