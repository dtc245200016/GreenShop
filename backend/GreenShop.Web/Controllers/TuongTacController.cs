using GreenShop.Web.Data;
using GreenShop.Web.Models;
using GreenShop.Web.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace GreenShop.Web.Controllers;

[Authorize(Roles="Customer")]
public class TuongTacController(AppDbContext db,IWebHostEnvironment environment,ILogger<TuongTacController> logger) : ChatControllerBase(db)
{
    [HttpGet] public Task<IActionResult> TroChuyen(CancellationToken ct)=>ChatAsync(0,false,ct);
    [HttpGet] public Task<IActionResult> TinNhanMoi(long after=0,CancellationToken ct=default)=>MessagesAsync(0,false,after,ct);
    [HttpPost,ValidateAntiForgeryToken] public Task<IActionResult> GuiTinNhan(MessageInput input,CancellationToken ct)=>SendAsync(0,false,input,ct);
    [HttpPost,ValidateAntiForgeryToken] public Task<IActionResult> DaDoc(long through,CancellationToken ct)=>ReadAsync(0,false,through,ct);

    private Task<OrderItem?> PurchasedAsync(int id,CancellationToken ct)=>Db.OrderItems.AsNoTracking().Include(i=>i.Order)
        .FirstOrDefaultAsync(i=>i.Id==id && i.Order.UserId==ShoppingIdentity.UserId(User) && i.Order.Status==OrderStatus.Completed && i.ProductId!=null,ct);

    [HttpGet] public async Task<IActionResult> DanhGia([FromRoute]int id,CancellationToken ct)
    {
        var item=await PurchasedAsync(id,ct);if(item==null) return NotFound();
        if(await Db.ProductReviews.AnyAsync(r=>r.OrderItemId==id,ct)) {TempData["SuccessMessage"]="Bạn đã đánh giá sản phẩm này.";return RedirectToAction("ChiTietDonHang","ThanhToan",new{id=item.OrderId});}
        return View(new ReviewInput{OrderItemId=id,ProductName=item.ProductName});
    }
    [HttpPost,ValidateAntiForgeryToken,RequestSizeLimit(6*1024*1024)]
    public async Task<IActionResult> DanhGia([FromRoute]int id,ReviewInput input,CancellationToken ct)
    {
        var item=await PurchasedAsync(id,ct);if(item==null) return NotFound();
        input.OrderItemId=id;input.ProductName=item.ProductName;input.Content=input.Content?.Trim()??"";
        if(input.Content.Length<3) ModelState.AddModelError(nameof(input.Content),"Nhận xét cần ít nhất 3 ký tự.");
        var storage=new ProductImageStorage(environment,logger);
        if(input.Photos.Count>3 || input.Photos.Sum(f=>f.Length)>5*1024*1024) ModelState.AddModelError(nameof(input.Photos),"Tối đa 3 ảnh, tổng dung lượng không quá 5 MiB.");
        foreach(var photo in input.Photos.Take(3)) {
            var error=photo.Length>2*1024*1024?"Mỗi ảnh tối đa 2 MiB.":await storage.ValidateAsync(photo,ct);
            if(error!=null) ModelState.AddModelError(nameof(input.Photos),error);
        }
        if(!ModelState.IsValid) {Response.StatusCode=400;return View(input);}
        var urls=new List<string>();var kept=false;
        try {
            foreach(var photo in input.Photos) urls.Add(await storage.SaveAsync(photo,ct));
            var result=await Db.Database.CreateExecutionStrategy().ExecuteAsync(async()=> {
                Db.ChangeTracker.Clear();await using var tx=await Db.Database.BeginTransactionAsync(ct);
                var actor=await ShoppingIdentity.LockUserAsync(Db,ShoppingIdentity.UserId(User),ct);
                if(actor==null || actor.Role!=UserRole.Customer || !actor.IsActive || actor.SessionVersion!=UserSession.Version(User)) return 403;
                if(await PurchasedAsync(id,ct)==null) return 404;
                var existing=await Db.ProductReviews.AsNoTracking().FirstOrDefaultAsync(r=>r.OrderItemId==id,ct);
                if(existing!=null) return existing.Content==input.Content && existing.Stars==input.Stars && existing.Image1==urls.ElementAtOrDefault(0) && existing.Image2==urls.ElementAtOrDefault(1) && existing.Image3==urls.ElementAtOrDefault(2) ? 200 : 409;
                Db.ProductReviews.Add(new ProductReview{OrderItemId=id,UserId=actor.Id,ProductId=item.ProductId,ProductName=item.ProductName,Stars=input.Stars,Content=input.Content,Image1=urls.ElementAtOrDefault(0),Image2=urls.ElementAtOrDefault(1),Image3=urls.ElementAtOrDefault(2),CreatedAt=DateTime.UtcNow});
                await Db.SaveChangesAsync(ct);await tx.CommitAsync(ct);return 200;
            });
            if(result==403) return Forbid();if(result==404) return NotFound();
            kept=result==200;TempData[result==200?"SuccessMessage":"WarningMessage"]=result==200?"Cảm ơn bạn! Đánh giá đã được đăng.":"Sản phẩm này đã được đánh giá trước đó.";
            return RedirectToAction("ChiTietDonHang","ThanhToan",new{id=item.OrderId});
        } catch(Exception ex) when(ex is DbUpdateException or IOException or UnauthorizedAccessException) {
            logger.LogWarning("Chưa thể lưu đánh giá hoặc ảnh đính kèm.");ModelState.AddModelError("","Chưa thể lưu đánh giá. Vui lòng thử lại.");Response.StatusCode=503;return View(input);
        } finally {
            if(!kept && urls.Count>0) {
                // A cancelled response or transient commit error may still have committed.
                // Never remove an image referenced by the persisted review.
                using var cleanupTimeout=new CancellationTokenSource(TimeSpan.FromSeconds(3));
                try {
                    var committed=await Db.ProductReviews.AsNoTracking().FirstOrDefaultAsync(r=>r.OrderItemId==id,cleanupTimeout.Token);
                    var referenced=new[]{committed?.Image1,committed?.Image2,committed?.Image3};
                    foreach(var url in urls.Where(u=>!referenced.Contains(u))) storage.Delete(url);
                } catch(Exception ex) when(ex is System.Data.Common.DbException or Microsoft.EntityFrameworkCore.Storage.RetryLimitExceededException or OperationCanceledException) {
                    logger.LogWarning("Giữ ảnh đính kèm vì chưa thể xác minh kết quả lưu đánh giá.");
                }
            }
        }
    }
}
