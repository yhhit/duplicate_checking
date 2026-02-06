# rebuild_postings_sharded.py
import asyncio
from tortoise import Tortoise, run_async
from tortoise.transactions import in_transaction
from winnowing_utils import shard_fp
from config import settings
from models import CodeOrder, OrderStatus
from winnowing_utils import normalize_to_tokens_with_lines, winnow, group_fps_by_shard
from winnowing_utils import normalize_to_tokens_with_lines, winnow, shard_of_fp
BATCH_SIZE = 20

# Control storage: cap fingerprints per order to avoid extreme docs blowing up storage.
MAX_FPS_PER_DOC = 5000

BATCH_SIZE = 10
MAX_FPS_PER_DOC = 1200
INSERT_BATCH = 300
K = 35
WINDOW = 10

def table_for_shard(shard: int) -> str:
    return f"code_postings_{shard:02x}"

async def init():
    await Tortoise.init(db_url=settings.DATABASE_URL, modules={"model": ["models"]})

async def get_last_order_id():
    # Use max(order_id) across shards is expensive; keep a progress table in production.
    # Minimal version: just start from 0.
    return 0

async def delete_existing_postings(conn, order_id: int):
    # Delete from all shards. This is 64 statements; acceptable for rebuild, but you
    # can optimize by only deleting shards you are about to touch (we do that below).
    for shard in range(64):
        await conn.execute_query(f"DELETE FROM {table_for_shard(shard)} WHERE order_id=%s", [order_id])

async def rebuild():
    await init()
    last_id = await get_last_order_id()

    while True:
        orders = await CodeOrder.filter(
            id__gt=last_id,
            id__lte=50000,          # 先跑 5w
            status=OrderStatus.COMPLETED,
        ).order_by("id").limit(BATCH_SIZE)

        if not orders:
            print("All done.")
            break

        for order in orders:
            last_id = order.id
            code = order.generated_code or ""
            if not code.strip():
                continue

            tokens, token_lines = normalize_to_tokens_with_lines(code)
            fps = winnow(tokens, token_lines, k=K, window=WINDOW)

            if not fps:
                continue

            # Cap fingerprints to control storage / query cost (uniform sampling).
            if len(fps) > MAX_FPS_PER_DOC:
                step = max(1, len(fps) // MAX_FPS_PER_DOC)
                fps = fps[::step][:MAX_FPS_PER_DOC]

            fps_by_shard = {}
            for f in fps:
                fps_by_shard.setdefault(shard_of_fp(f.fp), []).append(f)

            async with in_transaction() as conn:
                # Delete only shards we will write into.
                for shard in fps_by_shard.keys():
                    await conn.execute_query(
                        f"DELETE FROM {table_for_shard(shard)} WHERE order_id=%s",
                        [order.id],
                    )
                def chunked(lst, n):
                    for i in range(0, len(lst), n):
                        yield lst[i:i+n]
                # Insert per shard in bulk.
                for shard, fplist in fps_by_shard.items():
                    tbl = table_for_shard(shard)

                    for part in chunked(fplist, INSERT_BATCH):
                        values = []
                        for f in part:
                            values.extend([f.fp, order.id, f.pos, f.start_line, f.end_line])

                        row_ph = "(%s,%s,%s,%s,%s)"
                        sql = f"INSERT INTO {tbl} (fp, order_id, pos, start_line, end_line) VALUES " + ",".join(
                            [row_ph] * len(part)
                        )
                        await conn.execute_query(sql, values)

            print(f"order {order.id}: inserted {len(fps)} fingerprints into {len(fps_by_shard)} shards")

if __name__ == "__main__":
    run_async(rebuild())