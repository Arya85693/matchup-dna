import assert from "node:assert/strict";
import { test } from "node:test";
import { ago, dayKey, familyName, favourite, levelLabel, pct, roundLabel, utcDate } from "./format.ts";

test("percentages are the stored value rounded for display", () => {
  assert.equal(pct(0.6463), "64.6");
  assert.equal(pct(0.551), "55.1");
  assert.equal(pct(0.0004), "0.0");
});

test("the favourite is the higher stored probability; a tie has none", () => {
  assert.equal(favourite([0.449, 0.551]), 1);
  assert.equal(favourite([0.811, 0.189]), 0);
  assert.equal(favourite([0.5, 0.5]), null);
});

test("family names keep particles", () => {
  assert.equal(familyName("Luca Van Assche"), "Van Assche");
  assert.equal(familyName("Tomas Martin Etcheverry"), "Etcheverry");
  assert.equal(familyName("Adolfo Daniel Vallejo"), "Vallejo");
  assert.equal(familyName(null), "Unknown");
});

test("rounds and levels fall back to the stored code", () => {
  assert.equal(roundLabel("R32"), "Round of 32");
  assert.equal(roundLabel("Q1"), "Q1");
  assert.equal(levelLabel("WTA", "F"), "WTA Finals");
  assert.equal(levelLabel("ATP", null), "ATP");
});

test("relative times", () => {
  const now = new Date("2026-11-09T05:00:00Z");
  assert.equal(ago("2026-11-09T04:59:40Z", now), "just now");
  assert.equal(ago("2026-11-09T04:25:00Z", now), "35 minutes ago");
  assert.equal(ago("2026-11-09T00:55:00Z", now), "4 hours ago");
  assert.equal(ago("2026-11-06T05:00:00Z", now), "3 days ago");
});

test("day keys follow the viewer's time zone", () => {
  assert.equal(dayKey("2026-11-09T03:00:00Z", "UTC"), "2026-11-09");
  assert.equal(dayKey("2026-11-09T03:00:00Z", "America/New_York"), "2026-11-08");
});

test("protocol dates are read in UTC", () => {
  assert.equal(utcDate("2026-11-09T00:29:15Z"), "9 November 2026");
  assert.equal(utcDate("2027-07-15T00:00:00Z"), "15 July 2027");
});
