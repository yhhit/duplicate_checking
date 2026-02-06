# 查重索引重新构建指南

当你修改了代码查重的核心参数（如 `winnowing_utils.py` 中的 `K` 值或 `WINDOW` 窗口大小）后，数据库中已有的旧指纹将不再适用于新的查询逻辑。为了保证查重率（特别是针对 3000 行以上的大型文件），你需要按照以下步骤重新构建索引。

## 1. 核心参数确认

在开始之前，请确保以下文件中的参数已保持一致：
- `winnowing_utils.py`: 影响指纹生成逻辑。
- `main.py`: 影响 API 查询时的匹配逻辑。
- `rebuild_postings_sharded.py`: 影响入库时的索引逻辑。

**建议参数（针对高查重率优化）：**
- `K`: 20 (原为 35)
- `WINDOW`: 5 (原为 10)
- `MAX_FPS_PER_DOC`: 10000 (原为 1200)

---

## 2. 重新构建指纹索引 (Winnowing / v2 接口)

这是目前最主要的查重方式，数据存储在 64 个分片表 (`code_postings_00` 到 `code_postings_3f`) 中。

### 步骤 A：清空旧指纹 (可选但推荐)
如果你想彻底清除旧参数生成的指纹，可以手动清空数据库表，或者直接依赖脚本的自动删除逻辑。
*脚本逻辑已包含：在插入每个订单的新指纹前，会自动执行 `DELETE FROM table WHERE order_id = ...`。*

### 步骤 B：运行重构脚本
确保 `rebuild_postings_sharded.py` 中的 `get_last_order_id()` 返回 `0`。

```bash
python rebuild_postings_sharded.py
```

**运行说明：**
- 脚本会从 `id=1` 的订单开始扫描。
- 每次处理 `BATCH_SIZE` 个订单（默认 10）。
- 对于每个订单，它会：
  1. 计算高密度指纹。
  2. 删除该订单在数据库中的旧记录。
  3. 批量插入新指纹到对应的分片表中。

---

## 3. 重新构建 SimHash 索引 (v1 接口)

如果你也使用了基础的 SimHash 查重（`code_fingerprints` 表），请运行：

```bash
python rebuild_index.py
```

**注意：** 此脚本同样支持断点续传。如果需要彻底重跑，请先清空 `code_fingerprints` 表：
```sql
TRUNCATE TABLE code_fingerprints;
```

---

## 4. 进度监控与验证

### 监控日志
在运行 `rebuild_postings_sharded.py` 时，你会在终端看到类似以下的输出：
```text
order 101: inserted 2543 fingerprints into 64 shards
order 102: inserted 1890 fingerprints into 64 shards
```
如果 `inserted` 的数量显著增加（例如从几百个变成几千个），说明高密度指纹已生效。

### 验证查重率
重构完成后，通过 API 重新上传之前查重率低的文件。
- **预期结果：** 3000 行代码的 `duplicate_rate` 应该有明显提升。
- **原因：** 更小的 `K` 和 `WINDOW` 捕捉了更细碎的逻辑，更高的 `MAX_FPS` 避免了长代码的采样丢失。

---

## 5. 故障排除

1. **速度变慢：** 增加指纹密度会显著增加数据库负载。如果重构过慢，可尝试调大 `INSERT_BATCH`。
2. **内存溢出：** 如果处理超大型项目出现内存问题，请减小 `BATCH_SIZE`。
3. **数据库空间：** 高密度指纹会占用更多磁盘空间（约为原来的 4-6 倍），请确保数据库磁盘空间充足。
