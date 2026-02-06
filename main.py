import time
import uvicorn
from fastapi import FastAPI, UploadFile, File
from tortoise.contrib.fastapi import register_tortoise
from tortoise.expressions import Q
from typing import Optional
from winnowing_utils import normalize_to_tokens_with_lines, winnow, shard_of_fp
# 导入你项目中的模块
# 确保 models.py, config.py, fingerprint_utils.py 在同一目录下
from models import CodeOrder, CodeFingerprint
from fingerprint_utils import SimHashEngine, split_code_into_chunks
from config import settings

app = FastAPI(title="Code Duplicate Checker")
engine = SimHashEngine()


# main.py 里新增 imports
from collections import Counter, defaultdict
from tortoise.transactions import in_transaction

from winnowing_utils import normalize_to_tokens_with_lines, winnow

MAX_QUERY_FPS = 1200
RECALL_BATCH = 300
TOP_N = 80
MIN_HIT = 6
MIN_COVERAGE = 0.06
K = 35
WINDOW = 10

def table_for_shard(shard: int) -> str:
    return f"code_postings_{shard:02x}"

def merge_intervals(intervals):
    intervals = sorted(intervals)
    merged = []
    for s, e in intervals:
        if not merged or s > merged[-1][1] + 1:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    return [(a, b) for a, b in merged]

def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

