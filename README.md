# gomag-mcp

A production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for the **[Gomag Public API](https://api.gomag.ro)**, giving AI assistants like Claude direct, audited access to your Gomag e-commerce store.

> **Gomag** is a Romanian e-commerce platform. This server exposes its entire public REST API as 48 typed MCP tools across 10 categories — from product and order management to shipping (AWB), invoicing, and loyalty points.

---

## Features

- **48 MCP tools** covering every Gomag Public API endpoint
- **Full structured audit logging** — every tool call produces an immutable JSON Lines record (file + stderr)
- **Sensitive-field redaction** — passwords, tokens, and API keys are masked in logs
- **Rate-limit awareness** — tracks Gomag's Leaky Bucket headers and backs off automatically on 429
- **Exponential back-off retry** for transient 429 / 5xx failures (configurable retries and factor)
- **Connection pooling** via `httpx.AsyncClient` (keep-alive, max connections)
- **Fully async** — non-blocking from transport to tool handler
- **Two MCP resources** — `gomag://health` and `gomag://rate-limit` for observability
- **Zero secrets in code** — all credentials come from environment variables

---

## Requirements

- Python ≥ 3.10
- A Gomag store with Public API access enabled
- Your **API Key** and **Shop URL** from the Gomag admin panel

---

## Installation

### From source (recommended while in beta)

```bash
git clone https://github.com/florinel-chis/gomag-mcp.git
cd gomag-mcp

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install
pip install -e .
```

### Using pip (once published)

```bash
pip install gomag-mcp
```

---

## Configuration

All configuration is via environment variables (prefix `GOMAG_`). Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

### Required

| Variable | Description |
|---|---|
| `GOMAG_API_KEY` | Your Gomag API key (`Apikey` header) — from *Admin → API Settings* |
| `GOMAG_API_SHOP` | Your shop URL, e.g. `https://yourshop.gomag.ro` (`ApiShop` header) |

### Optional

| Variable | Default | Description |
|---|---|---|
| `GOMAG_BASE_URL` | `https://api.gomag.ro` | Gomag API base URL |
| `GOMAG_USER_AGENT` | `GomagMCP/1.0` | Custom User-Agent (must not be `PostmanRuntime/…`) |
| `GOMAG_REQUEST_TIMEOUT` | `30.0` | HTTP timeout in seconds |
| `GOMAG_MAX_RETRIES` | `3` | Retry attempts for 429 / 5xx responses |
| `GOMAG_RETRY_BACKOFF_FACTOR` | `1.0` | Exponential back-off multiplier (seconds) |
| `GOMAG_AUDIT_LOG_FILE` | `gomag_audit.jsonl` | Path to the rotating JSON Lines audit log |
| `GOMAG_AUDIT_LOG_MAX_BYTES` | `10485760` | Max log file size before rotation (10 MB) |
| `GOMAG_AUDIT_LOG_BACKUP_COUNT` | `5` | Number of rotated backup files to keep |
| `GOMAG_AUDIT_LOG_TO_STDERR` | `true` | Also emit audit events to stderr |

---

## Integration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "gomag": {
      "command": "gomag-mcp",
      "env": {
        "GOMAG_API_KEY": "your_api_key_here",
        "GOMAG_API_SHOP": "https://yourshop.gomag.ro"
      }
    }
  }
}
```

### Claude CLI (`claude`)

```bash
# Run once to register
claude mcp add gomag -- gomag-mcp

# Or with environment variables inline
GOMAG_API_KEY=xxx GOMAG_API_SHOP=https://yourshop.gomag.ro gomag-mcp
```

### Run manually

```bash
# With .env file in current directory
gomag-mcp

# Or explicit env vars
GOMAG_API_KEY=xxx GOMAG_API_SHOP=https://yourshop.gomag.ro gomag-mcp
```

---

## Available Tools

### Products (`/api/v1/product/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `product_list` | GET | `/read/json` | List products — filter by id, sku, category, brand, updated date, promo tag, language |
| `product_create` | POST | `/write/json` | Create products — supports multi-language names/descriptions and product variants |
| `product_update` | POST | `/patch/json` | Patch existing products by id or sku |
| `product_update_inventory` | POST | `/inventory/json` | Bulk-update price, special price, and stock levels |
| `product_delete` | POST | `/delete/json` | Delete products by id or sku |

### Categories (`/api/v1/category/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `category_list` | GET | `/read/json` | List categories — filter by id, parent, language |
| `category_create` | POST | `/write/json` | Create categories with multi-language names |
| `category_update` | POST | `/patch/json` | Patch existing categories |
| `category_delete` | POST | `/delete/json` | Delete empty categories |

