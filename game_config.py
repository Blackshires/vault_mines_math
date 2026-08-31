"""Vault Mines game configuration for EngineIO math-sdk."""

from src.config.config import Config
from src.config.distributions import Distribution
from src.config.betmode import BetMode


class GameConfig(Config):
    """Configuration for Vault Mines."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__()

        self.game_id = "vault_mines"
        self.provider_number = 0
        self.working_name = "Vault Mines"

        self.wincap = 5000
        self.win_type = "other"
        self.rtp = 0.967

        # V1 feature parameters. These are deliberately configurable and are
        # not certification-final frequencies yet.
        # - A round has at most one natural Shield payload.
        # - Keys are independently assigned to other safe cells.
        # - The 3rd revealed Key grants one Vault Protection shield charge.
        self.natural_shield_round_probability = 0.05
        self.key_cell_probability = 0.13
        self.keys_for_vault_protection = 3
        self.max_shield_charges = 2

        self.construct_paths()

        # Non-slot game: no reels or paytable.
        self.num_reels = 0
        self.num_rows = []
        self.paytable = {}
        self.include_padding = False
        self.special_symbols = {
            "wild": [],
            "scatter": [],
            "multiplier": [],
        }

        self.freespin_triggers = {
            self.basegame_type: {},
            self.freegame_type: {},
        }
        self.anticipation_triggers = {
            self.basegame_type: 0,
            self.freegame_type: 0,
        }

        self.bet_modes = [
            BetMode(
                name="base",
                cost=1.0,
                rtp=self.rtp,
                max_win=self.wincap,
                auto_close_disabled=False,
                is_feature=True,
                is_buybonus=False,
                distributions=[
                    Distribution(
                        criteria="basegame",
                        quota=1.0,
                        conditions={
                            "reel_weights": {},
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    )
                ],
            )
        ]
