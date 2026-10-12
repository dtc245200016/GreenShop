"""M1: cold-start/privileges/readiness/proxy acceptance; all business writes use QA only.

Run modes sequentially: prepare, cold, regression, resilience, main, evidence, teardown.
Private credentials/backups stay in /tmp/greenshop-m1; public evidence is sanitized.
"""
import sys,os,json,subprocess,secrets,time,hashlib,urllib.request,urllib.error,ssl
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import storefront_regression as gs
import order_management as om
import portal_sessions as ps

ROOT=gs.ROOT
PRIVATE=Path('/tmp/greenshop-m1')
OUT=PRIVATE/'qa';OUT.mkdir(mode=0o700,parents=True,exist_ok=True)
EVIDENCE=ROOT/'docs/evidence/commit1'
MAIN_COMPOSE=gs.compose;MAIN_SQL=gs.sql
PROJECT='greenshop-m1-qa'
om.OUT=ps.OUT=OUT;om.QA_PROJECT=PROJECT

def run(command,**kwargs):
    return subprocess.run(command,cwd=ROOT,text=True,capture_output=True,**kwargs)

def record(name,value):
    p=PRIVATE/(name+'.json');p.write_text(json.dumps(value,indent=2));os.chmod(p,0o600)

def prepare():
    assert not om.qa_compose('ps','-q','db') if (OUT/'compose.yaml').exists() else True
    result=run(['docker','compose','config','--format','json']);assert result.returncode==0
    configuration=json.loads(result.stdout);services=configuration['services']
    root_password=secrets.token_hex(32);app_password=secrets.token_hex(32)
    for name in ('keys','images','ssl'):(OUT/name).mkdir(mode=0o700,exist_ok=True)
    assert run(['bash','scripts/generate-dev-cert.sh','localhost','--output-dir',str(OUT/'ssl')]).returncode==0
    services['db']['environment']={'MYSQL_ROOT_PASSWORD':root_password,'MYSQL_DATABASE':'greenshop_order_qa','MYSQL_USER':'greenshop_app','MYSQL_PASSWORD':app_password}
    services['db']['ports']=[];services['db']['volumes']=[];services['db']['tmpfs']=['/var/lib/mysql']
    services['web_app']['environment']={'ASPNETCORE_ENVIRONMENT':'Production','ASPNETCORE_URLS':'http://+:8080','ConnectionStrings__DefaultConnection':f'Server=db;Database=greenshop_order_qa;Uid=greenshop_app;Pwd={app_password};','Security__LoginAttemptsPerMinute':'200','Security__RegistrationAttemptsPerMinute':'200'}
    services['web_app']['image']='dtc245200016_btl_tkqt_htpm-web_app:latest';services['web_app'].pop('build',None);services['web_app']['ports']=[]
    services['web_app']['volumes']=[{'type':'bind','source':str(OUT/'keys'),'target':'/app/keys'},{'type':'bind','source':str(OUT/'images'),'target':'/app/wwwroot/uploads/products'}]
    conf=(ROOT/'nginx/default.conf').read_text().replace('return 301 https://$host$request_uri;','return 301 https://$host:18543$request_uri;').replace('proxy_set_header Host $host;','proxy_set_header Host $http_host;')
    (OUT/'nginx.conf').write_text(conf)
    services['nginx']['ports']=[{'target':443,'published':'18543','host_ip':'127.0.0.1','protocol':'tcp'},{'target':80,'published':'18581','host_ip':'127.0.0.1','protocol':'tcp'}]
    services['nginx']['volumes']=[{'type':'bind','source':str(OUT/'nginx.conf'),'target':'/etc/nginx/conf.d/default.conf','read_only':True},{'type':'bind','source':str(OUT/'ssl'),'target':'/etc/nginx/ssl','read_only':True}]
    services['phpmyadmin']['ports']=[{'target':80,'published':'18580','host_ip':'127.0.0.1','protocol':'tcp'}]
    services['phpmyadmin']['environment']={'PMA_HOST':'db','PMA_PORT':'3306','PMA_VERBOSE':'GreenShop M1 - disposable QA'}
    for service in services.values():service.pop('container_name',None)
    # An isolated, explicit subnet makes a real IP-change proxy test reproducible.
    used=run(['docker','network','inspect',*run(['docker','network','ls','-q']).stdout.split()]);assert used.returncode==0
    assert all(c.get('Subnet')!='172.30.250.0/24' for n in json.loads(used.stdout) for c in (n.get('IPAM',{}).get('Config') or []))
    configuration={'services':services,'networks':{'app_net':{'driver':'bridge','ipam':{'config':[{'subnet':'172.30.250.0/24'}]}}}}
    p=OUT/'compose.yaml';p.write_text(json.dumps(configuration,indent=2));os.chmod(p,0o600)
    (OUT/'qa.env').write_text('QA_DB_PASSWORD='+root_password+'\n');os.chmod(OUT/'qa.env',0o600)
    (OUT/'credentials.json').write_text(json.dumps({'root':root_password,'app':app_password}));os.chmod(OUT/'credentials.json',0o600)
    print('PASS: Four-service disposable QA prepared; no production volumes/keys/certificates shared.',flush=True)

