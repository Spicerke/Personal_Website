#!/usr/bin/env python3
"""Dev server for public/ that mirrors how Cloudflare Workers serves this site.

Two things the stdlib server gets wrong for this project:

1. No Cache-Control at all -- only Last-Modified -- so browsers apply heuristic
   freshness and reuse stale files. That made edits look like they had not
   landed. Everything here is no-store.

2. No extensionless URL resolution. Workers serves /resume from resume.html
   automatically; without this, every internal link 404s locally while working
   in production.
"""
import http.server
import os
import sys

ROOT = "/Users/kaispicer/Desktop/Personal_Website/public"


class Dev(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        local = super().translate_path(path)
        if not os.path.exists(local) and not os.path.splitext(local)[1]:
            if os.path.exists(local + ".html"):
                return local + ".html"
        return local

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.chdir(ROOT)
http.server.ThreadingHTTPServer(("", port), Dev).serve_forever()
