"""Real Chromium form interaction with invented fake data, no family private inputs."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import os
from playwright.sync_api import sync_playwright

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=Thread(target=server.serve_forever,daemon=True)
thread.start()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, **({"executable_path":os.environ["CHROMIUM_PATH"],"args":["--no-sandbox"]} if os.getenv("CHROMIUM_PATH") else {}))
        page=browser.new_page(viewport={'width':390,'height':844})
        page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
        assert page.locator('#calculate').is_enabled()
        fake={'husband_birth':'1990-01-01','wife_birth':'1991-06-01',
              'kid1_birth':'2020-01-01','kid2_birth':'2022-01-01','kid3_birth':'2024-01-01',
              'husband_month_net':'450000','wife_month_net':'250000',
              'current_savings':'12000000','living_cost_annual':'5600000'}
        for key,val in fake.items():page.locator('#'+key).fill(val)
        page.locator('#calculate').click()
        assert page.locator('#results').is_visible(),'結果が表示されない'
        assert page.locator('#kpis .kpi').count()==4,'主要指標が足りない'
        assert page.locator('#tableBody tr').count()>20,'年次表の件数不足'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'横方向にはみ出し'
        print('PASS: iPhone 390px, fake data, result screen')
        page.locator('#edit').click()
        page.locator('#kid4_has').select_option('yes')
        page.locator('#kid4_birth').fill('2028-01-01')
        page.locator('#calculate').click()
        assert page.locator('#eduBreakdown').get_by_text('四男').count()>0,'4人目の教育費が出ない'
        page.reload()
        assert page.locator('#kid4_birth').input_value()=='2028-01-01','保存できない'
        print('PASS: 4th child, storage')
        page.locator('#calculate').click()
        page.locator('#edit').click()
        for key in ['husband_month_net','wife_month_net','husband_bonus_net','wife_bonus_net',
                    'current_savings','current_invest_balance']:
            page.locator('#'+key).fill('0')
        page.locator('#calculate').click()
        assert page.locator('#debtAlert').is_visible(),'資金不足の表示がない'
        print('PASS: shortage displayed')
        browser.close()
finally:
    server.shutdown()
    server.server_close()
