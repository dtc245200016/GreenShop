using System.Security.Claims;
using GreenShop.Web.Data;
using GreenShop.Web.Models;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using BCryptNet = BCrypt.Net.BCrypt;

namespace GreenShop.Web.Controllers
{
    public class AccountController : Controller
    {
        private readonly AppDbContext _context;

        public AccountController(AppDbContext context)
        {
            _context = context;
        }

        #region 1. ĐĂNG KÝ (REGISTER)

        [HttpGet]
        public IActionResult Register()
        {
            if (User.Identity != null && User.Identity.IsAuthenticated)
            {
                return RedirectToUserRolePage();
            }
            return View();
        }

        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Register(RegisterViewModel model)
        {
            if (!ModelState.IsValid) return View(model);

            if (await _context.Users.AnyAsync(u => u.Email.ToLower() == model.Email.ToLower()))
            {
                ModelState.AddModelError("Email", "Email này đã được đăng ký sử dụng.");
                return View(model);
            }

            string hashedPassword = BCryptNet.HashPassword(model.Password);

            var newUser = new User
            {
                FullName = model.FullName,
                Email = model.Email.ToLower().Trim(),
                Phone = model.Phone ?? string.Empty,
                PasswordHash = hashedPassword,
                Role = UserRole.Customer,
                CreatedAt = DateTime.UtcNow
            };

            _context.Users.Add(newUser);
            await _context.SaveChangesAsync();

            TempData["RegisteredEmail"] = newUser.Email;
            TempData["SuccessMessage"] = "Đăng ký tài khoản thành công! Vui lòng đăng nhập.";
            return RedirectToAction("Login");
        }

        #endregion

        #region 2. ĐĂNG NHẬP (LOGIN)

        [HttpGet]
        public IActionResult Login(string? returnUrl = null)
        {
            if (User.Identity != null && User.Identity.IsAuthenticated)
            {
                return RedirectToUserRolePage();
            }

            ViewData["ReturnUrl"] = returnUrl;
            var registeredEmail = TempData["RegisteredEmail"] as string;
            ViewBag.RegisteredEmail = registeredEmail;
            return View(new LoginViewModel
            {
                Email = registeredEmail ?? string.Empty
            });
        }

        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Login(LoginViewModel model, string? returnUrl = null)
        {
            ViewData["ReturnUrl"] = returnUrl;

            if (!ModelState.IsValid) return View(model);

            var user = await _context.Users.FirstOrDefaultAsync(u => u.Email.ToLower() == model.Email.ToLower());

            if (user == null || !BCryptNet.Verify(model.Password, user.PasswordHash))
            {
                ModelState.AddModelError(string.Empty, "Email hoặc mật khẩu không chính xác.");
                return View(model);
            }

            string? assignedRole = user.Role switch
            {
                UserRole.Customer => "Customer",
                UserRole.Admin => "Admin",
                _ => null
            };

            if (assignedRole == null)
            {
                ModelState.AddModelError(string.Empty, "Tài khoản chưa được cấu hình quyền hợp lệ.");
                return View(model);
            }

            bool isAdmin = user.Role == UserRole.Admin;

            // Sử dụng định danh chuẩn của .NET để hệ thống tự nhận diện Role
            var claims = new List<Claim>
            {
                new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                new Claim(ClaimTypes.Name, user.FullName),
                new Claim(ClaimTypes.Email, user.Email),
                new Claim(ClaimTypes.Role, assignedRole)
            };

            var claimsIdentity = new ClaimsIdentity(
                claims,
                CookieAuthenticationDefaults.AuthenticationScheme,
                ClaimTypes.Name,
                ClaimTypes.Role);
            var authProperties = new AuthenticationProperties
            {
                IsPersistent = model.RememberMe,
                ExpiresUtc = DateTimeOffset.UtcNow.AddDays(7)
            };

            await HttpContext.SignInAsync(
                CookieAuthenticationDefaults.AuthenticationScheme,
                new ClaimsPrincipal(claimsIdentity),
                authProperties);

            if (isAdmin)
            {
                return RedirectToAction("Index", "Admin", new { area = "Admin" });
            }

            if (!string.IsNullOrEmpty(returnUrl) && Url.IsLocalUrl(returnUrl))
            {
                return Redirect(returnUrl);
            }

            return RedirectToAction("Index", "Home");
        }

        #endregion

        #region 3. ĐĂNG XUẤT & ACCESS DENIED

        [HttpPost]
        [ValidateAntiForgeryToken]
        [Authorize]
        public async Task<IActionResult> Logout()
        {
            await HttpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
            return RedirectToAction("Login", "Account");
        }

        [HttpGet]
        public IActionResult AccessDenied()
        {
            return View();
        }

        #endregion

        #region HELPER METHODS

        private IActionResult RedirectToUserRolePage()
        {
            if (User.IsInRole("Admin"))
            {
                return RedirectToAction("Index", "Admin", new { area = "Admin" });
            }
            return RedirectToAction("Index", "Home");
        }

        #endregion
    }
}