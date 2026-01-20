#!/usr/bin/env python3
"""
モデレーション・フィルタモジュール

コンテンツの自動フィルタリングと手動モデレーション機能を提供:
- 禁止語句フィルタ
- スパム検出
- 感情分析によるフラグ付け
- モデレーションキュー管理

環境変数:
    MODERATION_ENABLED: モデレーション有効化 (true/false)
    BANNED_WORDS_FILE: 禁止語句ファイルパス
    SPAM_THRESHOLD: スパム判定閾値 (0.0-1.0)
    AUTO_APPROVE: 自動承認有効化 (true/false)
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ===== 設定 =====

MODERATION_ENABLED = os.getenv("MODERATION_ENABLED", "false").lower() == "true"
BANNED_WORDS_FILE = os.getenv("BANNED_WORDS_FILE", "")
SPAM_THRESHOLD = float(os.getenv("SPAM_THRESHOLD", "0.7"))
AUTO_APPROVE = os.getenv("AUTO_APPROVE", "true").lower() == "true"


class ModerationStatus(Enum):
    """モデレーションステータス"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class ViolationType(Enum):
    """違反タイプ"""
    BANNED_WORD = "banned_word"
    SPAM = "spam"
    INAPPROPRIATE = "inappropriate"
    DUPLICATE = "duplicate"
    LOW_QUALITY = "low_quality"


@dataclass
class ModerationResult:
    """モデレーション結果"""
    passed: bool
    status: ModerationStatus
    violations: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 1.0  # 0.0-1.0、高いほど安全
    flags: List[str] = field(default_factory=list)
    suggestion: Optional[str] = None


# ===== 禁止語句フィルタ =====

