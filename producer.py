from confluent_kafka import Producer
import requests
import json
import time
import logging
from datetime import datetime, timezone

dev_mode = 0
seen_pitches = set()

logging.basicConfig(
    level=logging.INFO,   
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def read_config():
    config = {}
    with open('client.properties') as fh:
        for line in fh:
            line = line.strip()
            if len(line) != 0 and line[0] != '#':
                try:
                    parameter, value = line.strip().split('=', 1)
                    config[parameter] = value.strip()
                except ValueError:
                    continue
    return config


def delivery_report(err, msg):
    if err is not None:
        logger.error(f'Delivery failed: {err}')
    elif dev_mode:
       logger.debug(f'Delivered {msg.topic()}')

def fetch_upcoming_games():
    upcoming = []
    print('fetching upcoming games')
    today = datetime.now().strftime('%Y-%m-%d')
    url = f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}'

    response = requests.get(url, timeout=10)
    data = response.json()

    for date_obj in data.get('dates', []):

        for game in date_obj.get('games', []):
            status = game.get('status', {}).get('abstractGameState')
            
            if status in ['Preview', 'Scheduled']:
                game_data = {
                    'message_type': 'upcoming_game',
                    'game_pk': str(game['gamePk']),
                    'away_team': game.get('teams', {}).get('away', {}).get('team', {}).get('name'),
                    'home_team': game.get('teams', {}).get('home', {}).get('team', {}).get('name'),
                    'start_time': game.get('gameDate'),
                    'venue': game.get('venue', {}).get('name', ''),
                }

                upcoming.append(game_data)
    return upcoming


def fetch_live_game_pks():
    today = datetime.now().strftime('%Y-%m-%d')
    url = f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        live_games = []
        for date_obj in data.get('dates', []):
            for game in date_obj.get('games', []):
                status = game.get('status', {}).get('abstractGameState')
                if status == 'Live':
                    live_games.append(game['gamePk'])
        return live_games
    except Exception as e:
        logger.info(f'Error fetching live games: {e}')
        return []


def extract_game_state(game_pk, data):
    game_data = data.get('gameData', {})
    live_data = data.get('liveData', {})
    linescore = live_data.get('linescore', {})
    current_play = live_data.get('plays', {}).get('currentPlay', {})
    matchup = current_play.get('matchup', {})
    count = current_play.get('count', {})

    return {
        'message_type': 'game_state',
        'game_pk': str(game_pk),
        'ingest_timestamp': datetime.now(timezone.utc).isoformat(),
        'status': game_data.get('status', {}).get('detailedState'),
        'abstract_state': game_data.get('status', {}).get('abstractGameState'),
        'home_team': game_data.get('teams', {}).get('home', {}).get('name'),
        'away_team': game_data.get('teams', {}).get('away', {}).get('name'),
        'home_team_id': game_data.get('teams', {}).get('home', {}).get('id'),
        'away_team_id': game_data.get('teams', {}).get('away', {}).get('id'),
        'home_score': linescore.get('teams', {}).get('home', {}).get('runs', 0),
        'away_score': linescore.get('teams', {}).get('away', {}).get('runs', 0),
        'home_hits': linescore.get('teams', {}).get('home', {}).get('hits', 0),
        'away_hits': linescore.get('teams', {}).get('away', {}).get('hits', 0),
        'home_errors': linescore.get('teams', {}).get('home', {}).get('errors', 0),
        'away_errors': linescore.get('teams', {}).get('away', {}).get('errors', 0),
        'current_inning': linescore.get('currentInning'),
        'inning_half': linescore.get('inningHalf'),
        'inning_ordinal': linescore.get('currentInningOrdinal'),
        'outs': count.get('outs'),
        'balls': count.get('balls'),
        'strikes': count.get('strikes'),
        'runner_on_first': linescore.get('offense', {}).get('first') is not None,
        'runner_on_second': linescore.get('offense', {}).get('second') is not None,
        'runner_on_third': linescore.get('offense', {}).get('third') is not None,
        'batter_id': matchup.get('batter', {}).get('id'),
        'batter_name': matchup.get('batter', {}).get('fullName'),
        'pitcher_id': matchup.get('pitcher', {}).get('id'),
        'pitcher_name': matchup.get('pitcher', {}).get('fullName'),
        'venue': game_data.get('venue', {}).get('name'),
        'weather_condition': game_data.get('weather', {}).get('condition'),
        'weather_temp': game_data.get('weather', {}).get('temp'),
        'weather_wind': game_data.get('weather', {}).get('wind'),
    }


