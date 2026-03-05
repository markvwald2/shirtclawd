# Shirt Scrape Workflow

This folder contains the minimal workflow to periodically scrape the Third String Shirts storefront and view results.

## Files

- `scrape.js`: Scrapes product image URLs from all storefront pages into JSON.
- `output_image_urls.json`: Latest scraped image list used by the viewer.
- `image-grid-viewer.html`: Local grid viewer for the JSON output (includes theme toggles).
- `package.json` / `package-lock.json`: Node dependencies (Playwright).

## Setup

From this folder:

```bash
npm install
```

## Re-scrape Store Data

```bash
node scrape.js --url 'https://shop.spreadshirt.com/thirdstringshirts/'
```

This overwrites `output_image_urls.json` with the newest scrape.

## View Results

Start a local web server in this folder:

```bash
python3 -m http.server 8000
```

Open:

- `http://localhost:8000/image-grid-viewer.html`

## Notes

- The scraper handles multi-page navigation and attempts to resolve placeholder images via detail pages.
- The viewer always shows non-themed shirts, and lets you hide/show themed groups with checkboxes.
