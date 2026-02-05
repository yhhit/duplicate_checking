# rebuild_index_fast.py
import asyncio
from tortoise import Tortoise, run_async
from tortoise.functions import Max
from models import CodeOrder, CodeFingerprint, OrderStatus
from fingerprint_utils import SimHashEngine, split_code_into_chunks
from config import settings

BATCH_SIZE = 100  # 每次处理 100 个订单，根据内存大小调整

async def init():
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={"model": ["models"]}
    )
    # 生产环境通常不需要 generate_schemas，除非是新库
    # await Tortoise.generate_schemas(safe=True)

async def get_start_id():
    """
    获取当前指纹库中处理到的最大 Order ID。
    这能让我们瞬间定位到上次结束的位置。
    """
    print("正在查询最后一次构建的进度...")
    # 使用聚合函数 Max 查找，速度极快
    result = await CodeFingerprint.all().annotate(max_oid=Max("order_id")).first()
    
    if result and result.max_oid:
        return result.max_oid
    return 0

async def rebuild_fast():
    await init()
    engine = SimHashEngine()
    
    # 1. 快速定位起点
    last_id = await get_start_id()
    print(f"检测到上次处理到了 订单ID: {last_id}，将从此处继续...")

    total_processed = 0
    
    while True:
        # 2. 批量获取未处理的订单 (利用主键索引，速度极快)
        # 逻辑：获取 ID 比 last_id 大的已完成订单，限制数量
        # orders = await CodeOrder.filter(
        #     id__gt=last_id, 
        #     status=OrderStatus.COMPLETED
        # ).order_by("id").limit(BATCH_SIZE).all()
        orders = await CodeOrder.filter(
            id__gt=last_id,
            id__lte=50000,          # 先跑 5w
            status=OrderStatus.COMPLETED,
        ).order_by("id").limit(BATCH_SIZE)

        if not orders:
            print("所有订单已处理完毕。")
            break

        fingerprints_buffer = []
        current_batch_ids = []

        print(f"正在处理批次: ID {orders[0].id} -> {orders[-1].id} (共 {len(orders)} 个)...")

        for order in orders:
            current_batch_ids.append(order.id)
            
            if not order.generated_code:
                continue

            # 这里的业务逻辑不变
            chunks = split_code_into_chunks(order.generated_code, window_size=15, step=10)
            
            for chunk in chunks:
                f_val = engine.compute_simhash(chunk['content'])
                parts = engine.split_fingerprint_to_parts(f_val)
                
                fp = CodeFingerprint(
                    order_id=order.id, # 直接使用ID，避免对象关联查询开销
                    fingerprint=f_val,
                    part_1=parts[0],
                    part_2=parts[1],
                    part_3=parts[2],
                    part_4=parts[3],
                    start_line=chunk['start_line'],
                    end_line=chunk['end_line']
                )
                fingerprints_buffer.append(fp)

        # 3. 批量入库
        if fingerprints_buffer:
            # 这里的 batch_size 是 SQL 语句层面的分批，防止单条 SQL 过长
            await CodeFingerprint.bulk_create(fingerprints_buffer, batch_size=500)
            total_processed += len(fingerprints_buffer)
        
        # 4. 更新游标
        last_id = orders[-1].id
        print(f"批次完成。当前进度 ID: {last_id}，本次新增指纹: {len(fingerprints_buffer)}")

    print(f"任务结束，本次运行共插入 {total_processed} 条指纹。")

if __name__ == "__main__":
    # 建议使用 uvloop 提高异步性能 (可选)
    # import uvloop
    # uvloop.install()
    run_async(rebuild_fast())