"""Customer UI and homepage Buy Now QA, using a disposable database only."""
import sys,os,json,re,hashlib,subprocess,urllib.request
from pathlib import Path
from decimal import Decimal
import dashboard_management as dm
import order_management as om
import storefront_regression as gs

OUT=Path('/tmp/greenshop-customer-ui-qa-20261012');OUT.mkdir(mode=0o700,exist_ok=True)
om.OUT=dm.OUT=OUT;om.QA_PROJECT='greenshop-customer-ui-qa-20261012'

def prepare():
    om.prepare()
    for name in ('keys','images'):(OUT/name).mkdir(mode=0o700,exist_ok=True)
    file=OUT/'compose.yaml';s=file.read_text().replace('    environment:\n      ASPNETCORE_ENVIRONMENT: Production',f'    volumes:\n      - {OUT}/keys:/app/keys\n      - {OUT}/images:/app/wwwroot/uploads/products\n    environment:\n      ASPNETCORE_ENVIRONMENT: Production');file.write_text(s)

def preservation():
    before=json.loads((OUT/'baseline.json').read_text());after=om.real_snapshot()
    for key in ('products','categories','users','images','keys','infrastructure_source','containers','Orders','OrderItems','CartItems','migrations'):assert before[key]==after[key],key
    assert before['extra']==dm.extra_snapshot()
    for section in ('business_sources','admin_assets'):
        for name,digest in before[section].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
    (OUT/'preservation-results.json').write_text(json.dumps({'status':'PASS','checks':'All business source and entire Admin UI unchanged; all real data, stock, user roles/passwords, images, keys, migrations and infrastructure preserved'}))
    print('PASS: Business source, Admin UI and all production data/keys/images preserved.',flush=True)

