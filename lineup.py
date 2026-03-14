from espn_api.basketball import League
from collections import defaultdict
from espn_api.basketball.constant import PRO_TEAM_MAP
from web_scrape import scrape_team_injuries_for_my_team, scrape_injury_returns_batch, scrape_team_injury_data

 

# Configuration

LEAGUE_ID = '1180307072'

YEAR = 2026

ESPN_S2 = 'AEBXZm75odBD99itbp%2BRzB%2BN7dkfkbGX%2Bbom96yHWXrl2kFAf31wWzPfKgh9RiqQ45gMw%2BcCZeio%2F8iu5xCy1FVwGqaMmBAwzgB35ALb2io1DCekBW%2FapvpkagePaxP%2By4%2F%2FJhACu9bHV%2F%2B34GZoj4r5p6A4aLYXNVZwyketyD5eRBK0eR1RUYHIeyo5fBwMTxPbwN%2BAPpL0%2FhZvevapH3QrPXloQ1iTnd2zPiPBIkRXq1uuJpW1VtLgPd%2FaIKjGn1jiLcKBbtWuYmurMDqOzTuX5S1G9iQR18BtKmR9xpb6eQ%3D%3D'  # Optional: needed for private leagues

SWID = '{D169E8B5-EEDF-4E32-88CB-549C26F247EE}'



   
def get_scoring_periods_for_matchup(league, matchup_period):
    """
    Calculate which scoring periods belong to a matchup period.
    Uses the league's actual current state to determine boundaries.
    
    Logic: If we're in matchup 1 on scoring period 6, then matchup 1 = days 1-6
    """
    
    # Check if API has the mapping
    if hasattr(league, 'matchup_ids') and matchup_period in league.matchup_ids:
        api_periods = league.matchup_ids[matchup_period]
        
        # If we're in this matchup period currently, extend to include current day
        if matchup_period == league.currentMatchupPeriod:
            current_period = str(league.scoringPeriodId)
            if current_period not in api_periods:
                # Add current day if it's missing
                api_periods = api_periods + [current_period]
        
        return api_periods
    
    # Fallback: Manual calculation (7 days per matchup except for first week)
    if matchup_period == 1:
        start_day = 1
        end_day = 6
    else:
        start_day = (matchup_period - 1) * 7
        end_day = start_day + 6  # 7 days total

    return [str(i) for i in range(start_day, end_day + 1)]
 

def count_games_this_week(player, league):
    """
    Count games across ALL scoring periods in the current matchup period.
    Matchup Period = Fantasy week (e.g., Week 1)
    Scoring Period = Individual game days (e.g., Day 1, Day 2, etc.)
    """
    
    if not hasattr(player, 'proTeam') or not player.proTeam:
        return 0
    
    # Convert team abbreviation to team ID
    pro_team_id = None
    for team_id, abbrev in PRO_TEAM_MAP.items():
        if abbrev == player.proTeam:
            pro_team_id = team_id
            break
    
    if pro_team_id is None or not hasattr(league, 'pro_schedule'):
        return 0
    
    if pro_team_id not in league.pro_schedule:
        return 0
    # Get the current matchup period (fantasy week)
    # Get scoring periods for current matchup
    current_matchup = league.currentMatchupPeriod

    scoring_periods = get_scoring_periods_for_matchup(league, current_matchup + 1)
    
    # Count games across ALL days in this week
    total_games = 0
    for period in scoring_periods:
        period_str = str(period)
        if period_str in league.pro_schedule[pro_team_id]:
            games_count = len(league.pro_schedule[pro_team_id][period_str])
            total_games += games_count
    
    return total_games
 

