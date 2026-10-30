from typing import Literal

from app.models import ProductSummary, Sensitivity

Bucket = Literal["90+", "70-89", "<70", "n/a"]
_RANK = {"Public": 0, "Internal": 1, "Confidential": 2}


def table_quality(statuses: list[str]) -> int | None:
    if not statuses:
        return None
    return round(100 * statuses.count("Success") / len(statuses))


def product_quality(table_scores: list[int | None]) -> int | None:
    scores = [s for s in table_scores if s is not None]
    return round(sum(scores) / len(scores)) if scores else None


def quality_bucket(score: int | None) -> Bucket:
    if score is None:
        return "n/a"
    if score >= 90:
        return "90+"
    return "70-89" if score >= 70 else "<70"


def derive_sensitivity(tag_fqns: list[str]) -> Sensitivity:
    level: Sensitivity = "Public"
    for fqn in tag_fqns:
        if fqn.startswith(("PII.Sensitive", "PersonalData.")):
            found: Sensitivity = "Confidential"
        elif fqn == "Sensitivity.Internal":
            found = "Internal"
        else:
            continue
        if _RANK[found] > _RANK[level]:
            level = found
    return level


def filter_products(
    products: list[ProductSummary], *, domain=None, sensitivity=None, quality=None,
    owner=None, certification=None, q=None,
) -> list[ProductSummary]:
    needle = q.lower() if q else None
    result = []
    for p in products:
        if domain and p.domain != domain:
            continue
        if sensitivity and p.sensitivity != sensitivity:
            continue
        if quality and quality_bucket(p.quality) != quality:
            continue
        if owner and owner not in p.owners:
            continue
        if certification and p.certification != certification:
            continue
        if needle:
            haystack = [p.name, p.display_name, p.description, *p.glossary_terms, *p.tags]
            if not any(needle in h.lower() for h in haystack):
                continue
        result.append(p)
    return result


def facets(products: list[ProductSummary]) -> dict[str, list[str]]:
    return {
        "domain": sorted({p.domain for p in products if p.domain}),
        "sensitivity": sorted({p.sensitivity for p in products}),
        "quality": sorted({quality_bucket(p.quality) for p in products}),
        "owner": sorted({o for p in products for o in p.owners}),
        "certification": sorted({p.certification for p in products if p.certification}),
    }
