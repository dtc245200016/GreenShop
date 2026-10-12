
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using GreenShop.Web.Data;
using System.Net;
using System.Net.Sockets;
using Microsoft.AspNetCore.RateLimiting;
using System.Threading.RateLimiting;

if(await GreenShop.Web.Services.DeploymentCommands.TryRunAsync(args))return;

var builder = WebApplication.CreateBuilder(args);

// Cấu hình Database Context MySQL
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
if (string.IsNullOrWhiteSpace(connectionString))
{
    throw new InvalidOperationException(
        "Missing required configuration: ConnectionStrings:DefaultConnection.");
}

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseMySql(
        connectionString,
        new MySqlServerVersion(new Version(8, 0, 0)),
        mysqlOptions => mysqlOptions.EnableRetryOnFailure()));

// Bật Razor Runtime Compilation để tự nhận thay đổi file .cshtml
builder.Services.AddControllersWithViews().AddRazorRuntimeCompilation();

builder.Services.AddRateLimiter(options=>
{
    options.GlobalLimiter=PartitionedRateLimiter.Create<HttpContext,string>(context=>
        context.GetEndpoint()?.Metadata.GetMetadata<EnableRateLimitingAttribute>()==null
            ? RateLimitPartition.GetNoLimiter("pages")
            : RateLimitPartition.GetConcurrencyLimiter("accounts",_=>new ConcurrencyLimiterOptions{PermitLimit=8,QueueLimit=0}));
    options.AddPolicy("account",context=>
    {
        var registration=string.Equals(context.Request.RouteValues["action"]?.ToString(),"Register",StringComparison.OrdinalIgnoreCase);
        var key=registration?"Security:RegistrationAttemptsPerMinute":"Security:LoginAttemptsPerMinute";
        var limit=int.TryParse(builder.Configuration[key],out var configured)&&configured>=1&&configured<=2000?configured:registration?8:20;
        return RateLimitPartition.GetFixedWindowLimiter($"{(registration?"register":"login")}:{context.Connection.RemoteIpAddress}",
            _=>new FixedWindowRateLimiterOptions{PermitLimit=limit,Window=TimeSpan.FromMinutes(1),QueueLimit=0,AutoReplenishment=true});
    });
    options.OnRejected=async(context,ct)=>
    {
        var response=context.HttpContext.Response;response.StatusCode=StatusCodes.Status429TooManyRequests;
        response.Headers["Retry-After"]=context.Lease.TryGetMetadata(MetadataName.RetryAfter,out var retry)
            ? Math.Max(1,(int)Math.Ceiling(retry.TotalSeconds)).ToString(System.Globalization.CultureInfo.InvariantCulture):"5";
        response.Headers["Cache-Control"]="no-store";response.ContentType="text/plain; charset=utf-8";
        await response.WriteAsync("Bạn thao tác đăng nhập hoặc đăng ký quá nhanh. Vui lòng đợi một chút rồi thử lại.",ct);
    };
});

