#!/usr/bin/env python3
"""
FIFA World Cup 2026 Dashboard Auto-Updater
Fetches live scores and deploys to Netlify automatically.
Run via Windows Task Scheduler every 5 minutes.
"""

import requests
import json
import os
import re
import sys
import zipfile
import io
import shutil
import glob
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
CONFIG_FILE  = SCRIPT_DIR / 'wc2026_config.json'
HTML_TEMPLATE = SCRIPT_DIR / 'wc2026_dashboard.html'
LOG_FILE     = SCRIPT_DIR / 'wc2026_updater.log'

GITHUB_USER = 'shotakdecsix-oss'
GITHUB_REPO = 'wc2026-dashboard'
JST = timezone(timedelta(hours=9))

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    )
}

# ── Logging ──────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S JST')
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', 'replace').decode())
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# ── Config load/save ─────────────────────────────────────────────────────────
def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    return {}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')


# ── Flag / team helpers ───────────────────────────────────────────────────────
FLAG_MAP = {
    'JPN':'🇯🇵','NLD':'🇳🇱','NED':'🇳🇱','SWE':'🇸🇪','TUN':'🇹🇳','USA':'🇺🇸',
    'CAN':'🇨🇦','MEX':'🇲🇽','BRA':'🇧🇷','ARG':'🇦🇷','FRA':'🇫🇷','ESP':'🇪🇸',
    'GER':'🇩🇪','DEU':'🇩🇪','ENG':'🏴󠁧󠁢󠁥󠁮󠁧󠁿','PRT':'🇵🇹','ITA':'🇮🇹','BEL':'🇧🇪',
    'CRO':'🇭🇷','URU':'🇺🇾','COL':'🇨🇴','ECU':'🇪🇨','CHL':'🇨🇱','PER':'🇵🇪',
    'MAR':'🇲🇦','SEN':'🇸🇳','NGA':'🇳🇬','CMR':'🇨🇲','EGY':'🇪🇬','GHA':'🇬🇭',
    'CIV':'🇨🇮','SAU':'🇸🇦','KSA':'🇸🇦','IRQ':'🇮🇶','AUS':'🇦🇺','KOR':'🇰🇷',
    'POL':'🇵🇱','UKR':'🇺🇦','CZE':'🇨🇿','SRB':'🇷🇸','DEN':'🇩🇰','TUR':'🇹🇷',
    'CHE':'🇨🇭','SUI':'🇨🇭','NZL':'🇳🇿','JAM':'🇯🇲','BHR':'🇧🇭','SVN':'🇸🇮',
    'PAN':'🇵🇦','ALG':'🇩🇿','CRC':'🇨🇷','RSA':'🇿🇦','QAT':'🇶🇦','NOR':'🇳🇴',
    'SWZ':'🇸🇿','HAI':'🇭🇹','SCO':'🏴󠁧󠁢󠁳󠁣󠁴󠁿','PAR':'🇵🇾','BOH':'🇧🇦','UZB':'🇺🇿',
    'CPV':'🇨🇻','URY':'🇺🇾','DRC':'🇨🇩','GRD':'🇬🇩','AUT':'🇦🇹','JOR':'🇯🇴',
    'ALG':'🇩🇿','HTI':'🇭🇹',
}

TEAM_JP = {
    'Japan':'日本','Netherlands':'オランダ','Sweden':'スウェーデン','Tunisia':'チュニジア',
    'France':'フランス','Mexico':'メキシコ','Belgium':'ベルギー','Algeria':'アルジェリア',
    'Brazil':'ブラジル','Colombia':'コロンビア','Ecuador':'エクアドル','Iraq':'イラク',
    'Spain':'スペイン','Germany':'ドイツ','Costa Rica':'コスタリカ','Slovenia':'スロベニア',
    'Argentina':'アルゼンチン','Chile':'チリ','Croatia':'クロアチア','Peru':'ペルー',
    'United States':'USA','USA':'USA','Canada':'カナダ','Uruguay':'ウルグアイ',
    'Panama':'パナマ','Portugal':'ポルトガル','England':'イングランド','Morocco':'モロッコ',
    'Jamaica':'ジャマイカ','Italy':'イタリア','Egypt':'エジプト','New Zealand':'ニュージーランド',
    'South Korea':'韓国','Korea Republic':'韓国','Poland':'ポーランド',
    'Saudi Arabia':'サウジアラビア','Ghana':'ガーナ','Australia':'オーストラリア',
    'Ukraine':'ウクライナ','Senegal':'セネガル','Nigeria':'ナイジェリア','Cameroon':'カメルーン',
    "Ivory Coast":'コートジボワール',"Côte d'Ivoire":'コートジボワール',
    'Czechia':'チェコ','Czech Republic':'チェコ','Serbia':'セルビア','Denmark':'デンマーク',
    'Turkey':'トルコ','Türkiye':'トルコ','Switzerland':'スイス','Bahrain':'バーレーン',
    'South Africa':'南アフリカ','Qatar':'カタール','Norway':'ノルウェー','Haiti':'ハイチ',
    'Scotland':'スコットランド','Paraguay':'パラグアイ','Bosnia and Herzegovina':'ボスニア',
    'Bosnia & Herzegovina':'ボスニア','Uzbekistan':'ウズベキスタン','Cape Verde':'カーボベルデ',
    'DR Congo':'コンゴ民主共和国','Democratic Republic of Congo':'コンゴ民主共和国',
    'Austria':'オーストリア','Jordan':'ヨルダン','Croatia':'クロアチア',
    'Iran':'イラン','New Zealand':'ニュージーランド','Belgium':'ベルギー',
}

