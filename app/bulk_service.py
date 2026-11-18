import io
import csv
from datetime import datetime
from app.extensions import db
from app.models import BookTitle, BookCopy
from app.services import clean_isbn, fetch_book_metadata, download_cover_locally

def process_bulk_csv(file_stream):
    """
    Reads CSV rows with headers: ISBN, Accession Number, Rack, Shelf (Title/Author optional).
    - Fetches metadata from OpenLibrary/Google Books if not present
    - Downloads and saves cover images locally in media/covers/
    - Checks accession number uniqueness per row
    Returns summary dict:
      {
        'total_rows': int,
        'success_count': int,
        'failed_count': int,
        'successes': list of dicts,
        'errors': list of dicts (row_num, isbn, accession_no, reason)
      }
    """
    stream = io.StringIO(file_stream.read().decode("UTF-8", errors="ignore"))
    reader = csv.DictReader(stream)

    total_rows = 0
    success_count = 0
    failed_count = 0
    successes = []
    errors = []

    # Normalize header keys
    if not reader.fieldnames:
        return {
            'total_rows': 0, 'success_count': 0, 'failed_count': 0,
            'successes': [], 'errors': [{'row': 0, 'reason': 'Empty or invalid CSV file format'}]
        }

    header_map = {}
    for col in reader.fieldnames:
        key = col.strip().lower().replace(' ', '_').replace('.', '')
        header_map[key] = col

    for row_idx, row in enumerate(reader, start=2):  # row 1 is header
        total_rows += 1
        
        # Extract fields
        isbn_val = ""
        acc_val = ""
        rack_val = ""
        shelf_val = ""
        title_val = ""
        author_val = ""

        for key, orig_col in header_map.items():
            val = row.get(orig_col, '').strip()
            if 'isbn' in key:
                isbn_val = val
            elif 'accession' in key or 'acc' in key:
                acc_val = val
            elif 'rack' in key:
                rack_val = val
            elif 'shelf' in key:
                shelf_val = val
            elif 'title' in key:
                title_val = val
            elif 'author' in key:
                author_val = val

        cleaned_isbn = clean_isbn(isbn_val)
        cleaned_acc = acc_val.upper()

        if not cleaned_isbn:
            failed_count += 1
            errors.append({'row': row_idx, 'isbn': isbn_val, 'accession': acc_val, 'reason': 'Missing or invalid ISBN'})
            continue

        if not cleaned_acc:
            failed_count += 1
            errors.append({'row': row_idx, 'isbn': cleaned_isbn, 'accession': acc_val, 'reason': 'Missing Accession Number'})
            continue

        # Check if accession number already exists in DB
        if BookCopy.query.filter_by(accession_no=cleaned_acc).first():
            failed_count += 1
            errors.append({'row': row_idx, 'isbn': cleaned_isbn, 'accession': cleaned_acc, 'reason': f'Accession Number "{cleaned_acc}" already exists in library inventory'})
            continue

        # Check if title exists, else fetch from API
        book_title = BookTitle.query.get(cleaned_isbn)
        if not book_title:
            # If title is in CSV, use it; otherwise fetch from OpenLibrary / Google Books
            meta = fetch_book_metadata(cleaned_isbn)
            t_text = title_val or (meta.get('title') if meta.get('success') else f"Book ISBN {cleaned_isbn}")
            a_text = author_val or (meta.get('authors') if meta.get('success') else "Unknown Author")
            pub_text = meta.get('publisher') if meta.get('success') else ""
            yr_val = meta.get('year') if meta.get('success') else None
            cat_val = meta.get('category') if meta.get('success') else "General"
            cover_url = meta.get('cover_url') if meta.get('success') else ""

            cover_path = None
            if cover_url:
                cover_path = download_cover_locally(cover_url, cleaned_isbn)

            book_title = BookTitle(
                isbn=cleaned_isbn,
                title=t_text,
                authors=a_text,
                publisher=pub_text,
                year=yr_val,
                category=cat_val,
                cover_path=cover_path
            )
            db.session.add(book_title)

        # Create physical copy
        new_copy = BookCopy(
            accession_no=cleaned_acc,
            isbn=cleaned_isbn,
            rack_no=rack_val or 'Rack A1',
            shelf_no=shelf_val or 'Shelf 1',
            status='Available'
        )
        db.session.add(new_copy)
        db.session.commit()

        success_count += 1
        successes.append({
            'row': row_idx,
            'isbn': cleaned_isbn,
            'accession': cleaned_acc,
            'title': book_title.title,
            'rack': rack_val,
            'shelf': shelf_val
        })

    return {
        'total_rows': total_rows,
        'success_count': success_count,
        'failed_count': failed_count,
        'successes': successes,
        'errors': errors
    }
