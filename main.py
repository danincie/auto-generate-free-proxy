import asyncio
import aiohttp
import json
import time
import os
import urllib.request
import geoip2.database
from aiohttp_socks import ProxyConnector
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()

class ModernProxyBot:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.raw_proxies = [] # Menyimpan dict {ip, protocol}
        self.working_proxies = []

    def load_config(self, path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            console.print("[red]config.json tidak ditemukan![/red]")
            return {"timeout": 5, "sources": {}}

    async def fetch_source(self, session, url, protocol):
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    text = await response.text()
                    proxies = [p.strip() for p in text.strip().split('\n') if p.strip()]
                    for p in proxies:
                        self.raw_proxies.append({"ip": p, "protocol": protocol})
        except Exception:
            pass 

    async def scrape_proxies(self):
        console.print("[bold cyan]Memulai Scraping Multi-Protokol...[/bold cyan]")
        async with aiohttp.ClientSession() as session:
            tasks = []
            for protocol, urls in self.config.get('sources', {}).items():
                for url in urls:
                    tasks.append(self.fetch_source(session, url, protocol))
            await asyncio.gather(*tasks)
        
        # Menghapus duplikat data mentah
        self.raw_proxies = [dict(t) for t in {tuple(d.items()) for d in self.raw_proxies}]
        console.print(f"[bold green]✓ Berhasil mengumpulkan {len(self.raw_proxies)} proxy mentah.[/bold green]\n")

    async def check_proxy(self, proxy_info, progress, task_id):
        proxy_ip = proxy_info['ip']
        protocol = proxy_info['protocol']
        start_time = time.time()
        
        try:
            if protocol in ['socks4', 'socks5']:
                connector = ProxyConnector.from_url(f"{protocol}://{proxy_ip}")
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get('http://httpbin.org/get', timeout=self.config.get('timeout', 5)) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._process_success(proxy_ip, protocol, start_time, data)
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://httpbin.org/get', proxy=f"http://{proxy_ip}", timeout=self.config.get('timeout', 5)) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._process_success(proxy_ip, protocol, start_time, data)
        except Exception:
            pass
        finally:
            progress.advance(task_id)

    def _process_success(self, proxy_ip, protocol, start_time, data):
        latency = round((time.time() - start_time) * 1000)
        headers = {k.lower(): v for k, v in data.get('headers', {}).items()}
        anonymity = "Elite"
        
        if 'x-forwarded-for' in headers or 'x-real-ip' in headers:
            anonymity = "Transparent"
        elif 'via' in headers or 'forwarded' in headers:
            anonymity = "Anonymous"

        self.working_proxies.append({
            "proxy": proxy_ip,
            "protocol": protocol.upper(),
            "latency_ms": latency,
            "anonymity": anonymity
        })

    async def verify_proxies(self):
        console.print("[bold cyan]Memverifikasi Kualitas Proxy (HTTP & SOCKS)...[/bold cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("[yellow]Memeriksa IP...", total=len(self.raw_proxies))
            
            semaphore = asyncio.Semaphore(200)
            async def sem_task(proxy_info):
                async with semaphore:
                    await self.check_proxy(proxy_info, progress, task)
            
            tasks = [sem_task(proxy_info) for proxy_info in self.raw_proxies]
            await asyncio.gather(*tasks)
        
        self.working_proxies = sorted(self.working_proxies, key=lambda x: x['latency_ms'])
        console.print(f"\n[bold green]✓ Ditemukan {len(self.working_proxies)} proxy aktif![/bold green]")

    async def enrich_with_geo_data(self):
        console.print("\n[bold cyan]Melacak Lokasi Geografis (Mode Database Lokal MaxMind)...[/bold cyan]")
        db_path = "GeoLite2-Country.mmdb"
        
        # Otomatis mengunduh berkas database jika belum ada di folder lokalan
        if not os.path.exists(db_path):
            console.print("[yellow]Database lokal tidak ditemukan. Mengunduh database GeoIP...[/yellow]")
            url = "https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb"
            try:
                urllib.request.urlretrieve(url, db_path)
                console.print("[green]✓ Database GeoIP berhasil diunduh secara lokal.[/green]")
            except Exception as e:
                console.print(f"[red]Gagal mengunduh database: {e}[/red]")
                # Mekanisme pertahanan aman agar bot tidak crash jika internet mati saat unduh database
                for item in self.working_proxies:
                    item['country'] = 'Unknown'
                    item['country_code'] = 'UN'
                return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ) as progress:
            
            task = progress.add_task("[yellow]Mencocokkan IP dengan Kamus Database...", total=len(self.working_proxies))
            
            try:
                # Membuka kamus biner lokal
                with geoip2.database.Reader(db_path) as reader:
                    for item in self.working_proxies:
                        ip_only = item['proxy'].split(':')[0]
                        try:
                            response = reader.country(ip_only)
                            item['country'] = response.country.name or 'Unknown'
                            item['country_code'] = response.country.iso_code or 'UN'
                        except Exception:
                            item['country'] = 'Unknown'
                            item['country_code'] = 'UN'
                        finally:
                            progress.advance(task)
            except Exception as e:
                console.print(f"[red]Gagal membaca database GeoIP: {e}[/red]")
                for item in self.working_proxies:
                    item['country'] = 'Unknown'
                    item['country_code'] = 'UN'
                    progress.advance(task)

    def export_data(self):
        if not self.working_proxies:
            console.print("[red]Tidak ada proxy aktif untuk disimpan.[/red]")
            return

        with open('working_proxies.txt', 'w') as f:
            for p in self.working_proxies:
                f.write(f"{p['protocol'].lower()}://{p['proxy']}\n")
        
        with open('working_proxies.json', 'w') as f:
            json.dump({
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_active": len(self.working_proxies),
                "proxies": self.working_proxies
            }, f, indent=4)
        
        console.print("\n[bold blue]Data berhasil diekspor![/bold blue]")

async def main():
    bot = ModernProxyBot()
    await bot.scrape_proxies()
    
    if bot.raw_proxies:
        await bot.verify_proxies()
        if bot.working_proxies:
            await bot.enrich_with_geo_data()
        bot.export_data()

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())