def get_flag(abbr):
    return FLAG_MAP.get(abbr, '🏳️')

def get_jp(name):
    return TEAM_JP.get(name, name)


# ── ESPN fetch ────────────────────────────────────────────────────────────────
def fetch_espn():
    """Fetch all WC2026 events using date-range query to get full schedule."""
    from datetime import date as _date
    base = 'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?limit=150&dates='
    seen, events = set(), []

    # First try: single range query covering entire tournament
    try:
        r = requests.get(base + '20260611-20260720', headers=HEADERS, timeout=15)
        for ev in r.json().get('events', []):
            if ev['id'] not in seen:
                seen.add(ev['id'])
                events.append(ev)
        log(f"ESPN range query: {len(events)} events")
    except Exception as e:
        log(f"ESPN range query failed: {e}")

    # Fallback: daily queries for every day in tournament (if range returned too few)
    if len(events) < 20:
        log("Falling back to daily queries...")
        d = _date(2026, 6, 11)
        end = _date(2026, 7, 20)
        while d <= end:
            ds = d.strftime('%Y%m%d')
            try:
                r = requests.get(base + ds, headers=HEADERS, timeout=10)
                for ev in r.json().get('events', []):
                    if ev['id'] not in seen:
                        seen.add(ev['id'])
                        events.append(ev)
            except Exception:
                pass
            d += timedelta(days=1)
        log(f"ESPN daily queries total: {len(events)} events")

    log(f"ESPN: {len(events)} events fetched")
    return events


def transform_espn(events, team_to_group=None):
    """Transform ESPN raw events into dashboard data format."""
    teams_map = {}
    matches   = []
    for ev in events:
        comp = (ev.get('competitions') or [{}])[0]
        # group: try notes first
        group_note = ''
        for n in comp.get('notes', []):
            if n.get('headline') and re.search(r'Group [A-L]', n['headline'], re.I):
                group_note = n['headline']
        gm   = re.search(r'Group ([A-L])', group_note, re.I)
        g_id_from_notes = gm.group(1).upper() if gm else None

        comps = comp.get('competitors', [])
        home = next((c for c in comps if c['homeAway'] == 'home'), None)
        away = next((c for c in comps if c['homeAway'] == 'away'), None)
        if not home or not away:
            continue

        h_name = home['team']['displayName']
        a_name = away['team']['displayName']

        # Determine group: notes → standings lookup → slug check → KO
        if g_id_from_notes:
            g_id = g_id_from_notes
        elif team_to_group:
            g_id = team_to_group.get(h_name) or team_to_group.get(a_name) or 'KO'
        else:
            slug = ev.get('season', {}).get('slug', '')
            g_id = 'GROUP' if 'group' in slug.lower() else 'KO'
        h_jp   = get_jp(h_name)
        a_jp   = get_jp(a_name)
        h_flag = get_flag(home['team']['abbreviation'])
        a_flag = get_flag(away['team']['abbreviation'])

        sn = comp.get('status', {}).get('type', {}).get('name', '')
        FINISHED_STATUSES = {'STATUS_FINAL', 'STATUS_FULL_TIME',
                             'STATUS_FINAL_AET', 'STATUS_FINAL_PEN'}
        if sn in FINISHED_STATUSES:
            status = 'FINISHED'
        elif sn in ('STATUS_IN_PROGRESS', 'STATUS_HALFTIME'):
            status = 'LIVE'
        else:
            status = 'SCHEDULED'

        score = None
        if status != 'SCHEDULED':
            try:
                score = {'home': int(home.get('score', 0) or 0),
                         'away': int(away.get('score', 0) or 0)}
            except Exception:
                pass

        utc = datetime.fromisoformat(ev['date'].replace('Z', '+00:00'))
        jst = utc.astimezone(JST)
        date_str = jst.strftime('%Y-%m-%d')
        time_str = jst.strftime('%H:%M')
        is_japan = h_name == 'Japan' or a_name == 'Japan'

        matches.append({
            'id': ev['id'],
            'homeTeam': {'name': h_jp, 'flag': h_flag},
            'awayTeam': {'name': a_jp, 'flag': a_flag},
            'homeTeamEn': h_name,
            'awayTeamEn': a_name,
            'group': g_id, 'date': date_str, 'kickoff': time_str,
            'venue': comp.get('venue', {}).get('fullName', ''),
            'status': status, 'score': score, 'isJapan': is_japan,
        })

        # standings calc
        if g_id in ('KO', 'GROUP') or status != 'FINISHED' or not score:
            continue
        for (raw, jp, fl, is_home) in [
                (h_name, h_jp, h_flag, True),
                (a_name, a_jp, a_flag, False)]:
            if g_id not in teams_map:
                teams_map[g_id] = {}
            if raw not in teams_map[g_id]:
                teams_map[g_id][raw] = {'name':jp,'flag':fl,'played':0,
                                         'won':0,'drawn':0,'lost':0,
                                         'gf':0,'ga':0,'pts':0}
            t  = teams_map[g_id][raw]
            tf = score['home'] if is_home else score['away']
            ta = score['away'] if is_home else score['home']
            t['played'] += 1; t['gf'] += tf; t['ga'] += ta
            if tf > ta:   t['won']   += 1; t['pts'] += 3
            elif tf == ta: t['drawn'] += 1; t['pts'] += 1
            else:          t['lost']  += 1

    groups = [
        {'id': g, 'teams': sorted(list(tm.values()),
                                   key=lambda x: (-x['pts'], -(x['gf']-x['ga']), -x['gf']))}
        for g, tm in sorted(teams_map.items())
    ]
    return {
        'groups':  groups  if groups  else None,
        'matches': matches if matches else None,
        'scorers': None,
        'updatedAt': datetime.now(JST).strftime('%Y-%m-%d %H:%M JST'),
        'source': 'ESPN',
    }


