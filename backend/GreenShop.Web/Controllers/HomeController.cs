using Microsoft.AspNetCore.Mvc;
using GreenShop.Web.Models;

namespace GreenShop.Web.Controllers
{
    public class HomeController : Controller
    {
        public IActionResult Index()
        {
            var products = new List<Product>
            {
                new Product { Id = 1, Name = "Cây Kim Tiền Phong Thủy", Price = 250000, ImageUrl = "https://images.unsplash.com/photo-1614594975525-e45190c55d0b?w=400" },
                new Product { Id = 2, Name = "Cây Trầu Bà Thanh Xuân", Price = 180000, ImageUrl = "https://images.unsplash.com/photo-1598880940371-c756e015ba29?w=400" },
                new Product { Id = 3, Name = "Cây Sen Đá Nhỏ Xinh", Price = 95000, ImageUrl = "https://images.unsplash.com/photo-1509423350716-97f9360b4e09?w=400" },
                new Product { Id = 4, Name = "Cây Lưỡi Hổ Lọc Không Khí", Price = 320000, ImageUrl = "https://images.unsplash.com/photo-1599598425949-6234b7da5fa8?w=400" }
            };
            return View(products);
        }
    }
}
