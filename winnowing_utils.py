# winnowing_utils.py
import re
import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

@dataclass(frozen=True)
class Fingerprint:
    fp: int
    pos: int
    start_line: int
    end_line: int

# Coarse keyword set for Python/Java/JS. Keeps structure tokens stable under renaming.
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
    """
    Minimal cross-language token normalization:
    - removes //, /* */, # comments (best-effort)
    - normalizes strings->STR, numbers->NUM, identifiers->ID (keeps keywords)
    - keeps operators/punctuations as tokens
    Returns: (tokens, token_line_numbers)
    """
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.DOTALL)
    code = re.sub(r"//.*", " ", code)
    code = re.sub(r"#.*", " ", code)

    tokens: List[str] = []
    lines: List[int] = []

    for ln, line in enumerate(code.splitlines(), start=1):
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
                elif w == "str":
                    tok = "STR"
                elif w == "num":
                    tok = "NUM"
                else:
                    tok = "ID"
                tokens.append(tok)
                lines.append(ln)
                i = m.end()
                continue

            i += 1

    return tokens, lines

MASK64 = (1 << 64) - 1
SIGN_BIT = 1 << 63

def to_int64(u: int) -> int:
    """Map 0..2^64-1 -> signed int64 range."""
    u &= MASK64
    return u - (1 << 64) if (u & SIGN_BIT) else u

def _hash64(s: str) -> int:
    h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest()
    u = int.from_bytes(h, "big", signed=False)
    return to_int64(u)

def shard_fp(fp: int) -> int:
    # fp is signed; convert back to 64-bit unsigned space for sharding
    u = fp & MASK64
    return u & 0x3F


def _hash64(s: str) -> int:
    # stable 64-bit hash
    h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "big", signed=False)

def _kgram_hash(tokens: List[str], start: int, k: int) -> int:
    return _hash64("\x1f".join(tokens[start:start + k]))

def winnow(tokens: List[str], token_lines: List[int], k: int = 25, window: int = 6) -> List[Fingerprint]:
    if len(tokens) < k:
        return []

    hashes = [_kgram_hash(tokens, i, k) for i in range(0, len(tokens) - k + 1)]
    fps: List[Fingerprint] = []

    last_idx = -1
    last_val = None

    for i in range(0, len(hashes) - window + 1):
        w = hashes[i:i + window]
        min_val = min(w)
        j = i + w.index(min_val)

        if j != last_idx or min_val != last_val:
            start_line = token_lines[j]
            end_line = token_lines[min(j + k - 1, len(token_lines) - 1)]
            fps.append(Fingerprint(fp=min_val, pos=j, start_line=start_line, end_line=end_line))
            last_idx = j
            last_val = min_val

    return fps

def shard_fp(fp: int) -> int:
    return fp & 0x3F  # 64 shards

def group_fps_by_shard(fps: Iterable[int]) -> Dict[int, List[int]]:
    out: Dict[int, List[int]] = {}
    for fp in fps:
        s = shard_fp(fp)
        out.setdefault(s, []).append(fp)
    return out