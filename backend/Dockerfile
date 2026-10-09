FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY . ./
RUN dotnet restore "GreenShop.Web/GreenShop.Web.csproj"
RUN dotnet publish "GreenShop.Web/GreenShop.Web.csproj" -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

# Copy tường minh thư mục Views vào container để đảm bảo Razor engine chạy ổn định 100%
COPY --from=build /src/GreenShop.Web/Views ./Views

ENV ASPNETCORE_URLS=http://+:3000
EXPOSE 3000
ENTRYPOINT ["dotnet", "GreenShop.Web.dll"]
