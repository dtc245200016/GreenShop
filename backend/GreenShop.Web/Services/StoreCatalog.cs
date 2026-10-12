using GreenShop.Web.Data;
using GreenShop.Web.Models;
using Microsoft.EntityFrameworkCore;

namespace GreenShop.Web.Services;

public static class StoreCatalog
{
    public static IQueryable<Product> Saleable(AppDbContext db) => db.Products.AsNoTracking()
        .Where(p => p.CategoryId == null || p.Category!.IsActive);

    public static IQueryable<StoreProductViewModel> Project(IQueryable<Product> products, AppDbContext db) => products.Select(p => new StoreProductViewModel
    {
        Id = p.Id, Name = p.Name, Price = p.Price, ImageUrl = p.ImageUrl, Description = p.Description,
        StockQuantity = p.StockQuantity, CategoryId = p.CategoryId,
        CategoryName = p.Category == null ? "Chưa phân loại" : p.Category.Name,
        SoldCount = db.OrderItems.Where(i => i.ProductId == p.Id && i.Order.Status == OrderStatus.Completed)
            .Sum(i => (long?)i.Quantity) ?? 0
    });

    public static async Task<StoreCatalogViewModel?> LoadAsync(AppDbContext db, int? categoryId, string? search, string sort, int page, CancellationToken ct)
    {
        var categories = await db.Categories.AsNoTracking().Where(c => c.IsActive).OrderBy(c => c.Name)
            .Select(c => new StoreCategoryViewModel { Id = c.Id, Name = c.Name, ProductCount = c.Products.Count }).ToListAsync(ct);
        var selected = categories.FirstOrDefault(c => c.Id == categoryId);
        if (categoryId.HasValue && selected == null) return null;
        var query = Saleable(db);
        if (categoryId.HasValue) query = query.Where(p => p.CategoryId == categoryId);
        if (!string.IsNullOrEmpty(search)) query = query.Where(p => p.Name.Contains(search));
        var count = await query.CountAsync(ct);
        var totalPages = Math.Max(1, (int)Math.Ceiling(count / 12d));
        page = Math.Min(page, totalPages);
        var ordered = sort switch
        {
            "price-asc" => query.OrderBy(p => p.Price).ThenByDescending(p => p.Id),
            "price-desc" => query.OrderByDescending(p => p.Price).ThenByDescending(p => p.Id),
            _ => query.OrderByDescending(p => p.Id)
        };
        return new StoreCatalogViewModel
        {
            Categories = categories, CategoryId = categoryId, CategoryName = selected?.Name, Search = search,
            Sort = sort, Page = page, TotalCount = count,
            Products = await Project(ordered.Skip((page - 1) * 12).Take(12), db).ToListAsync(ct)
        };
    }
}
