import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List
from discovery.schemas import DiscoveredPaper
from langfuse.decorators import observe

logger = logging.getLogger(__name__)

@observe(as_type="span")
def search_arxiv(query: str, limit: int = 10) -> List[DiscoveredPaper]:
    """Search the ArXiv API over HTTPS to avoid 301 redirects."""
    try:
        # ArXiv API requires search_query format like 'all:query'
        safe_query = urllib.parse.quote(f"all:{query}")
        url = f"https://export.arxiv.org/api/query?search_query={safe_query}&start=0&max_results={limit}&sortBy=relevance&sortOrder=descending"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        
        # XML namespace for Atom
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        results = []
        for entry in root.findall('atom:entry', ns):
            paper_id = entry.find('atom:id', ns).text
            title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
            summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
            
            authors = []
            for author in entry.findall('atom:author', ns):
                name = author.find('atom:name', ns).text
                authors.append(name)
            
            if len(authors) > 5:
                authors = authors[:5] + ["et al."]
                
            pdf_url = None
            for link in entry.findall('atom:link', ns):
                if link.attrib.get('title') == 'pdf':
                    pdf_url = link.attrib.get('href')
                    break
                    
            if not pdf_url:
                pdf_url = paper_id.replace('abs', 'pdf') + '.pdf'
                
            paper = DiscoveredPaper(
                paper_id=paper_id,
                title=title,
                authors=authors,
                abstract=summary,
                url=paper_id,
                pdf_url=pdf_url
            )
            results.append(paper)
            
        return results
    except Exception as e:
        logger.error(f"Error querying ArXiv API: {e}")
        raise

