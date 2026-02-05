# models.py
from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
import enum

class OrderStatus(str, enum.Enum):
    """Represents a code generation order."""
    PENDING = "PENDING"         # Waiting for processing
    GENERATING = "GENERATING"   # Generation in progress
    COMPLETED = "COMPLETED"     # Generation complete
    FAILED = "FAILED"           # Generation failed
    UNKNOWN = "UNKNOWN"         # Status couldn't be determined

class CodeOrder(models.Model):
    """Represents a code generation order."""
    id = fields.IntField(pk=True, description="The unique ID provided for the order")
    project_name = fields.CharField(max_length=255)
    source = fields.CharField(max_length=50)
    language = fields.CharField(max_length=50)
    grade = fields.IntField()
    function_descriptions_json = fields.TextField(description="JSON string of function descriptions")
    status = fields.CharEnumField(OrderStatus, default=OrderStatus.PENDING, max_length=20)
    generated_code = fields.TextField(null=True, description="Generated code or result")
    error_message = fields.TextField(null=True)
    client_ip = fields.CharField(max_length=45, null=True, description="IP address of the client who created the order")
    current_line = fields.IntField(default=0, description="当前已生成行数")
    api_key = fields.CharField(max_length=100, null=True, description="Openai api key")
    base_url = fields.CharField(max_length=100, null=True, description="Openai api base url")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "code_orders"
        ordering = ["-created_at"]
        indexes = (
            ("status",),
            ("created_at",),
            ("updated_at",),
            ("client_ip",),
            ("project_name",),
            # 常见组合：按状态筛选后按时间排序/查询
            ("status", "created_at"),
        )

    def __str__(self):
        return f"Order {self.id} ({self.project_name})"

CodeOrder_Pydantic = pydantic_model_creator(CodeOrder, name="CodeOrder")
CodeOrderIn_Pydantic = pydantic_model_creator(CodeOrder, name="CodeOrderIn", exclude_readonly=True)

class AllowedIPs(models.Model):
    """Represents allowed IPs for the service."""
    ip = fields.CharField(max_length=50, pk=True, description="The IP address")
    port = fields.IntField(description="Port number")
    description = fields.CharField(max_length=255, null=True, description="Description of the allowed IP")

    class Meta:
        table = "allowed_ips"
        indexes = (
            ("port",),
        )

    def __str__(self):
        return f"Allowed IP {self.ip}:{self.port} ({self.description})"
    
AllowedIPs_Pydantic = pydantic_model_creator(AllowedIPs, name="AllowedIPs")
AllowedIPsIn_Pydantic = pydantic_model_creator(AllowedIPs, name="AllowedIPsIn", exclude_readonly=True)


class CodeFingerprint(models.Model):
    id = fields.IntField(pk=True)
    order = fields.ForeignKeyField('model.CodeOrder', related_name='fingerprints')
    
    # 完整指纹 (64位二进制字符串)
    fingerprint = fields.CharField(max_length=64, description="Full 64-bit binary SimHash")
    
    # 【新增】分段索引，用于加速查询
    # 将64位切分为4段，每段16位，存为Hex字符串(4个字符)
    part_1 = fields.CharField(max_length=4, index=True) 
    part_2 = fields.CharField(max_length=4, index=True)
    part_3 = fields.CharField(max_length=4, index=True)
    part_4 = fields.CharField(max_length=4, index=True)
    
    start_line = fields.IntField()
    end_line = fields.IntField()

    class Meta:
        table = "code_fingerprints"

# models_fingerprint.py（或直接放 models.py）
from tortoise import fields, models

class CodePosting(models.Model):
    id = fields.BigIntField(pk=True)
    fp = fields.BigIntField(index=True, description="winnowing fingerprint (64-bit int)")
    order = fields.ForeignKeyField("model.CodeOrder", related_name="postings", index=True)

    # 指纹在归一化 token 序列中的位置（用于拼接连续命中片段）
    pos = fields.IntField(description="token position")

    # 证据用：落在原始代码的行范围（粗粒度即可）
    start_line = fields.IntField()
    end_line = fields.IntField()

    class Meta:
        table = "code_postings"
        indexes = (
            ("fp", "order_id"),   # 倒排扫描后可快速按 order 聚合
            ("order_id", "pos"),  # 精排时按位置取片段
        )
        # 如果你用 PostgreSQL，后续可考虑 fp 用 BIGINT + 分区/哈希分片（量大时）

class CodeDocStat(models.Model):
    """
    可选：存每个 order 的指纹数量、token数量，方便算覆盖率/比例并做过滤
    """
    order = fields.OneToOneField("model.CodeOrder", related_name="doc_stat", pk=True)
    fp_count = fields.IntField()
    token_count = fields.IntField()
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "code_doc_stats"
        indexes = (("fp_count",),)