def certificates():
    checks=[]
    for host,label in (('192.0.2.8','ip'),('greenshop.example.invalid','dns'),('::1','ipv6')):
        directory=PRIVATE/('cert-'+label);directory.mkdir(exist_ok=True)
        result=run(['bash','scripts/generate-dev-cert.sh',host,'--output-dir',str(directory)]);assert result.returncode==0,result.stderr
        before={f:hashlib.sha256((directory/f).read_bytes()).hexdigest() for f in ('key.pem','cert.pem')}
        certificate=run(['openssl','x509','-in',str(directory/'cert.pem'),'-noout','-ext','subjectAltName']);assert certificate.returncode==0
        kind='-checkhost' if label=='dns' else '-checkip';assert run(['openssl','x509','-in',str(directory/'cert.pem'),'-noout',kind,host]).returncode==0
        certpub=run(['openssl','x509','-in',str(directory/'cert.pem'),'-pubkey','-noout']).stdout
        keypub=run(['openssl','pkey','-in',str(directory/'key.pem'),'-pubout']).stdout;assert certpub==keypub
        assert (directory/'key.pem').stat().st_mode&0o777==0o600
        assert run(['bash','scripts/generate-dev-cert.sh',host,'--output-dir',str(directory)]).returncode!=0
        assert before=={f:hashlib.sha256((directory/f).read_bytes()).hexdigest() for f in before}
        assert run(['bash','scripts/generate-dev-cert.sh','bad/name','--force','--output-dir',str(directory)]).returncode!=0
        assert before=={f:hashlib.sha256((directory/f).read_bytes()).hexdigest() for f in before}
        assert run(['bash','scripts/generate-dev-cert.sh',host,'--force','--output-dir',str(directory)]).returncode==0
        checks.append(label+': SAN/type, matching key, 600, no implicit overwrite, rejected invalid host, explicit force')
    record('cert-script',{'status':'PASS','checks':checks});print('PASS: Certificate script IP/DNS/IPv6, SAN/key match, permissions, overwrite guard and explicit rotation.',flush=True)

