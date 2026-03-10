import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_USAGE_LOG_PATH = Path("data/ai_usage.jsonl")
DEFAULT_PRICING_PATH = Path("config/model_pricing.json")


def create_run_context(platform, writer_mode, ai_model, count, max_ai_calls=None, max_total_tokens=None, max_estimated_cost=None):
    started_at = datetime.now(timezone.utc)
    return {
        "run_id": f"run_{started_at.strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}",
        "started_at": started_at.isoformat(),
        "platform": platform,
        "writer_mode": writer_mode,
        "ai_model": ai_model,
        "requested_count": count,
        "limits": {
            "max_ai_calls": max_ai_calls,
            "max_total_tokens": max_total_tokens,
            "max_estimated_cost": max_estimated_cost,
        },
        "budget_state": {
            "ai_calls": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "limit_triggered": None,
        },
    }


def load_pricing(path=DEFAULT_PRICING_PATH):
    pricing_path = Path(path)
    if not pricing_path.exists():
        return {}

    with pricing_path.open() as handle:
        payload = json.load(handle)

    return payload if isinstance(payload, dict) else {}


def log_usage_event(event, path=DEFAULT_USAGE_LOG_PATH):
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as handle:
        handle.write(json.dumps(event) + "\n")


def build_usage_event(run_context, shirt, platform, model, writer_mode, status, usage=None, latency_ms=None, error=None, pricing=None):
    usage = usage or {}
    pricing = pricing or {}
    cached_tokens = safe_nested_int(usage, "input_tokens_details", "cached_tokens")
    reasoning_tokens = safe_nested_int(usage, "output_tokens_details", "reasoning_tokens")
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)

    return {
        "event_type": "ai_generation",
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_context["run_id"],
        "shirt_id": shirt["shirt_id"],
        "title": shirt["title"],
        "platform": platform,
        "model": model,
        "writer_mode": writer_mode,
        "status": status,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "estimated_cost_usd": estimate_cost_usd(usage, pricing.get(model)),
        "error": error,
    }


def build_run_summary(run_context, posts, usage_events):
    ai_events = [event for event in usage_events if event["status"] in {"success", "fallback", "error", "budget_fallback"}]
    success_events = [event for event in usage_events if event["status"] == "success"]
    fallback_events = [event for event in usage_events if event["status"] in {"fallback", "budget_fallback"}]
    error_events = [event for event in usage_events if event["status"] == "error"]

    return {
        "run_id": run_context["run_id"],
        "started_at": run_context["started_at"],
        "platform": run_context["platform"],
        "writer_mode": run_context["writer_mode"],
        "ai_model": run_context["ai_model"],
        "requested_count": run_context["requested_count"],
        "limits": run_context.get("limits", {}),
        "generated_count": len(posts),
        "ai_attempts": len(ai_events),
        "ai_successes": len(success_events),
        "ai_fallbacks": len(fallback_events),
        "ai_errors": len(error_events),
        "input_tokens": sum(event["input_tokens"] for event in usage_events),
        "output_tokens": sum(event["output_tokens"] for event in usage_events),
        "total_tokens": sum(event["total_tokens"] for event in usage_events),
        "cached_tokens": sum(event["cached_tokens"] for event in usage_events),
        "reasoning_tokens": sum(event["reasoning_tokens"] for event in usage_events),
        "estimated_cost_usd": round(
            sum(event["estimated_cost_usd"] or 0 for event in usage_events),
            6,
        )
        if usage_events
        else 0,
        "budget_state": run_context.get("budget_state", {}),
        "posts_by_writer_mode": summarize_counts(post.get("writer_mode", "unknown") for post in posts),
        "posts_by_post_type": summarize_counts(post.get("post_type", "unknown") for post in posts),
    }


def write_run_summary(summary, output_dir):
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / f"{summary['run_id']}_summary.json"
    with summary_path.open("w") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    return summary_path


def safe_nested_int(payload, *keys):
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return 0
        current = current.get(key)
    return int(current or 0)


def estimate_cost_usd(usage, pricing):
    if not pricing:
        return None

    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    cached_tokens = safe_nested_int(usage, "input_tokens_details", "cached_tokens")
    uncached_tokens = max(input_tokens - cached_tokens, 0)

    input_rate = pricing.get("input_per_1m")
    cached_input_rate = pricing.get("cached_input_per_1m", input_rate)
    output_rate = pricing.get("output_per_1m")
    if input_rate is None or output_rate is None:
        return None

    estimated = (
        (uncached_tokens / 1_000_000) * float(input_rate)
        + (cached_tokens / 1_000_000) * float(cached_input_rate)
        + (output_tokens / 1_000_000) * float(output_rate)
    )
    return round(estimated, 8)


def summarize_counts(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def budget_status(run_context):
    limits = run_context.get("limits", {})
    budget_state = run_context.get("budget_state", {})

    if limits.get("max_ai_calls") is not None and budget_state.get("ai_calls", 0) >= limits["max_ai_calls"]:
        return f"max_ai_calls={limits['max_ai_calls']}"
    if limits.get("max_total_tokens") is not None and budget_state.get("total_tokens", 0) >= limits["max_total_tokens"]:
        return f"max_total_tokens={limits['max_total_tokens']}"
    if limits.get("max_estimated_cost") is not None and budget_state.get("estimated_cost_usd", 0.0) >= limits["max_estimated_cost"]:
        return f"max_estimated_cost={limits['max_estimated_cost']}"
    return None


def update_budget_state(run_context, event):
    budget_state = run_context.setdefault("budget_state", {})
    if event["status"] == "success":
        budget_state["ai_calls"] = budget_state.get("ai_calls", 0) + 1
    budget_state["total_tokens"] = budget_state.get("total_tokens", 0) + (event.get("total_tokens") or 0)
    budget_state["estimated_cost_usd"] = round(
        budget_state.get("estimated_cost_usd", 0.0) + float(event.get("estimated_cost_usd") or 0.0),
        8,
    )
    if not budget_state.get("limit_triggered"):
        budget_state["limit_triggered"] = budget_status(run_context)


def set_budget_trigger(run_context, trigger):
    budget_state = run_context.setdefault("budget_state", {})
    if trigger and not budget_state.get("limit_triggered"):
        budget_state["limit_triggered"] = trigger