@app.post("/api/duplicate-check-v2")
async def duplicate_check_v2(
    file: UploadFile = File(...),
    top_n: int = TOP_N,
    exclude_order_ids: Optional[str] = None,  # 例如 "12,34,56"
):
    exclude_set = set()
    if exclude_order_ids:
        exclude_set = {int(x) for x in exclude_order_ids.split(",") if x.strip().isdigit()}
    code = (await file.read()).decode("utf-8", errors="ignore")
    total_lines = len(code.splitlines())

    tokens, token_lines = normalize_to_tokens_with_lines(code)
    in_fps = winnow(tokens, token_lines, k=K, window=WINDOW)
    if not in_fps:
        return {"filename": file.filename, "total_lines": total_lines, "duplicate_rate": "0.00%", "details": []}

    # Cap query fps
    if len(in_fps) > MAX_QUERY_FPS:
        step = max(1, len(in_fps) // MAX_QUERY_FPS)
        in_fps = in_fps[::step][:MAX_QUERY_FPS]

    fp_values = [f.fp for f in in_fps]

    # Build input index: fp -> list of Fingerprint
    in_by_fp = defaultdict(list)
    for f in in_fps:
        in_by_fp[f.fp].append(f)

    # group fps by shard
    fps_by_shard = defaultdict(list)
    for fp in fp_values:
        fps_by_shard[shard_of_fp(fp)].append(fp)

    # 1) recall: order_id -> hit count
    hits = defaultdict(int)
    async with in_transaction() as conn:
        for shard, fps in fps_by_shard.items():
            tbl = table_for_shard(shard)
            for sub in chunked(fps, RECALL_BATCH):
                ph = ",".join(["%s"] * len(sub))
                sql = f"""
                    SELECT order_id, COUNT(*) AS hit
                    FROM {tbl}
                    WHERE fp IN ({ph})
                    GROUP BY order_id
                """
                rows = await conn.execute_query_dict(sql, sub)
                for r in rows:
                    oid = int(r["order_id"])
                    if oid in exclude_set:
                        continue
                    hits[oid] += int(r["hit"])

    if not hits:
        return {"filename": file.filename, "total_lines": total_lines, "duplicate_rate": "0.00%", "details": []}

    # Pick top candidates
    candidates = [
        oid for oid, _ in sorted(hits.items(), key=lambda x: x[1], reverse=True)
        if oid not in exclude_set
    ][:top_n]

    details = []
    suspicious_input_intervals = []

    # 2) rerank + evidence per candidate
    for oid in candidates:
        if oid in exclude_set:
            continue
        # Pull matched postings for this order, across shards.
        postings = []
        async with in_transaction() as conn:
            for shard, fps in fps_by_shard.items():
                tbl = table_for_shard(shard)
                for sub in chunked(fps, RECALL_BATCH):
                    ph = ",".join(["%s"] * len(sub))
                    sql = f"""
                        SELECT fp, pos, start_line, end_line
                        FROM {tbl}
                        WHERE order_id=%s AND fp IN ({ph})
                    """
                    rows = await conn.execute_query_dict(sql, [oid] + sub)
                    postings.extend(rows)

        if len(postings) < MIN_HIT:
            continue

        # offset alignment
        offset_counter = Counter()
        pairs = []
        for p in postings:
            fp = int(p["fp"])
            for inf in in_by_fp.get(fp, []):
                off = int(p["pos"]) - inf.pos
                offset_counter[off] += 1
                pairs.append((off, inf, p))

        if not offset_counter:
            continue

        best_off, best_cnt = offset_counter.most_common(1)[0]
        if best_cnt < MIN_HIT:
            continue

        in_intervals = []
        db_intervals = []
        for off, inf, p in pairs:
            if off != best_off:
                continue
            in_intervals.append((inf.start_line, inf.end_line))
            db_intervals.append((int(p["start_line"]), int(p["end_line"])))

        in_merged = merge_intervals(in_intervals)
        db_merged = merge_intervals(db_intervals)

        covered = sum(e - s + 1 for s, e in in_merged)
        coverage = covered / total_lines if total_lines else 0.0
        if coverage < MIN_COVERAGE:
            continue

        order = await CodeOrder.get(id=oid)
        suspicious_input_intervals.extend(in_merged)

        details.append({
            "match_order_id": oid,
            "match_project": order.project_name,
            "hit_fingerprints": int(best_cnt),
            "coverage": f"{coverage*100:.2f}%",
            "evidence": [
                {"input_lines": f"{s1}-{e1}", "match_lines": f"{s2}-{e2}"}
                for (s1, e1), (s2, e2) in list(zip(in_merged, db_merged))[:10]
            ],
        })

    merged_all = merge_intervals(suspicious_input_intervals)
    covered_all = sum(e - s + 1 for s, e in merged_all)
    dup_rate = covered_all / total_lines if total_lines else 0.0

    return {
        "filename": file.filename,
        "total_lines": total_lines,
        "duplicate_rate": f"{dup_rate*100:.2f}%",
        "details": details[:20],
    }

@app.post("/api/duplicate-check")
async def check_duplicate(file: UploadFile = File(...)):
    """
    上传代码文件，返回查重报告。
    """
    start_time = time.time()
    content_bytes = await file.read()
    
    try:
        code_content = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return {"error": "文件编码格式错误，请上传 UTF-8 文本文件"}

    # 1. 将上传的代码切片
    input_chunks = split_code_into_chunks(code_content, window_size=15, step=10)
    
    report = []
    total_suspicious_lines = set()
    
    # 2. 逐个块进行比对
    for chunk in input_chunks:
        chunk_hash = engine.compute_simhash(chunk['content'])
        
        # 切分指纹用于索引查询
        parts = engine.split_fingerprint_to_parts(chunk_hash)
        
        # 【核心优化】利用数据库索引快速筛选候选集
        # 查找任意一段指纹(part_1...part_4)相同的记录
        candidates = await CodeFingerprint.filter(
            Q(part_1=parts[0]) | 
            Q(part_2=parts[1]) | 
            Q(part_3=parts[2]) | 
            Q(part_4=parts[3])
        ).values(
            'fingerprint', 
            'order_id', 
            'order__project_name', 
            'start_line', 
            'end_line'
        )
        
        best_match = None
        min_dist = 100
        
        # 在候选集中精算海明距离
        for db_fp in candidates:
            dist = engine.hamming_distance(chunk_hash, db_fp['fingerprint'])
            
            # 阈值判定：海明距离 <= 3 视为高度相似
            if dist <= 3:
                if dist < min_dist:
                    min_dist = dist
                    best_match = db_fp
        
        if best_match:
            # 记录重复详情
            match_info = {
                "input_lines": f"{chunk['start_line']} - {chunk['end_line']}",
                "match_project": best_match['order__project_name'],
                "match_order_id": best_match['order_id'],
                "match_lines": f"{best_match['start_line']} - {best_match['end_line']}",
                "similarity_score": f"{(1 - min_dist/64)*100:.1f}%"
            }
            report.append(match_info)
            
            # 记录行号用于计算总重复率
            for i in range(chunk['start_line'], chunk['end_line'] + 1):
                total_suspicious_lines.add(i)

    # 3. 计算统计数据
    total_lines = len(code_content.split('\n'))
    duplicate_rate = len(total_suspicious_lines) / total_lines if total_lines > 0 else 0

    return {
        "filename": file.filename,
        "total_lines": total_lines,
        "duplicate_rate": f"{duplicate_rate * 100:.2f}%",
        "process_time": f"{time.time() - start_time:.2f}s",
        "details": report[:50] # 只返回前50条详情
    }

# 注册 Tortoise ORM
register_tortoise(
    app,
    db_url=settings.DATABASE_URL,
    modules={"model": ["models"]}, 
    generate_schemas=True,
    add_exception_handlers=True,
)

# --- 这里是关键：添加启动入口 ---
if __name__ == "__main__":
    # 使用 uvicorn 启动应用
    # host="0.0.0.0" 允许局域网访问
    # port=8000 默认端口
    # reload=True 代码修改后自动重启 (仅开发模式推荐)
    print("启动查重服务: http://127.0.0.1:8003/docs")
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)