class BannedWordFilter:
    """禁止語句フィルタ"""

    def __init__(self):
        self.banned_words: List[str] = []
        self.banned_patterns: List[re.Pattern] = []
        self._load_banned_words()

    def _load_banned_words(self):
        """禁止語句をファイルから読み込み"""
        if BANNED_WORDS_FILE and Path(BANNED_WORDS_FILE).exists():
            try:
                with open(BANNED_WORDS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith("#"):
                            self.banned_words.append(word.lower())
            except Exception as e:
                logger.error(f"Failed to load banned words: {e}")

        # デフォルトの禁止パターン（正規表現）
        default_patterns = [
            r"\b(spam|広告|宣伝)\b",
            r"(https?://[^\s]+){5,}",  # 5つ以上のURL
        ]
        for pattern in default_patterns:
            try:
                self.banned_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                pass

    def check(self, text: str) -> Tuple[bool, List[str]]:
        """テキストに禁止語句が含まれているかチェック"""
        text_lower = text.lower()
        found_words = []

        # 禁止語句チェック
        for word in self.banned_words:
            if word in text_lower:
                found_words.append(word)

        # パターンチェック
        for pattern in self.banned_patterns:
            if pattern.search(text):
                found_words.append(f"pattern:{pattern.pattern}")

        return len(found_words) == 0, found_words


# ===== スパム検出 =====

class SpamDetector:
    """スパム検出"""

    def __init__(self):
        self.spam_indicators = [
            (r"(.)\1{5,}", 0.3),  # 同じ文字の繰り返し
            (r"https?://[^\s]+", 0.1),  # URL（1つにつき）
            (r"[A-Z]{10,}", 0.2),  # 大文字の連続
            (r"[!?]{3,}", 0.1),  # 感嘆符・疑問符の連続
            (r"\b(buy|click|free|win|prize)\b", 0.2),  # スパムキーワード（英語）
            (r"(今すぐ|無料|当選|クリック)", 0.2),  # スパムキーワード（日本語）
        ]

    def calculate_spam_score(self, text: str) -> float:
        """スパムスコアを計算（0.0-1.0、高いほどスパムの可能性）"""
        score = 0.0

        for pattern, weight in self.spam_indicators:
            matches = re.findall(pattern, text, re.IGNORECASE)
            score += len(matches) * weight

        # 最大1.0に制限
        return min(score, 1.0)

    def is_spam(self, text: str) -> Tuple[bool, float]:
        """スパム判定"""
        score = self.calculate_spam_score(text)
        return score >= SPAM_THRESHOLD, score


# ===== 品質チェック =====

class QualityChecker:
    """コンテンツ品質チェック"""

    def __init__(self):
        self.min_length = 10
        self.max_length = 10000

    def check(self, text: str) -> Tuple[bool, List[str]]:
        """品質チェック"""
        issues = []

        # 長さチェック
        if len(text) < self.min_length:
            issues.append(f"too_short:{len(text)}<{self.min_length}")

        if len(text) > self.max_length:
            issues.append(f"too_long:{len(text)}>{self.max_length}")

        # 空白のみチェック
        if not text.strip():
            issues.append("empty_content")

        # 意味のある文字が少ない
        meaningful_chars = len(re.sub(r"[\s\d\W]", "", text))
        if meaningful_chars < 5:
            issues.append("low_meaningful_content")

        return len(issues) == 0, issues


# ===== 重複検出 =====

class DuplicateDetector:
    """重複コンテンツ検出"""

    def __init__(self):
        self.recent_hashes: Dict[str, datetime] = {}
        self.hash_expiry_hours = 24

    def _simple_hash(self, text: str) -> str:
        """シンプルなハッシュ生成"""
        import hashlib
        # 正規化（小文字、空白削除）
        normalized = re.sub(r"\s+", "", text.lower())
        return hashlib.md5(normalized.encode()).hexdigest()

    def check(self, text: str) -> Tuple[bool, Optional[str]]:
        """重複チェック"""
        text_hash = self._simple_hash(text)
        now = datetime.now()

        # 古いエントリを削除
        expired = []
        for h, timestamp in self.recent_hashes.items():
            hours_diff = (now - timestamp).total_seconds() / 3600
            if hours_diff > self.hash_expiry_hours:
                expired.append(h)
        for h in expired:
            del self.recent_hashes[h]

        # 重複チェック
        if text_hash in self.recent_hashes:
            return False, text_hash

        # 新しいハッシュを登録
        self.recent_hashes[text_hash] = now
        return True, None


# ===== モデレーションキュー =====

class ModerationQueue:
    """モデレーションキュー管理"""

    def __init__(self):
        self.queue: List[Dict[str, Any]] = []

    def add(self, item_id: str, content: str, result: ModerationResult):
        """キューに追加"""
        self.queue.append({
            "id": item_id,
            "content": content[:500],  # 最初の500文字のみ
            "status": result.status.value,
            "violations": result.violations,
            "score": result.score,
            "flags": result.flags,
            "created_at": datetime.now().isoformat(),
        })

    def get_pending(self, limit: int = 50) -> List[Dict[str, Any]]:
        """保留中のアイテムを取得"""
        pending = [
            item for item in self.queue
            if item["status"] == ModerationStatus.PENDING.value
        ]
        return pending[:limit]

    def update_status(self, item_id: str, status: ModerationStatus) -> bool:
        """ステータスを更新"""
        for item in self.queue:
            if item["id"] == item_id:
                item["status"] = status.value
                item["updated_at"] = datetime.now().isoformat()
                return True
        return False


# ===== メインモデレーター =====

class ContentModerator:
    """コンテンツモデレーター"""

    def __init__(self):
        self.banned_word_filter = BannedWordFilter()
        self.spam_detector = SpamDetector()
        self.quality_checker = QualityChecker()
        self.duplicate_detector = DuplicateDetector()
        self.queue = ModerationQueue()

    def moderate(self, content: str, item_id: Optional[str] = None) -> ModerationResult:
        """コンテンツをモデレート"""
        if not MODERATION_ENABLED:
            return ModerationResult(
                passed=True,
                status=ModerationStatus.APPROVED,
                score=1.0
            )

        violations = []
        flags = []
        total_score = 1.0

        # 1. 禁止語句チェック
        passed, found_words = self.banned_word_filter.check(content)
        if not passed:
            violations.append({
                "type": ViolationType.BANNED_WORD.value,
                "details": found_words
            })
            total_score -= 0.5

        # 2. スパムチェック
        is_spam, spam_score = self.spam_detector.is_spam(content)
        if is_spam:
            violations.append({
                "type": ViolationType.SPAM.value,
                "score": spam_score
            })
            total_score -= 0.3
            flags.append("spam_detected")

        # 3. 品質チェック
        quality_passed, quality_issues = self.quality_checker.check(content)
        if not quality_passed:
            violations.append({
                "type": ViolationType.LOW_QUALITY.value,
                "details": quality_issues
            })
            total_score -= 0.2

        # 4. 重複チェック
        is_unique, dup_hash = self.duplicate_detector.check(content)
        if not is_unique:
            violations.append({
                "type": ViolationType.DUPLICATE.value,
                "hash": dup_hash
            })
            flags.append("duplicate_content")

        # スコアを0-1に制限
        total_score = max(0.0, min(1.0, total_score))

        # ステータス決定
        if len(violations) == 0:
            status = ModerationStatus.APPROVED if AUTO_APPROVE else ModerationStatus.PENDING
            passed = True
        elif total_score < 0.3:
            status = ModerationStatus.REJECTED
            passed = False
        else:
            status = ModerationStatus.FLAGGED
            passed = AUTO_APPROVE  # 自動承認が有効なら通す

        result = ModerationResult(
            passed=passed,
            status=status,
            violations=violations,
            score=total_score,
            flags=flags,
            suggestion=self._generate_suggestion(violations)
        )

        # キューに追加（保留またはフラグ付きの場合）
        if item_id and status in (ModerationStatus.PENDING, ModerationStatus.FLAGGED):
            self.queue.add(item_id, content, result)

        return result

    def _generate_suggestion(self, violations: List[Dict]) -> Optional[str]:
        """改善提案を生成"""
        suggestions = []

        for v in violations:
            vtype = v.get("type")
            if vtype == ViolationType.BANNED_WORD.value:
                suggestions.append("不適切な表現を含む可能性があります。内容を確認してください。")
            elif vtype == ViolationType.SPAM.value:
                suggestions.append("スパムの特徴が検出されました。URLや繰り返しを減らしてください。")
            elif vtype == ViolationType.LOW_QUALITY.value:
                suggestions.append("内容が短すぎるか、意味のある文字が少ないです。")
            elif vtype == ViolationType.DUPLICATE.value:
                suggestions.append("同じ内容が既に投稿されている可能性があります。")

        return " ".join(suggestions) if suggestions else None


# シングルトンインスタンス
moderator = ContentModerator()


def moderate_content(content: str, item_id: Optional[str] = None) -> ModerationResult:
    """コンテンツをモデレート（簡易関数）"""
    return moderator.moderate(content, item_id)


def get_moderation_queue(limit: int = 50) -> List[Dict[str, Any]]:
    """モデレーションキューを取得"""
    return moderator.queue.get_pending(limit)


def approve_content(item_id: str) -> bool:
    """コンテンツを承認"""
    return moderator.queue.update_status(item_id, ModerationStatus.APPROVED)


def reject_content(item_id: str) -> bool:
    """コンテンツを拒否"""
    return moderator.queue.update_status(item_id, ModerationStatus.REJECTED)
