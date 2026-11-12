/**
 * The slice of an archive entry the Model Lab's live record needs (activity, stage counts, prediction ledger).
 * Trimmed on the server so the page does not ship every forecast's features, contributions and integrity block:
 * the ITF archive alone grows by hundreds of forecasts a week.
 */
import type { ArchiveEntry } from "./contract";

export type LedgerEntry = Pick<ArchiveEntry,
  "prediction_id" | "match_uid" | "model_version" | "kind" | "issued_at" | "p" | "players" | "event" |
  "counted" | "favourite_won" | "result_state" | "result_status" | "record_hash" | "ledger_position">;

export const toLedgerEntry = (e: ArchiveEntry): LedgerEntry => ({
  prediction_id: e.prediction_id, match_uid: e.match_uid, model_version: e.model_version, kind: e.kind,
  issued_at: e.issued_at, p: e.p, players: e.players, event: e.event, counted: e.counted, favourite_won: e.favourite_won,
  result_state: e.result_state, result_status: e.result_status, record_hash: e.record_hash, ledger_position: e.ledger_position,
});
