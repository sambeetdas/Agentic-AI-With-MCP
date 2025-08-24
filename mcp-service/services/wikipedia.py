import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, Any, Optional
import urllib.parse

class WikipediaService:

    def clean_text(self, text: str) -> str:
        """Clean and normalize text by removing extra whitespace and unwanted characters"""
        if not text:
            return ""
        # Remove citations like [1], [2], etc.
        text = re.sub(r'\[\d+\]', '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text.strip()

    def extract_revenue_from_text(self, text: str) -> Dict[str, str]:
        """Extract revenue information from text"""
        revenue_info = {}
        
        # Common revenue patterns
        patterns = [
            r'revenue[:\s]+.*?\$[\d,.]+ (?:billion|million|trillion)',
            r'\$[\d,.]+ (?:billion|million|trillion).*?revenue',
            r'total revenue.*?\$[\d,.]+',
            r'net revenue.*?\$[\d,.]+',
            r'annual revenue.*?\$[\d,.]+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                revenue_info['raw_text'] = matches[0]
                # Extract the dollar amount
                dollar_match = re.search(r'\$[\d,.]+ (?:billion|million|trillion)', matches[0], re.IGNORECASE)
                if dollar_match:
                    revenue_info['amount'] = dollar_match.group()
                break
        
        return revenue_info

    def extract_headcount_from_text(self, text: str) -> Dict[str, str]:
        """Extract employee/headcount information from text"""
        headcount_info = {}
        
        # Common employee patterns
        patterns = [
            r'employs?\s+(?:over\s+|approximately\s+|about\s+)?[\d,]+ (?:people|employees)',
            r'(?:over\s+|approximately\s+|about\s+)?[\d,]+ employees',
            r'workforce of (?:over\s+|approximately\s+|about\s+)?[\d,]+',
            r'staff of (?:over\s+|approximately\s+|about\s+)?[\d,]+',
            r'[\d,]+ (?:full-time )?(?:employees|workers|staff)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                headcount_info['raw_text'] = matches[0]
                # Extract the number
                number_match = re.search(r'[\d,]+', matches[0])
                if number_match:
                    headcount_info['count'] = number_match.group().replace(',', '')
                break
        
        return headcount_info

    def get_company_info_wikipedia(self, company_name: str) -> Dict[str, Any]:
        """
        Extract detailed company information from Wikipedia including revenue, headcount, headquarters
        
        Args:
            company_name: Name of the company
        
        Returns:
            Dictionary with extracted company information
        """
        
        # URL encode the company name
        encoded_name = urllib.parse.quote(company_name.replace(" ", "_"))
        
        # First, get the page content using Wikipedia API
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/html/{encoded_name}"
        
        try:
            response = requests.get(api_url, timeout=15) 
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            result = {
                "company_name": company_name,
                "wikipedia_url": f"https://en.wikipedia.org/wiki/{encoded_name}",
                "revenue": {},
                "headcount": {},
                "headquarters": {},
                "founded": "",
                "industry": "",
                "website": "",
                "ceo": "",
                "market_cap": {},
                "source": "Wikipedia"
            }
            
            # Extract infobox information
            infobox = soup.find('table', {'class': re.compile(r'infobox')})
            
            if infobox:
                # Extract information from infobox rows
                rows = infobox.find_all('tr')
                
                for row in rows:
                    header = row.find('th')
                    data = row.find('td')
                    
                    if header and data:
                        header_text = self.clean_text(header.get_text()).lower()
                        data_text = self.clean_text(data.get_text())
                        
                        # Revenue patterns
                        if any(keyword in header_text for keyword in ['revenue', 'turnover', 'sales']):
                            result['revenue'] = {
                                'raw_text': data_text,
                                'field_name': header_text
                            }
                            # Try to extract amount
                            dollar_match = re.search(r'\$[\d,.]+ (?:billion|million|trillion)', data_text, re.IGNORECASE)
                            if dollar_match:
                                result['revenue']['amount'] = dollar_match.group()
                        
                        # Employee/headcount patterns
                        elif any(keyword in header_text for keyword in ['employees', 'workforce', 'staff']):
                            result['headcount'] = {
                                'raw_text': data_text,
                                'field_name': header_text
                            }
                            # Extract number
                            number_match = re.search(r'[\d,]+', data_text)
                            if number_match:
                                result['headcount']['count'] = number_match.group().replace(',', '')
                        
                        # Headquarters patterns
                        elif any(keyword in header_text for keyword in ['headquarters', 'head office', 'hq']):
                            result['headquarters'] = {
                                'raw_text': data_text,
                                'field_name': header_text
                            }
                        
                        # Other useful information
                        elif 'founded' in header_text:
                            result['founded'] = data_text
                        elif 'industry' in header_text or 'industries' in header_text:
                            result['industry'] = data_text
                        elif 'website' in header_text:
                            result['website'] = data_text
                        elif any(keyword in header_text for keyword in ['ceo', 'chief executive']):
                            result['ceo'] = data_text
                        elif 'market cap' in header_text:
                            result['market_cap'] = {
                                'raw_text': data_text,
                                'field_name': header_text
                            }
            
            # If infobox didn't provide revenue/headcount, search in article text
            if not result['revenue'] or not result['headcount']:
                # Get the full article text
                paragraphs = soup.find_all('p')
                full_text = ' '.join([p.get_text() for p in paragraphs[:10]])  # First 10 paragraphs
                
                if not result['revenue']:
                    revenue_info = self.extract_revenue_from_text(full_text)
                    if revenue_info:
                        result['revenue'] = revenue_info
                
                if not result['headcount']:
                    headcount_info = self.extract_headcount_from_text(full_text)
                    if headcount_info:
                        result['headcount'] = headcount_info
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {"error": f"Wikipedia request failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Error processing Wikipedia data: {str(e)}"}

    