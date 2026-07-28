"""
日志清洗规则 — 单一数据源。

Python 和 JS 共用这些规则：Python 直接 import，JS 通过 /api/cleaning-rules 获取。
修改过滤规则只需改这一个文件。
"""

import re
from dataclasses import dataclass, field


# ── 需要跳过的行（正则表达式） ──
SKIP_LINE_PATTERNS: list[str] = [
    r"SingleMessageQueueSys ReadFrame:\s*\d+",
    r"ClientLog:",
]

# ── 前缀替换（from → to） ──
PREFIX_REPLACEMENTS: list[tuple[str, str]] = [
    ("ServerGamePlayModules.", ""),
    ("UnityHotfix.", ""),
    ("GameplayModules.", ""),
]


def compile_skip_patterns() -> list[re.Pattern]:
    return [re.compile(p) for p in SKIP_LINE_PATTERNS]


def should_skip_line(raw_line: str, compiled: list[re.Pattern] | None = None) -> bool:
    if compiled is None:
        compiled = compile_skip_patterns()
    for pat in compiled:
        if pat.search(raw_line):
            return True
    return False


def clean_common_prefixes(line: str) -> str:
    for old, new in PREFIX_REPLACEMENTS:
        line = line.replace(old, new)
    return line


@dataclass
class CleaningRulesResponse:
    """API 返回给 JS 的规则"""
    skip_patterns: list[str] = field(default_factory=lambda: SKIP_LINE_PATTERNS)
    prefix_replacements: list[tuple[str, str]] = field(default_factory=lambda: PREFIX_REPLACEMENTS)
