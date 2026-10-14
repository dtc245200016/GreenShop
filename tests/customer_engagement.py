"""Customer engagement regression. Requires order_management's disposable QA guard.

Uses synthetic sales fixtures, real purchase/workflow/review/chat HTTP endpoints,
and Chromium to verify transitions, polling, ownership, CSRF and escaped content.
Never invoke with production Compose/database; configure_qa verifies isolation.
"""
import base64,json,re,uuid,urllib.request,urllib.error,concurrent.futures
from pathlib import Path
import storefront_regression as gs
import order_management as om
import portal_sessions as ps

OUT=Path('/tmp/greenshop-engagement/qa')

def autoplay(page):
    """GET-only regression: hover, retained arrow focus and a complete automatic loop."""
    from playwright.sync_api import expect
    root=page.locator('[data-hero-slider]');slides=root.locator('[data-hero-slide]');count=slides.count()
    assert count>=2,'The autoplay test needs at least two products.'
    expect(root).to_have_attribute('data-hero-index','0');expect(root).to_have_attribute('data-hero-autoplay','running')
    slides.first.locator('.hero-featured').hover();expect(root).to_have_attribute('data-hero-autoplay','running')
    expect(root).to_have_attribute('data-hero-index','1',timeout=6000)
    next_button=root.locator('[data-hero-next]');next_button.click();expect(next_button).to_be_focused()
    index=2%count;expect(root).to_have_attribute('data-hero-index',str(index));expect(root).to_have_attribute('data-hero-autoplay','running')
    page.wait_for_timeout(4000);expect(root).to_have_attribute('data-hero-index',str(index))
    # Leave mouse/focus on the arrow. It must keep rotating through last -> first.
    for _ in range(count+1):
        previous=index;index=(index+1)%count
        expect(root).to_have_attribute('data-hero-index',str(index),timeout=6000)
        assert index!=previous
        active=root.locator('[data-hero-slide][aria-hidden=false]');assert active.count()==1
        assert active.get_attribute('data-product-id')==slides.nth(index).get_attribute('data-product-id')
        assert next_button.evaluate('(e)=>document.activeElement===e')
    root.locator('[data-hero-pause]').click();frozen=root.get_attribute('data-hero-index');page.wait_for_timeout(5300);expect(root).to_have_attribute('data-hero-index',frozen)
    root.locator('[data-hero-pause]').click();expect(root).to_have_attribute('data-hero-index',str((int(frozen)+1)%count),timeout=6000)
    page.emulate_media(reduced_motion='reduce');frozen=root.get_attribute('data-hero-index');page.wait_for_timeout(5300);expect(root).to_have_attribute('data-hero-index',frozen)
    print('PASS: Mouse hover and retained arrow focus no longer stop 5s autoplay; complete loop, manual reset, pause/resume and reduced motion verified.',flush=True)

def file_picker(page,selector,files):
    """The styled button must open the real chooser and retain native form binding."""
    from playwright.sync_api import expect
    native=page.locator(selector);picker=native.locator('..');button=picker.get_by_role('button',name='Chọn file',exact=True)
    original_name=native.get_attribute('name');assert original_name
    expect(button).to_be_visible();button.focus()
    with page.expect_file_chooser() as event:button.press('Enter')
    event.value.set_files(files)
    assert native.get_attribute('name')==original_name
    assert native.evaluate('(e)=>e.files.length')==len(files)
    expect(picker.locator('.file-picker-name')).to_contain_text(files[0]['name'])
    assert native.evaluate('(e)=>e.form!==null')
    print('PASS: Chọn file opens native chooser by keyboard, shows filenames and preserves form fields/files.',flush=True)

