# winnowing_utils.py
import re
import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

MASK64 = (1 << 64) - 1
SIGN_BIT = 1 << 63

def to_uint64(x: int) -> int:
    return x & MASK64

def to_int64(x: int) -> int:
    """
    Map any int to signed int64 range [-2^63, 2^63-1] using 2's complement.
    """
    u = x & MASK64
    return u - (1 << 64) if (u & SIGN_BIT) else u

def shard_of_fp(fp_int64: int) -> int:
    """
    fp is stored/transferred as signed int64.
    For sharding we interpret it as uint64 and take low 6 bits.
    """
    return (fp_int64 & MASK64) & 0x3F  # 0..63

@dataclass(frozen=True)
class Fingerprint:
    fp: int          # signed int64
    pos: int
    start_line: int
    end_line: int

_KEYWORDS = {
    "if","else","elif","for","while","return","break","continue",
    "try","except","finally","catch","throw",
    "class","def","function","lambda",
    "import","from","as","export","default",
    "new","this","super","extends","implements","interface",
    "switch","case",
    "public","private","protected","static","final",
    "void","int","float","double","boolean","char","string",
    "true","false","null","none",
}

_STR_RE = re.compile(r"""('([^'\\]|\\.)*'|"([^"\\]|\\.)*"|`([^`\\]|\\.)*`)""")
_NUM_RE = re.compile(r"\b\d+(\.\d+)?\b")
_ID_RE = re.compile(r"\b[a-zA-Z_]\w*\b")
_OP_RE = re.compile(r"==|!=|<=|>=|\+\+|--|\+=|-=|\*=|/=|&&|\|\||[+\-*/%<>=!(){}\[\].,;:]")

def normalize_to_tokens_with_lines(code: str) -> Tuple[List[str], List[int]]:
    # 移除注释
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.DOTALL)
    code = re.sub(r"//.*", " ", code)
    code = re.sub(r"#.*", " ", code)

    tokens: List[str] = []
    lines: List[int] = []

    for ln, line in enumerate(code.splitlines(), start=1):
        # 预处理：跳过导入语句和空行，减少干扰
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith(("import ", "from ", "include ", "#include")):
            continue

        line = _STR_RE.sub(" STR ", line)
        line = _NUM_RE.sub(" NUM ", line)

        i = 0
        while i < len(line):
            m = _OP_RE.match(line, i)
            if m:
                tokens.append(m.group(0))
                lines.append(ln)
                i = m.end()
                continue

            m = _ID_RE.match(line, i)
            if m:
                w = m.group(0).lower()
                if w in _KEYWORDS:
                    tok = w
                else:
                    # 将所有非常量/关键字的标识符统一为 ID，增强抗混淆能力
                    tok = "ID"
                tokens.append(tok)
                lines.append(ln)
                i = m.end()
                continue

            i += 1

    return tokens, lines

def _hash64_signed(s: str) -> int:
    """
    stable 64-bit hash, returned as signed int64 (fits MySQL BIGINT and asyncmy)
    """
    b = hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest()
    u = int.from_bytes(b, "big", signed=False)  # 0..2^64-1
    return to_int64(u)

def _kgram_hash(tokens: List[str], start: int, k: int) -> int:
    return _hash64_signed("\x1f".join(tokens[start:start + k]))

def winnow(tokens: List[str], token_lines: List[int], k: int = 20, window: int = 5) -> List[Fingerprint]:
    if len(tokens) < k:
        return []

    hashes = [_kgram_hash(tokens, i, k) for i in range(0, len(tokens) - k + 1)]
    fps: List[Fingerprint] = []

    last_idx = -1
    last_val = None

    for i in range(0, len(hashes) - window + 1):
        w = hashes[i:i + window]
        min_val = min(w)  # signed compare OK; stable as long as both sides use same function
        j = i + w.index(min_val)

        if j != last_idx or min_val != last_val:
            start_line = token_lines[j]
            end_line = token_lines[min(j + k - 1, len(token_lines) - 1)]
            fps.append(Fingerprint(fp=min_val, pos=j, start_line=start_line, end_line=end_line))
            last_idx = j
            last_val = min_val

    return fps

def group_fps_by_shard(fps: Iterable[int]) -> Dict[int, List[int]]:
    out: Dict[int, List[int]] = {}
    for fp in fps:
        out.setdefault(shard_of_fp(fp), []).append(fp)
    return out