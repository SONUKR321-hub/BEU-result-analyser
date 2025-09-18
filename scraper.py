import asyncio
import aiohttp
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import streamlit as st
from typing import List, Dict, Optional
import functools
import logging
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Session configuration - will be created when needed
def get_session_config():
    """Create session configuration when needed"""
    return {
        'timeout': aiohttp.ClientTimeout(total=10, connect=5),
        'connector': aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
    }

class FastResultScraper:
    def __init__(self):
        self.session = None
        self.successful_fetches = 0
        self.failed_fetches = 0
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(**get_session_config())
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_single_result(self, base_url: str, registration_no: int, retries: int = 2) -> Optional[Dict]:
        """Async function to fetch a single student result with optimized parsing"""
        url = f"{base_url}{registration_no}"
        
        for attempt in range(retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        result = self._parse_html_optimized(html, registration_no)
                        if result:
                            self.successful_fetches += 1
                            return result
                    elif response.status == 503:
                        # Server temporarily unavailable
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                        
            except Exception as e:
                logger.debug(f"Attempt {attempt + 1} failed for {registration_no}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    
        self.failed_fetches += 1
        return None

    def _parse_html_optimized(self, html: str, reg_no: int) -> Optional[Dict]:
        """Optimized HTML parsing with better error handling"""
        try:
            soup = BeautifulSoup(html, "lxml")  # lxml is faster than html.parser
            
            # Quick check if page has data
            if not soup.select_one("#ContentPlaceHolder1_DataList1_RegistrationNoLabel_0"):
                return None
                
            # Extract basic info with fallbacks
            result = {
                "Registration No.": self._safe_extract(soup, "#ContentPlaceHolder1_DataList1_RegistrationNoLabel_0", str(reg_no)),
                "Student Name": self._safe_extract(soup, "#ContentPlaceHolder1_DataList1_StudentNameLabel_0", "N/A"),
                "Father's Name": self._safe_extract(soup, "#ContentPlaceHolder1_DataList1_FatherNameLabel_0", "N/A"),
                "Mother's Name": self._safe_extract(soup, "#ContentPlaceHolder1_DataList1_MotherNameLabel_0", "N/A"),
                "Current SGPA": self._safe_extract(soup, "#ContentPlaceHolder1_DataList5_GROSSTHEORYTOTALLabel_0", "0.0")
            }
            
            # Extract semester data if available
            table = soup.select_one("#ContentPlaceHolder1_GridView3")
            if table and table.select("tr"):
                rows = table.select("tr")
                if len(rows) >= 2:
                    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
                    values = [td.get_text(strip=True) for td in rows[1].find_all("td")]
                    
                    for header, value in zip(headers, values):
                        if header and value:  # Only add non-empty data
                            result[f"Sem {header}"] = value
            
            return result
            
        except Exception as e:
            logger.debug(f"Parsing failed for {reg_no}: {e}")
            return None

    def _safe_extract(self, soup, selector: str, default: str = "N/A") -> str:
        """Safely extract text from soup with fallback"""
        try:
            element = soup.select_one(selector)
            return element.get_text(strip=True) if element else default
        except:
            return default

async def fetch_all_results_async(base_url: str, start_reg: int, end_reg: int, 
                                 progress_callback=None) -> List[Dict]:
    """Async function to fetch all results with progress tracking"""
    
    async with FastResultScraper() as scraper:
        # Create semaphore to limit concurrent requests (respect server limits)
        semaphore = asyncio.Semaphore(15)  # Increased from 5 for better performance
        
        async def fetch_with_semaphore(reg_no):
            async with semaphore:
                return await scraper.fetch_single_result(base_url, reg_no)
        
        # Create all tasks
        reg_numbers = list(range(start_reg, end_reg + 1))
        total_requests = len(reg_numbers)
        
        # Show initial progress
        if progress_callback:
            progress_callback(0, total_requests, 0, 0)
        
        # Execute tasks with progress tracking
        tasks = [fetch_with_semaphore(reg_no) for reg_no in reg_numbers]
        results = []
        completed = 0
        
        # Process results as they complete
        for future in asyncio.as_completed(tasks):
            result = await future
            completed += 1
            
            if result:
                results.append(result)
            
            # Update progress every 5 completions or at the end
            if progress_callback and (completed % 5 == 0 or completed == total_requests):
                progress_callback(completed, total_requests, scraper.successful_fetches, scraper.failed_fetches)
        
        logger.info(f"Scraping complete: {scraper.successful_fetches} successful, {scraper.failed_fetches} failed")
        return results

def fetch_all_results(base_url: str, start_reg: int, end_reg: int) -> List[Dict]:
    """Wrapper function to run async scraper from sync context"""
    
    # Create progress placeholder
    progress_placeholder = st.empty()
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    
    def update_progress(completed, total, successful, failed):
        progress = completed / total if total > 0 else 0
        progress_bar.progress(progress)
        
        status_placeholder.write(
            f"⚡ **Fast Scraping in Progress:** {completed}/{total} processed "
            f"| ✅ {successful} successful | ❌ {failed} failed"
        )
    
    try:
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            fetch_all_results_async(base_url, start_reg, end_reg, update_progress)
        )
        loop.close()
        
        # Clear progress indicators
        progress_placeholder.empty()
        progress_bar.empty()
        status_placeholder.empty()
        
        return results
        
    except Exception as e:
        st.error(f"Scraping failed: {e}")
        progress_placeholder.empty()
        progress_bar.empty()
        status_placeholder.empty()
        return []

# Legacy sync function for compatibility (significantly optimized)
def fetch_and_parse_result(base_url, registration_no, retries=2, backoff_factor=0.5):
    """Optimized sync version with reduced retries and faster parsing"""
    url = f"{base_url}{registration_no}"
    
    # Use session with connection pooling
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=3)  # Reduced timeout
            response.raise_for_status()
            
            # Use lxml parser for speed
            soup = BeautifulSoup(response.text, "lxml")
            
            # Quick validation
            if not soup.select_one("#ContentPlaceHolder1_DataList1_RegistrationNoLabel_0"):
                return None
                
            result = {
                "Registration No.": _safe_get_text(soup, "#ContentPlaceHolder1_DataList1_RegistrationNoLabel_0"),
                "Student Name": _safe_get_text(soup, "#ContentPlaceHolder1_DataList1_StudentNameLabel_0"),
                "Father's Name": _safe_get_text(soup, "#ContentPlaceHolder1_DataList1_FatherNameLabel_0"),
                "Mother's Name": _safe_get_text(soup, "#ContentPlaceHolder1_DataList1_MotherNameLabel_0"),
                "Current SGPA": _safe_get_text(soup, "#ContentPlaceHolder1_DataList5_GROSSTHEORYTOTALLabel_0")
            }
            
            # Optimized table parsing
            table = soup.select_one("#ContentPlaceHolder1_GridView3")
            if table:
                rows = table.select("tr")
                if len(rows) >= 2:
                    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
                    values = [td.get_text(strip=True) for td in rows[1].find_all("td")]
                    for header, value in zip(headers, values):
                        if header and value:
                            result[f"Sem {header}"] = value
            
            session.close()
            return result
            
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(backoff_factor * (attempt + 1))
            else:
                session.close()
                return None

def _safe_get_text(soup, selector, default="N/A"):
    """Helper function for safe text extraction"""
    try:
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else default
    except:
        return default

# Optimized sorting functions with caching
@functools.lru_cache(maxsize=128)
def sort_by_current_cgpa(df_hash):
    """Cached sorting function"""
    df = pd.read_json(df_hash)
    df["Sem Cur. CGPA"] = pd.to_numeric(df["Sem Cur. CGPA"], errors="coerce")
    return df.sort_values(by="Sem Cur. CGPA", ascending=False)

def sort_by_latest_semester_grade(df):
    """Optimized semester grade sorting"""
    sem_columns = [col for col in df.columns if col.startswith("Sem ")]
    
    if not sem_columns:
        return df
    
    # Vectorized operation for better performance
    df_numeric = df[sem_columns].apply(pd.to_numeric, errors='coerce')
    df["Latest Semester Grade"] = df_numeric.iloc[:, -1:].max(axis=1)
    
    sorted_df = df.sort_values(by="Latest Semester Grade", ascending=False)
    return sorted_df.drop(columns=["Latest Semester Grade"])




