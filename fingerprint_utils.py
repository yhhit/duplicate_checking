# fingerprint_utils.py
import re
import hashlib

class SimHashEngine:
    def __init__(self, width=64):
        self.width = width

    # 在 SimHashEngine 类中增加或作为独立函数
    def split_fingerprint_to_parts(self, fp_bin: str):
        """
        将64位二进制字符串切分为4段16位的Hex字符串
        """
        parts = []
        for i in range(4):
            start = i * 16
            segment = fp_bin[start : start + 16]
            # 二进制转Hex，去掉 '0x' 前缀，补齐4位
            hex_val = hex(int(segment, 2))[2:].zfill(4)
            parts.append(hex_val)
        return parts

    def _clean_code(self, content: str) -> str:
        """
        清洗代码：去注释、去标点、转小写。
        保留核心逻辑结构。
        """
        # 1. 去除注释 (简单正则，涵盖 // 和 /**/)
        content = re.sub(r'//.*', '', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # 2. 转小写
        content = content.lower()
        # 3. 仅保留字母数字 (Token化)
        tokens = re.findall(r'[a-z0-9]+', content)
        return tokens

    def _get_features(self, tokens, n_gram=3):
        """生成 N-gram 特征，锁定代码顺序结构"""
        features = []
        if len(tokens) < n_gram:
            return [' '.join(tokens)]
        for i in range(len(tokens) - n_gram + 1):
            features.append(' '.join(tokens[i:i+n_gram]))
        return features

    def _hash_func(self, x):
        return int(hashlib.md5(x.encode('utf-8')).hexdigest(), 16)

    def compute_simhash(self, content: str) -> str:
        """计算文本的 SimHash，返回 64位 二进制字符串"""
        tokens = self._clean_code(content)
        if not tokens:
            return "0" * self.width
            
        features = self._get_features(tokens)
        v = [0] * self.width
        
        for feature in features:
            h = self._hash_func(feature)
            for i in range(self.width):
                mask = 1 << i
                if h & mask:
                    v[i] += 1
                else:
                    v[i] -= 1
        
        fingerprint = 0
        for i in range(self.width):
            if v[i] > 0:
                fingerprint |= (1 << i)
        
        # 返回二进制字符串，补齐64位
        return bin(fingerprint)[2:].zfill(self.width)

    def hamming_distance(self, hash1_bin: str, hash2_bin: str) -> int:
        """计算两个二进制字符串的海明距离"""
        x = int(hash1_bin, 2) ^ int(hash2_bin, 2)
        return bin(x).count('1')

def split_code_into_chunks(code: str, window_size=20, step=10):
    """
    滑动窗口切分代码。
    window_size: 每个块包含多少行 (例如20行)
    step: 步长 (例如10行)，有重叠可以防止漏掉跨块的逻辑
    """
    lines = code.split('\n')
    total_lines = len(lines)
    chunks = []
    
    for i in range(0, total_lines, step):
        end = min(i + window_size, total_lines)
        if i >= end: break
        
        chunk_content = '\n'.join(lines[i:end])
        # 忽略过短的块
        if len(chunk_content.strip()) < 50: 
            continue
            
        chunks.append({
            "start_line": i + 1,
            "end_line": end,
            "content": chunk_content
        })
        
        if end == total_lines: break
        
    return chunks