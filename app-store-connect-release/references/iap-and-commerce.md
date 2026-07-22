# IAP And Commerce

## Manifest

`sync_iap.py` accepts a JSON object with a `products` array:

```json
{
  "products": [
    {
      "product_id": "com.example.pro",
      "name": "Pro Unlock",
      "type": "NON_CONSUMABLE",
      "localizations": {
        "en-US": {
          "name": "Pro Unlock",
          "description": "Unlock all features."
        },
        "ja": {
          "name": "Pro Unlock",
          "description": "すべての機能を利用できます。"
        }
      }
    }
  ]
}
```

Supported product types are `CONSUMABLE`, `NON_CONSUMABLE`, and `NON_RENEWING_SUBSCRIPTION`. Product IDs and product types are treated as stable identifiers. The script refuses to change a type that Apple already has.

## Workflow

1. Run without `--apply` to discover current products and calculate changes.
2. Confirm product IDs, product type, localized name, and localized description.
3. Run with `--apply` to create missing products or update API-supported names/localizations.
4. Verify the product state in App Store Connect.
5. Configure price schedules, review information, and version attachment in App Store Connect before submission.

The script does not invent prices, territories, tax treatment, review screenshots, or review notes. It also does not claim that a product is submitted merely because its resource exists.

## Roles And Boundaries

The API key must have a role that can manage the requested product resources. Apple may reject writes for products that are in a state requiring portal action. Subscription groups, price schedules, review information, and version submission have separate API contracts and should be implemented only after verifying the current Apple API surface.