def browser():
    om.configure_qa();sys.path.insert(0,'/tmp/greenshop-category-python-packages');os.environ['PLAYWRIGHT_BROWSERS_PATH']='/tmp/greenshop-category-browsers'
    from playwright.sync_api import sync_playwright,expect
    account=json.loads((OUT/'accounts.json').read_text())[2];checks=[]
    def passed(s):checks.append(s);print('PASS: '+s,flush=True)
    def overflow(page,label,width):
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(label,width,page.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,6).map(e=>[e.tagName,e.className,e.getBoundingClientRect().width])"))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);context=browser.new_context(ignore_https_errors=True);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_init_script("document.addEventListener('animationstart',e=>{if(e.animationName==='customer-page-enter')window.__customerEntrance=(window.__customerEntrance||0)+1},true)")
        product=int(om.qa_sql('SELECT Id FROM Products WHERE StockQuantity>3 ORDER BY Id DESC LIMIT 1'))
        empty=om.qa_sql("SELECT c.Id FROM Categories c WHERE c.IsActive=1 AND NOT EXISTS (SELECT 1 FROM Products p WHERE p.CategoryId=c.Id) ORDER BY c.Id DESC LIMIT 1")
        if not empty:empty=om.qa_sql("INSERT INTO Categories (Name,Description,IsActive) VALUES ('Customer UI Empty','Owned UI fixture',1); SELECT LAST_INSERT_ID()")
        empty_category=int(empty)
        for width in (1440,768,360,320):
            page.set_viewport_size({'width':width,'height':1000})
            for label,path in [('home','/'),('catalog','/SanPham/CuaHang'),('detail',f'/SanPham/ChiTietSanPham/{product}'),('single','/SanPham/CuaHang?search=QA%20Legacy%20Plant'),('empty',f'/SanPham/CuaHang?categoryId={empty_category}'),('login','/Account/Login'),('register','/Account/Register')]:
                page.goto(om.QA_BASE+path);page.evaluate('document.fonts.ready');overflow(page,label,width)
                assert page.evaluate("document.fonts.check('400 14px \"Be Vietnam Pro\"','Đăng nhập Giỏ hàng')")
                assert 'Be Vietnam Pro' in page.locator('body').evaluate('e=>getComputedStyle(e).fontFamily')
                assert page.evaluate('window.__customerEntrance')==1
                assert not re.search(r'@(Model|foreach|if)',page.locator('main').inner_text())
                page.screenshot(path=str(OUT/f'customer-{label}-{width}.png'),full_page=True,animations='disabled')
                if label in ('home','catalog'):page.screenshot(path=str(OUT/f'customer-{label}-viewport-{width}.png'),animations='disabled')
            passed(f'{width}px: home/catalog/detail/single/empty/login/register; local Vietnamese font, entrance animation and no overflow')
        page.set_viewport_size({'width':1440,'height':1000});page.goto(om.QA_BASE+'/');page.evaluate('document.fonts.ready')
        before=om.qa_sql('SELECT COUNT(*) FROM Orders');stocks=om.qa_sql('SELECT Id,StockQuantity FROM Products ORDER BY Id')
        available=page.locator('.shop-product-card:has(.product-card-buy button:not(:disabled))').first;pid=int(available.get_attribute('data-product-id'))
        card=available;card.hover();page.wait_for_timeout(230);assert card.evaluate('e=>getComputedStyle(e).transform')!='none'
        card.get_by_role('button',name='Mua ngay',exact=False).click();expect(page).to_have_url(re.compile('/Account/Login\\?returnUrl='));expect(page.locator('[name=returnUrl]')).to_have_value(re.compile(f'/ThanhToan/XacNhanMuaHang/{pid}'))
        assert om.qa_sql('SELECT COUNT(*) FROM Orders')==before and stocks==om.qa_sql('SELECT Id,StockQuantity FROM Products ORDER BY Id')
        page.locator('#Email').fill(account[0]);page.locator('[name=Password]').fill(account[1]);page.locator('form:has(#Email) button[type=submit]').click();expect(page.locator('.checkout-form')).to_be_visible();expect(page.locator('#Quantity')).to_have_value('1');assert page.url.endswith(f'/ThanhToan/XacNhanMuaHang/{pid}?quantity=1')
        assert om.qa_sql('SELECT COUNT(*) FROM Orders')==before
        page.locator('#Address').fill('123 Đường kiểm thử giao diện, Hà Nội');page.locator('.checkout-form button[type=submit]').click();expect(page.locator('.order-items')).to_be_visible();expect(page.locator('.shop-page-heading')).to_contain_text('Chờ xác nhận')
        oid=int(page.url.rsplit('/',1)[1]);assert om.qa_sql(f'SELECT Quantity FROM OrderItems WHERE OrderId={oid}')=='1'
        passed('Homepage card Buy Now: real anonymous POST -> safe login return -> quantity 1 confirmation -> real COD order; no order/stock change before confirmation')
        # Hero Buy Now uses its own form and exact featured ID. Going back then adding to cart remains separate.
        page.goto(om.QA_BASE+'/');hero=page.locator('.hero-purchase form');action=hero.get_attribute('action');hero_pid=int(action.rsplit('/',1)[1]);assert hero_pid==int(page.locator('.hero-featured').get_attribute('href').rsplit('/',1)[1])
        if page.locator('.hero-purchase button').is_enabled():
            count=om.qa_sql('SELECT COUNT(*) FROM Orders');page.locator('.hero-purchase button').click();expect(page).to_have_url(re.compile(f'/ThanhToan/XacNhanMuaHang/{hero_pid}'));assert om.qa_sql('SELECT COUNT(*) FROM Orders')==count
            page.go_back();expect(page.locator('.hero-purchase')).to_be_visible()
        available=page.locator('.shop-product-card:has(.product-card-action button:not(:disabled))').first;cart_pid=int(available.get_attribute('data-product-id'));available.get_by_role('button',name='Thêm vào giỏ',exact=True).click();expect(page).to_have_url(re.compile('/GioHang/QuanLyGioHang'));assert int(om.qa_sql(f'SELECT Quantity FROM CartItems WHERE UserId=3 AND ProductId={cart_pid}'))>=1
        passed('Hero Buy Now targets the displayed product; authenticated confirmation; independent Add to cart works after back navigation')
        for width in (1440,768,360,320):
            page.set_viewport_size({'width':width,'height':1000})
            for label,path in [('cart','/GioHang/QuanLyGioHang'),('checkout',f'/ThanhToan/XacNhanMuaHang/{pid}?quantity=1'),('history','/ThanhToan/DonHangCuaToi'),('receipt',f'/ThanhToan/ChiTietDonHang/{oid}')]:
                page.goto(om.QA_BASE+path);overflow(page,label,width);page.screenshot(path=str(OUT/f'customer-{label}-{width}.png'),full_page=True,animations='disabled')
        passed('Authenticated cart/checkout/order history/receipt responsive at 1440/768/360/320')
        page.set_viewport_size({'width':1440,'height':1000});page.goto(om.QA_BASE+'/');page.get_by_role('button',name='Mở tìm kiếm',exact=True).click();dialog=page.locator('#shop-search-dialog');expect(dialog).to_be_visible()
        for _ in range(5):page.keyboard.press('Tab');assert page.evaluate("document.querySelector('#shop-search-dialog').contains(document.activeElement)")
        page.keyboard.press('Escape');expect(dialog).not_to_be_visible();expect(page.get_by_role('button',name='Mở tìm kiếm',exact=True)).to_be_focused()
        page.set_viewport_size({'width':360,'height':800});page.get_by_role('button',name='Mở menu điều hướng',exact=True).click();expect(page.locator('#shop-navigation-dialog')).to_be_visible();page.keyboard.press('Escape');expect(page.locator('#shop-navigation-dialog')).not_to_be_visible()
        page.reload();page.wait_for_function('window.__customerEntrance===1')
        page.emulate_media(reduced_motion='reduce');page.reload();assert page.locator('main').evaluate('e=>getComputedStyle(e).animationName')=='none';assert page.locator('.shop-btn').first.evaluate('e=>getComputedStyle(e).transitionDuration')=='0s'
        page.emulate_media(reduced_motion='no-preference');page.set_viewport_size({'width':1440,'height':1000});page.goto(om.QA_BASE+'/')
        bad=page.locator('[data-product-image]').first;bad.evaluate("e=>e.src='/uploads/products/missing-customer-ui.png'");expect(bad).to_have_attribute('src','/images/product-placeholder.svg')
        zero=int(om.qa_sql('SELECT Id FROM Products WHERE StockQuantity=0 ORDER BY Id DESC LIMIT 1'));page.goto(om.QA_BASE+f'/SanPham/CuaHang?search='+__import__('urllib.parse',fromlist=['quote']).quote(om.qa_sql(f'SELECT Name FROM Products WHERE Id={zero}')))
        empty_card=page.locator(f'[data-product-id="{zero}"]');expect(empty_card.locator('.product-card-buy button')).to_be_disabled();expect(empty_card.locator('.product-card-action button')).to_be_disabled()
        passed('Native search/menu dialogs, keyboard/focus/Escape, reload/reduced motion, image fallback and out-of-stock Buy Now/Add to cart disabled')
        assert not errors,errors;context.close();browser.close()
    (OUT/'customer-browser-results.json').write_text(json.dumps({'status':'PASS','checks':checks,'writes':'synthetic isolated only'},indent=2))

