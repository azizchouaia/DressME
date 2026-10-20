import json, sys
from playwright.sync_api import sync_playwright
meta=json.load(open("meta.json"))
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(device_scale_factor=2)
    for m in meta:
        svg=open(f"{m['item_id']}.svg").read()
        pg.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
        pg.locator("svg").screenshot(path=f"{m['item_id']}.png", omit_background=True)
    b.close()