### Orders (`/api/v1/order/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `order_list` | GET | `/read/json` | List orders — filter by id, number, status, date range, email, phone |
| `order_status_types` | GET | `/status/read/json` | Get all available order status types |
| `order_create` | POST | `/add/json` | Create an order with billing, shipping, products, and discounts |
| `order_update_status` | POST | `/status/json` | Change order status with optional customer notification |
| `order_add_note` | POST | `/note/add/json` | Attach a public or private note to an order |
| `order_add_file` | POST | `/file/add/json` | Attach a file (by URL) to an order |

### Customers (`/api/v1/customer/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `customer_list` | GET | `/read/json` | List customers — filter by id, email, phone, modified date |
| `customer_ordered_products` | GET | `/orderedproducts/json` | Products a customer has previously ordered |
| `customer_create` | POST | `/add/json` | Register a new customer account |
| `customer_update` | POST | `/update/json` | Update customer details |
| `customer_login` | POST | `/login/json` | Authenticate a customer |
| `customer_change_password` | POST | `/passwordchange/json` | Change customer password |
| `customer_password_recovery` | POST | `/passwordrecovery/json` | Trigger password recovery email |
| `customer_delete_request` | POST | `/deleterequest/json` | Submit GDPR account-deletion request |

### Shipping / AWB (`/api/v1/awb/`)

> AWB = Air Waybill — the tracking/shipping label used by Romanian courier services.

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `awb_carrier_list` | GET | `/carrier/read/json` | List configured courier/carrier integrations |
| `awb_list` | GET | `/read/json` | List AWB records — filter by order, tracking number, carrier |
| `awb_create` | POST | `/add/json` | Manually register an AWB tracking number |
| `awb_generate` | POST | `/generate/json` | Auto-generate an AWB via the carrier API |
| `awb_delete` | POST | `/delete/json` | Delete an AWB record |
| `awb_print` | POST | `/print/json` | Generate a printable shipping label |
| `awb_update_status` | POST | `/status/update/json` | Update AWB delivery status |

### Invoices (`/api/v1/invoice/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `invoice_create` | POST | `/add/json` | Register an invoice for an order |
| `invoice_generate` | POST | `/generate/json` | Auto-generate invoice using store settings |
| `invoice_cancel` | POST | `/cancel/json` | Cancel (void) an invoice |

### Attributes (`/api/v1/attribute/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `attribute_list` | GET | `/read/json` | List product attributes |
| `attribute_create` | POST | `/write/json` | Create attributes with multi-language names and values |
| `attribute_update` | POST | `/patch/json` | Patch existing attributes |

### Reviews (`/api/v1/review/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `review_list` | GET | `/read/json` | List reviews — filter by product, customer, approval status |
| `review_create` | POST | `/write/json` | Submit a product review (1–5 stars) |

### Wishlist (`/api/v1/wishlist/`)

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `wishlist_list` | GET | `/read/json` | List a customer's saved products |
| `wishlist_add` | POST | `/add/json` | Add a product to a customer's wishlist |
| `wishlist_remove` | POST | `/delete/json` | Remove a product from a wishlist |

### Store Reference Data

| Tool | Method | Endpoint | Description |
|---|---|---|---|
| `currency_list` | GET | `/api/v1/currency/read/json` | List configured currencies |
| `payment_list` | GET | `/api/v1/payment/read/json` | List payment methods |
| `brand_list` | GET | `/api/v1/brand/read/json` | List brands/manufacturers |
| `filter_list` | GET | `/api/v1/filter/read/json` | Filterable attributes for a category |
| `banner_list` | GET | `/api/v1/banner/read/json` | Promotional banners |
| `fidelity_read` | POST | `/api/v1/fidelity/read/json` | Customer loyalty points balance |
| `rulecart_add` | POST | `/api/v1/rulecart/add/json` | Create a shopping cart discount rule |

---

## MCP Resources

Two read-only resources are exposed for observability:

| URI | Description |
|---|---|
| `gomag://health` | Server status, configured shop URL, and current rate-limit snapshot |
| `gomag://rate-limit` | Live rate-limit counters from the most recent API response |

---

## Audit Logging

Every tool call — success or failure — writes one JSON Lines record to `gomag_audit.jsonl` (and optionally stderr). The file rotates automatically at 10 MB (5 backups kept by default).

### Log record schema

```json
{
  "timestamp": "2026-03-27T10:00:00.123456+00:00",
  "level": "AUDIT",
  "event_type": "tool_call",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "tool_name": "product_list",
  "parameters": { "page": 1, "limit": 10 },
  "api_method": "GET",
  "api_path": "/api/v1/product/read/json",
  "http_status": 200,
  "duration_ms": 123.456,
  "success": true,
  "error_message": null,
  "rate_limit_remaining_read": 45,
  "rate_limit_remaining_write": 10
}
```

On error, `event_type` is `"tool_error"`, `success` is `false`, and `error_message` contains the exception text.

### Sensitive field redaction

The following parameter names are **always** replaced with `***REDACTED***` in audit records, regardless of case:

`password` · `confirmpassword` · `apikey` · `api_key` · `token` · `secret` · `authorization`

---

## Rate Limiting

