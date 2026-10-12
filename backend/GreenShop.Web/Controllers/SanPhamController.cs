using GreenShop.Web.Data;
using GreenShop.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace GreenShop.Web.Controllers;

public class SanPhamController(AppDbContext db) : Controller
{
    [HttpGet]
    public async Task<IActionResult> CuaHang(int? categoryId, string? search, string sort = "newest", int page = 1, CancellationToken ct = default)
    {
        search = search?.Trim();
        if (!ModelState.IsValid || categoryId <= 0 || page <= 0 || search?.Length > 150 || sort is not ("newest" or "price-asc" or "price-desc")) return BadRequest();
        var model = await StoreCatalog.LoadAsync(db, categoryId, search, sort, page, ct);
        return model == null ? NotFound() : View(model);
    }

    [HttpGet]
    public async Task<IActionResult> ChiTietSanPham([FromRoute] int id, CancellationToken ct)
    {
        if (!ModelState.IsValid || id <= 0) return NotFound();
        var model = await StoreCatalog.Project(StoreCatalog.Saleable(db).Where(p => p.Id == id), db).FirstOrDefaultAsync(ct);
        return model == null ? NotFound() : View(model);
    }
}