def cards_security():
    om.configure_qa();buyer=gs.client();gs.login(buyer,json.loads((OUT/'accounts.json').read_text())[2]);page=gs.get(buyer,'/')[0]
    before=om.qa_sql('SELECT COUNT(*) FROM Orders');stocks=om.qa_sql('SELECT Id,StockQuantity FROM Products ORDER BY Id')
    assert gs.request(buyer,'/ThanhToan/MuaNgay/1')[0]==405
    assert gs.request(buyer,'/ThanhToan/MuaNgay/1',{'Quantity':1})[0]==400
    assert gs.post(buyer,'/ThanhToan/MuaNgay/1',page,{'Quantity':0})[0]==302
    assert om.qa_sql('SELECT COUNT(*) FROM Orders')==before and om.qa_sql('SELECT Id,StockQuantity FROM Products ORDER BY Id')==stocks
    for _,a in page.nodes:
        if a.get('class') in ('product-card-buy',):assert a['method']=='post' and '/ThanhToan/MuaNgay/' in a['action']
    print('PASS: Homepage Buy Now remains POST/CSRF protected; invalid/GET requests do not create orders or change stock.',flush=True)
    (OUT/'buy-now-security-results.json').write_text(json.dumps({'status':'PASS','checks':'POST-only, CSRF, quantity validation; no premature order or stock mutation'}))

def production():
    om.production_checks();client=gs.client();page,body,_=gs.get(client,'/')
    forms=[a for tag,a in page.nodes if tag=='form' and '/ThanhToan/MuaNgay/' in a.get('action','')];assert forms and all(a.get('method')=='post' for a in forms)
    for path in ('/css/storefront-theme.css','/js/storefront-theme.js'):
        code,_,text=gs.request(client,path);assert code==200 and len(text)>100
    assert gs.sql('SELECT COUNT(*) FROM __EFMigrationsHistory')=='5'
    (OUT/'customer-production-results.json').write_text(json.dumps({'status':'PASS','checks':'HTTPS/storefront/auth 200; homepage Buy Now POST forms present; theme assets serve; protected Admin unchanged; 5 migrations; production read-only'},indent=2))
    print('PASS: Production homepage has Buy Now, theme assets serve 200, HTTPS and existing modules healthy.',flush=True)

def public_preview():
    """Capture the actual public catalogue; no sign-in or form submissions."""
    sys.path.insert(0,'/tmp/greenshop-category-python-packages');os.environ['PLAYWRIGHT_BROWSERS_PATH']='/tmp/greenshop-category-browsers'
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        context=browser.new_context(ignore_https_errors=True)
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        for width in (1440,360):
            page.set_viewport_size({'width':width,'height':1000})
            for label,path in [('home','/'),('catalog','/SanPham/CuaHang')]:
                response=page.goto(gs.BASE+path);assert response.status==200
                page.evaluate('document.fonts.ready')
                page.wait_for_function("[...document.querySelectorAll('[data-product-image]')].every(e=>e.complete && e.naturalWidth>0)")
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(OUT/f'production-customer-{label}-{width}.png'),full_page=True,animations='disabled')
                page.screenshot(path=str(OUT/f'production-customer-{label}-viewport-{width}.png'),animations='disabled')
        assert not errors,errors
        context.close();browser.close()
    (OUT/'public-preview-results.json').write_text(json.dumps({'status':'PASS','checks':'Production public home/catalog at 1440/360px; real photos load; no overflow or JS errors; GET only'}))
    print('PASS: Production public home/catalog screenshots, real photos, responsive layout and no JavaScript errors; GET only.',flush=True)

if __name__=='__main__':
    {'prepare':prepare,'start':om.start,'refresh':lambda:om.start(False),'business':om.run_business,'edge':om.edge_checks,'browser':browser,'security':cards_security,'preservation':preservation,'production':production,'public-preview':public_preview,'teardown':om.teardown,'admin-regression':om.browser_checks}[sys.argv[1]]()
