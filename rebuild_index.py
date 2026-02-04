# rebuild_index.py
from tortoise import Tortoise, run_async
from models import CodeOrder, CodeFingerprint, OrderStatus
from fingerprint_utils import SimHashEngine, split_code_into_chunks
from config import settings

async def init():
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={"model": ["models"]}
    )

async def rebuild():
    await init()
    engine = SimHashEngine()
    
    # 1. 清空旧指纹 (可选)
    # await CodeFingerprint.all().delete()
    # print("旧指纹已清理")

    # 2. 获取所有已完成的订单
    orders = await CodeOrder.filter(status=OrderStatus.COMPLETED).all()
    print(f"找到 {len(orders)} 个已完成订单，开始构建索引...")

    count = 0
    for order in orders:
        if not order.generated_code:
            continue
            
        # 检查是否已经建立过索引 (避免重复)
        exists = await CodeFingerprint.filter(order=order).exists()
        if exists:
            continue

        chunks = split_code_into_chunks(order.generated_code, window_size=15, step=10)
        
        fingerprint_objects = []
        for chunk in chunks:
            f_val = engine.compute_simhash(chunk['content'])
            
            # 切分指纹
            parts = engine.split_fingerprint_to_parts(f_val)
            
            fp = CodeFingerprint(
                order=order,
                fingerprint=f_val,
                # 填充索引字段
                part_1=parts[0],
                part_2=parts[1],
                part_3=parts[2],
                part_4=parts[3],
                start_line=chunk['start_line'],
                end_line=chunk['end_line']
            )
            fingerprint_objects.append(fp)
        
        # 批量插入
        if fingerprint_objects:
            await CodeFingerprint.bulk_create(fingerprint_objects)
            count += len(fingerprint_objects)
            
        print(f"订单 {order.id} ({order.project_name}) 索引构建完成，生成 {len(fingerprint_objects)} 个指纹块")

    print(f"所有任务完成，共插入 {count} 条指纹记录。")

if __name__ == "__main__":
    run_async(rebuild())