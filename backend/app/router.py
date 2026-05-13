"""HeuristicRouter — chọn model dựa trên đặc điểm query, không cần học."""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_CODE_RE = re.compile(
    r"```|`[^`]+`"                                      # code block hoặc inline code
    r"|(?:^|\s)(def |class |import |from \w+ import)"  # Python keywords
    r"|(?:^|\s)(function |const |let |var |=>)"        # JS keywords
    r"|\{[\s\S]*?\}|#include|System\.out"              # braces, C++, Java
    r"|\bfor\s+\w+\s+in\b|\bif\s*\("                  # Python for/if patterns
    r"|\b(python|javascript|typescript|golang|rust|java|c\+\+|sql)\b"  # language names
    r"|\b(code|script|function|algorithm|debug|compile|execute)\b",    # coding-intent words
    re.IGNORECASE | re.MULTILINE,
)

_MATH_RE = re.compile(
    r"\b(tính|giải|tích phân|đạo hàm|phương trình|xác suất"
    r"|integral|derivative|equation|calculate|compute|solve"
    r"|matrix|sigma|probability|theorem|proof|factorial)\b"
    r"|[Σσ∫∂√π±]",
    re.IGNORECASE,
)

_GREETING_RE = re.compile(
    r"^(xin chào|chào|hello|hi|hey|alo|good morning|good evening|good afternoon"
    r"|howdy|sup|what'?s up|yo)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RoutingContext:
    query: str
    query_length: int
    has_code: bool
    has_math: bool
    is_greeting: bool
    is_short_reply: bool
    urgency: float = 0.5


@dataclass
class RoutingDecision:
    model: str
    reason: str
    routing_context: RoutingContext


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_routing_context(query: str, urgency: float = 0.5) -> RoutingContext:
    q = query.strip()
    length = len(q)
    has_code = bool(_CODE_RE.search(q))
    has_math = bool(_MATH_RE.search(q))
    is_greeting = bool(_GREETING_RE.match(q))
    is_short_reply = length < 20 and not has_code and not has_math

    return RoutingContext(
        query=q,
        query_length=length,
        has_code=has_code,
        has_math=has_math,
        is_greeting=is_greeting,
        is_short_reply=is_short_reply,
        urgency=urgency,
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class HeuristicRouter:
    def __init__(self, large_model: str, small_model: str) -> None:
        self._large = large_model
        self._small = small_model

    def select_model(self, ctx: RoutingContext) -> RoutingDecision:
        model, reason = self._apply_rules(ctx)
        logger.info(
            '[ROUTER] "%s..." → %s (%s)',
            ctx.query[:40].replace("\n", " "),
            model,
            reason,
        )
        return RoutingDecision(model=model, reason=reason, routing_context=ctx)

    def _apply_rules(self, ctx: RoutingContext) -> tuple[str, str]:
        # Priority 1 — urgency override: speed above everything
        if ctx.urgency > 0.8:
            return self._small, "urgency>0.8 → speed priority"

        # Priority 2 — trivial queries: greetings and very short replies
        if ctx.is_greeting:
            return self._small, "greeting → small model"
        if ctx.is_short_reply:
            return self._small, "short_reply → small model"

        # Priority 3 — code reasoning required
        if ctx.has_code:
            return self._large, "has_code → large model"

        # Priority 4 — math reasoning required
        if ctx.has_math:
            return self._large, "has_math → large model"

        # Priority 5 — long/complex query
        if ctx.query_length > 300:
            return self._large, "long_query → large model"

        # Priority 6 — safe default
        return self._large, "fallback → large model"
