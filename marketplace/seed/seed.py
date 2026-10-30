"""Seed OMD with the demo's metadata. Run from the repo root: python -m marketplace.seed.seed (or from marketplace/: python -m seed.seed)."""
from app.config import get_settings
from app.omd import OmdClient
from seed import definitions as d
from seed import writer


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
    writer.ensure_classification_tag(client)
    print("tag       Sensitivity.Internal")
    writer.ensure_custom_property(client)
    print(f"property  dataProduct.{d.ENTRA_PROPERTY}")
    for product in d.PRODUCTS:
        writer.ensure_product(client, product)
        print(f"product   {product.name} -> {product.entra_group}")


def main() -> None:
    run_base_seed(OmdClient(get_settings()))
    print(f"Done: {len(d.PRODUCTS)} data products.")


if __name__ == "__main__":
    main()
