# TODAY.html for one day: only what you do by hand today, in your order (settings.today.order), with items marked
# "done": true in data/today.json left out. The full page with every item is written as TODAY-all.html.
# usage: python3 -I tools/build_today_focus.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit as K, build_today as B

B.write_all()
secs = B.sections(include_done=False)
order = [k for k in K.S['today']['order'] if k in B.TITLES] or list(B.TITLES)
chosen = [secs[k] for k in order if k in secs]
page = B.render(f"{K.S['today']['title']}: {K.now():%A %d %B %Y}", chosen,
                'Only your by-hand jobs, in your order. The full page with older items is TODAY-all.html in the same folder.')
open(f'{K.ROOT}/TODAY.html', 'w', encoding='utf-8').write(page)
print('TODAY.html', len(page), 'bytes; sections:', [(t, len(v)) for t, v in chosen])
