"""Custom events for Vault Mines."""


def mines_result_event(gamestate, mines: int, safe_picks: int, multiplier: float, hit: bool):
    """Emit a compact pure-Mines simulation result."""

    event = {
        "index": len(gamestate.book.events),
        "type": "minesResult",
        "mines": mines,
        "safePicks": safe_picks,
        "multiplier": int(round(multiplier * 100)),
        "hit": hit,
    }
    gamestate.book.add_event(event)
