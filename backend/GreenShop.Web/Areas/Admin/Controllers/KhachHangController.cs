using GreenShop.Web.Controllers;
using GreenShop.Web.Data;
using GreenShop.Web.Models;
using GreenShop.Web.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace GreenShop.Web.Areas.Admin.Controllers;

[Area("Admin"),Authorize(Roles="Admin")]
public class KhachHangController(AppDbContext db) : ChatControllerBase(db)
{
    [HttpGet] public async Task<IActionResult> Slider(CancellationToken ct)=>View(await Db.HomeSliderSettings.AsNoTracking().SingleAsync(ct));
    [HttpPost,ValidateAntiForgeryToken] public async Task<IActionResult> Slider(HomeSliderSettings input,CancellationToken ct)
    {
        if(!ModelState.IsValid) {Response.StatusCode=400;return View(input);}
        var changed=await Db.HomeSliderSettings.Where(s=>s.Id==1 && s.Version==input.Version).ExecuteUpdateAsync(s=>s.SetProperty(s=>s.Mode,input.Mode).SetProperty(s=>s.ProductCount,input.ProductCount).SetProperty(s=>s.Days,input.Days).SetProperty(s=>s.Version,s=>s.Version+1),ct);
        if(changed==0) {Response.StatusCode=409;ModelState.Clear();ModelState.AddModelError("","Cấu hình vừa được thay đổi. Kiểm tra dữ liệu mới rồi lưu lại.");return View(await Db.HomeSliderSettings.AsNoTracking().SingleAsync(ct));}
        TempData["SuccessMessage"]="Đã cập nhật slider trang chủ.";return RedirectToAction(nameof(Slider));
    }
    [HttpGet] public async Task<IActionResult> ThongBao(CancellationToken ct) {Response.Headers.CacheControl="no-store";return Json(await ShopCommunication.AlertsAsync(Db,ct));}
    [HttpGet] public async Task<IActionResult> TinNhan(int page=1,CancellationToken ct=default)
    {
        if(page<1 || page>100000) return BadRequest();
        var rows=await Db.ShopConversations.AsNoTracking().Include(c=>c.Customer).OrderByDescending(c=>c.UpdatedAt).ThenByDescending(c=>c.Id).Skip((page-1)*20).Take(21).ToListAsync(ct);
        var ids=rows.Take(20).Select(c=>c.Id).ToArray();
        var unread=await Db.ShopMessages.Where(m=>ids.Contains(m.ConversationId) && !m.FromAdmin && m.Id>m.Conversation.AdminReadMessageId).GroupBy(m=>m.ConversationId).Select(g=>new{Id=g.Key,Count=g.Count()}).ToDictionaryAsync(g=>g.Id,g=>g.Count,ct);
        return View(new ShopInboxViewModel(rows.Take(20).ToList(),page,rows.Count>20){Unread=unread});
    }
    [HttpGet] public Task<IActionResult> TroChuyen([FromRoute]int id,CancellationToken ct)=>ChatAsync(id,true,ct);
    [HttpGet] public Task<IActionResult> TinNhanMoi([FromRoute]int id,long after=0,CancellationToken ct=default)=>MessagesAsync(id,true,after,ct);
    [HttpPost,ValidateAntiForgeryToken] public Task<IActionResult> GuiTinNhan([FromRoute]int id,MessageInput input,CancellationToken ct)=>SendAsync(id,true,input,ct);
    [HttpPost,ValidateAntiForgeryToken] public Task<IActionResult> DaDoc([FromRoute]int id,long through,CancellationToken ct)=>ReadAsync(id,true,through,ct);
    [HttpGet] public async Task<IActionResult> DanhGia(int page=1,CancellationToken ct=default)
    {
        if(page<1 || page>100000) return BadRequest();
        var rows=await Db.ProductReviews.AsNoTracking().Include(r=>r.User).OrderByDescending(r=>r.Id).Skip((page-1)*20).Take(21).ToListAsync(ct);
        return View(new ShopReviewsViewModel(rows.Take(20).ToList(),page,rows.Count>20));
    }
    [HttpPost,ValidateAntiForgeryToken] public async Task<IActionResult> DaDocDanhGia([FromRoute]int id,CancellationToken ct)
    {
        if(!await Db.ProductReviews.AnyAsync(r=>r.Id==id,ct)) return NotFound();
        await Db.ProductReviews.Where(r=>r.Id==id && r.AdminReadAt==null).ExecuteUpdateAsync(s=>s.SetProperty(r=>r.AdminReadAt,DateTime.UtcNow),ct);
        return RedirectToAction(nameof(DanhGia));
    }
}