def fetch_espn_standings():
    """Fetch group standings from ESPN standings API."""
    url = 'https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings'
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            log(f"ESPN standings: HTTP {r.status_code}")
            return None
        children = r.json().get('children', [])
        groups = []
        for child in children:
            gname = child.get('name', '')  # "Group A"
            gm = re.search(r'Group ([A-L])', gname, re.I)
            if not gm:
                continue
            g_id = gm.group(1).upper()
            entries = child.get('standings', {}).get('entries', [])
            teams = []
            for e in entries:
                team = e.get('team', {})
                tname = team.get('displayName', '')
                abbr  = team.get('abbreviation', '')
                stats = {s['name']: s.get('displayValue', s.get('value', 0))
                         for s in e.get('stats', []) if 'name' in s}
                def sv(k):
                    try: return int(float(stats.get(k, 0) or 0))
                    except: return 0
                teams.append({
                    'name':   get_jp(tname),
                    'flag':   get_flag(abbr),
                    'played': sv('gamesPlayed'),
                    'won':    sv('wins'),
                    'drawn':  sv('ties'),
                    'lost':   sv('losses'),
                    'gf':     sv('pointsFor'),
                    'ga':     sv('pointsAgainst'),
                    'pts':    sv('points'),
                })
            if teams:
                groups.append({'id': g_id, 'teams': teams})
        log(f"ESPN standings: {len(groups)} groups")
        return groups if groups else None
    except Exception as e:
        log(f"ESPN standings error: {e}")
        return None


# ── SofaScore fetch ───────────────────────────────────────────────────────────
def fetch_sofascore():
    """
    Fetch WC2026 match results from SofaScore's unofficial API.
    Fetches day-by-day from Jun 11 onward and collects FINISHED games.
    """
    results = []
    seen = set()
    today = datetime.now(JST).date()
    start = datetime(2026, 6, 11).date()
    days_done = (today - start).days + 1

    for i in range(days_done):
        d = start + timedelta(days=i)
        url = f'https://www.sofascore.com/api/v1/sport/football/events/date/{d}'
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                log(f"  SofaScore {d}: HTTP {r.status_code}")
                continue
            for ev in r.json().get('events', []):
                # Filter for FIFA World Cup
                tn = (ev.get('tournament', {})
                        .get('uniqueTournament', {})
                        .get('name', ''))
                if 'World Cup' not in tn:
                    continue
                st = ev.get('status', {}).get('type', '')
                if st != 'finished':
                    continue
                h = ev.get('homeTeam', {}).get('name', '')
                a = ev.get('awayTeam', {}).get('name', '')
                hs = ev.get('homeScore', {}).get('current')
                as_ = ev.get('awayScore', {}).get('current')
                if h and a and hs is not None and as_ is not None:
                    key = (h.lower(), a.lower())
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            'home': h, 'away': a,
                            'homeScore': int(hs), 'awayScore': int(as_),
                            'status': 'FINISHED',
                        })
        except Exception as e:
            log(f"  SofaScore {d}: {e}")

    log(f"SofaScore: {len(results)} finished matches")
    return results


def fetch_fotmob():
    """
    Fallback: Fotmob unofficial API for WC2026 results.
    """
    results = []
    today_str = datetime.now(JST).strftime('%Y%m%d')
    url = f'https://www.fotmob.com/api/matches?date={today_str}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        for league in data.get('leagues', []):
            if 'World Cup' not in league.get('name', ''):
                continue
            for m in league.get('matches', []):
                if m.get('status', {}).get('finished') is not True:
                    continue
                h = m.get('home', {}).get('name', '')
                a = m.get('away', {}).get('name', '')
                hs = m.get('home', {}).get('score')
                as_ = m.get('away', {}).get('score')
                if h and a and hs is not None and as_ is not None:
                    results.append({
                        'home': h, 'away': a,
                        'homeScore': int(hs), 'awayScore': int(as_),
                        'status': 'FINISHED',
                    })
        log(f"Fotmob: {len(results)} finished matches")
    except Exception as e:
        log(f"Fotmob: {e}")
    return results


FIFA_CHANNEL_ID = 'UCpcTrCXblq78GZrTUTLWeBw'

