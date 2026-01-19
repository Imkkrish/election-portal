from app import app
from models import compute_all_results

with app.app_context():
    results = compute_all_results()
    print("-" * 50)
    print("ELECTION RESULTS")
    print("-" * 50)
    for res in results:
        position = res['position_name']
        winner = res['winner']['name'] if res['winner'] else "No Winner"
        votes = res['winner']['votes'] if res['winner'] else 0
        print(f"{position:<20} : {winner} ({votes} votes)")
    print("-" * 50)
