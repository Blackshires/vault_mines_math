"""Deterministic interactive runtime contract for Vault Mines.

This module is deliberately RGS-agnostic. It defines the server-side state and
public responses required by an interactive adapter:

    start_round -> reveal -> cashout

The actual EngineIO/RGS transport and settlement adapter can wrap this contract.
Hidden board contents and the seed are never exposed while a round is active.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

from round_state import VaultMinesRound


@dataclass
class RuntimeSession:
    round_id: str
    seed: int
    bet: float
    state: VaultMinesRound
    settled: bool = False


class VaultMinesRuntime:
    """Minimal in-memory reference runtime around the deterministic math core."""

    def __init__(self, engine):
        self.engine = engine
        self.sessions: dict[str, RuntimeSession] = {}

    def _session(self, round_id: str) -> RuntimeSession:
        try:
            return self.sessions[round_id]
        except KeyError as exc:
            raise KeyError(f"unknown round_id: {round_id}") from exc

    def _public_state(self, session: RuntimeSession) -> dict[str, Any]:
        state = session.state
        return {
            "roundId": session.round_id,
            "mines": state.mine_count,
            "remainingMines": int(state.remaining_mines),
            "successfulReveals": state.successful_reveals,
            "keysFound": state.keys_found,
            "shieldCharges": state.shield_charges,
            "depth": self.engine.depth_label(state.successful_reveals),
            "cashoutMultiplier": self.engine.current_cashout(state),
            "canContinue": self.engine.can_continue_round(state),
            "alive": state.alive,
            "settled": session.settled,
        }

    def _terminal_reveal(self, session: RuntimeSession) -> dict[str, Any]:
        """Reveal full board only once the wager is no longer live."""
        if not session.settled:
            raise RuntimeError("full board is only available after settlement")
        return {
            "board": list(session.state.board),
            "seed": session.seed,
        }

    def start_round(
        self,
        round_id: str,
        mines: int,
        bet: float,
        seed: int,
    ) -> dict[str, Any]:
        """Create one deterministic hidden round and return public state only."""

        if round_id in self.sessions:
            raise ValueError(f"round_id already exists: {round_id}")
        if bet <= 0:
            raise ValueError("bet must be positive")

        rng = random.Random(seed)
        state = self.engine.create_round(mines, rng)
        session = RuntimeSession(
            round_id=round_id,
            seed=seed,
            bet=float(bet),
            state=state,
        )
        self.sessions[round_id] = session

        return {
            "type": "roundStarted",
            **self._public_state(session),
        }

    def reveal(self, round_id: str, cell: int) -> dict[str, Any]:
        """Reveal exactly one requested cell; never expose unrelated hidden cells."""

        session = self._session(round_id)
        if session.settled:
            raise RuntimeError("round is already settled")

        result = self.engine.reveal_cell(session.state, cell)
        response = {
            "type": "cellRevealed",
            "roundId": round_id,
            **result,
        }

        if result["terminalLoss"]:
            session.settled = True
            response["settlement"] = {
                "payoutMultiplier": 0.0,
                "payout": 0.0,
            }
            response.update(self._terminal_reveal(session))

        return response

    def cashout(self, round_id: str) -> dict[str, Any]:
        """Settle a surviving round at its current deterministic cashout."""

        session = self._session(round_id)
        if session.settled:
            raise RuntimeError("round is already settled")

        multiplier = self.engine.cashout_round(session.state)
        session.settled = True
        return {
            "type": "roundCashedOut",
            "roundId": round_id,
            "payoutMultiplier": multiplier,
            "payout": session.bet * multiplier,
            **self._public_state(session),
            **self._terminal_reveal(session),
        }

    def replay_board(self, mines: int, seed: int) -> list[str]:
        """Recreate the original board from the stored seed for audit/replay."""

        return list(self.engine.create_round(mines, random.Random(seed)).board)

    def validate_contract(self) -> dict[str, Any]:
        """Self-check hidden-data isolation and deterministic replay."""

        probe = VaultMinesRuntime(self.engine)
        start = probe.start_round("contract-probe", mines=3, bet=1.0, seed=20260902)

        forbidden = {"board", "seed"}
        leaked_start_fields = sorted(forbidden.intersection(start))

        original_board = list(probe.sessions["contract-probe"].state.board)
        replay_board = probe.replay_board(3, 20260902)
        deterministic_replay = original_board == replay_board

        reveal = probe.reveal("contract-probe", 0)
        leaked_reveal_fields = []
        if not reveal.get("terminalLoss"):
            leaked_reveal_fields = sorted(forbidden.intersection(reveal))
            settlement = probe.cashout("contract-probe")
        else:
            settlement = reveal

        terminal_has_board = "board" in settlement and "seed" in settlement

        if leaked_start_fields or leaked_reveal_fields:
            raise AssertionError("active-round response leaked hidden board or seed")
        if not deterministic_replay:
            raise AssertionError("seeded board replay is not deterministic")
        if not terminal_has_board:
            raise AssertionError("settled response must include audit board and seed")

        return {
            "hidden_start_ok": not leaked_start_fields,
            "hidden_reveal_ok": not leaked_reveal_fields,
            "deterministic_replay": deterministic_replay,
            "terminal_audit_data": terminal_has_board,
        }
