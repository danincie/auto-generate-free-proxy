import asyncio
import aiohttp
import json
import time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()

class ModernProxyBot:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.raw_proxies = set()
        self.working_proxies = []

    def load_config(self, path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            console.print("[red]config.json tidak ditemukan, menggunakan pengaturan default.[/red]")
            return {"timeout": 5, "sources": []}

    async def fetch_source(self, session, url):
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    text = await response.text()
                    # Memisahkan berdasarkan baris dan membersihkan whitespace
                    proxies = [p.strip() for p in text.strip().split('\n') if p.strip()]
                    self.raw_proxies.update(proxies)
        except Exception as e:
            pass # Abaikan sumber yang error agar proses tetap berjalan

    async def scrape_proxies(self):
        console.print("[bold cyan]Memulai Scraping Proxy Asynchronous...[/bold cyan]")
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_source(session, url) for url in self.config.get('sources', [])]
            await asyncio.gather(*tasks)
        console.print(f"[bold green]✓ Berhasil mengumpulkan {len(self.raw_proxies)} proxy mentah.[/bold green]\n")

    async def check_proxy(self, proxy, session, progress, task_id):
        proxy_url = f"http://{proxy}"
        start_time = time.time()
        try:
            # Menggunakan httpbin untuk menguji IP
            async with session.get('http://httpbin.org/ip', proxy=proxy_url, timeout=self.config.get('timeout', 5)) as response:
                if response.status == 200:
                    latency = round((time.time() - start_time) * 1000)
                    self.working_proxies.append({
                        "proxy": proxy,
                        "latency_ms": latency
                    })
        except Exception:
            pass # Proxy mati atau timeout
        finally:
            progress.advance(task_id)

    async def verify_proxies(self):
        console.print("[bold cyan]Memverifikasi Kualitas Proxy...[/bold cyan]")
        
        # Limitasi TCP koneksi untuk mencegah crash jaringan lokal
        connector = aiohttp.TCPConnector(limit_per_host=0, limit=200)
        async with aiohttp.ClientSession(connector=connector) as session:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
            ) as progress:
                
                task = progress.add_task("[yellow]Memeriksa IP...", total=len(self.raw_proxies))
                tasks = [self.check_proxy(proxy, session, progress, task) for proxy in self.raw_proxies]
                await asyncio.gather(*tasks)
        
        # Mengurutkan dari yang paling cepat (ms terendah)
        self.working_proxies = sorted(self.working_proxies, key=lambda x: x['latency_ms'])
        console.print(f"\n[bold green]✓ Ditemukan {len(self.working_proxies)} proxy aktif![/bold green]")

    def export_data(self):
        if not self.working_proxies:
            console.print("[red]Tidak ada proxy aktif untuk disimpan.[/red]")
            return

        # Format TXT Klasik
        with open('working_proxies.txt', 'w') as f:
            for p in self.working_proxies:
                f.write(f"{p['proxy']}\n")
        
        # Format JSON Modern (Sangat cocok untuk API / Aplikasi Web / Mobile)
        with open('working_proxies.json', 'w') as f:
            json.dump({
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_active": len(self.working_proxies),
                "proxies": self.working_proxies
            }, f, indent=4)
        
        console.print("[bold blue]Data berhasil diekspor ke working_proxies.txt & working_proxies.json[/bold blue]")

async def main():
    bot = ModernProxyBot()
    await bot.scrape_proxies()
    
    if bot.raw_proxies:
        await bot.verify_proxies()
        bot.export_data()

if __name__ == "__main__":
    # Menghindari error Asyncio pada environment Windows
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())