# Alternative English keywords for team name matching in video titles
TEAM_TITLE_ALIASES = {
    'South Korea':          ['korea', 'korea republic'],
    'Bosnia-Herzegovina':   ['bosnia'],
    'United States':        ['usa', 'united states'],
    'Ivory Coast':          ['cote d', 'ivory coast'],
    'DR Congo':             ['congo'],
    'Czech Republic':       ['czechia', 'czech'],
    'North Macedonia':      ['macedonia'],
    'Trinidad and Tobago':  ['trinidad'],
    'Saudi Arabia':         ['saudi'],
    'New Zealand':          ['new zealand'],
}

def _team_words(name):
    """Return a list of lowercase keywords to search for in a video title."""
    name_l = name.lower()
    aliases = TEAM_TITLE_ALIASES.get(name, [])
    # Also add first word of team name as a fallback
    first_word = name_l.split()[0]
    return list({name_l, first_word} | set(aliases))


def fetch_fifa_recent_videos(yt_key, max_videos=100):
    """Fetch recent videos from FIFA official YouTube channel via uploads playlist.
    Costs ~2 API units regardless of how many matches we need to cover."""
    try:
        # Get uploads playlist ID
        r = requests.get('https://www.googleapis.com/youtube/v3/channels',
                         params={'part': 'contentDetails', 'id': FIFA_CHANNEL_ID, 'key': yt_key},
                         timeout=15)
        playlist_id = r.json()['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        videos, page_token = [], None
        while len(videos) < max_videos:
            params = {'part': 'snippet', 'playlistId': playlist_id,
                      'maxResults': min(50, max_videos - len(videos)), 'key': yt_key}
            if page_token:
                params['pageToken'] = page_token
            r = requests.get('https://www.googleapis.com/youtube/v3/playlistItems',
                             params=params, timeout=15)
            data = r.json()
            for item in data.get('items', []):
                snip = item['snippet']
                vid_id = snip.get('resourceId', {}).get('videoId')
                if vid_id:
                    videos.append({'id': vid_id, 'title': snip['title'],
                                   'thumb': snip['thumbnails'].get('medium', {}).get('url', '')})
            page_token = data.get('nextPageToken')
            if not page_token:
                break
        log(f"FIFA YouTube: fetched {len(videos)} recent videos")
        return videos
    except Exception as e:
        log(f"FIFA YouTube fetch error: {e}")
        return []


def find_match_video(videos, h_name, a_name, mode='highlight'):
    """Match a video from the FIFA channel list to a specific match.
    mode='highlight': prefers 'Highlights |' prefix.
    mode='preview':   prefers 'Preview', 'Match Preview', or 'Train Before' titles."""
    h_kws = _team_words(h_name)
    a_kws = _team_words(a_name)

    def title_has(title_l, kws):
        return any(k in title_l for k in kws)

    # Score each video
    scored = []
    for v in videos:
        tl = v['title'].lower()
        if not (title_has(tl, h_kws) and title_has(tl, a_kws)):
            continue
        if mode == 'highlight':
            score = 3 if tl.startswith('highlights |') else \
                    2 if 'highlights' in tl else 1
        else:
            score = 3 if 'match preview' in tl else \
                    2 if 'preview' in tl else \
                    1 if ('train before' in tl or 'prepare' in tl) else 0
        scored.append((score, v))

    if not scored:
        return []
    scored.sort(key=lambda x: -x[0])
    return [scored[0][1]]


def merge_scores_into_espn(espn_data, ext_results, source_name):
    """
    Overlay external scores onto ESPN schedule data.
    Matches by English team name reverse-mapped from JP.
    """
    if not espn_data.get('matches') or not ext_results:
        return espn_data

    # Build lookup by lowercase name
    lookup = {}
    for b in ext_results:
        key = (b['home'].strip().lower(), b['away'].strip().lower())
        lookup[key] = b

    finished_count = 0
    for m in espn_data['matches']:
        h_en = next((k for k, v in TEAM_JP.items()
                     if v == m['homeTeam']['name']), m['homeTeam']['name'])
        a_en = next((k for k, v in TEAM_JP.items()
                     if v == m['awayTeam']['name']), m['awayTeam']['name'])
        b = lookup.get((h_en.lower(), a_en.lower()))
        if b:
            m['status'] = 'FINISHED'
            m['score']  = {'home': b['homeScore'], 'away': b['awayScore']}
            finished_count += 1

    log(f"{source_name} merge: {finished_count} matches updated")
    espn_data['source'] = f'ESPN+{source_name}'
    return espn_data


# ── ESPN match stats (shots / possession) ────────────────────────────────────
def fetch_espn_match_stats(event_id):
    """Fetch shot stats from ESPN event summary API for a single match."""
    url = (f'https://site.api.espn.com/apis/site/v2/sports/soccer/'
           f'fifa.world/summary?event={event_id}')
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        d = r.json()
        boxscore = d.get('boxScore') or d.get('boxscore') or {}
        teams = boxscore.get('teams') or boxscore.get('players') or []
        if len(teams) < 2:
            return None

        def _stat(team_obj, *keys):
            for key in keys:
                for s in (team_obj.get('statistics') or []):
                    if s.get('name') == key:
                        try:
                            return float(s.get('displayValue', 0) or 0)
                        except Exception:
                            return 0.0
            return None

        h, a = teams[0], teams[1]
        result = {}
        for keys, out_h, out_a in [
            (('shotsTotal','totalShots','shots'),                        'hShots',    'aShots'),
            (('shotsOnTarget','onTargetShotsTotal','shotsOnGoal'),       'hOnTarget', 'aOnTarget'),
            (('possessionPct','possession'),                             'hPoss',     'aPoss'),
            (('totalPasses','passes','passAttempts','totalPassAttempts'),'hPasses',   'aPasses'),
            (('accuratePasses','passesAccurate'),                        'hAccPasses','aAccPasses'),
        ]:
            hv = _stat(h, *keys)
            av = _stat(a, *keys)
            if hv is not None or av is not None:
                result[out_h] = hv or 0
                result[out_a] = av or 0
        return result if result else None
    except Exception as e:
        log(f'fetch_espn_match_stats({event_id}): {e}')
        return None


# ── HTML injection & Netlify deploy ───────────────────────────────────────────
INJECT_MARKER = '/* __WC2026_LIVE_DATA__ */null'

def inject_data(html: str, data: dict) -> str:
    """Replace the marker in HTML with serialised live data."""
    json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    replacement = f'/* __WC2026_LIVE_DATA__ */ {json_str}'
    if INJECT_MARKER in html:
        return html.replace(INJECT_MARKER, replacement, 1)
    # Fallback
    return html.replace(
        '// ==================== INIT ====================',
        f'var __WC2026_LIVE_DATA__={json_str};\n// ==================== INIT ====================',
        1
    )


def deploy_to_github(html_content: str, token: str) -> bool:
    """Commit index.html to GitHub Pages repo via API."""
    import base64
    url  = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/index.html'
    hdrs = {'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'}
    # Get current file SHA (required for updates)
    sha = None
    try:
        r = requests.get(url, headers=hdrs, timeout=15)
        if r.status_code == 200:
            sha = r.json().get('sha')
    except Exception as e:
        log(f"GitHub SHA lookup error: {e}")

    content_b64 = base64.b64encode(html_content.encode('utf-8')).decode()
    payload = {
        'message': f'Update dashboard {datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")}',
        'content': content_b64,
    }
    if sha:
        payload['sha'] = sha

    try:
        r = requests.put(url, headers=hdrs, json=payload, timeout=60)
        if r.status_code in (200, 201):
            page_url = f'https://{GITHUB_USER}.github.io/{GITHUB_REPO}/'
            log(f"GitHub Pages deploy OK → {page_url}")
            return True
        else:
            log(f"GitHub deploy FAILED {r.status_code}: {r.text[:300]}")
            return False
    except Exception as e:
        log(f"GitHub deploy error: {e}")
        return False



# ── AI Analysis ──────────────────────────────────────────────────────────────
def generate_ai_analysis(data, cfg):
    """Call Claude API to generate AI analysis text; returns dict or None."""
    anthropic_key = cfg.get('anthropic_key', '')
    if not anthropic_key:
        log("AI分析: anthropic_key not set in config. Skipping.")
        return None

    try:
        import importlib
        if importlib.util.find_spec('anthropic') is None:
            log("AI分析: installing anthropic package...")
            import subprocess
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', 'anthropic',
                 '--break-system-packages', '-q'],
                check=True
            )
        import anthropic
    except Exception as e:
        log(f"AI分析: anthropic import failed: {e}")
        return None

    matches  = data.get('matches') or []
    groups   = data.get('groups') or []
    standings = data.get('standings') or []

    now_jst = datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')

    # ── Recent finished matches (last 10) ────────────────────────────────────
    finished = [m for m in matches if m.get('status') == 'FINISHED']
    finished_sorted = sorted(
        finished,
        key=lambda m: m.get('utcDate', ''),
        reverse=True
    )
    recent_lines = []
    for m in finished_sorted[:10]:
        h  = m.get('homeTeam', {}).get('name', '?')
        a  = m.get('awayTeam', {}).get('name', '?')
        sc = m.get('score') or {}
        hs = sc.get('home', '?')
        as_ = sc.get('away', '?')
        grp = m.get('group', '')
        date = m.get('utcDate', '')[:10]
        recent_lines.append(f"  {h} {hs}-{as_} {a}  (グループ{grp} / {date})")
    recent_matches_text = '\n'.join(recent_lines) if recent_lines else '  データなし'

    # ── Group standings ───────────────────────────────────────────────────────
    group_standing_lines = []
    # Prefer explicit standings data; fall back to groups array
    if standings:
        for grp in standings:
            gid  = grp.get('group', grp.get('id', ''))
            rows = grp.get('table') or grp.get('teams') or []
            cols = []
            for t in rows:
                name = t.get('team', {}).get('name', '') or t.get('name', '')
                pts  = t.get('points', t.get('pts', 0))
                gf   = t.get('goalsFor', t.get('gf', 0))
                ga   = t.get('goalsAgainst', t.get('ga', 0))
                cols.append(f"{name}({pts}pt {gf}-{ga})")
            group_standing_lines.append(f"  グループ{gid}: " + ' / '.join(cols))
    elif groups:
        for g in groups:
            gid   = g.get('id', '')
            teams = g.get('teams') or []
            cols  = [
                f"{t.get('name','')}({t.get('pts',0)}pt)"
                for t in teams
            ]
            group_standing_lines.append(f"  グループ{gid}: " + ' / '.join(cols))
    group_standings_text = '\n'.join(group_standing_lines) if group_standing_lines else '  データなし'

    # ── Stats summary (shots / possession) ───────────────────────────────────
    total_goals = sum(
        (m.get('score') or {}).get('home', 0) or 0
        + (m.get('score') or {}).get('away', 0) or 0
        for m in finished
    )
    stats_lines = []
    if finished:
        stats_lines.append(f"  完了試合数: {len(finished)}")
        stats_lines.append(f"  総得点: {total_goals}  (平均 {total_goals/len(finished):.2f}点/試合)")
    # Shot/possession data (if available in match objects)
    shots_data = [
        m for m in finished
        if m.get('stats') or m.get('homeShots') is not None
    ]
    if shots_data:
        stats_lines.append(f"  スタッツ付き試合: {len(shots_data)}件")
    stats_summary = '\n'.join(stats_lines) if stats_lines else '  詳細スタッツ未取得'

    # ── FIFA Rankings (June 2026) ─────────────────────────────────────────────
    FIFA_RANKS_TEXT = (
        "アルゼンチン1位、スペイン2位、フランス3位、イングランド4位、"
        "ポルトガル5位、ブラジル6位、モロッコ7位、オランダ8位、"
        "コロンビア9位、ドイツ10位、クロアチア12位、メキシコ13位、"
        "アメリカ16位、日本18位、カナダ19位、韓国22位、セネガル23位"
    )

    # ── Build shared context string ───────────────────────────────────────────
    WC_HISTORY = """
### 過去ワールドカップ優勝実績
- ブラジル: 5回優勝 (1958, 62, 70, 94, 2002) — 最多優勝国
- ドイツ: 4回 (1954, 74, 90, 2014)
- イタリア: 4回 (1934, 38, 82, 2006)
- アルゼンチン: 3回 (1978, 86, 2022) — 前回王者
- フランス: 2回 (1998, 2018)
- ウルグアイ: 2回 (1930, 50)
- イングランド: 1回 (1966)
- スペイン: 1回 (2010)
- 日本: ベスト16 (2002, 10, 22)、グループ突破７回

### 中心選手と注目点（2026年時点）
- メッシ（アルゼンチン）: 38歳、前回大会MVP、コンディションが鍵
- エムバペ（フランス）: 27歳、絶対的エース、スペインへ移籍後初W杯
- ロナウド（ポルトガル）: 41歳、サウジリーグ。体力面に疑問符
- ヴィニシウス（ブラジル）: 25歳、世界最高レベルのドリブラー
- ベリンガム（イングランド）: 22歳、レアルで急成長
- ラッシュフォード（イングランド）: 怪我明け
- 久保建英（日本）: バルセロナで台頭、攻撃の軸
- 前田大然（日本）: スプリント能力、チェイシングの要
- サカ（イングランド）: アーセナルの主力、安定したパフォーマンス
- ムシアラ（ドイツ）: 21歳、バイエルンでの活躍継続

### WC2026大会形式
- 12グループ（A～L）× 4チーム = 48チーム
- 各グループ1位・2位(24チーム) + グループ3位上位8チーム → ラウンド32
- グループ4位(12チーム)は全員敗退確定
- グループ3位12チームのうち、成績下位4チームが敗退
- 3位同士の比較基準: 勝ち点 → 得失点差 → 総得点
"""

    context = f"""## WC2026 現況データ（{now_jst}時点）

### 直近の試合結果（最新10試合）
{recent_matches_text}

### グループ別順位（暫定）
{group_standings_text}

### 主要チームFIFAランキング（2026年6月時点）
{FIFA_RANKS_TEXT}

### スタッツ傾向
{stats_summary}

{WC_HISTORY}
"""

    # ── Prompts ───────────────────────────────────────────────────────────────
    prompts = {
        'groupPrediction': (
            context
            + "\n## タスク\n"
            "WC2026全12グループ(A～L)の突破予想をしてください。\n\n"
            "【STEP 1】各グループの1〜4位を予想し、各チームに必ず予想理由（一言15字以内）を添えてください。\n"
            "理由の省略は禁止。以下の例のフォーマット通りに出力してください：\n\n"
            "グループ例:\n"
            "- 1位: ブラジル — W杯実績と攻撃力が群を抜く（自動通過）\n"
            "- 2位: ドイツ — 堅守速攻で安定した勝ち点（自動通過）\n"
            "- 3位: チェコ — 個人技はあるが総合力で一歩及ばず（3位通過争い参加）\n"
            "- 4位: パナマ — 格上相手に得点力が課題（最下位敗退）\n\n"
            "グループA～Lの12グループ全てを上記フォーマットで出力してください。\n\n"
            "---\n"
            "【STEP 2】自分が上で3位と予想した12チームを列挙（必ず記入）：\n"
            "- A-3位: \n- B-3位: \n- C-3位: \n- D-3位: \n- E-3位: \n- F-3位: \n"
            "- G-3位: \n- H-3位: \n- I-3位: \n- J-3位: \n- K-3位: \n- L-3位: \n\n"
            "---\n"
            "【STEP 3】STEP 2の12チームの中から、勝ち点・得失点差・総得点が最も劣ると予想される4チームを指定（STEP 2のチーム名のみ使用、決してSTEP 1の4位チームを含めない）：\n\n"
            "## 3位チーム敗退予想（全12グループの3位から4チーム）\n"
            "敗退予想:\n"
            "- **[STEP 2に記載した3位チーム名]**（理由）\n"
            "- **[STEP 2に記載した3位チーム名]**（理由）\n"
            "- **[STEP 2に記載した3位チーム名]**（理由）\n"
            "- **[STEP 2に記載した3位チーム名]**（理由）\n\n"
            "現在の大会結果データを最大限活用し、未終了グループは現時点の結果から傾向を分析して予想してください。"
            "回答は日本語で。**キーワード**は太字で。"
        ),
                'japanScenario': (
            context
            + "\n## タスク\n"
            "日本代表（FIFAランク18位）がグループを突破するための**具体的シナリオ**を分析してください。\n"
            "久保建英、前田大然、遠藤航などの主力選手の状態と、日本のグループ突破に必要な条件を具体的に分析してください。\n"
            "直近の試合結果とグループ内の対戦相手のランキングを踏まえ、\n"
            "必要勝ち点・有利な点・リスクを明示してください。250字以内で日本語で。"
        ),
        'winnerPrediction': (
            context
            + "\n## タスク\n"
            "優勝候補トップ3と根拠（FIFAランキング・WC実績・主力選手の状態）を挙げてください。\n"
            "ダークホース1〜2カ国と、グループ敗退予想のランク上位国も記載してください。\n"
            "300字以内で日本語で。**キーワード**は太字で。"
        ),
        'bracketPrediction': (
            context
            + "\n## タスク\n"
            "WC2026のノックアウトトーナメント予想をJSON形式で出力してください。\n"
            "グループ各1位・2位（計24チーム）+ 3位上位8チームの計32チームで構成されます。\n"
            "現在の試合結果と傾向から、合理的な予想を行ってください。\n\n"
            "以下の構造のJSONのみ出力してください（マークダウン・コードブロック・説明文は一切不要）：\n\n"
            '{"r32":[{"home":"チームA","away":"チームB","winner":"チームA"},...],'
            '"r16":[...8試合...],"qf":[...4試合...],"sf":[...2試合...],'
            '"final":{"home":"X","away":"Y","winner":"X"},'
            '"third":{"home":"P","away":"Q","winner":"P"},'
            '"champion":"X"}'
            "\n\nルール：\n"
            "- r32は必ず16試合（home/away/winner の3フィールド必須）\n"
            "- r16は8試合、qfは4試合、sfは2試合、finalは1試合\n"
            "- winnerは必ずhomeかawayどちらかのチーム名と完全一致\n"
            "- チーム名は日本語で統一\n"
            "- JSONのみ出力、前後に何も書かない"
        ),
        'tacticalTrend': (
            context
            + "\n## タスク\n"
            "今大会で見られる**戦術トレンドや特徴的なパターン**を分析してください。\n"
            "得点傾向、守備組織、プレッシング強度など、直近の試合結果から読み取れる\n"
            "具体的なデータと傾向を挙げてください。200字以内で日本語で。"
        ),
    }

    client = anthropic.Anthropic(api_key=anthropic_key)
    # groupPrediction1/2 need more tokens for 6-group structured output + 敗退予想
    result = {}
    for key, prompt in prompts.items():
        try:
            resp = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=3000 if key == 'groupPrediction' else (2500 if key == 'bracketPrediction' else 800),
                messages=[{'role': 'user', 'content': prompt}]
            )
            result[key] = resp.content[0].text.strip()
            log(f"AI分析: {key} OK")
        except Exception as e:
            log(f"AI分析: {key} error: {e}")
            result[key] = None

    result['generatedAt'] = now_jst
    return result



# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log("=== WC2026 Updater starting ===")
    cfg = load_config()
    token = cfg.get('github_token', '')

    if not token:
        # First run: ask for token
        print("\nGitHub Personal Access Token を入力してください:")
        print("(取得場所: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic))")
        print("必要なスコープ: repo\n")
        token = input("Token (ghp_...): ").strip()
        if not token:
            log("トークンなし。終了します。")
            sys.exit(1)
        cfg['github_token'] = token
        save_config(cfg)
        log("トークンを保存しました。")

    yt_key = cfg.get('youtube_api_key', '')
    if not yt_key:
        print("\nYouTube Data API v3 キーを入力してください (スキップする場合はEnter):")
        yt_key = input("YouTube API Key (AIza...): ").strip()
        if yt_key:
            cfg['youtube_api_key'] = yt_key
            save_config(cfg)
            log("YouTube APIキーを保存しました。")

    # 1. Fetch ESPN schedule/scores
    events = fetch_espn()
    if not events:
        log("ESPN: データなし。終了します。")
        sys.exit(1)

    # Build team→group map from standings for group-label fallback
    team_to_group = {}
    try:
        r = requests.get('https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings',
                         headers=HEADERS, timeout=15)
        for child in r.json().get('children', []):
            gm2 = re.search(r'Group ([A-L])', child.get('name', ''), re.I)
            if gm2:
                g_letter = gm2.group(1).upper()
                for e in child.get('standings', {}).get('entries', []):
                    tname = e.get('team', {}).get('displayName', '')
                    if tname:
                        team_to_group[tname] = g_letter
        log(f"team_to_group: {len(team_to_group)} teams mapped")
    except Exception as e:
        log(f"team_to_group build failed: {e}")

    data = transform_espn(events, team_to_group=team_to_group)

    # Check if ESPN returned any FINISHED games
    finished = [m for m in (data.get('matches') or []) if m['status'] == 'FINISHED']
    log(f"ESPN finished games: {len(finished)}")

    # 2. If ESPN has no finished games, try external score sources
    if not finished:
        log("ESPN にスコアなし → SofaScore を試します")
        ext = fetch_sofascore()
        if ext:
            data = merge_scores_into_espn(data, ext, 'SofaScore')
        else:
            log("SofaScore にスコアなし → Fotmob を試します")
            ext = fetch_fotmob()
            if ext:
                data = merge_scores_into_espn(data, ext, 'Fotmob')

    # 2b. Fetch group standings from ESPN standings API
    standings = fetch_espn_standings()
    if standings:
        data['groups'] = standings

    # 2b2. Enrich FINISHED/LIVE matches with shot stats from ESPN event summary
    stat_targets = [m for m in (data.get('matches') or [])
                    if m['status'] in ('FINISHED', 'LIVE')]
    log(f'Fetching shot stats for {len(stat_targets)} matches...')
    for m in stat_targets:
        ss = fetch_espn_match_stats(m['id'])
        if ss:
            m['shotStats'] = ss
    log(f'Shot stats done.')

    # 2c. Enrich matches with YouTube videos via FIFA channel playlist (costs ~2 API units total)
    if yt_key:
        yt_videos = fetch_fifa_recent_videos(yt_key, max_videos=100)
        hl_count, pv_count = 0, 0
        for m in (data.get('matches') or []):
            h_en = next((k for k, v in TEAM_JP.items() if v == m['homeTeam']['name']), m['homeTeam']['name'])
            a_en = next((k for k, v in TEAM_JP.items() if v == m['awayTeam']['name']), m['awayTeam']['name'])
            if m['status'] == 'FINISHED':
                vids = find_match_video(yt_videos, h_en, a_en, mode='highlight')
                if vids:
                    m['ytVideos'] = vids
                    hl_count += 1
                    log(f"  HL {h_en} vs {a_en}: {vids[0]['title'][:70].encode('ascii','replace').decode()}")
            elif m['status'] == 'SCHEDULED':
                vids = find_match_video(yt_videos, h_en, a_en, mode='preview')
                if vids:
                    m['ytVideos'] = vids
                    pv_count += 1
        log(f"YouTube matched: {hl_count} highlights, {pv_count} previews")

    # 2d. Generate AI analysis via Claude API (requires anthropic_key in config)
    ai_analysis = generate_ai_analysis(data, cfg)
    if ai_analysis:
        data['aiAnalysis'] = ai_analysis
        log("AI分析: stored in data['aiAnalysis']")

    log(f"Data ready: {len(data.get('matches') or [])} matches, "
        f"{len(data.get('groups') or [])} groups, "
        f"source={data.get('source')}, "
        f"updated={data.get('updatedAt')}")

    # 3. Read HTML template & inject data
    if not HTML_TEMPLATE.exists():
        log(f"HTML template not found: {HTML_TEMPLATE}")
        log("Searching Cowork sessions for template...")
        appdata = Path(os.environ.get('APPDATA', r'C:\Users\Shoichi\AppData\Roaming'))
        # Try glob across all Cowork sessions
        pattern = str(appdata / 'Claude' / 'local-agent-mode-sessions'
                      / '*' / '*' / 'agent' / '*' / 'outputs'
                      / 'worldcup2026_dashboard.html')
        candidates = sorted(glob.glob(pattern),
                            key=lambda p: os.path.getmtime(p), reverse=True)
        # Also try direct known path from current Cowork session
        direct = (appdata /
                  r'Claude\local-agent-mode-sessions'
                  r'\99e8f8bf-416a-4ed7-b904-0c7dbd762112'
                  r'\bf3f4a76-830c-4697-adbc-8f7a9955e569'
                  r'\agent'
                  r'\local_ditto_bf3f4a76-830c-4697-adbc-8f7a9955e569'
                  r'\outputs\worldcup2026_dashboard.html')
        if direct.exists() and str(direct) not in candidates:
            candidates.insert(0, str(direct))
        if candidates:
            src = Path(candidates[0])
            shutil.copy(src, HTML_TEMPLATE)
            log(f"Copied from {src}")
        else:
            log("HTML not found. Place worldcup2026_dashboard.html next to this script.")
            sys.exit(1)

    html = HTML_TEMPLATE.read_text(encoding='utf-8')
    html_updated = inject_data(html, data)

    # 4. Deploy to GitHub Pages
    ok = deploy_to_github(html_updated, token)
    if ok:
        log("=== 完了 ===")
    else:
        log("=== デプロイ失敗 ===")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("中断されました")
    except Exception:
        log("予期しないエラー:\n" + traceback.format_exc())
        sys.exit(1)