def get_best_players(team, league, scrape_injuries=False, scoring_method = "balanced"):
    """
    Calculate the best lineup based on player averages and games played this week.
    Includes injury status and expected return date.
    """
    available_players = []
    
    injury_returns = {}  # Initialize empty
    
    if scrape_injuries:
        my_team_id = team.team_id
        
        injury_returns = scrape_team_injuries_for_my_team(
            LEAGUE_ID,
            my_team_id,
            YEAR,
            ESPN_S2,
            SWID,
            team.roster
        )
        print(f"\nScraped injury data: {injury_returns}")  # DEBUG

    for player in team.roster:
        curr_avg_points = getattr(player, 'avg_points', 0) or 0
        proj_avg_points = getattr(player, 'projected_avg_points', 0) or 0
        if scoring_method == "actual":
            my_proj_avg_points = curr_avg_points
        elif scoring_method == "favor-actual":
            my_proj_avg_points = float(curr_avg_points) * 0.7 + float(proj_avg_points) * 0.3
        elif scoring_method == "balanced":
            my_proj_avg_points = float(curr_avg_points) * 0.5 + float(proj_avg_points) * 0.5
        elif scoring_method == "favor-proj":
            my_proj_avg_points = float(curr_avg_points) * 0.3 + float(proj_avg_points) * 0.7
        else:
            my_proj_avg_points = proj_avg_points
            
        games_this_week = count_games_this_week(player, league)
        projected_points = my_proj_avg_points * games_this_week
        
        # Get expected return date - check SCRAPED data first, then API
        expected_return = None
        
        # First try scraped data
        if player.playerId in injury_returns:
            date_str = injury_returns[player.playerId]
            # Format: "10/28/2025" → "10/28"
            date_parts = date_str.split('/')
            if len(date_parts) >= 2:
                expected_return = f"{date_parts[0]}/{date_parts[1]}"
        
        # Fallback to API data (rarely populated)
        elif hasattr(player, 'expected_return_date') and player.expected_return_date:
            expected_return = player.expected_return_date.strftime('%m/%d')
       
        player_info = {
            'name': player.name,
            'position': player.position,
            'eligible_slots': player.eligibleSlots,
            'avg_points': my_proj_avg_points,
            'games_this_week': games_this_week,
            'projected_points': projected_points,
            'injury_status': player.injuryStatus if player.injuryStatus else 'Healthy',
            'expected_return': expected_return,
            'player_obj': player
        }
       
        available_players.append(player_info)
   
    available_players.sort(key=lambda x: x['projected_points'], reverse=True)
   
    return available_players
 

def create_optimal_lineup(available_players):
    """
    Create the optimal lineup by filling roster slots with highest projected players.
    """
    lineup = {}  # Changed from defaultdict to regular dict
    used_players = set()
    bench = []
   
    # Use unique keys for duplicate slots
    slot_order = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UT1', 'UT2', 'UT3']
    
    # Map to display names
    slot_display = {
        'PG': 'PG', 'SG': 'SG', 'SF': 'SF', 'PF': 'PF', 'C': 'C',
        'G': 'G', 'F': 'F',
        'UT1': 'UT', 'UT2': 'UT', 'UT3': 'UT'
    }
   
    for slot in slot_order:
        # Find best available player for this slot
        best_player = None
        
        # Get the eligibility check (all UT slots check for 'UT')
        slot_check = 'UT' if slot.startswith('UT') else slot
        
        for player_info in available_players:

            if player_info['injury_status'] == 'OUT':
                continue
            
            player_name = player_info['name']
           
            if player_name in used_players:
                continue
           
            if slot_check in player_info['eligible_slots']:
                best_player = player_info
                lineup[slot] = best_player
                used_players.add(player_name)
                break

        if best_player is None:
            lineup[slot] = None
   
    for player_info in available_players:
        if player_info['name'] not in used_players:
            bench.append(player_info)
   
    return {
        'starters': lineup,
        'bench': bench,
        'total_projected': sum(p['projected_points'] for p in lineup.values() if p),
        'slot_display': slot_display  # Add this for printing
    }