def cold():
    om.qa_compose('config','--quiet');om.qa_compose('up','-d','--wait','--wait-timeout','150')
    om.configure_qa();assert om.qa_sql('SELECT COUNT(*) FROM __EFMigrationsHistory')=='6'
    assert om.qa_sql('SELECT COUNT(*) FROM Users')=='0' and om.qa_sql('SELECT COUNT(*) FROM Products')=='0'
    assert om.qa_sql('SELECT FlatShippingFee,FreeShippingThreshold,VietQrEnabled FROM PaymentShippingSettings')=='30000.00\t300000.00\t0'
    assert gs.request(gs.client(),'/health/ready')[0]==200
    # Exercise the exact operator shell wrapper with QA Compose overrides.
    env=os.environ.copy();env.update({'COMPOSE_FILE':str(OUT/'compose.yaml'),'COMPOSE_PROJECT_NAME':PROJECT,'COMPOSE_ENV_FILES':str(OUT/'qa.env')})
    result=run(['bash','scripts/bootstrap-db-user.sh'],env=env);assert result.returncode==0,result.stderr
    credentials=json.loads((OUT/'credentials.json').read_text())
    def app_sql(query):
        return om.qa_compose('exec','-T','db','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysql --protocol=TCP -h db -ugreenshop_app -N -B --database="$MYSQL_DATABASE"',input=query)
    assert app_sql('SELECT DATABASE(),CURRENT_USER()')=='greenshop_order_qa\tgreenshop_app@%'
    for query in ('SELECT User FROM mysql.user','CREATE DATABASE greenshop_forbidden','CREATE USER \'qa_forbidden\'@\'%\''):
        try:app_sql(query);raise AssertionError('Unexpected global privilege')
        except subprocess.CalledProcessError:pass
    # Fresh Admin: no default credentials; a repeat must refuse without data changes.
    accounts=[[f'qa-order-{i}@example.invalid',secrets.token_urlsafe(28)] for i in (1,2,3)]
    payload=json.dumps({'FullName':'QA Order User 1','Email':accounts[0][0],'Password':accounts[0][1]})
    assert om.qa_compose('exec','-T','web_app','dotnet','GreenShop.Web.dll','--create-initial-admin',input=payload)
    before=ps.table_hashes(om.qa_sql)
    try:om.qa_compose('exec','-T','web_app','dotnet','GreenShop.Web.dll','--create-initial-admin',input=payload);raise AssertionError('Initial Admin repeated')
    except subprocess.CalledProcessError:pass
    assert ps.table_hashes(om.qa_sql)==before
    import bcrypt
    for i in (2,3):
        digest=bcrypt.hashpw(accounts[i-1][1].encode(),bcrypt.gensalt()).decode()
        om.qa_sql(f"INSERT INTO Users (Id,FullName,Email,PasswordHash,Phone,Role,CreatedAt,IsActive,Version,SessionVersion) VALUES ({i},'QA Order User {i}',{gs.quote(accounts[i-1][0])},{gs.quote(digest)},'0912345678',{1 if i==2 else 0},UTC_TIMESTAMP(),1,0,0)")
    (OUT/'accounts.json').write_text(json.dumps(accounts));os.chmod(OUT/'accounts.json',0o600)
    om.qa_sql("INSERT INTO Products (Id,Name,Price,ImageUrl,Description,StockQuantity) VALUES (1,'QA Legacy Plant',100000,'/images/product-placeholder.svg','QA snapshot',18); INSERT INTO Orders (Id,UserId,ConfirmationToken,RecipientName,Phone,Address,CreatedAt,Total,Status,IsPaid,PaymentMethod,InventoryStatus,AdminNote,Version) VALUES (1,3,'00000000000000000000000000000001','QA Recipient','0912345678','QA Address','2026-01-01',200000,0,0,'COD',0,'',0); INSERT INTO OrderItems (OrderId,ProductId,ProductName,ImageUrl,UnitPrice,Quantity) VALUES (1,1,'QA Historical Plant','/images/product-placeholder.svg',100000,2)")
    # Prove readiness fails for unavailable DB while Kestrel remains listening.
    om.qa_compose('pause','db')
    try:
        assert gs.request(gs.client(),'/health/ready')[0]==503
        result=run(['docker','compose','--project-name',PROJECT,'--file',str(OUT/'compose.yaml'),'--env-file',str(OUT/'qa.env'),'exec','-T','web_app','dotnet','GreenShop.Web.dll','--healthcheck']);assert result.returncode!=0
    finally:om.qa_compose('unpause','db')
    for _ in range(20):
        if gs.request(gs.client(),'/health/ready')[0]==200:break
        time.sleep(1)
    else:raise AssertionError('Readiness did not recover')
    record('cold-start',{'status':'PASS','checks':['Four services start from empty tmpfs MySQL','Six migrations and default shipping initialized by schema-scoped app user','Bootstrap wrapper idempotent; app cannot read mysql.user/create users/other databases','First Admin created only on empty Users; repeat changes no data','Readiness 503/nonzero when QA DB paused, recovers automatically'],'writes':'synthetic QA only'})
    print('PASS: Cold start, schema-scoped DB privileges, safe first Admin, real DB readiness failure/recovery.',flush=True)

