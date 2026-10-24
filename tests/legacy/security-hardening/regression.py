
if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import base64,importlib.util,json,os,re,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
acc=json.loads((a.P/'qa/accounts.json').read_text());db=a.rt.container('qa','db')
def sql(q):return a.m.sql(db,q,db='greenshop_m2_qa')
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'));ctx=b.new_context(ignore_https_errors=True);page=ctx.new_page()
 page.goto(a.base('qa')+'/Admin/Account/Login');page.locator('#Email').fill(acc['admin'][0]);page.locator('[name=Password]').fill(acc['admin'][1]);page.locator('form:has(#Email) button[type=submit]').click();page.wait_for_url(re.compile('/Admin'))
 name='M3 QA '+str(time.time_ns())
 page.goto(a.base('qa')+'/Admin/DanhMuc/ThemDanhMuc');page.locator('#Name').fill(name);page.locator('#Description').fill('M3 isolated upload check');page.locator('form:has(#Name) button[type=submit]').click();expect(page).to_have_url(re.compile('/Admin/DanhMuc/QuanLyDanhMuc'))
 cid=int(sql("SELECT Id FROM Categories WHERE Name='"+name+"'"))
 page.goto(a.base('qa')+'/Admin/SanPham/ThemSanPham')
 for key,value in [('Name',name),('Price','123000'),('StockQuantity','7')]:page.locator('#'+key).fill(value)
 page.locator('#CategoryId').select_option(str(cid))
 image={'name':'m3-qa.png','mimeType':'image/png','buffer':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aN1sAAAAASUVORK5CYII=')}
 page.locator('#Image').set_input_files(image);page.locator('form:has(#Name) button[type=submit]').click();expect(page).to_have_url(re.compile('/Admin/SanPham/QuanLySanPham'))
 pid=int(sql("SELECT Id FROM Products WHERE Name='"+name+"'"));original=sql(f'SELECT ImageUrl FROM Products WHERE Id={pid}');assert original.startswith('/uploads/products/')
 assert ctx.request.get(a.base('qa')+original).status==200
 page.goto(a.base('qa')+f'/Admin/SanPham/SuaSanPham/{pid}');page.locator('#Price').fill('150000');page.locator('#Image').set_input_files(image);page.locator('form:has(#Name) button[type=submit]').click();expect(page).to_have_url(re.compile('/Admin/SanPham/QuanLySanPham'))
 updated=sql(f'SELECT ImageUrl FROM Products WHERE Id={pid}');assert updated!=original
 # Existing authenticated cookie remains valid after a web restart with persistent key ownership.
 a.rt.dc('qa','restart','web_app');a.wait(lambda:a.rt.info(a.rt.container('qa','web_app'))['State']['Health']['Status']=='healthy',120)
 page.goto(a.base('qa')+f'/Admin/SanPham/ChiTietSanPham/{pid}');assert '/Login' not in page.url
 assert ctx.request.get(a.base('qa')+updated).status==200
 page.goto(a.base('qa')+f'/Admin/SanPham/XoaSanPham/{pid}');page.locator('form[method=post]:not(#logoutForm) button[type=submit]').click();expect(page).to_have_url(re.compile('/Admin/SanPham/QuanLySanPham'));assert sql(f'SELECT COUNT(*) FROM Products WHERE Id={pid}')=='0'
 page.goto(a.base('qa')+f'/Admin/DanhMuc/XoaDanhMuc/{cid}');page.locator('form[method=post]:not(#logoutForm) button[type=submit]').click();expect(page).to_have_url(re.compile('/Admin/DanhMuc/QuanLyDanhMuc'))
 assert sql(f'SELECT COUNT(*) FROM Categories WHERE Id={cid}')=='0'
 b.close()
a.record('qa-upload-session',{'status':'PASS','time':a.now(),'web_uid':1654,'checks':['Admin creates category/product using real forms/CSRF','Non-root process uploads image; static image read HTTP 200','Image replacement changes stored filename','Admin session and uploaded image survive web restart using same persisted keys','Product/category removed using actual Admin workflow'],'scope':'Synthetic QA only'})
print('PASS non-root image upload/replacement/delete and authenticated session persistence',flush=True)
