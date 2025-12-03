import asyncio
import httpx
import json

# 关键修改：不再配置代理，直接设为 None
PROXY_URL = None 

KEYWORD = "IONQ"
# 注意：这是 JSON 接口
URL = f"https://www.reddit.com/search.json?q={KEYWORD}&sort=new&limit=5"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def main():
    print("🚀 开始直连测试 (AnyConnect)...")
    
    try:
        # proxy=None 表示不使用代理
        async with httpx.AsyncClient(proxy=None, timeout=10.0, follow_redirects=True) as client:
            print(f"   正在请求: {URL}")
            response = await client.get(URL, headers=HEADERS)
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ 网络连接成功！")
                data = response.json()
                children = data.get("data", {}).get("children", [])
                print(f"   获取到 {len(children)} 条帖子")
                if children:
                    print(f"   第一条: {children[0]['data']['title']}")
            else:
                print(f"   ❌ 请求失败: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())