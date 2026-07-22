#!/usr/bin/env python3
"""Discover or synchronize App Store Connect in-app purchases and localizations."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from asc_api_client import AppStoreConnectClient, attributes, data_list, resolve_credentials
from asc_workflow import (
    index_by_locale,
    list_localizations,
    manifest_locales,
    read_json,
    resolve_app,
    resource_body,
    resource_id,
)


IAP_TYPES = {"CONSUMABLE", "NON_CONSUMABLE", "NON_RENEWING_SUBSCRIPTION"}
IAP_LOCALIZATION_FIELDS = {"name": "name", "description": "description"}


def products_from_manifest(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.manifest:
        payload = read_json(args.manifest)
        products = payload.get("products", [])
        if not isinstance(products, list):
            raise SystemExit("IAP manifest 'products' must be a list.")
        result = [item for item in products if isinstance(item, dict) and item.get("product_id")]
    elif args.product_id:
        result = [{"product_id": product_id, "name": args.name or "", "type": args.product_type or ""} for product_id in args.product_id]
    else:
        result = []
    for product in result:
        product["product_id"] = str(product["product_id"])
        product["name"] = str(product.get("name", ""))
        product["type"] = str(product.get("type", product.get("in_app_purchase_type", ""))).upper()
        if product["type"] and product["type"] not in IAP_TYPES:
            raise SystemExit(f"Unsupported IAP type for {product['product_id']}: {product['type']}")
    return result


def localizations_for_product(product: dict[str, Any]) -> dict[str, dict[str, str]]:
    value = product.get("localizations", {})
    if isinstance(value, dict):
        return {
            str(locale): {str(key): str(field) for key, field in fields.items() if field is not None}
            for locale, fields in value.items()
            if isinstance(fields, dict)
        }
    if isinstance(value, list):
        return {
            str(item["locale"]): {str(key): str(field) for key, field in item.items() if key != "locale" and field is not None}
            for item in value
            if isinstance(item, dict) and item.get("locale")
        }
    raise SystemExit(f"IAP localizations must be an object or list for {product['product_id']}.")


def product_resources(client: AppStoreConnectClient, app_id: str) -> list[dict[str, Any]]:
    return data_list(client.get(f"/apps/{app_id}/inAppPurchases", {"limit": 200}))


def plan_localization(
    *,
    product_id: str,
    locale: str,
    desired: dict[str, str],
    existing: dict[str, Any] | None,
) -> dict[str, Any] | None:
    desired_fields = {api: desired[source] for source, api in IAP_LOCALIZATION_FIELDS.items() if desired.get(source, "").strip()}
    if not desired_fields:
        return None
    existing_attrs = attributes(existing)
    changed = {key: value for key, value in desired_fields.items() if str(existing_attrs.get(key, "")) != value}
    if not changed:
        return None
    if existing:
        return {
            "action": "patch",
            "kind": "iap_localization",
            "product_id": product_id,
            "locale": locale,
            "endpoint": f"/inAppPurchaseLocalizations/{resource_id(existing)}",
            "fields": sorted(changed),
            "body": resource_body("inAppPurchaseLocalizations", resource_id_value=resource_id(existing), resource_attributes=changed),
        }
    return {
        "action": "post",
        "kind": "iap_localization",
        "product_id": product_id,
        "locale": locale,
        "endpoint": "/inAppPurchaseLocalizations",
        "fields": sorted(desired_fields),
        "body": resource_body(
            "inAppPurchaseLocalizations",
            resource_attributes={"locale": locale, **desired_fields},
            relationships={"inAppPurchase": {"data": {"type": "inAppPurchases", "id": f"PENDING_PRODUCT_{product_id}"}}},
        ),
    }


def set_iap_parent(operation: dict[str, Any], product_resource_id: str) -> None:
    relationship = operation["body"]["data"].get("relationships", {}).get("inAppPurchase")
    if relationship:
        relationship["data"] = {"type": "inAppPurchases", "id": product_resource_id}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-id")
    parser.add_argument("--app-id")
    parser.add_argument("--manifest", help="JSON manifest containing a products array")
    parser.add_argument("--product-id", action="append", default=[])
    parser.add_argument("--name", help="Name used with --product-id when creating a product")
    parser.add_argument("--product-type", choices=sorted(IAP_TYPES))
    parser.add_argument("--apply", action="store_true", help="Write planned product/localization changes")
    parser.add_argument("--api-key-id", default="")
    parser.add_argument("--issuer-id", default="")
    parser.add_argument("--key-path", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.manifest and args.product_id:
        raise SystemExit("Use either --manifest or --product-id, not both.")

    desired_products = products_from_manifest(args)
    credentials = resolve_credentials(key_id=args.api_key_id, issuer_id=args.issuer_id, key_path=args.key_path)
    client = AppStoreConnectClient(credentials)
    app = resolve_app(client, app_id=args.app_id or "", bundle_id=args.bundle_id or "")
    app_id = resource_id(app)
    existing_products = {str(attributes(item).get("productId")): item for item in product_resources(client, app_id)}

    if not desired_products:
        result = {
            "dry_run": True,
            "app_id": app_id,
            "products": [
                {
                    "resource_id": resource_id(item),
                    "product_id": attributes(item).get("productId", ""),
                    "name": attributes(item).get("referenceName", ""),
                    "type": attributes(item).get("inAppPurchaseType", ""),
                    "state": attributes(item).get("state", ""),
                }
                for item in existing_products.values()
            ],
            "operations": [],
            "applied": [],
            "portal_actions": ["Configure price schedule and review information in App Store Connect.", "Attach products to the app version and submit the version for review in the portal."],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else json.dumps(result["products"], ensure_ascii=False, indent=2))
        return 0

    operations: list[dict[str, Any]] = []
    execution_products: list[dict[str, Any]] = []
    for desired in desired_products:
        product_id = desired["product_id"]
        existing = existing_products.get(product_id)
        desired_name = desired.get("name", "").strip()
        desired_type = desired.get("type", "").upper()
        if existing:
            existing_type = str(attributes(existing).get("inAppPurchaseType", ""))
            if desired_type and existing_type and desired_type != existing_type:
                raise SystemExit(f"IAP type cannot be changed for {product_id}: Apple has {existing_type}, manifest requests {desired_type}.")
            changed = {"referenceName": desired_name} if desired_name and str(attributes(existing).get("referenceName", "")) != desired_name else {}
            product_operation = None
            if changed:
                product_operation = {
                    "action": "patch",
                    "kind": "iap",
                    "product_id": product_id,
                    "endpoint": f"/inAppPurchases/{resource_id(existing)}",
                    "fields": sorted(changed),
                    "body": resource_body("inAppPurchases", resource_id_value=resource_id(existing), resource_attributes=changed),
                }
                operations.append(product_operation)
            product_resource = existing
            product_resource_id = resource_id(existing)
        else:
            if not desired_name or not desired_type:
                raise SystemExit(f"Creating {product_id} requires both name and type in the manifest.")
            product_operation = {
                "action": "post",
                "kind": "iap",
                "product_id": product_id,
                "endpoint": "/inAppPurchases",
                "fields": ["referenceName", "productId", "inAppPurchaseType"],
                "body": resource_body(
                    "inAppPurchases",
                    resource_attributes={"referenceName": desired_name, "productId": product_id, "inAppPurchaseType": desired_type},
                    relationships={"app": {"data": {"type": "apps", "id": app_id}}},
                ),
            }
            operations.append(product_operation)
            product_resource = None
            product_resource_id = f"DRY_RUN_PRODUCT_{product_id}"

        desired_localizations = localizations_for_product(desired)
        existing_localizations = (
            index_by_locale(list_localizations(client, "inAppPurchases", product_resource_id, "inAppPurchaseLocalizations"))
            if product_resource
            else {}
        )
        localization_operations = []
        for locale in sorted(desired_localizations):
            operation = plan_localization(
                product_id=product_id,
                locale=locale,
                desired=desired_localizations[locale],
                existing=existing_localizations.get(locale),
            )
            if operation:
                operations.append(operation)
                localization_operations.append(operation)
        execution_products.append({
            "desired": desired,
            "existing": product_resource,
            "product_id": product_id,
            "product_operation": product_operation,
            "localization_operations": localization_operations,
        })

    applied: list[dict[str, Any]] = []
    if args.apply:
        for execution in execution_products:
            product_operation = execution["product_operation"]
            if not product_operation:
                product_resource = execution["existing"]
            elif product_operation["action"] == "post":
                response = client.post(product_operation["endpoint"], product_operation["body"])
                product_resource = response.get("data") if isinstance(response, dict) else None
            else:
                response = client.patch(product_operation["endpoint"], product_operation["body"])
                product_resource = response.get("data") if isinstance(response, dict) else execution["existing"]
            if not product_resource or not resource_id(product_resource):
                raise SystemExit(f"Apple did not return an IAP resource for {execution['product_id']}.")
            product_resource_id = resource_id(product_resource)
            if product_operation:
                applied.append({"action": product_operation["action"], "kind": "iap", "product_id": execution["product_id"], "resource_id": product_resource_id})
            for operation in execution["localization_operations"]:
                set_iap_parent(operation, product_resource_id)
                if operation["action"] == "post":
                    response = client.post(operation["endpoint"], operation["body"])
                else:
                    response = client.patch(operation["endpoint"], operation["body"])
                applied.append({
                    "action": operation["action"],
                    "kind": "iap_localization",
                    "product_id": execution["product_id"],
                    "locale": operation["locale"],
                    "resource_id": resource_id(response.get("data") if isinstance(response, dict) else None),
                })

    result = {
        "dry_run": not args.apply,
        "app_id": app_id,
        "product_count": len(desired_products),
        "operation_count": len(operations),
        "operations": operations,
        "applied": applied,
        "portal_actions": ["Configure price schedules and App Store review information in App Store Connect.", "Attach products to the app version and submit the version for review in the portal."],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mode = "Applied" if args.apply else "Preview"
        print(f"{mode}: {len(operations)} IAP operation(s) for {len(desired_products)} product(s).")
        for operation in operations:
            fields = ", ".join(operation.get("fields", []))
            print(f"{operation['action'].upper():5} {operation.get('product_id', ''):<36} {operation.get('locale', ''):<12} {fields}")
        print("Portal actions remain: price schedule, review information, attaching products, and review submission.")
        if operations and not args.apply:
            print("No IAP was changed. Re-run with --apply to write these operations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
