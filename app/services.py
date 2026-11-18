import os
import re
import requests
from flask import current_app

def clean_isbn(isbn_str):
    if not isbn_str:
        return ""
    # Strip spaces, hyphens, and make uppercase (for 'X' in ISBN-10)
    cleaned = re.sub(r'[^0-9X]', '', isbn_str.upper())
    return cleaned

def fetch_book_metadata(isbn):
    """
    Fetches book metadata given an ISBN.
    1. Tries OpenLibrary API
    2. Falls back to Google Books API
    Returns dict:
      {
        'success': bool,
        'source': 'OpenLibrary' | 'GoogleBooks' | None,
        'title': str,
        'authors': str,
        'publisher': str,
        'year': int,
        'category': str,
        'cover_url': str
      }
    """
    cleaned = clean_isbn(isbn)
    if not cleaned:
        return {'success': False, 'error': 'Invalid ISBN format'}

    # 1. Try OpenLibrary API
    try:
        ol_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{cleaned}&jscmd=data&format=json"
        resp = requests.get(ol_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            key = f"ISBN:{cleaned}"
            if key in data:
                b = data[key]
                title = b.get('title', '')
                authors_list = [a.get('name') for a in b.get('authors', []) if 'name' in a]
                authors = ', '.join(authors_list)
                publishers_list = [p.get('name') for p in b.get('publishers', []) if 'name' in p]
                publisher = ', '.join(publishers_list)
                
                # Extract year
                pub_date = b.get('publish_date', '')
                year = None
                match = re.search(r'\b(19\d\d|20\d\d)\b', str(pub_date))
                if match:
                    year = int(match.group(1))

                # Category / subjects
                subjects = [s.get('name') for s in b.get('subjects', [])[:3] if isinstance(s, dict) and 'name' in s]
                category = ', '.join(subjects) if subjects else "General"

                # Cover URL
                cover_url = ''
                if 'cover' in b:
                    cover_url = b['cover'].get('large') or b['cover'].get('medium') or b['cover'].get('small') or ''

                return {
                    'success': True,
                    'source': 'OpenLibrary',
                    'isbn': cleaned,
                    'title': title,
                    'authors': authors,
                    'publisher': publisher,
                    'year': year,
                    'category': category,
                    'cover_url': cover_url
                }
    except Exception as e:
        current_app.logger.warning(f"OpenLibrary API error for ISBN {cleaned}: {e}")

    # 2. Fallback to Google Books API
    try:
        gb_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{cleaned}"
        resp = requests.get(gb_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if items:
                vol = items[0].get('volumeInfo', {})
                title = vol.get('title', '')
                authors = ', '.join(vol.get('authors', []))
                publisher = vol.get('publisher', '')

                pub_date = vol.get('publishedDate', '')
                year = None
                match = re.search(r'\b(19\d\d|20\d\d)\b', str(pub_date))
                if match:
                    year = int(match.group(1))

                category = ', '.join(vol.get('categories', [])[:2]) or "General"
                image_links = vol.get('imageLinks', {})
                cover_url = image_links.get('thumbnail') or image_links.get('smallThumbnail') or ''
                if cover_url and cover_url.startswith('http://'):
                    cover_url = 'https://' + cover_url[7:]

                return {
                    'success': True,
                    'source': 'GoogleBooks',
                    'isbn': cleaned,
                    'title': title,
                    'authors': authors,
                    'publisher': publisher,
                    'year': year,
                    'category': category,
                    'cover_url': cover_url
                }
    except Exception as e:
        current_app.logger.warning(f"Google Books API error for ISBN {cleaned}: {e}")

    return {'success': False, 'error': 'Book metadata could not be fetched from external APIs.'}


def download_cover_locally(cover_url, isbn):
    """
    Downloads cover image and saves it to media/covers/<isbn>.jpg.
    Returns relative web path: 'covers/<isbn>.jpg' or None on failure.
    """
    if not cover_url:
        return None

    try:
        resp = requests.get(cover_url, timeout=6)
        if resp.status_code == 200 and len(resp.content) > 500:
            filename = f"{clean_isbn(isbn)}.jpg"
            covers_dir = current_app.config['COVERS_FOLDER']
            os.makedirs(covers_dir, exist_ok=True)
            save_path = os.path.join(covers_dir, filename)
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            return f"covers/{filename}"
    except Exception as e:
        current_app.logger.warning(f"Failed to download cover from {cover_url}: {e}")

    return None