def extract_pitches(game_pk, data):
    live_data = data.get('liveData', {})
    current_play = live_data.get('plays', {}).get('currentPlay', {})
    at_bat_index = current_play.get('atBatIndex')
    play_events = current_play.get('playEvents', [])
    matchup = current_play.get('matchup', {})

    new_pitches = []

    for event in play_events:
        pitch_index = event.get('pitchNumber')
        pitch_key = (game_pk, at_bat_index, pitch_index)

        if pitch_key in seen_pitches:
            continue

        pitch_data = event.get('pitchData', {})
        details = event.get('details', {})
        coordinates = pitch_data.get('coordinates', {})
        breaks = pitch_data.get('breaks', {})

        record = {
            'message_type': 'pitch',
            'game_pk': str(game_pk),
            'ingest_timestamp': datetime.now(timezone.utc).isoformat(),
            'at_bat_index': at_bat_index,
            'pitch_number': pitch_index,
            'batter_id': matchup.get('batter', {}).get('id'),
            'batter_name': matchup.get('batter', {}).get('fullName'),
            'pitcher_id': matchup.get('pitcher', {}).get('id'),
            'pitcher_name': matchup.get('pitcher', {}).get('fullName'),
            'bat_side': matchup.get('batSide', {}).get('code'),
            'pitch_hand': matchup.get('pitchHand', {}).get('code'),
            'pitch_type_code': details.get('type', {}).get('code'),
            'pitch_type_desc': details.get('type', {}).get('description'),
            'call_code': details.get('call', {}).get('code'),
            'call_desc': details.get('call', {}).get('description'),
            'is_strike': details.get('isStrike'),
            'is_ball': details.get('isBall'),
            'is_in_play': details.get('isInPlay'),
            'start_speed': pitch_data.get('startSpeed'),
            'end_speed': pitch_data.get('endSpeed'),
            'zone': pitch_data.get('zone'),
            'plate_x': coordinates.get('pX'),
            'plate_z': coordinates.get('pZ'),
            'spin_rate': breaks.get('spinRate'),
            'break_angle': breaks.get('breakAngle'),
            'break_length': breaks.get('breakLength'),
            'break_vertical': breaks.get('breakVertical'),
        }

        new_pitches.append((pitch_key, record))

    return new_pitches


def extract_boxscore(game_pk, data):
    game_data = data.get('gameData', {})
    boxscore = data.get('liveData', {}).get('boxscore', {})
    teams = boxscore.get('teams', {})
    players = []

    for side in ['home', 'away']:
        team_box = teams.get(side, {})
        team_name = game_data.get('teams', {}).get(side, {}).get('name')
        team_id = game_data.get('teams', {}).get(side, {}).get('id')

        for player_key, player_obj in team_box.get('players', {}).items():
            person = player_obj.get('person', {})
            stats = player_obj.get('stats', {})
            batting = stats.get('batting', {})
            pitching = stats.get('pitching', {})
            position = player_obj.get('position', {})

            players.append({
                'player_id': person.get('id'),
                'player_name': person.get('fullName'),
                'team_side': side,
                'team_name': team_name,
                'team_id': team_id,
                'position_code': position.get('code'),
                'position_name': position.get('name'),
                'batting_order': player_obj.get('battingOrder'),
                'b_at_bats': batting.get('atBats'),
                'b_runs': batting.get('runs'),
                'b_hits': batting.get('hits'),
                'b_doubles': batting.get('doubles'),
                'b_triples': batting.get('triples'),
                'b_home_runs': batting.get('homeRuns'),
                'b_rbi': batting.get('rbi'),
                'b_walks': batting.get('baseOnBalls'),
                'b_strikeouts': batting.get('strikeOuts'),
                'b_left_on_base': batting.get('leftOnBase'),
                'p_innings_pitched': pitching.get('inningsPitched'),
                'p_hits': pitching.get('hits'),
                'p_runs': pitching.get('runs'),
                'p_earned_runs': pitching.get('earnedRuns'),
                'p_walks': pitching.get('baseOnBalls'),
                'p_strikeouts': pitching.get('strikeOuts'),
                'p_home_runs': pitching.get('homeRuns'),
                'p_pitches_thrown': pitching.get('pitchesThrown'),
                'p_strikes': pitching.get('strikes'),
            })

    return {
        'message_type': 'boxscore_snapshot',
        'game_pk': str(game_pk),
        'ingest_timestamp': datetime.now(timezone.utc).isoformat(),
        'players': players,
    }


