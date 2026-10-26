from flask import current_app


def ai_status() -> dict:
    configured = bool(current_app.config.get("AI_PROVIDER") and current_app.config.get("AI_API_KEY"))
    return {
        "available": configured,
        "label": "Optional AI is configured" if configured else "Optional AI is unavailable",
        "detail": (
            "AI suggestions can be connected later with an API key."
            if not configured
            else "AI provider is configured. This MVP still treats suggestions as optional helpers."
        ),
    }


def suggest_category(_image_path: str | None = None) -> dict:
    status = ai_status()
    if not status["available"]:
        return {"ok": False, "reason": "No AI service is configured. This is not a simulated prediction."}
    return {"ok": False, "reason": "AI category suggestion is prepared but not enabled for this hackathon MVP."}


def suggest_priority(_description: str, _category: str) -> dict:
    status = ai_status()
    if not status["available"]:
        return {"ok": False, "reason": "No AI service is configured. Priority must be judged by staff."}
    return {"ok": False, "reason": "AI priority suggestion is prepared but not enabled for this hackathon MVP."}


def summarise_complaints(_items) -> dict:
    status = ai_status()
    if not status["available"]:
        return {"ok": False, "reason": "No AI service is configured. Use filters and search instead."}
    return {"ok": False, "reason": "AI summaries are prepared but not enabled for this hackathon MVP."}
