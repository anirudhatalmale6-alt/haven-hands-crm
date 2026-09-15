from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto("http://127.0.0.1:8201/", wait_until="networkidle")
    pg.screenshot(path="demo-top.png")
    pg.mouse.wheel(0, 760)
    pg.wait_for_timeout(400)
    pg.screenshot(path="demo-scrolled.png")
    b.close()
print("ok")
