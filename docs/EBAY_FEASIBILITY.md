# S1-1 — eBay API Feasibility (November 12, 2026)

## Verified by Member B

### Developer Access and Authentication

- eBay Developers Program account approved.
- Sandbox OAuth 2.0 client-credentials authentication succeeded with a 7,200-second token lifetime.
- Sandbox Browse API `item_summary/search` returned 1 item for `denim jacket`.
- eBay granted a Marketplace Account Deletion notification **exemption based on not persisting eBay data**.
- Production OAuth 2.0 client-credentials authentication succeeded with a 7,200-second token lifetime.
- Production Browse API `item_summary/search` returned 3 live items for `denim jacket`.

These results confirm that the application can authenticate and access the eBay Browse API in both Sandbox and Production environments.

### Initial Production Search Verification

An initial Production search was performed using the following parameters:

- **Query:** `brown leather jacket`
- **Requested limit:** 5
- **Results returned:** 5
- **Condition filter:** None

All five results contained a title, price/currency, condition, image URL, and eBay listing URL.

However, only one listing was classified as pre-owned. The other four were classified as `New with tags`.

Because Thrift Finder focuses on secondhand clothing, this motivated implementing the `conditions:{USED}` filter.

### Used-Only Production Search Verification

The reusable eBay client was tested against the live Production Browse API using:

- **Query:** `brown leather jacket`
- **Filter:** `conditions:{USED}`
- **Requested limit:** 5
- **Results returned:** 5

**Verification Results:**

- All 5 listings were classified as `Pre-owned - Excellent`.
- All 5 contained titles, prices, conditions, image URLs, and eBay listing URLs.
- The used-condition filter successfully excluded new-condition listings in this test.
- Search results did not always match every requested attribute exactly; one returned jacket was black rather than brown.

The client successfully retrieved live secondhand clothing metadata without writing listing records to persistent storage.

Individual live listing records are not retained in this documentation.

## Reusable eBay API Client

The integration prototype consists of three files:

- **`backend/app/data/ebay_client.py`** — Handles OAuth authentication, Browse API requests, used-condition filtering, and normalized listing metadata.
- **`scripts/ebay_preview.py`** — Provides a command-line interface for previewing live eBay results in Sandbox or Production.
- **`backend/tests/test_ebay_client.py`** — Contains automated tests using mocked API responses.

### Supported Functionality

The reusable client supports:

- OAuth 2.0 application authentication using environment-specific developer credentials.
- Browse API searches using text queries.
- Used-only filtering through `conditions:{USED}`.
- Configurable search result limits.
- Retrieval of listing IDs, titles, prices, currencies, conditions, image URLs, and listing URLs.
- Normalization of listing metadata for future application integration.
- Error handling for authentication, network, and API response failures.

The client processes responses in memory and does not generate FashionCLIP similarity scores.

## Reproduce the Tests

From the repository root, activate the project's Python environment and run:

```bash
source .venv/bin/activate
```

### Production Search

```bash
python -m scripts.ebay_preview --environment production --query "brown leather jacket" --limit 5
```

### Sandbox Search

```bash
python -m scripts.ebay_preview --environment sandbox --query "denim jacket" --limit 5
```

### Automated Tests

```bash
python -m pytest backend/tests/test_ebay_client.py -q
python -m pytest backend/tests -q
python -m ruff check backend/ scripts/
```

The preview script prompts for an environment-specific App ID and hidden Cert ID. Alternatively, credentials can be supplied through the `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` environment variables.

**Never commit API credentials, client secrets, or OAuth access tokens to GitHub.**

By default, searches request only `USED` listings. The optional `--include-new` argument disables the used-only filter.

### Automated Test Results

The following checks were completed on November 12, 2026:

- 16 eBay client unit tests passed.
- Full backend test suite passed with 1 existing skipped test.
- Ruff linting passed.
- Sandbox OAuth and Browse API requests succeeded.
- Production OAuth and Browse API requests succeeded.
- Production used-only search returned 5 pre-owned listings.
- All 5 used-only results contained image and listing URLs.

These results demonstrate that the standalone eBay integration prototype functions successfully under the tested conditions.

## Privacy and Compliance

eBay granted a Marketplace Account Deletion notification exemption on the basis that Thrift Finder does not persist eBay data.

The current API client and preview script process eBay responses in memory without intentionally writing listing data, API responses, OAuth tokens, or credentials to a database, file, persistent cache, or application log.

Future integration must preserve this behavior unless the application's data-handling practices and compliance configuration are updated.

The existing 500-item local clothing dataset is independently sourced and does not contain imported eBay API listings.

Successful Sandbox and Production API requests demonstrate technical access at the time of testing. They do not independently establish that all applicable eBay partnership, contractual, or production-use requirements have been fulfilled.

Review [eBay's Buy API production requirements](https://developer.ebay.com/api-docs/buy/buy-requirements.html) before deploying the live integration.

## Integration Boundary

The eBay client is currently an **isolated feasibility prototype**, not an implementation of the application's `/api/search` endpoint.

The client can retrieve and normalize live secondhand clothing listings, but it is not yet connected to the frontend or FashionCLIP ranking pipeline.

The Backend Lead is responsible for coordinating search endpoint integration and any necessary result-score mapping.

The existing licensed dataset of 500 outerwear garments will remain available as a reliable local search fallback.

## Remaining Integration Steps

1. Coordinate with the Backend Lead before connecting the eBay client to `/api/search`.
2. Integrate live listing retrieval into the application's search workflow.
3. Ensure eBay data remains in memory and is not persistently stored.
4. Preserve the independent 500-item licensed local dataset as a fallback.
5. Validate listing metadata, image URLs, prices, and purchase links during integration.
6. Test API failures, empty results, and local fallback behavior.
7. Review applicable eBay production-use requirements before deployment.

## S1-1 Feasibility Outcome

**Status: Successfully verified**

Sandbox and Production OAuth authentication, Browse API requests, and live used-only clothing searches have been successfully tested.

The reusable eBay API client is implemented and verified through automated tests and live Production requests.

**S1-1 feasibility testing is complete.** Integration with the application's search endpoint and frontend remains a separate development task to be coordinated with the Backend Lead.
## Local credential configuration

The eBay preview script automatically reads `EBAY_CLIENT_ID` and
`EBAY_CLIENT_SECRET` from environment variables or the repository-root
`.env` file using the existing backend settings configuration.

For local development, create a private `.env` file in the repository root
containing the appropriate eBay application credentials. The `.env` file is
Git-ignored and must not be committed.

Example configuration (placeholders only):

```dotenv
EBAY_CLIENT_ID=your-app-id
EBAY_CLIENT_SECRET=your-cert-id
```

Run the preview from the repository root:

```bash
python -m scripts.ebay_preview --environment production --query "brown leather jacket" --limit 5
```

When credentials are configured, the script runs without interactive
credential prompts. If credentials are missing, the existing prompts remain
available.

Production deployments should configure credentials as backend environment
secrets rather than exposing them to the frontend or committing them to Git.
