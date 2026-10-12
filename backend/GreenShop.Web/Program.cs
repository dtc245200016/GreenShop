
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using GreenShop.Web.Data;
using System.Net;
using System.Net.Sockets;

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
        options.LoginPath = "/Admin/Account/Login";
        options.AccessDeniedPath = "/Admin/Account/AccessDenied";
        options.ExpireTimeSpan = TimeSpan.FromDays(7);
        options.EventsType = typeof(GreenShop.Web.Services.UserSession);
    })
    .AddCookie(GreenShop.Web.Services.PortalAuthentication.CustomerScheme, options =>
    {
        options.Cookie.Name = GreenShop.Web.Services.PortalAuthentication.CustomerCookie;
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
        ForwardedHeaders = ForwardedHeaders.XForwardedProto,
        ForwardLimit = 1
    };

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

app.Run();
