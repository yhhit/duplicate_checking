import time
import uvicorn
from fastapi import FastAPI, UploadFile, File
from tortoise.contrib.fastapi import register_tortoise
from tortoise.expressions import Q

# 导入你项目中的模块
# 确保 models.py, config.py, fingerprint_utils.py 在同一目录下
from models import CodeOrder, CodeFingerprint
from fingerprint_utils import SimHashEngine, split_code_into_chunks
from config import settings

app = FastAPI(title="Code Duplicate Checker")
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
    uvicorn.run("main:app", host="127.0.0.1", port=8003, reload=True)