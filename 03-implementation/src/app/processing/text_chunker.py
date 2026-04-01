"""
Text Splitter / Text Chunker — FR-03
三級遞迴文本切分器

將長文本切分為 ≤250 字的 chunks，同時保持語意完整性。
"""

from typing import List
import re


# 三級切分標記（優先順序）
SENTENCE_ENDINGS = r'[。！？!?\n]'
PHRASE_ENDINGS = r'[,，;；:：\t]'
MAX_CHUNK_SIZE = 250
MIN_CHUNK_SIZE = 50  # 避免過短 chunks


class TextSplitter:
    """
    三級遞迴文本切分器
    
    Level 1: 以句子為單位（。！？!?\n）
    Level 2: 以片語為單位（,，;；:：\t）
    Level 3: 強制以 MAX_CHUNK_SIZE 切斷
    """
    
    def __init__(self, max_chars: int = MAX_CHUNK_SIZE, min_chars: int = MIN_CHUNK_SIZE):
        self.max_chars = max_chars
        self.min_chars = min_chars
    
    def split(self, text: str) -> List[str]:
        """
        將文本切分為 chunks。
        
        Args:
            text: 輸入文本
            
        Returns:
            chunks 列表
        """
        if not text.strip():
            return []
        
        text = text.strip()
        
        # 如果小於等於 max_chars，直接返回
        if len(text) <= self.max_chars:
            return [text]
        
        # Level 1: 先以句子切分
        sentences = self._split_by_sentences(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 如果單一句子超過 max_chars，進入 Level 2
            if len(sentence) > self.max_chars:
                # 先把目前的 chunk 收集起來
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Level 2: 以片語切分這個長句
                sub_chunks = self._split_by_phrases(sentence)
                for sub in sub_chunks:
                    if len(sub) <= self.max_chars:
                        chunks.append(sub)
                    else:
                        # Level 3: 強制切斷
                        chunks.extend(self._force_split(sub))
            elif len(current_chunk) + len(sentence) <= self.max_chars:
                current_chunk += sentence
            else:
                # 累積超過 max_chars，先保存 current_chunk
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        # 最後一個 chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return [c for c in chunks if c]  # 過濾空 chunks
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """Level 1: 以句子為單位切分。"""
        sentences = re.split(SENTENCE_ENDINGS, text)
        result = []
        current = ""
        
        for sent in sentences:
            current += sent
            # 檢查結尾是否有句末標點
            if re.search(r'[。！？!?]$', sent) or '\n' in sent:
                result.append(current)
                current = ""
        
        if current.strip():
            result.append(current)
        
        return result if result else [text]
    
    def _split_by_phrases(self, text: str) -> List[str]:
        """Level 2: 以片語為單位切分長句。"""
        parts = re.split(PHRASE_ENDINGS, text)
        chunks = []
        current = ""
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            if len(current) + len(part) <= self.max_chars:
                current += part
            else:
                if current.strip():
                    chunks.append(current.strip())
                current = part
        
        if current.strip():
            chunks.append(current.strip())
        
        return chunks if chunks else [text]
    
    def _force_split(self, text: str) -> List[str]:
        """Level 3: 強制以 MAX_CHUNK_SIZE 切斷。"""
        chunks = []
        for i in range(0, len(text), self.max_chars):
            chunk = text[i:i+self.max_chars]
            if chunk.strip():
                chunks.append(chunk.strip())
        return chunks


def split_text(text: str, max_chars: int = MAX_CHUNK_SIZE) -> List[str]:
    """快速切分函數。"""
    splitter = TextSplitter(max_chars=max_chars)
    return splitter.split(text)
