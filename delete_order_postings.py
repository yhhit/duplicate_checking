# delete_order_postings.py
import sys
from tortoise import Tortoise, run_async
from tortoise.transactions import in_transaction
from config import settings

def tbl(i: int) -> str:
    return f"code_postings_{i:02x}"

async def main(order_id: int):
    await Tortoise.init(db_url=settings.DATABASE_URL, modules={"model": ["models"]})
    async with in_transaction() as conn:
        for i in range(64):
            await conn.execute_query(f"DELETE FROM {tbl(i)} WHERE order_id=%s", [order_id])
    await Tortoise.close_connections()
    print(f"deleted postings for order_id={order_id}")

if __name__ == "__main__":
    run_async(main(int(sys.argv[1])))