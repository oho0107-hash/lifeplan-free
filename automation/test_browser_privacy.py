"""Synthetic-only backup/restore and local-only data smoke; run as a script."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path
from threading import Thread
import json
import os
from playwright.sync_api import sync_playwright, expect


def main():
    root = Path(__file__).resolve().parent.parent
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(root)))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            options = {'executable_path': os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}
            browser = p.chromium.launch(**options)
            page = browser.new_page(viewport={'width': 390, 'height': 844}, accept_downloads=True)
            external = []
            page.on('request', lambda r: external.append(r.url) if not r.url.startswith(f'http://127.0.0.1:{server.server_port}/') else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
            page.locator('#husband_month_net').fill('123456')
            page.locator('#wife_month_net').fill('234567')
            with page.expect_download() as event:
                page.locator('#backup').click()
            download = event.value
            payload = json.loads(Path(download.path()).read_text())
            assert payload['husband_month_net'] == '123456'
            assert payload['wife_month_net'] == '234567'
            page.locator('#husband_month_net').fill('999')
            page.locator('#restoreFile').set_input_files({'name': 'synthetic.json', 'mimeType': 'application/json', 'buffer': json.dumps(payload).encode()})
            expect(page.locator('#status')).to_contain_text('バックアップを読み込みました')
            expect(page.locator('#husband_month_net')).to_have_value('123456')
            page.reload()
            expect(page.locator('#husband_month_net')).to_have_value('123456')
            print('PASS: synthetic JSON backup, restore, reload compatibility')
            for content in (b'not-json', b'[]', b'x' * 250001):
                page.locator('#restoreFile').set_input_files({'name': 'invalid.json', 'mimeType': 'application/json', 'buffer': content})
                expect(page.locator('#status')).to_contain_text('読み込み失敗')
                expect(page.locator('#husband_month_net')).to_have_value('123456')
            print('PASS: malformed, array and oversized backup rejected without data loss')
            page.goto(f'http://127.0.0.1:{server.server_port}/education-reserve.html')
            expect(page.locator('#sources')).to_contain_text('件の公式料金ページ')
            assert not external, f'Unexpected external browser requests: {external}'
            print('PASS: both pages send no external requests during tested interactions')
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
