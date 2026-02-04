# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from tortoise.contrib.fastapi import register_tortoise
from models import CodeOrder, CodeFingerprint
from fingerprint_utils import SimHashEngine, split_code_into_chunks
from config import settings
import time
from tortoise.expressions import Q
app = FastAPI()
engine = SimHashEngine()

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

    for chunk in input_chunks:
        chunk_hash = engine.compute_simhash(chunk['content'])
        parts = engine.split_fingerprint_to_parts(chunk_hash)
        
        # 【优化查询】只查找命中任意一段的记录
        # 这一步利用了数据库索引，极大减少了需要计算海明距离的数量
        candidates = await CodeFingerprint.filter(
            Q(part_1=parts[0]) | 
            Q(part_2=parts[1]) | 
            Q(part_3=parts[2]) | 
            Q(part_4=parts[3])
        ).values('fingerprint', 'order_id', 'order__project_name', 'start_line', 'end_line')
        
        best_match = None
        min_dist = 100 # 初始化一个大值
        
        # 在候选集中精细计算距离
        for db_fp in candidates:
            dist = engine.hamming_distance(chunk_hash, db_fp['fingerprint'])
            
            if dist <= 3: # 阈值
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
                "similarity_score": f"{(1 - min_dist/64)*100:.1f}%" # 简单估算
            }
            report.append(match_info)
            
            # 记录行号用于计算总重复率
            for i in range(chunk['start_line'], chunk['end_line'] + 1):
                total_suspicious_lines.add(i)

    # 4. 计算统计数据
    total_lines = len(code_content.split('\n'))
    duplicate_rate = len(total_suspicious_lines) / total_lines if total_lines > 0 else 0

    return {
        "filename": file.filename,
        "total_lines": total_lines,
        "duplicate_rate": f"{duplicate_rate * 100:.2f}%",
        "process_time": f"{time.time() - start_time:.2f}s",
        "details": report[:50] # 只返回前50条重复记录，避免包体过大
    }

# 注册数据库 (根据你的 config.py)
register_tortoise(
    app,
    db_url=settings.DATABASE_URL,
    modules={"model": ["models"]}, # 确保这里的模块路径正确
    generate_schemas=True,
    add_exception_handlers=True,
)