def multipart(client,path,source,values,photos):
    boundary='gs'+uuid.uuid4().hex;parts=[]
    for name,value in {**values,'__RequestVerificationToken':source.input('__RequestVerificationToken')}.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name,data in photos:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="Photos"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n'.encode()+data+b'\r\n')
    body=b''.join(parts)+f'--{boundary}--\r\n'.encode()
    request=urllib.request.Request(gs.BASE+path,data=body,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    try:response=client.open(request,timeout=30)
    except urllib.error.HTTPError as error:response=error
    return response.code,dict(response.headers),response.read().decode()

def run():
    om.configure_qa();accounts=json.loads((OUT/'accounts.json').read_text());checks=[]
    def passed(label):checks.append(label);print('PASS: '+label,flush=True)
    admin,buyer,other=gs.client(),gs.client(),gs.client();ps.sign_in(admin,accounts[0],True);ps.sign_in(buyer,accounts[2]);other_account=gs.register(other);gs.login(other,other_account)
    # Ranking: cancelled/pending and inactive products cannot displace recent delivered sales.
    cid=int(om.qa_sql("INSERT INTO Categories (Name,Description,IsActive) VALUES ('QA Slider "+uuid.uuid4().hex[:8]+"','',1); SELECT LAST_INSERT_ID()"))
    products=[]
    for index in range(7):
        products.append(int(om.qa_sql(f"INSERT INTO Products (Name,Price,ImageUrl,Description,StockQuantity,CategoryId) VALUES ('QA Slider {index}',100000,'/images/product-placeholder.svg','',50,{cid}); SELECT LAST_INSERT_ID()")))
    inactive=int(om.qa_sql("INSERT INTO Categories (Name,Description,IsActive) VALUES ('QA Hidden "+uuid.uuid4().hex[:8]+"','',0); SELECT LAST_INSERT_ID()"))
    om.qa_sql(f'UPDATE Products SET CategoryId={inactive} WHERE Id={products[6]}')
    base=int(om.qa_sql('SELECT COALESCE(MAX(s.Quantity),0) FROM (SELECT SUM(i.Quantity) Quantity FROM OrderItems i JOIN Orders o ON o.Id=i.OrderId JOIN Products p ON p.Id=i.ProductId LEFT JOIN Categories c ON c.Id=p.CategoryId WHERE o.Status=1 AND (p.CategoryId IS NULL OR c.IsActive=1) GROUP BY i.ProductId) s'))+10000
    for pid,quantity,status,days in [(products[i],base-i*100,1,2) for i in range(5)]+[(products[5],base*2,1,80),(products[5],base*20,2,1),(products[5],base*18,0,1),(products[6],base*22,1,1)]:
        oid=int(om.qa_sql(f"INSERT INTO Orders (UserId,ConfirmationToken,RecipientName,Phone,Address,CreatedAt,Total,Status,IsPaid,PaymentMethod,InventoryStatus,AdminNote,Version) VALUES (3,{gs.quote(uuid.uuid4().hex)},'QA Sales','0912345678','QA Synthetic sales address',DATE_SUB(UTC_TIMESTAMP(),INTERVAL {days} DAY),{quantity*100000},{status},0,'COD',1,'',0); SELECT LAST_INSERT_ID()"))
        om.qa_sql(f"INSERT INTO OrderItems (OrderId,ProductId,ProductName,ImageUrl,UnitPrice,Quantity) VALUES ({oid},{pid},'QA Sales Product','/images/product-placeholder.svg',100000,{quantity})")
    def configure_slider(mode,count,days,status=302,version=None):
        source=gs.get(admin,'/Admin/KhachHang/Slider')[0]
        values={'Mode':mode,'ProductCount':count,'Days':days,'Version':om.qa_sql('SELECT Version FROM HomeSliderSettings') if version is None else version}
        assert gs.post(admin,'/Admin/KhachHang/Slider',source,values)[0]==status
    def hero_ids():
        source=gs.get(buyer,'/')[0];return [int(a['data-product-id']) for tag,a in source.nodes if 'data-hero-slide' in a]
    configure_slider('bestsellers',5,30);assert hero_ids()==products[:5]
    configure_slider('bestsellers',2,0);assert hero_ids()==[products[5],products[0]]
    configure_slider('all',5,30);assert set(hero_ids())==set(map(int,om.qa_sql('SELECT Id FROM Products WHERE CategoryId IS NULL OR CategoryId IN (SELECT Id FROM Categories WHERE IsActive=1)').splitlines()))
    version=om.qa_sql('SELECT Version FROM HomeSliderSettings');configure_slider('bestsellers',5,30);configure_slider('all',5,30,409,version)
    for mode,count,days in [('invalid',5,30),('bestsellers',0,30),('bestsellers',101,30),('bestsellers',5,-1)]:configure_slider(mode,count,days,400)
    assert gs.request(admin,'/Admin/KhachHang/Slider',{'Mode':'all','ProductCount':5,'Days':30,'Version':version})[0]==400
    assert gs.request(buyer,'/Admin/KhachHang/Slider')[0]==302
    passed('Slider ranks only delivered saleable products in configurable time window; top X and all products work; validation, stale settings, Admin-only and CSRF guards')

    def purchase(client):
        oid=om.create_order(client,products[0],1);source=gs.get(client,f'/ThanhToan/ChiTietDonHang/{oid}')[0]
        item=int(om.qa_sql(f'SELECT Id FROM OrderItems WHERE OrderId={oid}'))
        assert gs.request(client,f'/TuongTac/DanhGia/{item}')[0]==404
        for state in (3,4,5,1):assert om.mutate(admin,oid,'CapNhatTrangThaiDonHang',{'TargetStatus':state})[0]==302
        return oid,item
    oid,item=purchase(buyer);_,other_item=purchase(other)
    assert gs.request(other,f'/TuongTac/DanhGia/{item}')[0]==404
    source=gs.get(buyer,f'/TuongTac/DanhGia/{item}')[0]
    assert gs.request(buyer,f'/TuongTac/DanhGia/{item}',{'Stars':5,'Content':'CSRF denied'})[0]==400
    assert gs.post(buyer,f'/TuongTac/DanhGia/{item}',source,{'Stars':0,'Content':'Bad stars'})[0]==400
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')
    for photos in [[('evil.svg',b'<svg onload="alert(1)"></svg>')],[('wrong.png',b'not a real PNG header')],[('valid.png',png)]*4,[('large.png',png+b'x'*(2*1024*1024))]]:
        assert multipart(buyer,f'/TuongTac/DanhGia/{item}',source,{'Stars':5,'Content':'Upload denied'},photos)[0]==400
    review_text='QA review <img src=x onerror="window.__reviewXss=1">'
    assert multipart(buyer,f'/TuongTac/DanhGia/{item}',source,{'Stars':5,'Content':review_text,'UserId':999,'ProductId':products[5]},[('experience.png',png)])[0]==302
    rid=int(om.qa_sql(f'SELECT Id FROM ProductReviews WHERE OrderItemId={item}'));image=om.qa_sql(f'SELECT Image1 FROM ProductReviews WHERE Id={rid}')
    assert re.fullmatch(r'/uploads/products/[a-f0-9]{32}\.png',image)
    assert om.qa_sql(f'SELECT UserId,ProductId,Stars FROM ProductReviews WHERE Id={rid}')==f'3\t{products[0]}\t5'
    assert gs.post(buyer,f'/TuongTac/DanhGia/{item}',source,{'Stars':1,'Content':'Repeat denied'})[0]==302
    assert om.qa_sql(f'SELECT COUNT(*) FROM ProductReviews WHERE OrderItemId={item}')=='1'
    other_source=gs.get(other,f'/TuongTac/DanhGia/{other_item}')[0]
    assert gs.post(other,f'/TuongTac/DanhGia/{other_item}',other_source,{'Stars':3,'Content':'QA second verified review'})[0]==302
    assert float(om.qa_sql(f'SELECT AVG(Stars) FROM ProductReviews WHERE ProductId={products[0]}'))==4
    _,body,_=gs.get(buyer,f'/SanPham/ChiTietSanPham/{products[0]}');assert re.search(r'4[.,]0/5 · 2 đánh giá',body)
    raw=gs.request(buyer,f'/SanPham/ChiTietSanPham/{products[0]}')[2];assert '<img src=x onerror=' not in raw
    alerts=json.loads(gs.request(admin,'/Admin/KhachHang/ThongBao')[2]);assert alerts['reviews']>=2
    source=gs.get(admin,'/Admin/KhachHang/DanhGia')[0];assert gs.post(admin,f'/Admin/KhachHang/DaDocDanhGia/{rid}',source,{})[0]==302
    assert om.qa_sql(f'SELECT AdminReadAt IS NOT NULL FROM ProductReviews WHERE Id={rid}')=='1'
    passed('Real COD purchase and delivered workflow -> owner-only review; 1-5 stars, text/image validation, safe images, duplicate prevention, real 4/5 average and unread review acknowledgements')

    chat=gs.get(buyer,'/TuongTac/TroChuyen')[0];message_token=uuid.uuid4().hex
    assert gs.request(buyer,'/TuongTac/GuiTinNhan',{'Content':'CSRF denied','RequestToken':message_token})[0]==400
    text='QA private message <script>window.__chatXss=1</script>'
    data={'Content':text,'RequestToken':message_token,'FromAdmin':'true','UserId':1}
    result=gs.post(buyer,'/TuongTac/GuiTinNhan',chat,data);assert result[0]==200;mid=json.loads(result[2])['id'];conv=int(om.qa_sql(f'SELECT ConversationId FROM ShopMessages WHERE Id={mid}'))
    retry=gs.post(buyer,'/TuongTac/GuiTinNhan',chat,data);assert retry[0]==200 and json.loads(retry[2])['id']==mid
    assert om.qa_sql(f'SELECT COUNT(*) FROM ShopMessages WHERE RequestToken={gs.quote(message_token)}')=='1'
    assert om.qa_sql(f'SELECT SenderId,FromAdmin FROM ShopMessages WHERE Id={mid}')=='3\t0'
    assert gs.post(buyer,'/TuongTac/GuiTinNhan',chat,{**data,'Content':'Changed replay'})[0]==409
    assert gs.post(buyer,'/TuongTac/GuiTinNhan',chat,{'Content':'x'*2001,'RequestToken':uuid.uuid4().hex})[0]==400
    assert gs.request(buyer,'/TuongTac/GuiTinNhan')[0]==405
    own=json.loads(gs.request(other,f'/TuongTac/TinNhanMoi/{conv}?UserId=3&role=Admin')[2]);assert own['messages']==[]
    assert gs.request(other,f'/Admin/KhachHang/TinNhanMoi/{conv}')[0]==302
    admin_chat=gs.get(admin,f'/Admin/KhachHang/TroChuyen/{conv}')[0]
    assert json.loads(gs.request(admin,f'/Admin/KhachHang/TinNhanMoi/{conv}')[2])['messages'][0]['content']==text
    before_read=om.qa_sql(f'SELECT AdminReadMessageId FROM ShopConversations WHERE Id={conv}')
    assert gs.post(admin,f'/Admin/KhachHang/DaDoc/{conv}',admin_chat,{'through':999999})[0]==400
    assert om.qa_sql(f'SELECT AdminReadMessageId FROM ShopConversations WHERE Id={conv}')==before_read
    assert gs.post(admin,f'/Admin/KhachHang/DaDoc/{conv}',admin_chat,{'through':mid})[0]==204
    assert gs.post(admin,f'/Admin/KhachHang/GuiTinNhan/{conv}',admin_chat,{'Content':'QA reply from real Admin','RequestToken':uuid.uuid4().hex})[0]==200
    assert len(json.loads(gs.request(buyer,f'/TuongTac/TinNhanMoi?after={mid-1}')[2])['messages'])==2
    passed('Persistent private chat, genuine Admin reply, anti-forgery and role/ownership guards, escaped content, idempotent send, invalid read cursor rejected')
    browser_review_order,browser_review_item=purchase(buyer)

    from playwright.sync_api import expect
    with ps.playwright() as pw:
        browser=pw.chromium.launch();ctx=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[];missing=[]
        page.on('pageerror',lambda e:errors.append(str(e)));page.on('response',lambda r:missing.append(r.url) if r.request.resource_type in ('script','stylesheet','font') and r.status>=400 else None)
        ps.login_page(page,accounts[2]);page.goto(om.QA_BASE+'/');page.mouse.move(0,0);page.wait_for_function('document.querySelector("[data-hero-slider]").dataset.heroAutoplay==="running"')
        start=page.locator('[data-hero-slider]').get_attribute('data-hero-index');page.wait_for_timeout(4300);assert page.locator('[data-hero-slider]').get_attribute('data-hero-index')==start
        page.wait_for_function('(old)=>document.querySelector("[data-hero-slider]").dataset.heroIndex!==old',arg=start,timeout=2000)
        page.get_by_role('button',name='Sản phẩm nổi bật tiếp theo',exact=True).click();expected_index=(int(start)+2)%5;expect(page.locator('[data-hero-slider]')).to_have_attribute('data-hero-index',str(expected_index))
        active=page.locator('[data-hero-slide][aria-hidden=false]');assert int(active.get_attribute('data-product-id'))==products[expected_index]
        assert int(active.locator('.hero-purchase form').get_attribute('action').rsplit('/',1)[1])==products[expected_index]
        page.get_by_role('button',name='Sản phẩm nổi bật trước',exact=True).click();expect(page.locator('[data-hero-slider]')).to_have_attribute('data-hero-index',str((expected_index-1)%5))
        box=page.locator('.hero-slider-viewport').bounding_box();x=box['x']+box['width']*.7;y=box['y']+box['width']*.45
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-130,y,steps=12);page.mouse.up();expect(page.locator('[data-hero-slider]')).to_have_attribute('data-hero-index',str(expected_index));assert page.url==om.QA_BASE+'/'
        page.locator('[data-hero-slider]').get_by_role('button',name='Tạm dừng tự trượt',exact=True).click();page.mouse.move(0,0);page.locator('h1').click();frozen=page.locator('[data-hero-slider]').get_attribute('data-hero-index');page.wait_for_timeout(5500);assert page.locator('[data-hero-slider]').get_attribute('data-hero-index')==frozen
        page.emulate_media(reduced_motion='reduce');page.reload();page.wait_for_timeout(5500);expect(page.locator('[data-hero-slider]')).to_have_attribute('data-hero-index','0');page.get_by_role('button',name='Sản phẩm nổi bật tiếp theo',exact=True).click();expect(page.locator('[data-hero-slider]')).to_have_attribute('data-hero-index','1')
        page.goto(om.QA_BASE+f'/SanPham/ChiTietSanPham/{products[0]}');assert page.evaluate('window.__reviewXss') is None;expect(page.locator('.review-content').filter(has_text='QA review')).to_contain_text('<img src=x')
        page.locator('.review-photos img').first.scroll_into_view_if_needed();page.wait_for_function('document.querySelector(".review-photos img").naturalWidth>0')
        page.goto(om.QA_BASE+f'/TuongTac/DanhGia/{browser_review_item}')
        assert page.locator('[id^="review-star-"]').evaluate_all('(els)=>new Set(els.map(e=>e.id)).size===els.length')
        page.get_by_role('radio',name='4 sao',exact=True).check();expect(page.get_by_role('radio',name='4 sao',exact=True)).to_be_checked()
        page.locator('#Content').fill('QA native star and photo form')
        page.locator('#Photos').set_input_files([{'name':f'experience-{n}.png','mimeType':'image/png','buffer':png} for n in range(3)])
        page.get_by_role('button',name='Gửi đánh giá',exact=True).click();expect(page).to_have_url(om.QA_BASE+f'/ThanhToan/ChiTietDonHang/{browser_review_order}');expect(page.locator('.review-complete')).to_be_visible()
        assert om.qa_sql(f'SELECT Stars,Image1 IS NOT NULL,Image2 IS NOT NULL,Image3 IS NOT NULL FROM ProductReviews WHERE OrderItemId={browser_review_item}')=='4\t1\t1\t1'
        page.goto(om.QA_BASE+'/TuongTac/TroChuyen');expect(page.locator(f'.chat-bubble[data-message-id="{mid}"]')).to_be_visible();assert page.evaluate('window.__chatXss') is None
        admin_ctx=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000});ap=admin_ctx.new_page();ps.login_page(ap,accounts[0],ps.ADMIN_LOGIN);ap.goto(om.QA_BASE+f'/Admin/KhachHang/TroChuyen/{conv}')
        expect(ap.locator(f'.chat-bubble[data-message-id="{mid}"]')).to_be_visible()
        customer_live=f'QA live browser customer {uuid.uuid4().hex[:8]}';shop_live=f'QA live browser shop {uuid.uuid4().hex[:8]}';second_live=f'QA second poll cycle {uuid.uuid4().hex[:8]}'
        page.locator('#chat-content').fill(customer_live);page.get_by_role('button',name='Gửi tin nhắn',exact=True).click();expect(ap.locator('.chat-bubble').filter(has_text=customer_live)).to_be_visible(timeout=14000)
        ap.locator('#chat-content').fill(shop_live);ap.get_by_role('button',name='Gửi tin nhắn',exact=True).click();expect(page.locator('.chat-bubble').filter(has_text=shop_live)).to_be_visible(timeout=14000)
        page.locator('#chat-content').fill(second_live);page.get_by_role('button',name='Gửi tin nhắn',exact=True).click();expect(ap.locator('.chat-bubble').filter(has_text=second_live)).to_be_visible(timeout=14000)
        expected_pending=om.qa_sql('SELECT COUNT(*) FROM Orders WHERE Status=0');expect(ap.locator('.admin-sidebar [data-alert-count=orders]')).to_have_text(expected_pending)
        live_order=om.create_order(buyer,products[1],1)
        expect(ap.locator('.admin-sidebar [data-alert-count=orders]')).to_have_text(str(int(expected_pending)+1),timeout=22000)
        assert om.mutate(admin,live_order,'XacNhanDonHang',{})[0]==302
        expect(ap.locator('.admin-sidebar [data-alert-count=orders]')).to_have_text(expected_pending,timeout=22000)
        for width in (320,390,768,1440):
            page.set_viewport_size({'width':width,'height':900});ap.set_viewport_size({'width':width,'height':900})
            for theme in ('light','dark'):
                page.evaluate('(t)=>localStorage.setItem("greenshop.theme",t)',theme)
                for path in ('/','/TuongTac/TroChuyen',f'/SanPham/ChiTietSanPham/{products[0]}'):
                    page.goto(om.QA_BASE+path,wait_until='networkidle');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,path)
                    assert page.locator('.shop-chat-launcher').evaluate('(e)=>getComputedStyle(e).position')=='fixed'
            for path in ('/Admin/KhachHang/Slider','/Admin/KhachHang/TinNhan','/Admin/KhachHang/DanhGia',f'/Admin/KhachHang/TroChuyen/{conv}'):
                ap.goto(om.QA_BASE+path,wait_until='networkidle');assert ap.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,path)
                assert ap.locator('.admin-topbar .btn').evaluate_all('(els)=>els.filter(e=>e.getClientRects().length).every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;})'),('Admin topbar controls',width,path)
                assert ap.locator('.admin-alerts>button').evaluate('(e)=>getComputedStyle(e).overflow')=='visible'
            page.screenshot(path=str(OUT/f'engagement-customer-{width}.png'),animations='disabled');ap.screenshot(path=str(OUT/f'engagement-admin-{width}.png'),animations='disabled')
        assert not errors and not missing,(errors,missing);ctx.close();admin_ctx.close();browser.close()
    passed('Actual 5-second slide timing, arrows/mouse drag/pause/reduced motion, current-product Buy Now; real two-way browser chat across multiple poll cycles; images/XSS/focus/assets and responsive Customer/Admin pages')
    _,concurrent_item=purchase(buyer);review_page=gs.get(buyer,f'/TuongTac/DanhGia/{concurrent_item}')[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda stars:gs.post(buyer,f'/TuongTac/DanhGia/{concurrent_item}',review_page,{'Stars':stars,'Content':'QA simultaneous review'}),[4,2]))
    assert all(r[0]==302 for r in results) and om.qa_sql(f'SELECT COUNT(*) FROM ProductReviews WHERE OrderItemId={concurrent_item}')=='1'
    other_chat=gs.get(other,'/TuongTac/TroChuyen')[0]
    for index in range(20):assert gs.post(other,'/TuongTac/GuiTinNhan',other_chat,{'Content':f'QA rate check {index}','RequestToken':uuid.uuid4().hex})[0]==200
    assert gs.post(other,'/TuongTac/GuiTinNhan',other_chat,{'Content':'QA exceeds rate','RequestToken':uuid.uuid4().hex})[0]==429
    other_mid=int(om.qa_sql(f'SELECT MAX(Id) FROM ShopMessages WHERE ConversationId<>{conv}'))
    assert gs.post(admin,f'/Admin/KhachHang/DaDoc/{conv}',admin_chat,{'through':other_mid})[0]==400
    passed('Red order badge increases on real QA checkout and decreases on confirmation; concurrent review creates one row; message spam limited server-side and cross-conversation read cursors denied')
    (OUT/'engagement-results.json').write_text(json.dumps({'status':'PASS','checks':checks,'database':'isolated QA only'},indent=2))
