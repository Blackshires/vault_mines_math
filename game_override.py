"""Vault Mines-specific state overrides."""

from game_executables import GameExecutables


class GameStateOverride(GameExecutables):
    """Custom state for Vault Mines."""

    def reset_book(self):
        super().reset_book()
        self.mine_count = 3
        self.safe_target = 1

    def assign_special_sym_function(self):
        """Vault Mines has no reel symbols or special-symbol assignment."""
        pass