def print_optimal_lineup(optimal_lineup):
    """
    Print the optimal starting lineup with bench, including injury status.
    """
    print("\n" + "="*80)
    print("OPTIMAL STARTING LINEUP")
    print("="*80)
   
    print(f"\n{'Slot':<6} {'Player':<25} {'Pos':<8} {'Games':<6} {'Proj':<8} {'Status':<15}")
    print("-"*80)
   
    slot_display = optimal_lineup.get('slot_display', {})
    
    for slot, player in optimal_lineup['starters'].items():
        display_slot = slot_display.get(slot, slot)
        
        if player:
            # Get injury info
            injury_status = player['injury_status']
            expected_return = player.get('expected_return', None)
            
            # Format status display
            if injury_status == 'OUT':
                if expected_return:
                    status_display = f"OUT ({expected_return})"
                else:
                    status_display = "OUT"
            elif injury_status and injury_status != 'Healthy':
                status_display = injury_status
            else:
                status_display = "✓"
            
            print(f"{display_slot:<6} "
                  f"{player['name']:<25} "
                  f"{player['position']:<8} "
                  f"{player['games_this_week']:<6} "
                  f"{player['projected_points']:<8.1f} "
                  f"{status_display:<15}")
        else:
            print(f"{display_slot:<6} {'EMPTY':<25}")
   
    print("-"*80)
    print(f"{'TOTAL':<6} {'':<25} {'':<8} {'':<6} {optimal_lineup['total_projected']:<8.1f}")
   
    if optimal_lineup['bench']:
        print("\n" + "="*80)
        print("BENCH")
        print("="*80)
        print(f"\n{'Player':<25} {'Pos':<8} {'Games':<6} {'Proj':<8} {'Status':<15}")
        print("-"*80)
        
        for player in optimal_lineup['bench']:
            # Get injury info
            injury_status = player['injury_status']
            expected_return = player.get('expected_return', None)
            
            # Format status display
            if injury_status == 'OUT':
                if expected_return:
                    status_display = f"OUT ({expected_return})"
                else:
                    status_display = "OUT"
            elif injury_status and injury_status != 'Healthy':
                status_display = injury_status
            else:
                status_display = "✓"
            
            print(f"{player['name']:<25} "
                  f"{player['position']:<8} "
                  f"{player['games_this_week']:<6} "
                  f"{player['projected_points']:<8.1f} "
                  f"{status_display:<15}")
   
    print("\n")


def show_out_players_summary(team, league):
    """
    Quick summary table of OUT players and their schedules.
    """
    print("\n" + "="*80)
    print("OUT PLAYERS QUICK SUMMARY")
    print("="*80)
    
    current_matchup = league.currentMatchupPeriod
    scoring_periods = get_scoring_periods_for_matchup(league, current_matchup)
    
    out_players = [p for p in team.roster if p.injuryStatus == 'OUT']
    
    if not out_players:
        print("\n✓ No OUT players")
        return
    
    print(f"\n{'Player':<20} {'Team':<5} {'Total for Week':<15} {'Proj/Game':<10} {'Potential':<10}")
    print("-" * 80)
    
    for player in out_players:
        # Count games
        total_games = 0
        games_left = 0
        
        for period in scoring_periods:
            if str(period) in player.schedule:
                total_games += 1
        
        proj_avg = player.projected_avg_points or 0
        potential = proj_avg * total_games
        
        print(f"{player.name:<20} "
              f"{player.proTeam:<5} "
              f"{total_games:<15} "
              f"{proj_avg:<10.1f} "
              f"{potential:<10.1f}")
    
    print()

def main():

    # Connect to league

    league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)

    print(league.teams)

    # debug_league_schedule(league)

    my_team = league.teams[0]  # Change index or use a specific team


    # debug_schedule(league, my_team)

    print(f"Team: {my_team.team_name}")

    print(f"Owner: {my_team.owners[0]['firstName']}")

    print(f"Current Scoring Period: {league.currentMatchupPeriod}") #Add +1 if you want to see the upcoming week schedule

    show_out_players_summary(my_team, league)

    # Get available players

    available_players = get_best_players(my_team, league, False, "favor-actual")

 

    optimal_lineup = create_optimal_lineup(available_players)


    # Print the optimal lineup

    print_optimal_lineup(optimal_lineup)

 

if __name__ == "__main__":

    main()