The Gomag API implements a **Leaky Bucket** algorithm applied per shop across all API access.

**Response headers** (present on every response until the limit is reached):

| Header | Description |
|---|---|
| `Api-RateLimit-Read` | Read request processing rate (req/s, default 1) |
| `Api-RateLimit-Read-Burst` | Maximum read requests in a burst |
| `Api-RateLimit-Read-Remaining` | Read requests remaining before throttling |
| `Api-RateLimit-Write` | Write request processing rate (req/s, default 1) |
| `Api-RateLimit-Write-Burst` | Maximum write requests in a burst |
| `Api-RateLimit-Write-Remaining` | Write requests remaining before throttling |

This server:
1. Parses all six headers after every request
2. Exposes the latest values via `gomag://rate-limit`
3. On a **429** response, waits at least 1 second before the first retry, then uses exponential back-off for subsequent retries
4. On **5xx** responses, uses pure exponential back-off (`factor × 2^attempt`)

---

## Gomag API Reference

The Gomag Public API is documented within the included Postman collection (`Gomag Public API.postman_collection.json`). Key details:

### Authentication

All requests require both the `ApiShop` and `Apikey` headers.

```
ApiShop: https://yourshop.gomag.ro        # every request
Apikey:  your_api_key_here                # every request
User-Agent: <custom value>                # must not be PostmanRuntime/…
```

Both values are obtained from your Gomag admin panel under **Settings → API**.

### Request format

| HTTP method | Parameters |
|---|---|
| `GET` | URL query string |
| `POST` | `multipart/form-data` with a single field `data` whose value is the JSON-serialised payload |

### Base URL

```
https://api.gomag.ro
```

### Response format

All endpoints return JSON. Paginated list endpoints include:

```json
{
  "total": 1250,
  "page": 1,
  "pages": 13,
  "items": [ ... ]
}
```

### Multi-language fields

Products, categories, and attributes support localised names. Language codes follow ISO 639-1 (`ro`, `en`, `hu`, etc.) and are configured per shop:

```json
{
  "name": {
    "ro": "Geacă softshell",
    "en": "Softshell jacket"
  }
}
```

---

## Security

### Password handling

The following tools accept **plaintext passwords** in their parameters:

| Tool | Sensitive parameters |
|---|---|
| `customer_create` | `password`, `confirm_password` |
| `customer_login` | `password` |
| `customer_change_password` | `old_password`, `new_password`, `confirm_new_password` |

**Important notes:**
- Passwords are transmitted to the Gomag API over HTTPS. Never call these tools over an unencrypted connection.
- Passwords are **never written to audit logs** — only the `email` field is logged for these calls.
- Do not pass plaintext passwords to an AI assistant in contexts where chat history is persisted or shared.

### Audit log security

- The audit log file (`gomag_audit.jsonl`) contains API call metadata. Restrict file permissions appropriately.
- The startup log prints the absolute path to the audit file — check this to confirm where logs are written.
- `.env` files and `*.jsonl` log files are excluded from git via `.gitignore`.

---

## Development

### Running tests

```bash
pip install -e ".[dev]"
pytest
```

Tests use [respx](https://lundberg.github.io/respx/) to mock HTTP responses — no live credentials required.

### Project layout

```
src/gomag_mcp/
├── __init__.py       # package version
├── __main__.py       # enables `python -m gomag_mcp`
├── server.py         # FastMCP entry point, lifespan, resources
├── config.py         # Pydantic settings (GOMAG_* env vars)
├── audit.py          # Structured JSON audit logger
├── client.py         # Async HTTP client (retry, rate-limit, pooling)
├── context.py        # Shared AppContext (avoids circular imports)
└── tools/
    ├── product.py    # 5 tools
    ├── category.py   # 4 tools
    ├── order.py      # 6 tools
    ├── customer.py   # 8 tools
    ├── awb.py        # 7 tools
    ├── invoice.py    # 3 tools
    ├── attribute.py  # 3 tools
    ├── review.py     # 2 tools
    ├── wishlist.py   # 3 tools
    └── misc.py       # 7 tools
```

### Adding a new tool

1. Find (or create) the appropriate module in `src/gomag_mcp/tools/`
2. Add a function inside the `register(mcp)` function decorated with `@mcp.tool()`
3. Call `get_context()` to access the shared `GomagClient` and `AuditLogger`
4. Wrap the API call with `async with ctx.audit.tool_call(...)` — all logging is automatic

```python
@mcp.tool()
async def my_new_tool(param: str) -> dict[str, Any]:
    """Clear docstring — this becomes the tool description visible to Claude."""
    ctx = get_context()
    params = {"param": param}
    async with ctx.audit.tool_call("my_new_tool", params, "GET", "/api/v1/...") as ar:
        result = await ctx.client.get("/api/v1/...", params=params)
        ar.update(result)
        return result["data"]
```

---

## License

[MIT](LICENSE) © 2026 florinel-chis