def regression():
    import payment_shipping as payment
    import customer_ui as customer
    import dashboard_management as dashboard
    import user_management as users
    for module in (om,ps,payment,customer,dashboard,users):module.OUT=OUT
    om.QA_PROJECT=PROJECT;payment.MAIN_COMPOSE=MAIN_COMPOSE
    gs.REPORTS=OUT/'storefront';gs.REPORTS.mkdir(exist_ok=True)
    callbacks={'business':payment.business_regression,'security':ps.security,'payment':ps.payment_smoke,'admin':om.browser_checks,'customer':customer.browser}
    callbacks[sys.argv[2]]()
    record('regression-'+sys.argv[2],{'status':'PASS','writes':'synthetic QA only','suite':sys.argv[2]})

def resilience():
    om.configure_qa();accounts=json.loads((OUT/'accounts.json').read_text());client=gs.client()
    ps.sign_in(client,accounts[0],True);ps.sign_in(client,accounts[2]);before=ps.table_hashes(om.qa_sql)
    inspect=lambda service:json.loads(subprocess.check_output(['docker','inspect',om.qa_compose('ps','-q',service)],text=True))[0]
    web=inspect('web_app');proxy=inspect('nginx');old_ip=next(iter(web['NetworkSettings']['Networks'].values()))['IPAddress']
    p=OUT/'compose.yaml';configuration=json.loads(p.read_text());configuration['services']['web_app']['networks']={'app_net':{'ipv4_address':'172.30.250.200'}};p.write_text(json.dumps(configuration,indent=2))
    om.qa_compose('up','-d','--no-deps','--no-build','--pull','never','--force-recreate','--wait','--wait-timeout','90','web_app')
    current=inspect('web_app');new_ip=next(iter(current['NetworkSettings']['Networks'].values()))['IPAddress'];assert old_ip!=new_ip
    for _ in range(20):
        try:
            if gs.request(gs.client(),'/')[0]==200:break
        except (urllib.error.URLError,OSError):pass
        time.sleep(1)
    else:raise AssertionError('Nginx retained stale upstream')
    now=inspect('nginx');assert now['Id']==proxy['Id'] and now['State']['StartedAt']==proxy['State']['StartedAt']
    assert ps.table_hashes(om.qa_sql)==before
    assert 'QA Order User 1' in gs.get(client,'/Admin/DonHang/QuanLyDonHang')[1]
    assert 'QA Order User 3' in gs.get(client,'/ThanhToan/DonHangCuaToi')[1]
    assert om.qa_compose('exec','-T','nginx','nginx','-t')==''
    record('qa-resilience',{'status':'PASS','old_ip':old_ip,'new_ip':new_ip,'checks':'Real web IP change; Nginx not restarted/reloaded; HTTPS recovers; all QA tables unchanged; simultaneous genuine Admin/Customer cookies still work'})
    print('PASS: Real QA web IP change recovers via unchanged Nginx; both cookies and all tables persist.',flush=True)

def browser_evidence():
    om.configure_qa();EVIDENCE.mkdir(parents=True,exist_ok=True);accounts=json.loads((OUT/'accounts.json').read_text());credentials=json.loads((OUT/'credentials.json').read_text())
    with ps.playwright() as pw:
        from playwright.sync_api import expect
        b=pw.chromium.launch();ctx=b.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000});p=ctx.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
        ps.login_page(p,accounts[0],ps.ADMIN_LOGIN);p.goto(om.QA_BASE+'/Admin/Admin/TongQuan');p.screenshot(path=str(EVIDENCE/'admin-dashboard-qa.png'),full_page=True,animations='disabled')
        for path in ('/Admin/SanPham/QuanLySanPham','/Admin/DanhMuc/QuanLyDanhMuc','/Admin/DonHang/QuanLyDonHang','/Admin/NguoiDung/QuanLyNguoiDung','/Admin/CaiDatCuaHang/QuanLyThanhToanVanChuyen'):
            assert p.goto(om.QA_BASE+path).status==200,path
        p.goto('http://127.0.0.1:18580/');expect(p.locator('#input_username')).to_be_visible();p.locator('#input_username').fill('greenshop_app');p.locator('#input_password').fill(credentials['app']);p.locator('#input_go').click()
        expect(p.locator('body')).to_contain_text('greenshop_order_qa');p.goto('http://127.0.0.1:18580/index.php?route=/database/structure&db=greenshop_order_qa')
        expect(p.locator('body')).to_contain_text('OrderItems');expect(p.locator('body')).to_contain_text('__EFMigrationsHistory')
        assert p.locator('input[type=password]').count()==0
        p.screenshot(path=str(EVIDENCE/'phpmyadmin-qa.png'),full_page=True)
        ctx.close();ctx=b.new_context(ignore_https_errors=True,viewport={'width':1280,'height':900});p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
        ps.login_page(p,accounts[2]);p.goto(om.QA_BASE+'/ThanhToan/XacNhanMuaHang/1');p.locator('#Address').fill('QA fixture - no real customer address')
        p.screenshot(path=str(EVIDENCE/'checkout-qa.png'),full_page=True,animations='disabled')
        assert not errors,errors;ctx.close();b.close()
    record('browser-evidence',{'status':'PASS','checks':'Actual QA Admin pages, authenticated phpMyAdmin schema and Customer checkout; synthetic accounts/records only; no credentials/tokens/cookies in screenshots'})
    print('PASS: Real QA Admin/phpMyAdmin/checkout screenshots and authenticated database access; no real customer credentials/data.',flush=True)

