using GreenShop.Web.Data;
using GreenShop.Web.Models;
using GreenShop.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace GreenShop.Web.Controllers;

public abstract class ChatControllerBase(AppDbContext db) : Controller
{
    protected AppDbContext Db => db;
    protected async Task<IActionResult> ChatAsync(int id,bool admin,CancellationToken ct)
    {
        var conversation=await new ShopCommunication(db).Accessible(id,User,admin).Include(c=>c.Customer).FirstOrDefaultAsync(ct);
        if(admin && conversation==null) return NotFound();
        return View("~/Views/Shared/ShopChat.cshtml",new ShopChatViewModel(conversation?.Id??0,admin?conversation!.Customer.FullName:"Chat với GreenShop"));
    }
    protected async Task<IActionResult> MessagesAsync(int id,bool admin,long after,CancellationToken ct)
    {
        if(after<0) return BadRequest();Response.Headers.CacheControl="no-store";
        var conversation=await new ShopCommunication(db).Accessible(id,User,admin).FirstOrDefaultAsync(ct);
        if(conversation==null) return admin ? NotFound() : Json(new {messages=Array.Empty<object>(),hasMore=false});
        var rows=await db.ShopMessages.AsNoTracking().Where(m=>m.ConversationId==conversation.Id && m.Id>after).OrderBy(m=>m.Id).Take(101)
            .Select(m=>new {m.Id,m.Content,m.FromAdmin,m.CreatedAt}).ToListAsync(ct);
        return Json(new {messages=rows.Take(100),hasMore=rows.Count>100});
    }
    protected async Task<IActionResult> SendAsync(int id,bool admin,MessageInput input,CancellationToken ct)
    {
        input.Content=input.Content?.Trim()??"";
        if(!ModelState.IsValid || input.Content.Length==0) return BadRequest(new {message="Nhập tin nhắn từ 1 đến 2.000 ký tự."});
        var result=await new ShopCommunication(db).SendAsync(id,User,admin,input,ct);
        if(result.Status==429) Response.Headers.RetryAfter="60";
        return result.Status==200 ? Json(new {id=result.Id}) : StatusCode(result.Status,new {message=result.Status==429?"Bạn gửi quá nhanh. Vui lòng đợi một phút.":"Chưa thể gửi tin nhắn. Hãy tải lại và thử lại."});
    }
    protected async Task<IActionResult> ReadAsync(int id,bool admin,long through,CancellationToken ct)
    {
        if(through<=0) return BadRequest();
        var conversation=await new ShopCommunication(db).Accessible(id,User,admin).FirstOrDefaultAsync(ct);
        if(conversation==null) return NotFound();
        if(!await db.ShopMessages.AnyAsync(m=>m.ConversationId==conversation.Id && m.Id==through,ct)) return BadRequest();
        if(admin) await db.ShopConversations.Where(c=>c.Id==conversation.Id && c.AdminReadMessageId<through).ExecuteUpdateAsync(s=>s.SetProperty(c=>c.AdminReadMessageId,through),ct);
        else await db.ShopConversations.Where(c=>c.Id==conversation.Id && c.CustomerReadMessageId<through).ExecuteUpdateAsync(s=>s.SetProperty(c=>c.CustomerReadMessageId,through),ct);
        return NoContent();
    }
}
