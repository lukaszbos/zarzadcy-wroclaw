import json
import os
import argparse
from datetime import datetime, timezone

SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dane', 'wroclaw', 'zarzadcy_wroclaw_full_details.json')
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')


def clean_place(p):
    reviews = []
    for r in p.get('reviews', []):
        ts = r.get('time', 0)
        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%d.%m.%Y') if ts else ''
        reviews.append({
            'author':    r.get('author_name', ''),
            'rating':    r.get('rating', ''),
            'timestamp': ts,
            'date':      date_str,
            'text':      r.get('text', '')[:600]
        })

    oh = p.get('opening_hours', {})
    hours = oh.get('weekday_text', []) if oh else []
    loc = p.get('geometry', {}).get('location', {})
    latest_ts = max((r['timestamp'] for r in reviews if r['timestamp']), default=0)

    return {
        'name':             p.get('name', ''),
        'address':          p.get('address', ''),
        'phone':            p.get('phone', '') or p.get('international_phone_number', ''),
        'website':          p.get('website', ''),
        'rating':           p.get('rating', 0),
        'reviews_count':    p.get('reviews_count', 0),
        'maps_url':         p.get('maps_url', ''),
        'status':           p.get('business_status', ''),
        'hours':            hours,
        'lat':              loc.get('lat'),
        'lng':              loc.get('lng'),
        'reviews':          reviews,
        'latest_review_ts': latest_ts
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()

    with open(SOURCE, encoding='utf-8') as f:
        raw = json.load(f)

    results = raw.get('results', [])
    if args.limit:
        results = results[:args.limit]

    cleaned = [clean_place(p) for p in results]
    output = {'generated_at': raw.get('generated_at', ''), 'total': len(cleaned), 'results': cleaned}

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Zapisano {len(cleaned)} firm -> {OUTPUT}")


if __name__ == '__main__':
    main()