def preservation():
    before=json.loads((PRIVATE/'baseline.json').read_text());assert ps.table_hashes(MAIN_SQL)==before['tables']
    after=om.real_snapshot()
    for key in ('products','categories','users','images','keys','Orders','OrderItems','CartItems','migrations'):assert before['real'][key]==after[key],key
    for file,digest in before['certs'].items():assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest,file
    for service,mounts in before['volumes'].items():
        current=json.loads(run(['docker','inspect','--format','{{json .Mounts}}',MAIN_COMPOSE('ps','-q',service)]).stdout)
        identity=lambda rows:sorted((r['Type'],r.get('Name',''),r['Source'],r['Destination']) for r in rows)
        assert identity(current)==identity(mounts),service
    local=json.loads((PRIVATE/'local-changes-before.json').read_text())
    for file,digest in local.items():
        if file not in ('docker-compose.yml','backend/GreenShop.Web/Program.cs'):assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest,file
    record('preservation',{'status':'PASS','checks':'All 8 business tables/credentials/roles/session versions/orders/payment/stock unchanged; same 3 named volumes, uploaded images, key hashes, existing cert/private key and 6 migrations; earlier unrelated local changes preserved'})
    print('PASS: Main business data, uploads, key ring, cert/key, volumes, schema and earlier local changes preserved.',flush=True)