def main():
    logger.info('mlb producer started')
    config = read_config()
    config['log_level'] = '0'
    logger.info('Config loaded')

    producer = Producer(config)
    logger.info('Producer connected to config')

    topics = {
        'game_state': 'mlb_game_state',
        'pitches': 'mlb_pitches',
        'boxscore': 'mlb_boxscore_snapshots',
        'upcoming': 'mlb_upcoming_games'
    }

    logger.info(f'Topics: {', '.join(topics.values())}\n')

    while True:
        try:
            try:
                upcoming_games = fetch_upcoming_games()

                producer.produce(
                    topic='mlb_upcoming_games',
                    key=b'upcoming_games',
                    value=json.dumps({
                        'message_type': 'upcoming_games',
                        'games': upcoming_games
                    }).encode('utf-8'),
                    callback=delivery_report,
                )
                                
                logger.info(f"Processed {len(upcoming_games)} upcoming games")
            except Exception as e:
                logger.warning(f"Failed to process upcoming games: {e}")

            live_game_pks = fetch_live_game_pks()
            timestamp = datetime.now().strftime('%H:%M:%S')
            count = len(live_game_pks)
            s = 's' if count > 1 else ''
            if not live_game_pks:
                logger.info(f'{timestamp} - No live games.')
            else:
                logger.info(f'\n{timestamp} - {count} live game{s}')



                for game_pk in live_game_pks:
                    try:
                        live_url = f'https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live'
                        data = requests.get(live_url, timeout=10).json()
                        key = str(game_pk).encode('utf-8')

                        game_state = extract_game_state(game_pk, data)

                        producer.produce(
                            topic=topics['game_state'],
                            key=key,
                            value=json.dumps(game_state).encode('utf-8'),
                            callback=delivery_report,
                        )

                        new_pitches = extract_pitches(game_pk, data)
                        for pitch_key, pitch_record in new_pitches:
                            producer.produce(
                                topic=topics['pitches'],
                                key=key,
                                value=json.dumps(pitch_record).encode('utf-8'),
                                callback=delivery_report,
                            )
                            seen_pitches.add(pitch_key)

                        producer.produce(
                            topic=topics['boxscore'],
                            key=key,
                            value=json.dumps(extract_boxscore(game_pk, data)).encode('utf-8'),
                            callback=delivery_report,
                        )

                        logger.info(f"  {game_pk} | {game_state['away_team']} {game_state['away_score']} @ {game_state['home_score']} {game_state['home_team']} | {len(new_pitches)} new pitches")
                    except Exception as e:
                        logger.info(f'  Error on game {game_pk}: {e}')

            producer.flush()
            time.sleep(10)

        except KeyboardInterrupt:
            logger.info('\nShutting down.')
            break
        except Exception as e:
            logger.info(f'Unexpected error: {e}')
            time.sleep(30)


if __name__ == '__main__':
    main()