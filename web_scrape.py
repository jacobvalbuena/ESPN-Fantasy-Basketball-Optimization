import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, Optional

def scrape_team_injury_data(league_id: str, team_id: int, season_id: int, espn_s2: str, swid: str) -> Dict[str, str]:
    """
    Scrape injury return dates from team roster page.
    Returns dictionary mapping player names to return dates.
    """
    # Use the team page URL format you found
    url = f"https://fantasy.espn.com/basketball/team?leagueId={league_id}&teamId={team_id}&seasonId={season_id}"
    
    cookies = {
        'espn_s2': espn_s2,
        'SWID': swid
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        print(f"\nScraping team page: {url}")
        response = requests.get(url, cookies=cookies, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        injury_data = {}
        
        # Find all injury return elements
        # Based on your HTML: class="jsx-2813592384 playerCardInjury_Return"
        return_elements = soup.find_all(class_=lambda x: x and 'playerCardInjury_Return' in str(x))
        
        for element in return_elements:
            return_text = element.get_text(strip=True)
            
            # Extract date from "EST. RETURN 10/28/2025" format
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', return_text)
            if date_match:
                return_date = date_match.group(1)
                
                # Try to find the player name (look in parent/sibling elements)
                # Navigate up to find player name container
                parent = element.parent
                for _ in range(5):  # Search up to 5 levels up
                    if parent:
                        # Look for player name elements
                        name_div = parent.find(class_=lambda x: x and 'player-name' in str(x))
                        if name_div:
                            # Get full name from divs
                            name_parts = [div.get_text(strip=True) for div in name_div.find_all('div')]
                            if name_parts:
                                player_name = ' '.join(name_parts)
                                injury_data[player_name] = return_date
                                print(f"  Found: {player_name} → {return_date}")
                                break
                        parent = parent.parent
        
        return injury_data
        
    except Exception as e:
        print(f"Error scraping team page: {e}")
        return {}


def scrape_injury_returns_batch(players, league_id: str, espn_s2: str, swid: str, delay: float = 0.5):
    """
    Scrape injury return dates for team's players.
    Now scrapes from team page instead of individual player cards.
    """
    # Get team_id from first player (they're all on same team)
    if not players:
        return {}
    
    # Since all players are on same team, just use the team page
    # We need to figure out which team they're on
    # For now, we'll need to pass team_id separately
    
    # This is a limitation - we need the team_id
    # Let's return empty dict and handle it differently
    return {}


def scrape_team_injuries_for_my_team(league_id: str, team_id: int, season_id: int, 
                                      espn_s2: str, swid: str, my_roster) -> Dict[int, str]:
    """
    Scrape injury data from team page and match to roster by player name.
    Returns dict mapping player_id to return_date.
    """
    # Scrape the team page
    injury_data_by_name = scrape_team_injury_data(league_id, team_id, season_id, espn_s2, swid)
    
    # Match scraped names to player IDs
    injury_data_by_id = {}
    
    for player in my_roster:
        if player.name in injury_data_by_name:
            injury_data_by_id[player.playerId] = injury_data_by_name[player.name]
            print(f"  Matched: {player.name} (ID: {player.playerId})")
    
    return injury_data_by_id