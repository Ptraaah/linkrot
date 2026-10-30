# linkrot

Find the dead links on your site before your readers do. Reads a `sitemap.xml` or a URL list, checks everything concurrently, reports dead, redirected, and slow URLs. Standard library only.

## Usage

```bash
python3 linkrot.py https://example.com/sitemap.xml
python3 linkrot.py --file urls.txt --workers 16
python3 linkrot.py https://example.com --crawl 2     # follow same-host links, 2 levels deep
```

Real output shape:

```
checking 3 URLs with 4 workers

DEAD   404  https://example.com/this-page-does-not-exist-xyz

linkrot: 3 checked, 1 dead, 0 redirected, 0 slow
```

- Sitemap indexes are followed automatically (up to 20 sub-sitemaps)
- Servers that refuse HEAD requests are retried with GET
- Responses slower than `--slow` seconds (default 3) are flagged
- Exit code is 1 when anything is dead, so a weekly cron plus this tool is a complete link-health monitor

## Indonesian summary

Pencari tautan mati di situs Anda: baca sitemap.xml atau daftar URL, periksa semuanya secara paralel, laporkan yang mati, yang berpindah, dan yang lambat. Cocok dijalankan berkala lewat cron atau CI.

## License

MIT. By ptraaa.