// Lưu key ring bền vững trong volume riêng khi chạy Production.
if (builder.Environment.IsProduction())
{
    var keysDirectory = new DirectoryInfo("/app/keys");
    keysDirectory.Create();
    if (OperatingSystem.IsLinux())
    {
        File.SetUnixFileMode(keysDirectory.FullName,
            UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
    }

    builder.Services.AddDataProtection()
        .SetApplicationName("GreenShop")
        .PersistKeysToFileSystem(keysDirectory);
}

builder.Services.AddScoped<GreenShop.Web.Services.UserSession>();
builder.Services.AddAuthentication(GreenShop.Web.Services.PortalAuthentication.PolicyScheme)
    .AddPolicyScheme(GreenShop.Web.Services.PortalAuthentication.PolicyScheme, null, options =>
    {
        options.ForwardDefaultSelector = context => GreenShop.Web.Services.PortalAuthentication.Scheme(context.Request);
    })
    .AddCookie(GreenShop.Web.Services.PortalAuthentication.AdminScheme, options =>
    {
        options.Cookie.Name = GreenShop.Web.Services.PortalAuthentication.AdminCookie;
        options.Cookie.SecurePolicy = builder.Environment.IsProduction()?CookieSecurePolicy.Always:CookieSecurePolicy.SameAsRequest;
        options.LoginPath = "/Admin/Account/Login";
        options.AccessDeniedPath = "/Admin/Account/AccessDenied";
        options.ExpireTimeSpan = TimeSpan.FromDays(7);
        options.EventsType = typeof(GreenShop.Web.Services.UserSession);
    })
    .AddCookie(GreenShop.Web.Services.PortalAuthentication.CustomerScheme, options =>
    {
        options.Cookie.Name = GreenShop.Web.Services.PortalAuthentication.CustomerCookie;
        options.Cookie.SecurePolicy = builder.Environment.IsProduction()?CookieSecurePolicy.Always:CookieSecurePolicy.SameAsRequest;
        options.LoginPath = "/Account/Login";
        options.AccessDeniedPath = "/Account/AccessDenied";
        options.ExpireTimeSpan = TimeSpan.FromDays(7);
        options.EventsType = typeof(GreenShop.Web.Services.UserSession);
    });

var app = builder.Build();

// Tra Docker DNS theo request để chỉ tin Nginx, kể cả khi proxy được recreate.
var loggerFactory = app.Services.GetRequiredService<ILoggerFactory>();
app.Use(async (context, next) =>
{
    if (!context.Request.Headers.ContainsKey("X-Forwarded-Proto"))
    {
        await next(context);
        return;
    }

    var options = new ForwardedHeadersOptions
    {
        ForwardedHeaders = ForwardedHeaders.XForwardedProto | ForwardedHeaders.XForwardedFor,
        ForwardLimit = 1
    };
    options.KnownNetworks.Clear();options.KnownProxies.Clear();

    try
    {
        var proxyAddresses = await Dns.GetHostAddressesAsync("nginx", context.RequestAborted);
        foreach (var address in proxyAddresses)
        {
            options.KnownProxies.Add(address);
        }
    }
    catch (SocketException)
    {
        app.Logger.LogWarning("Không thể phân giải Nginx; bỏ qua forwarded headers từ proxy chưa xác định.");
    }

    var forwardedHeaders = new ForwardedHeadersMiddleware(next, loggerFactory, Options.Create(options));
    await forwardedHeaders.Invoke(context);
});

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}

app.UseStatusCodePagesWithReExecute("/Home/ThongBaoHttp", "?statusCode={0}");
app.UseStaticFiles();
app.UseRouting();

app.Use(async (context, next) =>
{
    await GreenShop.Web.Services.PortalAuthentication.MigrateLegacyCustomerAsync(context);
    await next(context);
});
app.UseAuthentication();
app.Use(async (context, next) =>
{
    GreenShop.Web.Services.PortalAuthentication.RestoreMigratedCustomer(context);
    if (context.Items.ContainsKey(GreenShop.Web.Services.UserSession.UnavailableItem))
    {
        context.Response.StatusCode = StatusCodes.Status503ServiceUnavailable;
        context.Response.ContentType = "text/plain; charset=utf-8";
        await context.Response.WriteAsync("Chưa thể xác minh phiên đăng nhập. Vui lòng thử lại sau.");
        return;
    }
    await next(context);
});
app.UseAuthorization();
app.UseRateLimiter();

// Tự động áp dụng các EF Core Migrations chưa được thực thi
using (var scope = app.Services.CreateScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    dbContext.Database.Migrate();
}

app.MapControllerRoute(
    name: "areas",
    pattern: "{area:exists}/{controller=Admin}/{action=Index}/{id?}");

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

// Readiness checks real database access; reports no credentials, rows or exception details.
app.MapGet("/health/ready",async (AppDbContext db,HttpContext context)=>
{
    context.Response.Headers["Cache-Control"]="no-store";
    using var timeout=CancellationTokenSource.CreateLinkedTokenSource(context.RequestAborted);
    timeout.CancelAfter(TimeSpan.FromSeconds(2));
    try
    {
        await db.Database.ExecuteSqlRawAsync("SELECT 1",timeout.Token);
        return Results.Text("ready");
    }
    catch(Exception exception) when(exception is System.Data.Common.DbException or OperationCanceledException or TimeoutException or InvalidOperationException)
    {
        // Content type prevents status-page re-execution from rewriting 503 into 404.
        return Results.Text("unavailable",statusCode:StatusCodes.Status503ServiceUnavailable);
    }
});

app.Run();
