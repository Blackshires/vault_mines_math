"""Interactive round state for Vault Mines.

The math-sdk still generates completed books, while the live RGS/runtime will own
an interactive round between start -> reveal(s) -> cashout.  This dataclass is the
shared deterministic state model for that runtime layer.
"""

from dataclasses import dataclass, field


@dataclass
class VaultMinesRound:
    """Mutable state for one 5x5 Vault Mines round."""

    mine_count: int
    board: list[str]
    account: float = 1.0
    remaining_mines: int | None = None
    hidden_cells: set[int] = field(default_factory=set)
    keys_found: int = 0
    shield_charges: int = 0
    natural_shield_awarded: bool = False
    vault_protection_awarded: bool = False
    successful_reveals: int = 0
    alive: bool = True
    cashed_out: bool = False
    history: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.board) != 25:
            raise ValueError("Vault Mines board must contain exactly 25 cells")
        if self.remaining_mines is None:
            self.remaining_mines = self.mine_count
        if not self.hidden_cells:
            self.hidden_cells = set(range(25))

    @property
    def hidden_count(self) -> int:
        return len(self.hidden_cells)

    @property
    def finished(self) -> bool:
        return (not self.alive) or self.cashed_out or self.hidden_count == 0
