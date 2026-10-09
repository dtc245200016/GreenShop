FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["GreenShop.Web/GreenShop.Web.csproj", "GreenShop.Web/"]
RUN dotnet restore "GreenShop.Web/GreenShop.Web.csproj"

COPY . .
WORKDIR "/src/GreenShop.Web"
RUN dotnet build "GreenShop.Web.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "GreenShop.Web.csproj" -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=publish /app/publish .

# Mở cổng web bên trong container
EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080

ENTRYPOINT ["dotnet", "GreenShop.Web.dll"]
