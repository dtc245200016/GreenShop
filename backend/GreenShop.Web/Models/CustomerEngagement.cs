using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Mvc.ModelBinding;

namespace GreenShop.Web.Models;

public class HomeSliderSettings
{
    public int Id { get; set; } = 1;
    [Required, RegularExpression("^(bestsellers|all)$")] public string Mode { get; set; } = "bestsellers";
    [Range(1,100)] public int ProductCount { get; set; } = 5;
    [Range(0,3650)] public int Days { get; set; } = 30;
    [BindRequired, Range(0,long.MaxValue-1)] public long Version { get; set; }
}

public class ProductReview
{
    public int Id { get; set; }
    public int OrderItemId { get; set; }
    public OrderItem OrderItem { get; set; } = null!;
    public int UserId { get; set; }
    public User User { get; set; } = null!;
    public int? ProductId { get; set; }
    public Product? Product { get; set; }
    [MaxLength(150)] public string ProductName { get; set; } = "";
    public int Stars { get; set; }
    [MaxLength(1500)] public string Content { get; set; } = "";
    [MaxLength(255)] public string? Image1 { get; set; }
    [MaxLength(255)] public string? Image2 { get; set; }
    [MaxLength(255)] public string? Image3 { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? AdminReadAt { get; set; }
}

public class ShopConversation
{
    public int Id { get; set; }
    public int CustomerId { get; set; }
    public User Customer { get; set; } = null!;
    public long CustomerReadMessageId { get; set; }
    public long AdminReadMessageId { get; set; }
    public DateTime UpdatedAt { get; set; }
}

public class ShopMessage
{
    public long Id { get; set; }
    public int ConversationId { get; set; }
    public ShopConversation Conversation { get; set; } = null!;
    public int SenderId { get; set; }
    public User Sender { get; set; } = null!;
    public bool FromAdmin { get; set; }
    [MaxLength(2000)] public string Content { get; set; } = "";
    [MaxLength(32)] public string RequestToken { get; set; } = "";
    public DateTime CreatedAt { get; set; }
}

public class ReviewInput
{
    [BindRequired, Range(1,5,ErrorMessage="Vui lòng chọn từ 1 đến 5 sao.")] public int Stars { get; set; }
    [Required(ErrorMessage="Vui lòng nhập nhận xét."), StringLength(1500,MinimumLength=3)] public string Content { get; set; } = "";
    public List<IFormFile> Photos { get; set; } = new();
    [BindNever] public int OrderItemId { get; set; }
    [BindNever] public string ProductName { get; set; } = "";
}

public class MessageInput
{
    [Required, StringLength(2000,MinimumLength=1)] public string Content { get; set; } = "";
    [Required, RegularExpression("^[a-f0-9]{32}$")] public string RequestToken { get; set; } = "";
}

public record ShopAlertCounts(int Orders, int Messages, int Reviews)
{
    public int Total => Orders+Messages+Reviews;
}
public record ShopChatViewModel(int ConversationId, string Title);
public record ShopInboxViewModel(IReadOnlyList<ShopConversation> Conversations, int Page, bool HasNext)
{
    public IReadOnlyDictionary<int,int> Unread { get; init; } = new Dictionary<int,int>();
}
public record ShopReviewsViewModel(IReadOnlyList<ProductReview> Reviews, int Page, bool HasNext);