def main():
    assert run(['docker','compose','config','--quiet']).returncode==0
    result=run(['docker','compose','exec','-T','nginx','nginx','-t']);assert result.returncode==0
    route=run(['ip','-j','-4','route','get','1.1.1.1']);assert route.returncode==0
    address=json.loads(route.stdout)[0]['prefsrc']
    # Existing cert must validate without curl -k at its actual VM IP.
    certificate=ROOT/'nginx/ssl/cert.pem';key=ROOT/'nginx/ssl/key.pem'
    assert run(['openssl','x509','-in',str(certificate),'-noout','-checkip',address]).returncode==0
    assert run(['openssl','x509','-in',str(certificate),'-noout','-checkend','0']).returncode==0
    assert run(['openssl','x509','-in',str(certificate),'-pubkey','-noout']).stdout==run(['openssl','pkey','-in',str(key),'-pubout']).stdout
    assert run(['curl','--noproxy','*','--silent','--cacert',str(certificate),'--output','/dev/null','--write-out','%{http_code}','https://'+address+'/']).stdout=='200'
    for path in ('/','/SanPham/CuaHang','/Account/Login',ps.ADMIN_LOGIN,'/health/ready','/css/storefront-theme.css','/js/storefront-theme.js','/lib/fontawesome/css/all.min.css'):
        code,h,body=gs.request(gs.client(),path);assert code==200,path
        if path=='/':
            assert h['X-Content-Type-Options']=='nosniff' and h['X-Frame-Options']=='SAMEORIGIN' and h['Referrer-Policy']=='strict-origin-when-cross-origin'
            assert h['Server']=='nginx'
    opener=gs.client()
    try:opener.open('http://'+address+'/SanPham/CuaHang?search=qa');raise AssertionError('Missing HTTP redirect')
    except urllib.error.HTTPError as e:assert e.code==301 and e.headers['Location']=='https://'+address+'/SanPham/CuaHang?search=qa'
    for path,login in (('/Admin/DonHang/QuanLyDonHang',ps.ADMIN_LOGIN),('/ThanhToan/DonHangCuaToi','/Account/Login')):
        code,h,_=gs.request(gs.client(),path);assert code==302 and login in h['Location']
    assert MAIN_SQL('SELECT COUNT(*) FROM __EFMigrationsHistory')=='6'
    assert MAIN_COMPOSE('exec','-T','web_app','dotnet','GreenShop.Web.dll','--healthcheck')==''
    for service in ('db','web_app','nginx','phpmyadmin'):
        cid=MAIN_COMPOSE('ps','-q',service);assert run(['docker','inspect','--format','{{.State.Health.Status}}',cid]).stdout.strip()=='healthy'
    for service,port in (('db','3306/tcp'),('web_app','8080/tcp'),('phpmyadmin','80/tcp')):
        cid=MAIN_COMPOSE('ps','-q',service);bindings=json.loads(run(['docker','inspect','--format','{{json .NetworkSettings.Ports}}',cid]).stdout)[port]
        assert bindings and all(b['HostIp']=='127.0.0.1' for b in bindings)
    assert MAIN_COMPOSE('exec','-T','db','sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" mysql --protocol=TCP -h db -ugreenshop_app -N -B --database=greenshop -e "SELECT CURRENT_USER(),COUNT(*) FROM __EFMigrationsHistory"')=='greenshop_app@%\t6'
    # Verify the actual phpMyAdmin container reaches Main MySQL with the app account.
    resolved=json.loads(run(['docker','compose','config','--format','json']).stdout)
    password=resolved['services']['db']['environment']['MYSQL_PASSWORD']
    php='$v=json_decode(stream_get_contents(STDIN),true); $db=new mysqli("db","greenshop_app",$v["password"],"greenshop"); $r=$db->query("SELECT COUNT(*) AS n FROM __EFMigrationsHistory"); echo $r->fetch_assoc()["n"];'
    result=run(['docker','compose','exec','-T','phpmyadmin','php','-r',php],input=json.dumps({'password':password}))
    assert result.returncode==0 and result.stdout.strip()=='6'
    current=run(['docker','inspect','--format','{{.Image}}',MAIN_COMPOSE('ps','-q','web_app')]).stdout.strip()
    assert current==run(['docker','inspect','--format','{{.Image}}',om.qa_compose('ps','-q','web_app')]).stdout.strip()
    preservation();record('main-runtime',{'status':'PASS','image':current,'vm_ip':address,'checks':'Four real services healthy; trusted HTTPS/SAN/key match; live security headers/no version; HTTP preserves path/query; readiness+app-user SQL+phpMyAdmin SQL; protected auth challenges; loopback data ports; tested image deployed; data preserved'})
    print('PASS: Main runtime/TLS/security headers/DB/phpMyAdmin/health/ports match the QA-tested image.',flush=True)

def main_resilience():
    proxy=MAIN_COMPOSE('ps','-q','nginx');before=run(['docker','inspect','--format','{{.State.StartedAt}}',proxy]).stdout
    MAIN_COMPOSE('up','-d','--no-deps','--no-build','--pull','never','--force-recreate','--wait','--wait-timeout','90','web_app')
    for _ in range(20):
        try:
            if gs.request(gs.client(),'/')[0]==200:break
        except (urllib.error.URLError,OSError):pass
        time.sleep(1)
    else:raise AssertionError('Main proxy failed recovery')
    assert proxy==MAIN_COMPOSE('ps','-q','nginx') and before==run(['docker','inspect','--format','{{.State.StartedAt}}',proxy]).stdout
    preservation();record('main-resilience',{'status':'PASS','checks':'Only Main web recreated; Nginx not restarted/reloaded; HTTPS 200; same DB/volumes/keys/images/business data'})
    print('PASS: Main web recreate recovers without Nginx restart and preserves every business table/key/image.',flush=True)

if __name__=='__main__':
    {'prepare':prepare,'certificates':certificates,'cold':cold,'regression':regression,'resilience':resilience,'browser-evidence':browser_evidence,'preservation':preservation,'main':main,'main-resilience':main_resilience,'teardown':om.teardown}[sys.argv[1]]()
