"""Shared Admin appearance and regressions on a disposable Compose project."""
import sys,os,json,hashlib,subprocess,re
from pathlib import Path
import dashboard_management as dm
import user_management as us
import order_management as om
import storefront_regression as gs

OUT=Path('/tmp/greenshop-admin-ui-qa-20261012');OUT.mkdir(mode=0o700,exist_ok=True)
dm.OUT=us.OUT=om.OUT=OUT;om.QA_PROJECT='greenshop-admin-ui-qa-20261012'

def prepare():
    om.prepare()
    for name in ('keys','images'):(OUT/name).mkdir(mode=0o700,exist_ok=True)
    file=OUT/'compose.yaml';s=file.read_text().replace('    environment:\n      ASPNETCORE_ENVIRONMENT: Production',f'    volumes:\n      - {OUT}/keys:/app/keys\n      - {OUT}/images:/app/wwwroot/uploads/products\n    environment:\n      ASPNETCORE_ENVIRONMENT: Production');file.write_text(s)

def preservation():
    before=json.loads((OUT/'baseline.json').read_text());after=om.real_snapshot()
    for key in ('products','categories','users','images','keys','infrastructure_source','containers','Orders','OrderItems','CartItems','migrations'):assert before[key]==after[key],key
    assert before['extra']==dm.extra_snapshot()
    for name,digest in before['admin_source'].items():
        if not name.endswith('Shared/_AdminLayout.cshtml'):assert after['admin_source'][name]==digest,name
    for name,digest in before['business_sources'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
    (OUT/'preservation-results.json').write_text(json.dumps({'status':'PASS','checks':'Every controller/model/service/context/migration source unchanged; real users/order/history/stock/cart/data/images/keys/infrastructure preserved'}))
    print('PASS: All business source and real data/keys/images/migrations/containers preserved.',flush=True)

def browser():
    om.configure_qa();sys.path.insert(0,'/tmp/greenshop-category-python-packages');os.environ['PLAYWRIGHT_BROWSERS_PATH']='/tmp/greenshop-category-browsers'
    from playwright.sync_api import sync_playwright,expect
    account=json.loads((OUT/'accounts.json').read_text())[0];checks=[]
    def passed(s):checks.append(s);print('PASS: '+s,flush=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);context=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(om.QA_BASE+'/Account/Login');page.locator('#Email').fill(account[0]);page.locator('[name=Password]').fill(account[1]);page.locator('form:has(#Email) button[type=submit]').click();expect(page).to_have_url(om.QA_BASE+dm.BASE)
        admin=om.admin_sessions()[0]
        category=om.qa_sql("SELECT Id FROM Categories WHERE Name='UI Modal QA'")
        if not category:
            form=gs.get(admin,'/Admin/DanhMuc/ThemDanhMuc')[0]
            assert gs.post(admin,'/Admin/DanhMuc/ThemDanhMuc',form,{'Name':'UI Modal QA','Description':'Synthetic UI fixture','IsActive':'true'})[0]==302
            category=om.qa_sql("SELECT Id FROM Categories WHERE Name='UI Modal QA'")
        pages=[('dashboard',dm.BASE),('products','/Admin/SanPham/QuanLySanPham'),('product-create','/Admin/SanPham/ThemSanPham'),('product-edit','/Admin/SanPham/SuaSanPham/1'),('product-detail','/Admin/SanPham/ChiTietSanPham/1'),('product-delete','/Admin/SanPham/XoaSanPham/1'),('categories','/Admin/DanhMuc/QuanLyDanhMuc'),('category-create','/Admin/DanhMuc/ThemDanhMuc'),('users','/Admin/NguoiDung/QuanLyNguoiDung'),('user-detail','/Admin/NguoiDung/ChiTietNguoiDung/3'),('orders','/Admin/DonHang/QuanLyDonHang'),('order-detail','/Admin/DonHang/ChiTietDonHang/1')]
        pages.extend((label,'/Admin/DanhMuc/'+action+'/'+category) for label,action in [('category-detail','ChiTietDanhMuc'),('category-edit','SuaDanhMuc'),('category-delete','XoaDanhMuc')])
        page.add_init_script("document.addEventListener('animationstart',e=>{if(e.animationName==='admin-page-enter')window.__adminEntrance=(window.__adminEntrance||0)+1},true)")
        for width in (1440,768,360):
            page.set_viewport_size({'width':width,'height':1000})
            for label,path in pages:
                response=page.goto(om.QA_BASE+path);assert response.status==200,(label,response.status)
                page.evaluate('document.fonts.ready');page.wait_for_function("getComputedStyle(document.querySelector('.admin-page-content')).opacity==='1'")
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,label,page.evaluate("[...document.querySelectorAll('.admin-main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,5).map(e=>[e.tagName,e.className,e.getBoundingClientRect().width])"))
                assert 'Be Vietnam Pro' in page.locator('.admin-main').evaluate('e=>getComputedStyle(e).fontFamily')
                assert page.evaluate("document.fonts.check('400 14px \"Be Vietnam Pro\"','Quản lý Người dùng Đơn hàng')")
                assert page.evaluate('window.__adminEntrance')==1
                assert not re.search(r'@(if|foreach|Model)',page.locator('.admin-main').inner_text())
                page.screenshot(path=str(OUT/f'admin-{label}-{width}.png'),full_page=True,animations='disabled')
                if label in ('dashboard','products','users'):page.screenshot(path=str(OUT/f'admin-{label}-viewport-{width}.png'),animations='disabled')
            passed(f'{width}px: all five modules and product forms/detail/delete render; local Vietnamese font loaded; entrance animation; no page overflow')
        page.set_viewport_size({'width':1440,'height':1000});page.goto(om.QA_BASE+dm.BASE);page.evaluate('document.fonts.ready')
        page.reload();page.wait_for_function("getComputedStyle(document.querySelector('.admin-page-content')).opacity==='1'");assert page.evaluate('window.__adminEntrance')==1
        button=page.get_by_role('button',name='Áp dụng');normal=button.evaluate('e=>getComputedStyle(e).boxShadow');button.hover();page.wait_for_timeout(220);assert button.evaluate('e=>getComputedStyle(e).boxShadow')!=normal
        box=button.bounding_box();page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);page.mouse.down();expect(button).to_have_class(re.compile('admin-pressed'));page.wait_for_timeout(140);assert button.evaluate('e=>getComputedStyle(e).transform')!='none';page.mouse.move(10,90);page.mouse.up()
        page.locator('#dashRange').focus();page.keyboard.press('Tab');expect(button).to_be_focused();assert button.evaluate('e=>getComputedStyle(e).outlineStyle')=='solid'
        page.emulate_media(reduced_motion='reduce');page.reload();assert page.locator('.admin-page-content').evaluate('e=>getComputedStyle(e).animationName')=='none';assert button.evaluate('e=>getComputedStyle(e).transitionDuration')=='0s';expect(page.locator('h1')).to_be_visible()
        page.emulate_media(reduced_motion='no-preference')
        passed('Reload entrance, real hover/press feedback and keyboard focus; reduced motion removes animation and keeps content visible')
        page.goto(om.QA_BASE+'/Admin/DanhMuc/QuanLyDanhMuc');page.locator('[data-confirm-status]').first.click();modal=page.locator('#categoryConfirmModal');expect(modal).to_be_visible()
        page.wait_for_function("getComputedStyle(document.querySelector('#categoryConfirmModal .modal-dialog')).transform==='none'")
        bounds=page.locator('#categoryConfirmModal .modal-dialog').bounding_box();assert bounds['y']>=0 and bounds['y']+bounds['height']<=1000
        assert modal.get_by_role('button',name='Hủy',exact=True).evaluate("e=>{const b=e.getBoundingClientRect();return e.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2))}")
        page.screenshot(path=str(OUT/'admin-category-modal.png'),animations='disabled');page.keyboard.press('Escape');expect(modal).not_to_be_visible()
        passed('Existing Bootstrap confirmation modal stays inside the viewport and Escape closes it')
        page.set_viewport_size({'width':360,'height':800});page.goto(om.QA_BASE+dm.BASE);toggle=page.locator('#adminSidebarToggle');toggle.click();expect(toggle).to_have_attribute('aria-expanded','true');page.locator('#adminSidebarOverlay').click();expect(toggle).to_have_attribute('aria-expanded','false')
        page.goto(om.QA_BASE+'/Admin/DonHang/InDonHang/1');page.emulate_media(media='print');expect(page.locator('.admin-topbar')).not_to_be_visible();expect(page.locator('.order-action-panel')).not_to_be_visible();expect(page.locator('.order-purchased-items')).to_be_visible();assert page.locator('.admin-page-content').evaluate('e=>getComputedStyle(e).opacity')=='1';page.pdf(path=str(OUT/'admin-print.pdf'));page.emulate_media(media='screen')
        passed('Mobile menu works and existing printable receipt keeps content visible while hiding chrome/actions')
        assert not errors,errors;context.close();browser.close()
    (OUT/'ui-browser-results.json').write_text(json.dumps({'status':'PASS','checks':checks},indent=2))

def production():
    dm.production()
    client=gs.client()
    for path in ('/css/admin-fonts.css','/css/admin-theme.css','/js/admin-theme.js'):
        code,_,body=gs.request(client,path);assert code==200 and len(body)>100
    req=gs.BASE+'/fonts/be-vietnam-pro/be-vietnam-pro-400-vietnamese.woff2'
    response=client.open(req,timeout=30);assert response.code==200 and response.read(4)==b'wOF2'
    print('PASS: Production shared theme assets and local Vietnamese font serve 200.',flush=True)

if __name__=='__main__':
    {'prepare':prepare,'start':om.start,'refresh':lambda:om.start(False),'browser':browser,'preservation':preservation,'production':production,'teardown':om.teardown,'fixtures':dm.fixtures,'dashboard-browser':dm.browser,'user-business':lambda:us.business(check_legacy=False),'user-browser':us.browser,'order-business':om.run_business,'order-edge':om.edge_checks,'order-browser':om.browser_checks}[sys.argv[1]]()
