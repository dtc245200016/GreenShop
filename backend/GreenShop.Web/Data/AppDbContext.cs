
using Microsoft.EntityFrameworkCore;
using GreenShop.Web.Models;

namespace GreenShop.Web.Data
{
    public class AppDbContext : DbContext
    {
        public AppDbContext(
            DbContextOptions<AppDbContext> options
        ) : base(options)
        {
        }

        public DbSet<User> Users { get; set; } = null!;
        public DbSet<Product> Products { get; set; } = null!;
        public DbSet<Category> Categories { get; set; } = null!;
        public DbSet<CartItem> CartItems { get; set; } = null!;
        public DbSet<Order> Orders { get; set; } = null!;
        public DbSet<OrderItem> OrderItems { get; set; } = null!;
        public DbSet<OrderStatusHistory> OrderStatusHistories { get; set; } = null!;
        public DbSet<PaymentShippingSettings> PaymentShippingSettings { get; set; } = null!;

        protected override void OnModelCreating(
            ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            modelBuilder.Entity<User>()
                .HasIndex(u => u.Email)
                .IsUnique();
            modelBuilder.Entity<User>().Property(u => u.IsActive).HasDefaultValue(true);
            modelBuilder.Entity<User>().Property(u => u.Version).IsConcurrencyToken();
            modelBuilder.Entity<User>().HasIndex(u => new { u.Role, u.IsActive });

            modelBuilder.Entity<Product>(entity =>
            {
                entity.ToTable("Products");

                entity.Property(p => p.Name)
                    .HasMaxLength(150)
                    .IsRequired();

                entity.Property(p => p.Price)
                    .HasColumnType("decimal(18,2)");

                entity.Property(p => p.ImageUrl)
                    .HasMaxLength(255)
                    .IsRequired();

                entity.Property(p => p.Description)
                    .HasMaxLength(2000)
                    .IsRequired();

                entity.HasOne(p => p.Category)
                    .WithMany(c => c.Products)
                    .HasForeignKey(p => p.CategoryId)
                    .OnDelete(DeleteBehavior.Restrict);
            });

            modelBuilder.Entity<Category>(entity =>
            {
                entity.ToTable("Categories");
                entity.Property(c => c.Name)
                    .HasMaxLength(100)
                    .UseCollation("utf8mb4_0900_as_ci")
                    .IsRequired();
                entity.Property(c => c.Description).HasMaxLength(500).IsRequired();
                entity.HasIndex(c => c.Name).IsUnique();
            });

            modelBuilder.Entity<CartItem>(entity =>
            {
                entity.HasIndex(i => new { i.UserId, i.ProductId }).IsUnique();
                entity.HasOne(i => i.User).WithMany().HasForeignKey(i => i.UserId).OnDelete(DeleteBehavior.Restrict);
                entity.HasOne(i => i.Product).WithMany().HasForeignKey(i => i.ProductId).OnDelete(DeleteBehavior.Cascade);
                entity.ToTable(t => t.HasCheckConstraint("CK_CartItems_Quantity", "`Quantity` > 0"));
            });
            modelBuilder.Entity<Order>(entity =>
            {
                entity.Property(o => o.ConfirmationToken).HasMaxLength(32).IsRequired();
                entity.HasIndex(o => new { o.UserId, o.ConfirmationToken }).IsUnique();
                entity.Property(o => o.RecipientName).HasMaxLength(100).IsRequired();
                entity.Property(o => o.Phone).HasMaxLength(21).IsRequired();
                entity.Property(o => o.Address).HasMaxLength(500).IsRequired();
                entity.Property(o => o.PaymentMethod).HasMaxLength(10).IsRequired();
                entity.Property(o => o.Total).HasPrecision(18, 2);
                entity.Property(o=>o.Subtotal).HasPrecision(18,2);
                entity.Property(o=>o.ShippingFee).HasPrecision(18,2);
                entity.Property(o=>o.ShippingFlatFeeSnapshot).HasPrecision(18,2);
                entity.Property(o=>o.FreeShippingThresholdSnapshot).HasPrecision(18,2);
                entity.Property(o=>o.BankBinSnapshot).HasMaxLength(6);
                entity.Property(o=>o.BankNameSnapshot).HasMaxLength(200);
                entity.Property(o=>o.BankAccountSnapshot).HasMaxLength(19);
                entity.Property(o=>o.BankHolderSnapshot).HasMaxLength(100);
                entity.Property(o=>o.TransferContent).HasMaxLength(50);
                entity.Property(o=>o.PaymentConfirmedByName).HasMaxLength(100);
                entity.HasIndex(o=>o.TransferContent).IsUnique();
                entity.HasOne(o=>o.PaymentConfirmedBy).WithMany().HasForeignKey(o=>o.PaymentConfirmedById).OnDelete(DeleteBehavior.Restrict);
                entity.Property(o => o.AdminNote).HasMaxLength(1000).IsRequired();
                entity.Property(o => o.Version).IsConcurrencyToken();
                entity.HasIndex(o => new { o.Status, o.CreatedAt });
                entity.HasIndex(o => o.CreatedAt);
                entity.HasOne(o => o.User).WithMany().HasForeignKey(o => o.UserId).OnDelete(DeleteBehavior.Restrict);
                entity.HasIndex(o => new { o.UserId, o.CreatedAt });
            });
            modelBuilder.Entity<OrderItem>(entity =>
            {
                entity.Property(i => i.ProductName).HasMaxLength(150).IsRequired();
                entity.Property(i => i.ImageUrl).HasMaxLength(255).IsRequired();
                entity.Property(i => i.UnitPrice).HasPrecision(18, 2);
                entity.HasOne(i => i.Order).WithMany(o => o.Items).HasForeignKey(i => i.OrderId).OnDelete(DeleteBehavior.Cascade);
                entity.HasOne(i => i.Product).WithMany().HasForeignKey(i => i.ProductId).OnDelete(DeleteBehavior.SetNull);
                entity.ToTable(t => t.HasCheckConstraint("CK_OrderItems_Quantity", "`Quantity` > 0"));
            });
            modelBuilder.Entity<OrderStatusHistory>(entity =>
            {
                entity.Property(h => h.AdminName).HasMaxLength(100).IsRequired();
                entity.Property(h => h.Note).HasMaxLength(1000).IsRequired();
                entity.HasOne(h => h.Order).WithMany(o => o.History).HasForeignKey(h => h.OrderId).OnDelete(DeleteBehavior.Restrict);
                entity.HasOne(h => h.Admin).WithMany().HasForeignKey(h => h.AdminId).OnDelete(DeleteBehavior.SetNull);
                entity.HasIndex(h => new { h.OrderId, h.CreatedAt });
            });
            modelBuilder.Entity<PaymentShippingSettings>(entity=>
            {
                entity.Property(s=>s.Id).ValueGeneratedNever();
                entity.Property(s=>s.BankBin).HasMaxLength(6).IsRequired();
                entity.Property(s=>s.BankName).HasMaxLength(200).IsRequired();
                entity.Property(s=>s.AccountNumber).HasMaxLength(19).IsRequired();
                entity.Property(s=>s.AccountHolderName).HasMaxLength(100).IsRequired();
                entity.Property(s=>s.FlatShippingFee).HasPrecision(18,2);
                entity.Property(s=>s.FreeShippingThreshold).HasPrecision(18,2);
                entity.Property(s=>s.Version).IsConcurrencyToken();
                entity.ToTable(t=>t.HasCheckConstraint("CK_PaymentShippingSettings_Singleton","`Id` = 1"));
            });
        }
    }
}
