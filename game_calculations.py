"""Mathematical calculations for Vault Mines."""

from math import comb

from src.executables.executables import Executables


class GameCalculations(Executables):
    """Pure Mines probability and payout helpers."""

    BOARD_SIZE = 25

    @classmethod
    def survival_probability(cls, mines: int, safe_picks: int) -> float:
        """Probability of revealing ``safe_picks`` safe tiles in succession."""

        if mines < 1 or mines >= cls.BOARD_SIZE:
            raise ValueError("mines must be between 1 and 24")
        if safe_picks < 0 or safe_picks > cls.BOARD_SIZE - mines:
            return 0.0
        if safe_picks == 0:
            return 1.0

        safe_tiles = cls.BOARD_SIZE - mines
        return comb(safe_tiles, safe_picks) / comb(cls.BOARD_SIZE, safe_picks)

    def cashout_multiplier(self, mines: int, safe_picks: int) -> float:
        """Return the RTP-adjusted pure-Mines cashout multiplier."""

        if safe_picks <= 0:
            return 1.0

        probability = self.survival_probability(mines, safe_picks)
        if probability <= 0:
            return 0.0

        multiplier = self.config.rtp / probability
        return min(float(self.config.wincap), multiplier)

    def probability_next_safe(self, mines: int, revealed_safe: int) -> float:
        """Conditional probability that the next hidden tile is safe."""

        remaining_tiles = self.BOARD_SIZE - revealed_safe
        remaining_safe = self.BOARD_SIZE - mines - revealed_safe
        if remaining_tiles <= 0 or remaining_safe <= 0:
            return 0.0
        return remaining_safe / remaining_tiles

    def generate_multiplier_table(self) -> dict[int, list[float]]:
        """Generate payout multipliers for mine counts 1 through 20."""

        table = {}
        for mines in range(1, 21):
            table[mines] = [
                round(self.cashout_multiplier(mines, safe_picks), 8)
                for safe_picks in range(1, self.BOARD_SIZE - mines + 1)
            ]
        return table
