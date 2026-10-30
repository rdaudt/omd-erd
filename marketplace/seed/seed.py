"""Seed OMD with the demo's metadata. Run from the repo root: python -m marketplace.seed.seed (or from marketplace/: python -m seed.seed)."""
from app.config import get_settings
from app.omd import OmdClient
from seed import definitions as d
from seed import writer
from seed.lineage import ensure_edges
from seed.quality import ensure_test


def run_base_seed(client: OmdClient) -> None:
    for user in d.USERS:
        writer.ensure_user(client, user)
        print(f"user      {user.name}")
    for team in d.TEAMS:
        writer.ensure_team(client, team)
        print(f"team      {team.name}")
    for domain in d.DOMAINS:
        writer.ensure_domain(client, domain)
        print(f"domain    {domain}")
    writer.ensure_classification_tags(client)
    print("tags      Sensitivity.Public/Internal/Confidential")
    writer.ensure_custom_property(client)
    print(f"property  dataProduct.{d.ENTRA_PROPERTY}")
    for product in d.PRODUCTS:
        writer.ensure_product(client, product)
        print(f"product   {product.name} -> {product.entra_group}")


def run_full_seed(client: OmdClient) -> None:
    run_base_seed(client)
    for defn in d.build_tests():
        ensure_test(client, defn)
    print(f"tests     {len(d.build_tests())} test cases with results")
    ensure_edges(client, d.LINEAGE)
    print(f"lineage   {len(d.LINEAGE)} edges")


def main() -> None:
    # Bulk asset adds can take longer than the app's default read timeout.
    run_full_seed(OmdClient(get_settings().model_copy(update={"request_timeout_seconds": 120.0})))
    print(f"Done: {len(d.PRODUCTS)} data products.")


if __name__ == "__main__":
    main()
