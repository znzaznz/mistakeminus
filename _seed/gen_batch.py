"""通用：把 ROWS 列表写成 seed JSON。各 batch 改 ROWS 即可。"""
import json, sys

def build(rows):
    out = []
    for r in rows:
        kp, qt, stem, ans, expl = r[0], r[1], r[2], r[3], r[4]
        q = {"knowledge_point_id": kp, "question_type": qt, "stem": stem,
             "correct_answer": ans, "explanation": expl}
        if len(r) > 5 and r[5]:
            q["options"] = [{"key": k, "text": t} for k, t in r[5]]
        out.append(q)
    return out

if __name__ == "__main__":
    mod = __import__(sys.argv[1])
    data = build(mod.ROWS)
    path = sys.argv[2]
    open(path, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))
    print("题数", len(data), "覆盖KP", len(set(q["knowledge_point_id"] for q in data)))
