"""Fabric recommendation stubs."""


def rank_fabrics_for_user(preferences: dict, candidate_fabrics: list) -> list:
    query = str(preferences.get("query") or "").lower()
    if not query:
        return candidate_fabrics

    def score(item) -> int:
        text = " ".join(str(getattr(item, field, "") or "") for field in ["name", "category", "color", "pattern", "description_for_gpt"]).lower()
        return sum(1 for word in query.split() if word in text)

    return sorted(candidate_fabrics, key=score, reverse=True)
